"""Structural source types and their checked Java representation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Type:
    name: str
    args: tuple['Type', ...] = ()
    origin: str = ''

    def __str__(self):
        return self.name + ("<" + ", ".join(map(str, self.args)) + ">" if self.args else "") + (f'@{self.origin}' if self.origin else '')

    @property
    def numeric(self):
        return self.name in {"bool", "char", "int", "long long", "size_t", "float", "double"}

    @property
    def integral(self):
        return self.numeric and self.name not in {"float", "double"}

    @property
    def container(self):
        return self.name in {"vector", "map", "unordered_map", "set", "unordered_set", "array"}

    @property
    def value_object(self):
        return self.container or self.name == "pair"

    @property
    def java(self):
        primitives = {"int": "int", "long long": "long", "size_t": "long", "double": "double", "float": "float", "char": "char", "bool": "boolean", "void": "void", "string": "String"}
        if self.name in primitives:
            return primitives[self.name]
        if self.name == "array":
            return self.args[0].java + "[]"
        classes = {"vector": "ArrayList", "map": "TreeMap", "unordered_map": "HashMap", "set": "TreeSet", "unordered_set": "HashSet", "pair": "CppPair", "iterator": "CppIterator"}
        if self.name in classes:
            return classes[self.name] + "<" + ", ".join(a.boxed for a in self.args) + ">"
        return self.name

    @property
    def boxed(self):
        return {"int": "Integer", "long long": "Long", "size_t": "Long", "double": "Double", "float": "Float", "char": "Character", "bool": "Boolean"}.get(self.name, self.java)


INT, LONG, DOUBLE, FLOAT, CHAR, BOOL, STRING, VOID, AUTO = map(Type, ("int", "long long", "double", "float", "char", "bool", "string", "void", "auto"))
SIZE = Type('size_t')


def promote(t):
    return INT if t in (CHAR, BOOL) else t


def common_numeric(a, b):
    order = [INT, LONG, SIZE, FLOAT, DOUBLE]
    return order[max(order.index(promote(a)), order.index(promote(b)))]


def element_type(t):
    if t.name in {"map", "unordered_map"}:
        return Type("pair", t.args)
    if t == STRING:
        return CHAR
    return t.args[0]
