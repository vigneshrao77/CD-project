"""Typed AST node families. Semantic annotations are populated in a later pass."""
from dataclasses import dataclass, field, fields, is_dataclass
from .lexer import Token
from .typesys import Type


@dataclass
class Node:
    token: Token


@dataclass
class Expr(Node):
    type: Type | None = field(default=None, init=False)
    annotations: dict = field(default_factory=dict, init=False)


@dataclass
class Literal(Expr):
    value: object
    literal_type: Type


@dataclass
class Name(Expr):
    name: str


@dataclass
class UnaryExpr(Expr):
    op: str
    operand: Expr
    postfix: bool = False


@dataclass
class BinaryExpr(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class ConditionalExpr(Expr):
    condition: Expr
    when_true: Expr
    when_false: Expr


@dataclass
class CallExpr(Expr):
    callee: Expr
    arguments: list[Expr]


@dataclass
class MemberExpr(Expr):
    object: Expr
    member: str
    arrow: bool = False


@dataclass
class IndexExpr(Expr):
    object: Expr
    index: Expr


@dataclass
class InitList(Expr):
    values: list[Expr]


@dataclass
class ConstructExpr(Expr):
    target_type: Type
    arguments: list[Expr]


@dataclass
class CastExpr(Expr):
    target_type: Type
    operand: Expr


@dataclass
class Stmt(Node):
    pass


@dataclass
class Block(Stmt):
    statements: list[Stmt]


@dataclass
class VarDecl(Stmt):
    name: str
    declared_type: Type
    initializer: Expr | None = None
    dimensions: list[Expr | None] = field(default_factory=list)
    constant: bool = False
    java_name: str = ""


@dataclass
class VarGroup(Stmt):
    declarations: list[VarDecl]


@dataclass
class ExprStmt(Stmt):
    expression: Expr | None


@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None


@dataclass
class ForStmt(Stmt):
    initializer: Stmt | None
    condition: Expr | None
    update: Expr | None
    body: Stmt


@dataclass
class RangeForStmt(Stmt):
    variable: VarDecl
    iterable: Expr
    body: Stmt


@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt


@dataclass
class DoWhileStmt(Stmt):
    body: Stmt
    condition: Expr


@dataclass
class SwitchCase(Node):
    value: Expr | None
    statements: list[Stmt]


@dataclass
class SwitchStmt(Stmt):
    expression: Expr
    cases: list[SwitchCase]


@dataclass
class BreakStmt(Stmt):
    pass


@dataclass
class ContinueStmt(Stmt):
    pass


@dataclass
class ReturnStmt(Stmt):
    expression: Expr | None


@dataclass
class FunctionDecl(Node):
    name: str
    return_type: Type
    parameters: list[VarDecl]
    body: Block | None
    java_name: str = ""


@dataclass
class Program(Node):
    declarations: list[FunctionDecl | VarGroup]


def serialize(value, annotated=True):
    """Stable, cycle-free JSON-compatible representation for every phase dump."""
    if isinstance(value, Type):
        return {"cpp": str(value), "java": value.java, "boxed": value.boxed} if annotated else str(value)
    if isinstance(value, Token):
        return {"kind": value.kind, "lexeme": value.lexeme, "line": value.line, "column": value.column}
    if is_dataclass(value):
        result = {"node": type(value).__name__}
        for item in fields(value):
            if not annotated and item.name in {"type", "annotations", "java_name"}:
                continue
            result[item.name] = serialize(getattr(value, item.name), annotated)
        return result
    if isinstance(value, (list, tuple)):
        return [serialize(x, annotated) for x in value]
    if isinstance(value, dict):
        return {str(k): serialize(v, annotated) for k, v in value.items()}
    return value
