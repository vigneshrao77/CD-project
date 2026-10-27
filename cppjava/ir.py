"""Language-neutral, typed operations between semantics and Java rendering.

No AST nodes or Java source snippets appear in this representation. Storage,
conversions, copies, iteration, algorithms and stream operations are explicit.
"""
from dataclasses import dataclass, field
from .typesys import Type


@dataclass
class IRExpr:
    op: str
    type: Type
    args: list['IRExpr'] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    line: int = 1
    column: int = 1


@dataclass
class IRStmt:
    op: str
    data: dict = field(default_factory=dict)


@dataclass
class IRFunction:
    name: str
    return_type: Type
    parameters: list[dict]
    body: IRStmt


@dataclass
class IRProgram:
    globals: list[IRStmt]
    functions: list[IRFunction]
    entry: str
