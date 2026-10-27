"""Hand-written maximal-munch scanner. Input: source; output: located tokens."""
from dataclasses import dataclass
from .diagnostics import CompileError, Diagnostic


KEYWORDS = frozenset("int long double float char bool string void auto const if else for while do switch case default break continue return using namespace true false template class struct new delete unsigned signed short static sizeof nullptr enum typedef virtual public private protected volatile extern inline constexpr throw try catch goto union".split())
OPERATORS = tuple(sorted((":: -> ++ -- == != <= >= && || << >> += -= *= /= %= &= |= ^= <<= >>= ... + - * / % < > = ! ~ & | ^ ? : ; , . ( ) { } [ ] #".split()), key=len, reverse=True))


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    line: int
    column: int
    offset: int = 0


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.i = 0
        self.line = 1
        self.column = 1
        self.errors = []

    def advance(self):
        c = self.source[self.i]
        self.i += 1
        if c == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return c

    def error(self, line, column, message):
        self.errors.append(Diagnostic("lexer", "invalid-token", line, column, message))

    def tokenize(self):
        tokens = []
        n = len(self.source)
        while self.i < n:
            c = self.source[self.i]
            if c.isspace():
                self.advance()
                continue
            start, line, column = self.i, self.line, self.column
            if self.source.startswith("//", self.i):
                while self.i < n and self.source[self.i] != "\n":
                    self.advance()
                continue
            if self.source.startswith("/*", self.i):
                self.advance()
                self.advance()
                while self.i < n and not self.source.startswith("*/", self.i):
                    self.advance()
                if self.i == n:
                    self.error(line, column, "unterminated block comment")
                else:
                    self.advance()
                    self.advance()
                continue
            if c.isascii() and (c.isalpha() or c == "_"):
                self.advance()
                while self.i < n and self.source[self.i].isascii() and (self.source[self.i].isalnum() or self.source[self.i] == "_"):
                    self.advance()
                word = self.source[start:self.i]
                kind = "keyword" if word in KEYWORDS else "identifier"
            elif c.isdigit() or (c == "." and self.i + 1 < n and self.source[self.i + 1].isdigit()):
                kind = self.number(line, column)
            elif c in "\"'":
                kind = "string" if c == '"' else "char"
                quote = self.advance()
                closed = False
                while self.i < n:
                    ch = self.advance()
                    if ch == quote:
                        closed = True
                        break
                    if ch == "\n":
                        self.error(line, column, "newline in literal")
                        break
                    if ch == "\\":
                        if self.i == n:
                            break
                        escaped = self.advance()
                        if escaped not in "abfnrtv\\'\"?01234567xuU":
                            self.error(self.line, self.column - 1, f"invalid escape \\{escaped}")
                if not closed:
                    self.error(line, column, f"unterminated {kind} literal")
            else:
                op = next((op for op in OPERATORS if self.source.startswith(op, self.i)), None)
                if op is None:
                    self.error(line, column, f"invalid character {c!r}")
                    self.advance()
                    continue
                for _ in op:
                    self.advance()
                kind = "operator"
            tokens.append(Token(kind, self.source[start:self.i], line, column, start))
        tokens.append(Token("eof", "<eof>", self.line, self.column, self.i))
        if self.errors:
            raise CompileError(self.errors)
        return tokens

    def number(self, line, column):
        s, n = self.source, len(self.source)
        start = self.i
        floating = False
        if s.startswith(("0x", "0X", "0b", "0B"), self.i):
            base = s[self.i + 1].lower()
            self.advance()
            self.advance()
            digits = "0123456789abcdefABCDEF" if base == "x" else "01"
            first = self.i
            while self.i < n and (s[self.i] in digits or s[self.i] == "'"):
                self.advance()
            if first == self.i:
                self.error(line, column, "expected digits after numeric base prefix")
        else:
            while self.i < n and (s[self.i].isdigit() or s[self.i] == "'"):
                self.advance()
            if self.i < n and s[self.i] == ".":
                floating = True
                self.advance()
                while self.i < n and s[self.i].isdigit():
                    self.advance()
            if self.i < n and s[self.i] in "eE":
                floating = True
                self.advance()
                if self.i < n and s[self.i] in "+-":
                    self.advance()
                first = self.i
                while self.i < n and s[self.i].isdigit():
                    self.advance()
                if first == self.i:
                    self.error(line, column, "expected exponent digits")
        if self.i < n and s[self.i] in "fF":
            floating = True
            self.advance()
        elif self.i < n and s[self.i] in "lL":
            self.advance()
            if self.i < n and s[self.i] in "lL":
                self.advance()
        if self.i < n and (s[self.i].isalnum() or s[self.i] == "_"):
            while self.i < n and (s[self.i].isalnum() or s[self.i] == "_"):
                self.advance()
            self.error(line, column, f"invalid or unsupported numeric literal {s[start:self.i]!r}")
        return "floating" if floating else "integer"
