"""Reproducible differential tests against real g++ and javac/java processes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from cppjava.compiler import compile_source

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tests' / 'corpus'
BUILD = ROOT / '.build' / 'e2e'
PORTABLE_CXX = ROOT / '.build' / 'toolchain' / 'mingw64' / 'bin' / 'g++.exe'
CXX = os.environ.get('CXX') or (str(PORTABLE_CXX) if PORTABLE_CXX.is_file() else 'g++')


def command(args, *, cwd, input_bytes=None):
    environment = os.environ.copy()
    if Path(CXX).is_file():
        environment['PATH'] = str(Path(CXX).parent) + os.pathsep + environment.get('PATH', '')
    return subprocess.run(args, cwd=cwd, input=input_bytes, capture_output=True, timeout=40, check=False, env=environment)


def normalized(output):
    # MinGW's text stdout converts LF to CRLF; Java only does so for println.
    # No whitespace, numeric, token-order or floating-point normalization occurs.
    return output.replace(b'\r\n', b'\n')


def run_case(source):
    start = time.monotonic()
    case_dir = BUILD / source.stem
    case_dir.mkdir(parents=True, exist_ok=True)
    executable = case_dir / ('original.exe' if os.name == 'nt' else 'original')
    generated = case_dir / 'Main.java'
    result = {'name': source.stem, 'passed': False}
    try:
        cpp = command([CXX, '-std=c++17', '-O0', '-Wall', '-Wextra', str(source), '-o', str(executable)], cwd=case_dir)
        if cpp.returncode:
            raise AssertionError('g++ compilation failed:\n' + cpp.stderr.decode(errors='replace'))
        compilation = compile_source(source.read_text(encoding='utf-8'))
        generated.write_text(compilation.java, encoding='utf-8', newline='\n')
        java_compile = command(['javac', '-encoding', 'UTF-8', '-Xlint:all', '-Werror', str(generated)], cwd=case_dir)
        if java_compile.returncode:
            raise AssertionError('javac compilation failed:\n' + java_compile.stderr.decode(errors='replace'))
        inputs = sorted(CORPUS.glob(source.stem + '*.in')) or [None]
        for input_file in inputs:
            data = input_file.read_bytes() if input_file else b''
            original = command([str(executable)], cwd=case_dir, input_bytes=data)
            translated = command(['java', '-cp', str(case_dir), 'Main'], cwd=case_dir, input_bytes=data)
            (case_dir / 'cpp.stdout').write_bytes(original.stdout)
            (case_dir / 'java.stdout').write_bytes(translated.stdout)
            if original.returncode != translated.returncode:
                raise AssertionError(f'exit status mismatch: C++ {original.returncode}, Java {translated.returncode}\n' + translated.stderr.decode(errors='replace'))
            if normalized(original.stdout) != normalized(translated.stdout):
                raise AssertionError(f'output mismatch for {input_file}:\nC++:  {original.stdout!r}\nJava: {translated.stdout!r}')
        result.update(passed=True, inputs=len(inputs))
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    result['seconds'] = round(time.monotonic() - start, 3)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--case', help='Run matching filename substring only')
    args = parser.parse_args(argv)
    missing = [tool for tool in (CXX, 'javac', 'java') if not shutil.which(tool)]
    if missing:
        print('Missing required toolchain: ' + ', '.join(missing), file=sys.stderr)
        return 2
    version = command([CXX, '-dumpfullversion'], cwd=ROOT).stdout.decode().strip()
    if not version or int(version.split('.')[0]) < 11:
        print(f'The differential oracle requires GCC 11+ for C++17 sequencing; found {version or CXX}. Set CXX to a modern g++.', file=sys.stderr)
        return 2
    sources = sorted(CORPUS.glob('*.cpp'))
    if args.case:
        sources = [s for s in sources if args.case in s.stem]
    if not sources:
        print('No matching corpus programs', file=sys.stderr)
        return 2
    BUILD.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = [executor.submit(run_case, source) for source in sources]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(('PASS ' if result['passed'] else 'FAIL ') + result['name'], flush=True)
            if 'error' in result:
                print(result['error'], flush=True)
    passed = sum(r['passed'] for r in results)
    report = {'passed': passed, 'total': len(results), 'g++': CXX, 'gcc_version': version, 'normalization': 'CRLF to LF only; otherwise byte-identical', 'results': sorted(results, key=lambda r: r['name'])}
    (BUILD / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{passed}/{len(results)} end-to-end programs passed', flush=True)
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
