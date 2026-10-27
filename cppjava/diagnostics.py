"""Structured diagnostics shared by all compiler phases."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Diagnostic:
    phase: str
    code: str
    line: int
    column: int
    message: str

    def to_dict(self):
        return asdict(self)

    def __str__(self):
        return f"{self.phase}:{self.line}:{self.column}: {self.code}: {self.message}"


class CompileError(Exception):
    def __init__(self, diagnostics):
        self.diagnostics = list(diagnostics)
        super().__init__("\n".join(map(str, self.diagnostics)))


def fail(phase, token, message, code="invalid"):
    raise CompileError([Diagnostic(phase, code, token.line, token.column, message)])
