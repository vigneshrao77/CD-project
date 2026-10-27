"""Token-aware object macro expansion; retains invocation source locations."""
from dataclasses import replace
from .diagnostics import fail


HEADERS = frozenset("iostream vector string map unordered_map set unordered_set algorithm utility bits/stdc++.h cstdint climits limits cmath iomanip cstddef iterator cstdlib cstdio numeric array".split())


class Preprocessor:
    def process(self, tokens):
        macros, result = {}, []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t.lexeme != "#":
                result.extend(self.expand(t, macros, ()))
                i += 1
                continue
            if i and tokens[i - 1].line == t.line:
                fail("preprocessor", t, "directive must start a source line")
            end = i + 1
            while end < len(tokens) and tokens[end].line == t.line and tokens[end].kind != "eof":
                end += 1
            directive = tokens[i + 1:end]
            if not directive:
                fail("preprocessor", t, "expected directive after #")
            name = directive[0].lexeme
            if name == "include":
                header = "".join(x.lexeme for x in directive[1:])
                if not (header.startswith("<") and header.endswith(">") and header[1:-1] in HEADERS):
                    fail("preprocessor", t, f"unsupported include {header!r}; only recognized standard headers are allowed", "unsupported")
            elif name == "define":
                if len(directive) < 3 or directive[1].kind != "identifier":
                    fail("preprocessor", t, "expected #define NAME value")
                macro, value = directive[1], directive[2:]
                if value[0].lexeme == "(" and value[0].offset == macro.offset + len(macro.lexeme):
                    fail("preprocessor", macro, "function-like macros are unsupported", "unsupported")
                if any(v.lexeme == "#" for v in value):
                    fail("preprocessor", macro, "macro stringification/token pasting is unsupported", "unsupported")
                macros[macro.lexeme] = value
            else:
                fail("preprocessor", t, f"preprocessor directive #{name} is unsupported", "unsupported")
            i = end
        return result

    def expand(self, token, macros, active):
        if token.kind != "identifier" or token.lexeme not in macros:
            return [token]
        if token.lexeme in active:
            fail("preprocessor", token, f"recursive macro expansion of {token.lexeme}", "unsupported")
        result = []
        for item in macros[token.lexeme]:
            located = replace(item, line=token.line, column=token.column, offset=token.offset)
            result.extend(self.expand(located, macros, (*active, token.lexeme)))
        return result
