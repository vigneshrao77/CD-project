"""File-safe command-line interface, with JSON diagnostics and phase dumps."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from .compiler import compile_source
from .diagnostics import CompileError, Diagnostic


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compile a supported C++17 source file to Java.')
    parser.add_argument('source', type=Path)
    parser.add_argument('-o', '--output', type=Path, default=Path('Main.java'))
    parser.add_argument('--class-name', help='Defaults to the Java output filename stem')
    parser.add_argument('--dump-dir', type=Path, help='Write tokens, AST, annotated AST and IR as JSON')
    parser.add_argument('--json-errors', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise CompileError([Diagnostic('driver', 'path', 1, 1, 'input and output must be different files')])
        if args.output.suffix != '.java':
            raise CompileError([Diagnostic('driver', 'filename', 1, 1, 'output must have a .java extension')])
        name = args.class_name or args.output.stem
        if name != args.output.stem:
            raise CompileError([Diagnostic('driver', 'filename', 1, 1, 'public class name must match the output filename')])
        result = compile_source(args.source.read_text(encoding='utf-8-sig'), name)
        if args.dump_dir:
            args.dump_dir.mkdir(parents=True, exist_ok=True)
            for stage in ('tokens', 'preprocessed_tokens', 'ast', 'annotated_ast', 'ir'):
                (args.dump_dir / (stage + '.json')).write_text(json.dumps(result.dump(stage), indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', suffix='.java.tmp', dir=args.output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(result.java)
        try:
            temporary.replace(args.output)
        finally:
            temporary.unlink(missing_ok=True)
    except CompileError as error:
        if args.json_errors:
            print(json.dumps({'diagnostics': [d.to_dict() for d in error.diagnostics]}), file=sys.stderr)
        else:
            print(str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as error:
        diagnostic = Diagnostic('driver', 'io', 1, 1, str(error))
        print(json.dumps({'diagnostics': [diagnostic.to_dict()]}) if args.json_errors else str(diagnostic), file=sys.stderr)
        return 1
    return 0
