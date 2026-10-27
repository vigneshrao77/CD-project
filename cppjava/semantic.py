"""Lexical scopes, expression typing, conversions and resolved call targets."""
from dataclasses import dataclass
from . import ast as A
from .diagnostics import fail
from .controlflow import completion
from .typesys import Type, INT, LONG, SIZE, FLOAT, DOUBLE, CHAR, BOOL, STRING, VOID, AUTO, common_numeric, promote, element_type


JAVA_RESERVED = frozenset('abstract assert boolean byte case catch class const default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null var record yield sealed permits non-sealed'.split())
ASSIGNMENTS = {'=', '+=', '-=', '*=', '/=', '%=', '<<=', '>>=', '&=', '|=', '^='}
MAPS, SETS = {'map', 'unordered_map'}, {'set', 'unordered_set'}
INPUT, OUTPUT, ENDL, FUNCTION = map(Type, ('input', 'output', 'endl', 'function'))


@dataclass
class Symbol:
    name: str
    type: Type
    java_name: str
    constant: bool = False
    constant_value: int | None = None


class Scope:
    def __init__(self, parent=None):
        self.parent, self.symbols = parent, {}

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        return self.parent.lookup(name) if self.parent else None


class SemanticAnalyzer:
    def __init__(self):
        self.global_scope = Scope()
        self.scope = self.global_scope
        self.functions = {}
        self.used_names = set()
        self.function = None
        self.loop_depth = 0
        self.switch_depth = 0

    def error(self, node, message, code='type-error'):
        fail('semantic', node.token, message, code)

    def unique(self, name):
        base = name + '_' if name in JAVA_RESERVED or name.startswith('__cpp') else name
        candidate, count = base, 1
        while candidate in self.used_names:
            count += 1
            candidate = f'{base}_{count}'
        self.used_names.add(candidate)
        return candidate

    def validate_type(self, typ, node, allow_void=False, allow_auto=False):
        if typ == VOID and not allow_void or typ == AUTO and not allow_auto:
            self.error(node, f'{typ} is not valid in this type position')
        for arg in typ.args:
            self.validate_type(arg, node)
        if typ.name in {'unordered_map', 'unordered_set'} and typ.args[0].value_object:
            self.error(node, 'custom hashing for container/pair keys is unsupported', 'unsupported')
        if typ.name == 'array' and typ.args[0].value_object and typ.args[0].name != 'array':
            self.error(node, 'arrays of STL objects are unsupported; use vector<T>', 'unsupported')

    def analyze(self, program):
        definitions = []
        for decl in program.declarations:
            if not isinstance(decl, A.FunctionDecl):
                continue
            self.validate_type(decl.return_type, decl, allow_void=True)
            signature = tuple(p.declared_type for p in decl.parameters)
            for p in decl.parameters:
                self.validate_type(p.declared_type, p)
            existing = next((f for f in self.functions.get(decl.name, []) if tuple(p.declared_type for p in f.parameters) == signature), None)
            if existing:
                if existing.return_type != decl.return_type:
                    self.error(decl, 'overloads cannot differ only by return type', 'redeclaration')
                if existing.body is not None and decl.body is not None:
                    self.error(decl, f'redefinition of function {decl.name}', 'redeclaration')
                for old, new in zip(existing.parameters, decl.parameters):
                    if old.initializer and new.initializer:
                        self.error(new, 'default argument specified more than once', 'redeclaration')
                    if new.initializer:
                        old.initializer = new.initializer
                    elif old.initializer:
                        new.initializer = old.initializer
                if decl.body is not None:
                    decl.java_name = existing.java_name
                    self.functions[decl.name][self.functions[decl.name].index(existing)] = decl
            else:
                decl.java_name = self.unique('__entry' if decl.name == 'main' else decl.name)
                self.functions.setdefault(decl.name, []).append(decl)
        mains = self.functions.get('main', [])
        if len(mains) != 1 or mains[0].parameters or mains[0].return_type != INT or mains[0].body is None:
            self.error(program, 'expected exactly one definition of int main() without parameters', 'entry-point')
        for funcs in self.functions.values():
            for function in funcs:
                if function.body is None:
                    self.error(function, f'function {function.name} is declared but has no single-file definition', 'unsupported')
                definitions.append(function)
        for decl in program.declarations:
            if isinstance(decl, A.VarGroup):
                for var in decl.declarations:
                    if var.name in self.functions:
                        self.error(var, f'{var.name} is already a function', 'redeclaration')
                    self.variable(var)
        for function in definitions:
            default_seen = False
            for parameter in function.parameters:
                if parameter.initializer is not None:
                    default_seen = True
                    self.expression(parameter.initializer, parameter.declared_type)
                    self.require_convert(parameter.initializer, parameter.declared_type)
                elif default_seen:
                    self.error(parameter, 'parameters after a default argument must also have defaults')
        for function in definitions:
            self.function = function
            self.scope = Scope(self.global_scope)
            for parameter in function.parameters:
                self.declare(parameter)
            self.block(function.body, create_scope=False)
            if function.return_type != VOID and function.name != 'main' and not self.returns(function.body):
                self.error(function, f'not all paths in {function.name} return a value', 'missing-return')
            self.scope = self.global_scope
        program.declarations = [d for d in program.declarations if isinstance(d, A.VarGroup)] + definitions
        return program

    def declare(self, var):
        if var.name in self.scope.symbols:
            self.error(var, f'redeclaration of {var.name} in the same scope', 'redeclaration')
        var.java_name = self.unique(var.name)
        symbol = Symbol(var.name, var.declared_type, var.java_name, var.constant)
        self.scope.symbols[var.name] = symbol
        return symbol

    def variable(self, var):
        self.validate_type(var.declared_type, var, allow_auto=True)
        typ = var.declared_type
        if typ == AUTO:
            if var.initializer is None or isinstance(var.initializer, A.InitList):
                self.error(var, 'auto needs a typed initializer')
            typ = self.expression(var.initializer)
            if typ in {VOID, FUNCTION, INPUT, OUTPUT, ENDL}:
                self.error(var, f'cannot declare auto from {typ}')
            var.declared_type = typ
        symbol = self.declare(var)
        for i, dimension in enumerate(var.dimensions):
            if dimension is None:
                if i != 0 or not isinstance(var.initializer, A.InitList):
                    self.error(var, 'only the first array extent can be inferred from an initializer')
                var.dimensions[i] = A.Literal(var.token, len(var.initializer.values), INT)
                var.dimensions[i].type = INT
            else:
                dt = self.expression(dimension)
                if not dt.integral:
                    self.error(dimension, 'array extent must be integral')
                size = self.constant(dimension)
                if size is None:
                    self.error(dimension, 'variable-length arrays are not C++17; fixed-size arrays require a constant extent', 'unsupported')
                if size <= 0:
                    self.error(dimension, 'array extent must be positive')
        if var.initializer is not None:
            self.expression(var.initializer, typ)
            self.require_convert(var.initializer, typ)
            if typ.name == 'array':
                self.check_array_initializer(var.initializer, var.dimensions)
            if var.constant and typ.integral:
                symbol.constant_value = self.constant(var.initializer)
        elif var.constant and not typ.value_object and typ != STRING:
            self.error(var, 'const scalar declaration requires an initializer')

    def check_array_initializer(self, expr, dimensions):
        if not isinstance(expr, A.InitList):
            self.error(expr, 'array copy initialization is unsupported', 'unsupported')
        if len(expr.values) > self.constant(dimensions[0]):
            self.error(expr, 'too many array initializer elements')
        if len(dimensions) > 1:
            for child in expr.values:
                self.check_array_initializer(child, dimensions[1:])

    def block(self, block, create_scope=True):
        old = self.scope
        if create_scope:
            self.scope = Scope(old)
        for stmt in block.statements:
            self.statement(stmt)
        self.scope = old

    def scoped_statement(self, stmt):
        old = self.scope
        self.scope = Scope(old)
        self.statement(stmt)
        self.scope = old

    def condition(self, expr):
        typ = self.expression(expr)
        if typ == INPUT:
            self.error(expr, 'stream extraction in expressions/conditions is unsupported; use standalone cin chains', 'unsupported')
        if not typ.numeric:
            self.error(expr, f'condition requires scalar truth conversion, found {typ}')
        expr.annotations['condition_conversion'] = 'identity' if typ == BOOL else 'nonzero'
        constant = self.constant(expr)
        if constant is not None:
            expr.annotations['constant_truth'] = bool(constant)

    def statement(self, stmt):
        if isinstance(stmt, A.Block):
            self.block(stmt)
        elif isinstance(stmt, A.VarGroup):
            for decl in stmt.declarations:
                self.variable(decl)
        elif isinstance(stmt, A.ExprStmt):
            if stmt.expression:
                self.expression(stmt.expression)
        elif isinstance(stmt, A.IfStmt):
            self.condition(stmt.condition)
            self.scoped_statement(stmt.then_branch)
            if stmt.else_branch:
                self.scoped_statement(stmt.else_branch)
        elif isinstance(stmt, A.ForStmt):
            old, self.scope = self.scope, Scope(self.scope)
            if stmt.initializer:
                self.statement(stmt.initializer)
            if stmt.condition:
                self.condition(stmt.condition)
            if stmt.update:
                self.expression(stmt.update)
            self.loop_depth += 1
            self.scoped_statement(stmt.body)
            self.loop_depth -= 1
            self.scope = old
        elif isinstance(stmt, A.RangeForStmt):
            typ = self.expression(stmt.iterable)
            if not typ.container and typ != STRING:
                self.error(stmt.iterable, f'{typ} is not iterable')
            element = element_type(typ)
            old, self.scope = self.scope, Scope(self.scope)
            if stmt.variable.declared_type == AUTO:
                stmt.variable.declared_type = element
            elif self.rank(element, stmt.variable.declared_type) is None:
                self.error(stmt.variable, f'cannot initialize range variable from {element}')
            self.declare(stmt.variable)
            self.loop_depth += 1
            self.scoped_statement(stmt.body)
            self.loop_depth -= 1
            self.scope = old
        elif isinstance(stmt, (A.WhileStmt, A.DoWhileStmt)):
            self.condition(stmt.condition)
            self.loop_depth += 1
            self.scoped_statement(stmt.body)
            self.loop_depth -= 1
        elif isinstance(stmt, A.SwitchStmt):
            typ = self.expression(stmt.expression)
            if not typ.integral:
                self.error(stmt.expression, 'switch expression must be integral')
            self.switch_depth += 1
            old, self.scope = self.scope, Scope(self.scope)
            values = set()
            for case in stmt.cases:
                key = 'default'
                if case.value:
                    if not self.expression(case.value).integral:
                        self.error(case.value, 'case value must be integral')
                    key = self.constant(case.value)
                    if key is None:
                        self.error(case.value, 'case value must be a constant expression')
                    case.value.annotations['constant_value'] = key
                if key in values:
                    self.error(case, f'duplicate switch label {key}')
                values.add(key)
                for item in case.statements:
                    self.statement(item)
            self.scope = old
            self.switch_depth -= 1
        elif isinstance(stmt, A.BreakStmt):
            if not self.loop_depth and not self.switch_depth:
                self.error(stmt, 'break is only valid inside a loop or switch', 'control-flow')
        elif isinstance(stmt, A.ContinueStmt):
            if not self.loop_depth:
                self.error(stmt, 'continue is only valid inside a loop', 'control-flow')
        elif isinstance(stmt, A.ReturnStmt):
            ret = self.function.return_type
            if stmt.expression:
                self.expression(stmt.expression, ret)
                self.require_convert(stmt.expression, ret)
            elif ret != VOID:
                self.error(stmt, f'return requires a {ret} value')

    def expression(self, expr, expected=None):
        typ = None
        if isinstance(expr, A.Literal):
            typ = expr.literal_type
        elif isinstance(expr, A.Name):
            symbol = self.scope.lookup(expr.name)
            if symbol:
                typ = symbol.type
                expr.annotations.update(java_name=symbol.java_name, lvalue=True, constant=symbol.constant)
                if symbol.constant_value is not None:
                    expr.annotations['constant_value'] = symbol.constant_value
            elif expr.name in {'cin', 'cout', 'endl'}:
                typ = {'cin': INPUT, 'cout': OUTPUT, 'endl': ENDL}[expr.name]
            elif expr.name in self.functions or expr.name in {'sort', 'make_pair', 'begin', 'end'}:
                typ = FUNCTION
            elif expr.name in {'reverse', 'unique', 'accumulate', 'lower_bound', 'upper_bound', 'min', 'max', 'abs', 'sqrt', 'printf', 'scanf', 'getline', 'ios::sync_with_stdio', 'ios_base::sync_with_stdio', 'static_cast', 'dynamic_cast', 'reinterpret_cast', 'const_cast'}:
                self.error(expr, f'library operation or cast {expr.name} is unsupported in v1', 'unsupported')
            else:
                self.error(expr, f'use of undeclared identifier {expr.name}', 'undeclared-identifier')
        elif isinstance(expr, A.InitList):
            if expected is None:
                self.error(expr, 'initializer list needs a target type')
            typ = expected
            if typ.name == 'pair':
                targets = typ.args
                if len(expr.values) != 2:
                    self.error(expr, 'pair initializer requires two values')
            elif typ.container:
                targets = [element_type(typ)] * len(expr.values)
            elif not expr.values:
                targets = []
            elif len(expr.values) == 1:
                targets = [typ]
            else:
                self.error(expr, f'too many initializer values for {typ}')
            for value, target in zip(expr.values, targets):
                self.expression(value, target)
                self.require_convert(value, target)
        elif isinstance(expr, A.ConstructExpr):
            typ = self.construct(expr)
        elif isinstance(expr, A.CastExpr):
            source = self.expression(expr.operand)
            typ = expr.target_type
            if not source.numeric or not typ.numeric:
                self.error(expr, f'only numeric casts are supported, found {source} to {typ}', 'unsupported')
        elif isinstance(expr, A.IndexExpr):
            owner = self.expression(expr.object)
            index = self.expression(expr.index)
            if owner.name in {'vector', 'array'} or owner == STRING:
                if not index.integral:
                    self.error(expr.index, 'index must be integral')
                typ = element_type(owner)
                expr.annotations['index_type'] = INT
            elif owner.name in MAPS:
                self.require_convert(expr.index, owner.args[0])
                typ = owner.args[1]
                expr.annotations['index_type'] = owner.args[0]
                if expr.object.annotations.get('constant'):
                    self.error(expr, 'operator[] cannot be used on a const map')
            else:
                self.error(expr, f'{owner} does not support indexing')
            expr.annotations.update(lvalue=True, constant=expr.object.annotations.get('constant', False))
        elif isinstance(expr, A.MemberExpr):
            owner = self.expression(expr.object)
            if expr.arrow:
                if owner.name != 'iterator':
                    self.error(expr, 'arrow access is supported only on STL iterators', 'unsupported')
                owner = owner.args[0]
            if owner.name == 'pair' and expr.member in {'first', 'second'}:
                typ = owner.args[0 if expr.member == 'first' else 1]
                expr.annotations.update(lvalue=True, constant=expr.object.annotations.get('constant', False))
                if expr.arrow and (expr.object.type.origin in SETS or expr.object.type.origin.startswith('const ')):
                    expr.annotations['constant'] = True
                if expr.member == 'first' and (expr.arrow and expr.object.type.origin.removeprefix('const ') in MAPS or expr.object.annotations.get('map_entry')):
                    expr.annotations['constant'] = True
            else:
                self.error(expr, f'unsupported member {expr.member} on {owner}', 'unsupported')
        elif isinstance(expr, A.CallExpr):
            typ = self.call(expr)
        elif isinstance(expr, A.UnaryExpr):
            operand = self.expression(expr.operand)
            if expr.op == '*':
                if operand.name != 'iterator':
                    self.error(expr, 'dereference is supported only for STL iterators; pointers are unsupported', 'unsupported')
                typ = operand.args[0]
                origin = operand.origin
                expr.annotations.update(lvalue=True, constant=origin.startswith('const ') or origin in SETS or origin == 'string', map_entry=origin.removeprefix('const ') in MAPS)
            elif expr.op in {'++', '--'}:
                self.require_lvalue(expr.operand)
                if operand == BOOL or not operand.numeric and operand.name != 'iterator':
                    self.error(expr, f'{expr.op} requires numeric storage or an iterator')
                typ = operand
            elif expr.op == '!':
                if not operand.numeric:
                    self.error(expr, '! requires a scalar operand')
                typ = BOOL
            elif expr.op == '~':
                if not operand.integral:
                    self.error(expr, '~ requires an integral operand')
                typ = promote(operand)
            else:
                if not operand.numeric:
                    self.error(expr, f'{expr.op} requires a numeric operand')
                typ = promote(operand)
            expr.annotations['operand_type'] = typ if expr.op != '!' else BOOL
        elif isinstance(expr, A.ConditionalExpr):
            self.condition(expr.condition)
            yes, no = self.expression(expr.when_true, expected), self.expression(expr.when_false, expected)
            if yes == no:
                typ = yes
            elif yes.numeric and no.numeric:
                typ = common_numeric(yes, no)
            else:
                self.error(expr, f'incompatible conditional branches {yes} and {no}')
        elif isinstance(expr, A.BinaryExpr):
            typ = self.binary(expr)
        else:
            self.error(expr, f'unrecognized expression node {type(expr).__name__}', 'internal')
        expr.type = typ
        expr.annotations['java_type'] = typ.java
        return typ

    def construct(self, expr):
        typ, args = expr.target_type, expr.arguments
        self.validate_type(typ, expr)
        if len(args) == 1 and isinstance(args[0], A.InitList):
            self.expression(args[0], typ)
            expr.annotations['constructor'] = 'list'
        elif not args:
            expr.annotations['constructor'] = 'default'
        elif len(args) == 1 and self.expression(args[0]) == typ:
            expr.annotations['constructor'] = 'copy'
        elif typ.numeric and len(args) == 1:
            self.require_convert(args[0], typ)
            expr.annotations['constructor'] = 'cast'
        elif typ.name == 'vector' and len(args) in {1, 2}:
            if not self.expression(args[0]).integral:
                self.error(args[0], 'vector size must be integral')
            if len(args) == 2:
                self.expression(args[1], typ.args[0])
                self.require_convert(args[1], typ.args[0])
            expr.annotations['constructor'] = 'fill'
        elif typ == STRING and len(args) == 2:
            if not self.expression(args[0]).integral:
                self.error(args[0], 'string count must be integral')
            self.expression(args[1])
            self.require_convert(args[1], CHAR)
            expr.annotations['constructor'] = 'fill'
        elif typ.name == 'pair' and len(args) == 2:
            for arg, target in zip(args, typ.args):
                self.expression(arg, target)
                self.require_convert(arg, target)
            expr.annotations['constructor'] = 'pair'
        else:
            self.error(expr, f'unsupported constructor for {typ} with {len(args)} arguments', 'unsupported')
        return typ

    def binary(self, expr):
        op = expr.op
        left = self.expression(expr.left)
        right = self.expression(expr.right, left if op in ASSIGNMENTS else None)
        if left == OUTPUT and op == '<<':
            if not right.numeric and right not in {STRING, ENDL}:
                self.error(expr.right, f'cannot print {right}')
            return OUTPUT
        if left == INPUT and op == '>>':
            self.require_lvalue(expr.right)
            if not right.numeric and right != STRING:
                self.error(expr.right, f'cannot read {right}')
            return INPUT
        if op == ',':
            if left in {INPUT, OUTPUT} or right in {INPUT, OUTPUT}:
                self.error(expr, 'stream chains must be standalone statements', 'unsupported')
            return right
        if op in ASSIGNMENTS:
            self.require_lvalue(expr.left)
            if left.name == 'array':
                self.error(expr, 'C++ arrays are not assignable')
            if op == '=':
                self.require_convert(expr.right, left)
                expr.annotations['operation_type'] = left
            else:
                result = self.operator_type(op[:-1], left, right, expr)
                if self.rank(result, left) is None:
                    self.error(expr, f'cannot store {result} in {left}')
                expr.annotations['operation_type'] = result
            return left
        result = self.operator_type(op, left, right, expr)
        if left.numeric and right.numeric:
            expr.annotations['operand_type'] = BOOL if op in {'&&', '||'} else promote(left) if op in {'<<', '>>'} else common_numeric(left, right)
            if op == '/':
                expr.annotations['division'] = 'truncate-toward-zero (C++17 and Java agree)' if result.integral else 'IEEE-754 floating division'
        return result

    def operator_type(self, op, left, right, node):
        if op == '+' and (left == STRING and right in {STRING, CHAR} or right == STRING and left in {STRING, CHAR}):
            if isinstance(node, A.BinaryExpr) and isinstance(node.left, A.Literal) and node.left.literal_type == STRING and isinstance(node.right, A.Literal) and node.right.literal_type == STRING:
                self.error(node, 'adding two string literals is invalid C++; construct a string operand')
            return STRING
        if left.numeric and right.numeric:
            if op in {'&&', '||', '==', '!=', '<', '>', '<=', '>='}:
                return BOOL
            if op in {'%', '&', '|', '^', '<<', '>>'} and (not left.integral or not right.integral):
                self.error(node, f'{op} requires integral operands')
            return promote(left) if op in {'<<', '>>'} else common_numeric(left, right)
        if left == right and (left == STRING or left.value_object or left.name == 'iterator') and op in {'==', '!=', '<', '>', '<=', '>='}:
            if left.name == 'array':
                self.error(node, 'array comparisons decay to pointers and are unsupported', 'unsupported')
            if left.name in {'unordered_map', 'unordered_set'} and op not in {'==', '!='}:
                self.error(node, 'unordered containers have no relational ordering')
            if left.name == 'iterator' and op not in {'==', '!='}:
                self.error(node, 'only iterator equality comparisons are supported', 'unsupported')
            return BOOL
        self.error(node, f'operator {op} is invalid for {left} and {right}')

    def call(self, expr):
        if isinstance(expr.callee, A.MemberExpr):
            return self.method(expr)
        if not isinstance(expr.callee, A.Name):
            self.error(expr, 'indirect function calls are unsupported', 'unsupported')
        name = expr.callee.name
        self.expression(expr.callee)
        if self.scope.lookup(name):
            self.error(expr, f'{name} is a variable, not a callable function')
        if name == 'sort':
            return self.sort(expr)
        if name in {'begin', 'end'}:
            if len(expr.arguments) != 1:
                self.error(expr, f'{name} expects one container')
            typ = self.expression(expr.arguments[0])
            if not typ.container and typ != STRING:
                self.error(expr, f'{name} requires a container')
            expr.annotations.update(builtin=name, owner_type=typ)
            return Type('iterator', (element_type(typ),), ('const ' if expr.arguments[0].annotations.get('constant') else '') + typ.name)
        if name == 'make_pair':
            if len(expr.arguments) != 2:
                self.error(expr, 'make_pair expects two arguments')
            types = tuple(self.expression(arg) for arg in expr.arguments)
            if any(t in {VOID, FUNCTION, INPUT, OUTPUT} for t in types):
                self.error(expr, 'invalid pair element')
            expr.annotations['builtin'] = 'make_pair'
            return Type('pair', types)
        types = [self.expression(arg) for arg in expr.arguments]
        target = self.resolve(name, types, expr)
        expr.annotations.update(resolved_target=target.java_name, parameter_types=[p.declared_type for p in target.parameters], defaults=[p.initializer for p in target.parameters[len(types):]])
        return target.return_type

    def resolve(self, name, types, node):
        candidates = []
        for function in self.functions.get(name, []):
            params = function.parameters
            if len(types) > len(params) or any(p.initializer is None for p in params[len(types):]):
                continue
            ranks = [self.rank(t, p.declared_type) for t, p in zip(types, params)]
            if all(rank is not None for rank in ranks):
                candidates.append((function, ranks))
        if not candidates:
            self.error(node, f'no matching overload for {name}({", ".join(map(str, types))})', 'overload')
        best = []
        for candidate, ranks in candidates:
            if not any(all(a <= b for a, b in zip(other, ranks)) and any(a < b for a, b in zip(other, ranks)) for _, other in candidates):
                best.append(candidate)
        if len(best) != 1:
            self.error(node, f'ambiguous overload for {name}({", ".join(map(str, types))})', 'overload')
        return best[0]

    def method(self, expr):
        member, args = expr.callee, expr.arguments
        owner = self.expression(member.object)
        name = member.member
        if member.arrow:
            self.error(expr, 'iterator method calls are unsupported', 'unsupported')
        result, targets = None, []
        if name in {'size', 'empty'} and (owner.container or owner == STRING):
            result = SIZE if name == 'size' else BOOL
        elif name in {'begin', 'end'} and (owner.container or owner == STRING):
            result = Type('iterator', (element_type(owner),), ('const ' if member.object.annotations.get('constant') else '') + owner.name)
        elif name in {'push_back', 'pop_back'} and owner.name == 'vector':
            result = VOID
            targets = [owner.args[0]] if name == 'push_back' else []
        elif name in {'find', 'count', 'erase'} and owner.name in MAPS | SETS:
            result = Type('iterator', (element_type(owner),), ('const ' if member.object.annotations.get('constant') else '') + owner.name) if name == 'find' else INT
            targets = [owner.args[0]]
        elif name == 'insert' and owner.name in SETS:
            # Return type follows C++ insert: pair<iterator<T>, bool>.
            result = Type('pair', (Type('iterator', (owner.args[0],), owner.name), BOOL))
            targets = [owner.args[0]]
        elif name == 'clear' and owner.container and owner.name != 'array':
            result = VOID
        else:
            self.error(expr, f'unsupported operation .{name} on {owner}', 'unsupported')
        if len(args) != len(targets):
            self.error(expr, f'.{name} expects {len(targets)} arguments, found {len(args)}')
        if name in {'push_back', 'pop_back', 'insert', 'erase', 'clear'} and member.object.annotations.get('constant'):
            self.error(expr, f'cannot call .{name} on const storage')
        for arg, target in zip(args, targets):
            self.expression(arg, target)
            self.require_convert(arg, target)
        member.type = FUNCTION
        member.annotations['java_type'] = 'function'
        expr.annotations.update(method=name, owner_type=owner, parameter_types=targets)
        if owner.name in MAPS and result.name == 'iterator':
            expr.annotations['map_iterator'] = True
        return result

    def sort(self, expr):
        args = expr.arguments
        if len(args) not in {2, 3}:
            self.error(expr, 'sort requires begin, end, and optionally a comparator')
        first, last = self.expression(args[0]), self.expression(args[1])
        if first.name != 'iterator' or first != last:
            self.error(expr, 'sort endpoints must be compatible iterators')
        for endpoint in args[:2]:
            if not isinstance(endpoint, A.CallExpr) or endpoint.annotations.get('owner_type', Type('unknown')).name not in {'vector', 'array'}:
                self.error(endpoint, 'sort requires vector/array begin() and end() endpoints', 'unsupported')
            if endpoint.type.origin.startswith('const '):
                self.error(endpoint, 'sort cannot modify const storage')
        expr.annotations['builtin'] = 'sort'
        expr.annotations['element_type'] = first.args[0]
        if len(args) == 3:
            comparator = args[2]
            if not isinstance(comparator, A.Name):
                self.error(comparator, 'sort comparator must name a free function', 'unsupported')
            self.expression(comparator)
            target = self.resolve(comparator.name, [first.args[0], first.args[0]], comparator)
            if target.return_type != BOOL:
                self.error(comparator, 'sort comparator must return bool')
            expr.annotations['comparator'] = target.java_name
            expr.annotations['comparator_parameters'] = [p.declared_type for p in target.parameters]
        return VOID

    def require_lvalue(self, expr):
        if not expr.annotations.get('lvalue'):
            self.error(expr, 'operation requires assignable storage')
        if expr.annotations.get('constant'):
            self.error(expr, 'cannot modify const storage')
        if expr.annotations.get('map_entry'):
            self.error(expr, 'cannot assign a complete map entry because its key is const')

    @staticmethod
    def rank(source, target):
        if source == target:
            return 0
        if source.numeric and target.numeric:
            return 1 if promote(source) == target or source == FLOAT and target == DOUBLE else 2
        return None

    def require_convert(self, expr, target):
        if self.rank(expr.type, target) is None:
            self.error(expr, f'cannot convert {expr.type} to {target}')
        expr.annotations.setdefault('conversions', [])
        if target not in expr.annotations['conversions']:
            expr.annotations['conversions'].append(target)

    def constant(self, expr):
        if isinstance(expr, A.Literal) and expr.literal_type.integral:
            return ord(expr.value) if expr.literal_type == CHAR else int(expr.value)
        if isinstance(expr, A.Name):
            return expr.annotations.get('constant_value')
        if isinstance(expr, A.UnaryExpr):
            v = self.constant(expr.operand)
            if v is not None:
                return {'+': lambda: +v, '-': lambda: -v, '~': lambda: ~v, '!': lambda: int(not v)}.get(expr.op, lambda: None)()
        if isinstance(expr, A.BinaryExpr):
            a, b = self.constant(expr.left), self.constant(expr.right)
            if a is None or b is None:
                return None
            operations = {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1), '%': lambda: a - (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1) * b, '<<': lambda: a << b, '>>': lambda: a >> b, '&': lambda: a & b, '|': lambda: a | b, '^': lambda: a ^ b, '==': lambda: int(a == b), '!=': lambda: int(a != b), '<': lambda: int(a < b), '>': lambda: int(a > b), '<=': lambda: int(a <= b), '>=': lambda: int(a >= b), '&&': lambda: int(bool(a) and bool(b)), '||': lambda: int(bool(a) or bool(b))}
            try:
                return operations.get(expr.op, lambda: None)()
            except (ValueError, ZeroDivisionError):
                self.error(expr, 'invalid arithmetic in constant expression')
        return None

    @classmethod
    def returns(cls, stmt):
        return 'normal' not in completion(stmt)
