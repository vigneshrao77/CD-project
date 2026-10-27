"""Recursive descent plus precedence climbing; consumes preprocessed tokens."""
from . import ast as A
from .diagnostics import fail
from .lexer import Token
import math
from .typesys import Type, INT, LONG, FLOAT, DOUBLE, CHAR, STRING, BOOL, VOID


TYPE_NAMES = {"int", "long", "double", "float", "char", "bool", "string", "void", "auto", "vector", "pair", "map", "unordered_map", "set", "unordered_set"}
UNSUPPORTED = {"template", "class", "struct", "new", "delete", "unsigned", "signed", "short", "static", "sizeof", "nullptr", "enum", "typedef", "virtual", "public", "private", "protected", "volatile", "extern", "inline", "constexpr", "throw", "try", "catch", "goto", "union"}
PRECEDENCE = {",": 1, "=": 2, "+=": 2, "-=": 2, "*=": 2, "/=": 2, "%=": 2, "<<=": 2, ">>=": 2, "&=": 2, "^=": 2, "|=": 2, "||": 4, "&&": 5, "|": 6, "^": 7, "&": 8, "==": 9, "!=": 9, "<": 10, "<=": 10, ">": 10, ">=": 10, "<<": 11, ">>": 11, "+": 12, "-": 12, "*": 13, "/": 13, "%": 13}


class Parser:
    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.i = 0

    @property
    def current(self):
        return self.tokens[self.i]

    def peek(self, distance=1):
        return self.tokens[min(self.i + distance, len(self.tokens) - 1)]

    def take(self):
        t = self.current
        if t.kind != "eof":
            self.i += 1
        return t

    def accept(self, lexeme):
        if self.current.lexeme == lexeme:
            return self.take()
        return None

    def expect(self, lexeme):
        if self.current.lexeme != lexeme:
            self.expected(repr(lexeme))
        return self.take()

    def expected(self, what):
        t = self.current
        if t.lexeme in UNSUPPORTED or t.lexeme in {"&", "..."}:
            fail("parser", t, f"unsupported feature {t.lexeme!r}", "unsupported")
        fail("parser", t, f"expected {what}, found {t.lexeme!r}", "syntax")

    def identifier(self):
        if self.current.lexeme in {"*", "&", "&&"}:
            fail("parser", self.current, "pointer/reference declarations are unsupported", "unsupported")
        if self.current.kind != "identifier":
            self.expected("identifier")
        return self.take()

    def is_type(self, offset=0):
        token = self.tokens[min(self.i + offset, len(self.tokens) - 1)]
        if token.lexeme == "const":
            return True
        if token.lexeme == "std" and self.tokens[min(self.i + offset + 1, len(self.tokens) - 1)].lexeme == "::":
            return self.tokens[min(self.i + offset + 2, len(self.tokens) - 1)].lexeme in TYPE_NAMES
        return token.lexeme in TYPE_NAMES

    def parse_type(self):
        self.accept("std") and self.expect("::")
        token = self.take()
        name = token.lexeme
        if name not in TYPE_NAMES:
            fail("parser", token, f"expected supported type, found {name!r}", "unsupported" if name in UNSUPPORTED else "syntax")
        if name == "long":
            self.expect("long")
            return LONG
        count = {"vector": 1, "set": 1, "unordered_set": 1, "pair": 2, "map": 2, "unordered_map": 2}.get(name, 0)
        args = []
        if count:
            self.expect("<")
            for index in range(count):
                if index:
                    self.expect(",")
                args.append(self.parse_type())
            if self.current.lexeme == ">>":
                t = self.current
                self.tokens[self.i:self.i + 1] = [Token("operator", ">", t.line, t.column, t.offset), Token("operator", ">", t.line, t.column + 1, t.offset + 1)]
            self.expect(">")
        return Type(name, tuple(args))

    def parse(self):
        start, declarations = self.current, []
        while self.current.kind != "eof":
            if self.accept("using"):
                if self.accept("namespace"):
                    self.expect("std")
                else:
                    self.expect("std")
                    self.expect("::")
                    self.take()
                self.expect(";")
                continue
            if self.current.lexeme in UNSUPPORTED:
                fail("parser", self.current, f"unsupported feature {self.current.lexeme!r}", "unsupported")
            constant = bool(self.accept("const"))
            typ = self.parse_type()
            name = self.identifier()
            if self.current.lexeme == "(" and (self.is_type(1) or self.peek().lexeme == ")"):
                self.take()
                parameters = []
                if self.current.lexeme == "void" and self.peek().lexeme == ")":
                    self.take()
                elif self.current.lexeme != ")":
                    while True:
                        pc = bool(self.accept("const"))
                        pt = self.parse_type()
                        pn = self.identifier()
                        if self.current.lexeme == "[":
                            fail("parser", self.current, "array parameters decay to pointers and are unsupported", "unsupported")
                        default = self.expression(2) if self.accept("=") else None
                        parameters.append(A.VarDecl(pn, pn.lexeme, pt, default, constant=pc))
                        if not self.accept(","):
                            break
                self.expect(")")
                body = None if self.accept(";") else self.block()
                declarations.append(A.FunctionDecl(name, name.lexeme, typ, parameters, body))
            else:
                declarations.append(self.variable_group(typ, name, constant))
                self.expect(";")
        return A.Program(start, declarations)

    def variable_group(self, typ=None, name=None, constant=False):
        if typ is None:
            constant = bool(self.accept("const"))
            typ = self.parse_type()
            name = self.identifier()
        declarations = [self.declarator(typ, name, constant)]
        while self.accept(","):
            declarations.append(self.declarator(typ, self.identifier(), constant))
        return A.VarGroup(name, declarations)

    def declarator(self, typ, name, constant):
        dims = []
        while self.accept("["):
            dims.append(None if self.current.lexeme == "]" else self.expression(2))
            self.expect("]")
        declared_type = typ
        for _ in dims:
            declared_type = Type("array", (declared_type,))
        init = None
        if self.accept("="):
            init = self.expression(2)
        elif self.accept("("):
            init = A.ConstructExpr(name, typ, self.arguments(")"))
        elif self.current.lexeme == "{":
            init = self.primary()
        return A.VarDecl(name, name.lexeme, declared_type, init, dims, constant)

    def block(self):
        token = self.expect("{")
        statements = []
        while self.current.lexeme != "}":
            if self.current.kind == "eof":
                self.expected("'}'")
            statements.append(self.statement())
        self.take()
        return A.Block(token, statements)

    def statement(self):
        t = self.current
        if t.lexeme == "{":
            return self.block()
        if self.accept(";"):
            return A.ExprStmt(t, None)
        if self.accept("if"):
            condition = self.paren_expression()
            then = self.statement()
            other = self.statement() if self.accept("else") else None
            return A.IfStmt(t, condition, then, other)
        if self.accept("while"):
            return A.WhileStmt(t, self.paren_expression(), self.statement())
        if self.accept("do"):
            body = self.statement()
            self.expect("while")
            condition = self.paren_expression()
            self.expect(";")
            return A.DoWhileStmt(t, body, condition)
        if self.accept("for"):
            self.expect("(")
            init = None
            if self.is_type():
                const = bool(self.accept("const"))
                typ, name = self.parse_type(), self.identifier()
                if self.accept(":"):
                    iterable = self.expression()
                    self.expect(")")
                    return A.RangeForStmt(t, A.VarDecl(name, name.lexeme, typ, constant=const), iterable, self.statement())
                init = self.variable_group(typ, name, const)
            elif self.current.lexeme != ";":
                init = A.ExprStmt(self.current, self.expression())
            self.expect(";")
            condition = None if self.current.lexeme == ";" else self.expression()
            self.expect(";")
            update = None if self.current.lexeme == ")" else self.expression()
            self.expect(")")
            return A.ForStmt(t, init, condition, update, self.statement())
        if self.accept("switch"):
            expr = self.paren_expression()
            self.expect("{")
            cases = []
            while self.current.lexeme != "}":
                ct = self.current
                if self.accept("case"):
                    value = self.expression(2)
                elif self.accept("default"):
                    value = None
                else:
                    self.expected("case or default")
                self.expect(":")
                statements = []
                while self.current.lexeme not in {"case", "default", "}"}:
                    statements.append(self.statement())
                cases.append(A.SwitchCase(ct, value, statements))
            self.take()
            return A.SwitchStmt(t, expr, cases)
        if t.lexeme in {"break", "continue", "return"}:
            self.take()
            if t.lexeme == "return":
                node = A.ReturnStmt(t, None if self.current.lexeme == ";" else self.expression())
            else:
                node = A.BreakStmt(t) if t.lexeme == "break" else A.ContinueStmt(t)
            self.expect(";")
            return node
        if t.lexeme in UNSUPPORTED:
            fail("parser", t, f"unsupported feature {t.lexeme!r}", "unsupported")
        if self.is_type():
            group = self.variable_group()
            self.expect(";")
            return group
        expr = self.expression()
        self.expect(";")
        return A.ExprStmt(t, expr)

    def paren_expression(self):
        self.expect("(")
        expr = self.expression()
        self.expect(")")
        return expr

    def expression(self, minimum=1):
        left = self.unary()
        while True:
            t = self.current
            if t.lexeme == "?" and minimum <= 3:
                self.take()
                yes = self.expression()
                self.expect(":")
                no = self.expression(2)
                left = A.ConditionalExpr(t, left, yes, no)
                continue
            precedence = PRECEDENCE.get(t.lexeme, 0)
            if precedence < minimum:
                break
            self.take()
            right = self.expression(precedence if precedence == 2 else precedence + 1)
            left = A.BinaryExpr(t, t.lexeme, left, right)
        return left

    def unary(self):
        t = self.current
        if t.lexeme in {"+", "-", "!", "~", "++", "--", "*", "&"}:
            self.take()
            if t.lexeme == "&":
                fail("parser", t, "address-of/pointers are unsupported", "unsupported")
            return A.UnaryExpr(t, t.lexeme, self.unary())
        if t.lexeme == "(" and self.is_type(1):
            self.take()
            typ = self.parse_type()
            self.expect(")")
            return A.CastExpr(t, typ, self.unary())
        expr = self.primary()
        while True:
            t = self.current
            if self.accept("("):
                expr = A.CallExpr(t, expr, self.arguments(")"))
            elif self.accept("["):
                idx = self.expression()
                self.expect("]")
                expr = A.IndexExpr(t, expr, idx)
            elif t.lexeme in {".", "->"}:
                self.take()
                expr = A.MemberExpr(t, expr, self.identifier().lexeme, t.lexeme == "->")
            elif t.lexeme in {"++", "--"}:
                self.take()
                expr = A.UnaryExpr(t, t.lexeme, expr, True)
            else:
                break
        return expr

    def arguments(self, end):
        args = []
        if self.current.lexeme != end:
            while True:
                args.append(self.expression(2))
                if not self.accept(",") or self.current.lexeme == end:
                    break
        self.expect(end)
        return args

    def primary(self):
        t = self.current
        if self.accept("{"):
            return A.InitList(t, self.arguments("}"))
        if self.accept("("):
            expr = self.expression()
            self.expect(")")
            return expr
        if t.lexeme == "[":
            fail("parser", t, "lambdas are unsupported", "unsupported")
        if t.lexeme in UNSUPPORTED:
            fail("parser", t, f"unsupported feature {t.lexeme!r}", "unsupported")
        if t.kind in {"integer", "floating", "string", "char"} or t.lexeme in {"true", "false"}:
            self.take()
            if t.kind == "integer":
                raw = t.lexeme.replace("'", "")
                is_long = raw.lower().endswith("l")
                raw = raw.rstrip("lL")
                base = 16 if raw.lower().startswith("0x") else 2 if raw.lower().startswith("0b") else 8 if len(raw) > 1 and raw.startswith("0") else 10
                try:
                    val = int(raw, base)
                except ValueError:
                    fail("parser", t, "invalid integer literal", "syntax")
                typ = LONG if is_long or val > 2147483647 else INT
                if val > 9223372036854775807:
                    fail("parser", t, "integer literal exceeds signed long long range", "unsupported")
                return A.Literal(t, val, typ)
            if t.kind == "floating":
                if t.lexeme.lower().endswith("l"):
                    fail("parser", t, "long double literals are unsupported", "unsupported")
                value = float(t.lexeme.rstrip("fF"))
                if not math.isfinite(value):
                    fail('parser', t, 'floating literal is outside the representable range', 'syntax')
                return A.Literal(t, value, FLOAT if t.lexeme.lower().endswith("f") else DOUBLE)
            if t.kind in {"char", "string"}:
                value = decode_literal(t)
                if t.kind == "char" and len(value) != 1:
                    fail("parser", t, "expected a single character (multicharacter literals are unsupported)", "unsupported")
                if t.kind == "string":
                    while self.current.kind == "string":
                        value += decode_literal(self.take())
                return A.Literal(t, value, CHAR if t.kind == "char" else STRING)
            return A.Literal(t, t.lexeme == "true", BOOL)
        if self.is_type():
            typ = self.parse_type()
            if self.accept("{"):
                init = A.InitList(t, self.arguments("}"))
                return A.ConstructExpr(t, typ, [init])
            self.expect("(")
            return A.ConstructExpr(t, typ, self.arguments(")"))
        if t.kind == "identifier":
            name = self.take().lexeme
            while self.accept("::"):
                name += "::" + self.take().lexeme
            return A.Name(t, name.removeprefix("std::"))
        self.expected("expression")


def decode_literal(token):
    text, out, i = token.lexeme[1:-1], [], 0
    escapes = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
    while i < len(text):
        c = text[i]
        i += 1
        if c != "\\":
            if ord(c) > 127:
                fail('parser', token, 'non-ASCII literals are outside the portable character subset', 'unsupported')
            out.append(c)
            continue
        c = text[i]
        i += 1
        if c in escapes:
            out.append(escapes[c])
        else:
            start = i
            if c in "01234567":
                i -= 1
                start = i
                while i < len(text) and i - start < 3 and text[i] in "01234567":
                    i += 1
                base = 8
            elif c == "x":
                while i < len(text) and text[i] in "0123456789abcdefABCDEF":
                    i += 1
                base = 16
            else:
                i += 4 if c == "u" else 8
                base = 16
            try:
                val = int(text[start:i], base)
                if val > 127:
                    fail("parser", token, "non-ASCII character escapes are outside the portable char subset", "unsupported")
                out.append(chr(val))
            except ValueError:
                fail("parser", token, "invalid numeric character escape", "syntax")
    return "".join(out)
