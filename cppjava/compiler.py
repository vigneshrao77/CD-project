"""Public compiler API; artifacts from each independent phase remain inspectable."""
from dataclasses import dataclass
from .lexer import Lexer
from .preprocess import Preprocessor
from .parser import Parser
from .semantic import SemanticAnalyzer
from .lowering import Lowerer
from .codegen import JavaGenerator
from .ast import serialize
from .diagnostics import CompileError, Diagnostic


@dataclass
class Compilation:
    tokens: list
    preprocessed_tokens: list
    ast: dict
    annotated_ast: object
    ir: object
    java: str

    def dump(self, stage):
        return self.ast if stage == 'ast' else serialize(getattr(self, stage))


def compile_source(source: str, class_name: str = 'Main') -> Compilation:
    phase = 'lexer'
    try:
        tokens = Lexer(source).tokenize()
        phase = 'preprocessor'
        preprocessed = Preprocessor().process(tokens)
        phase = 'parser'
        tree = Parser(preprocessed).parse()
        parsed = serialize(tree, annotated=False)
        phase = 'semantic'
        annotated = SemanticAnalyzer().analyze(tree)
        phase = 'ir'
        ir = Lowerer().lower(annotated)
        phase = 'codegen'
        java = JavaGenerator(class_name).generate(ir)
        return Compilation(tokens, preprocessed, parsed, annotated, ir, java)
    except RecursionError as error:
        raise CompileError([Diagnostic(phase, 'resource-limit', 1, 1, 'source nesting exceeds the supported compiler recursion depth')]) from error
