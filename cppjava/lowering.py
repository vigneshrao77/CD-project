"""Transforms the annotated AST into semantic operations and explicit copies."""
from . import ast as A
from .ir import IRExpr as E, IRStmt as S, IRFunction, IRProgram
from .typesys import Type, INT, BOOL, STRING, CHAR, VOID, element_type, common_numeric, promote
from .semantic import ASSIGNMENTS, INPUT, OUTPUT, ENDL, SemanticAnalyzer
from .diagnostics import fail
from .controlflow import completion


class Lowerer:
    def __init__(self):
        self.return_type = VOID

    def lower(self, program):
        globals_, functions, entry = [], [], ''
        for decl in program.declarations:
            if isinstance(decl, A.VarGroup):
                globals_.extend(self.variable(var) for var in decl.declarations)
            else:
                self.return_type = decl.return_type
                body = self.statement(decl.body)
                if decl.name == 'main':
                    entry = decl.java_name
                    if not SemanticAnalyzer.returns(decl.body):
                        body.data['statements'].append(S('return', {'value': E('literal', INT, data={'value': 0})}))
                functions.append(IRFunction(decl.java_name, decl.return_type, [{'name': p.java_name, 'type': p.declared_type} for p in decl.parameters], body))
        return IRProgram(globals_, functions, entry)

    def converted(self, value, target, copy=False):
        if value.type != target:
            value = E('convert', target, [value], line=value.line, column=value.column)
        if copy and (target.value_object or target.name == 'iterator') and value.op not in {'construct', 'initializer', 'default', 'copy'}:
            value = E('copy', target, [value], line=value.line, column=value.column)
        return value

    def value(self, expr, target=None, copy=False):
        result = self.expression(expr)
        return self.converted(result, target or result.type, copy)

    def variable(self, var):
        initializer = self.value(var.initializer, var.declared_type, copy=True) if var.initializer else E('default', var.declared_type)
        return S('declare', {'name': var.java_name, 'type': var.declared_type, 'constant': var.constant, 'initializer': initializer, 'dimensions': [self.value(d, INT) for d in var.dimensions]})

    def statement(self, stmt):
        if isinstance(stmt, A.Block):
            result = []
            for child in stmt.statements:
                item = self.statement(child)
                if item.op == 'declarations':
                    result.extend(item.data['statements'])
                else:
                    result.append(item)
                if 'normal' not in completion(child):
                    break
            return S('block', {'statements': result})
        if isinstance(stmt, A.VarGroup):
            return S('declarations', {'statements': [self.variable(d) for d in stmt.declarations]})
        if isinstance(stmt, A.ExprStmt):
            if stmt.expression is None:
                return S('empty')
            expr = stmt.expression
            if expr.type in {INPUT, OUTPUT}:
                values = []
                cur = expr
                while isinstance(cur, A.BinaryExpr) and cur.type == expr.type:
                    values.append(cur.right)
                    cur = cur.left
                values.reverse()
                return S('input' if expr.type == INPUT else 'output', {'values': [self.expression(v) for v in values]})
            if isinstance(expr, A.BinaryExpr) and expr.op == '=' and isinstance(expr.left, A.IndexExpr) and expr.left.object.type == STRING:
                if not isinstance(expr.left.object, A.Name):
                    fail('ir', expr.token, 'string character writes require a named string variable', 'unsupported')
                return S('string_write', {'target': self.expression(expr.left.object), 'index': self.value(expr.left.index, INT), 'value': self.value(expr.right, CHAR)})
            return S('evaluate', {'value': self.expression(expr)})
        if isinstance(stmt, A.IfStmt):
            return S('branch', {'condition': self.value(stmt.condition, BOOL), 'then': self.statement(stmt.then_branch), 'else': self.statement(stmt.else_branch) if stmt.else_branch else None})
        if isinstance(stmt, A.ForStmt):
            return S('loop', {'initializer': self.statement(stmt.initializer) if stmt.initializer else None, 'condition': self.value(stmt.condition, BOOL) if stmt.condition else E('literal', BOOL, data={'value': True}), 'constant_truth': stmt.condition.annotations.get('constant_truth') if stmt.condition else True, 'update': self.expression(stmt.update) if stmt.update else None, 'body': self.statement(stmt.body)})
        if isinstance(stmt, A.RangeForStmt):
            return S('foreach', {'name': stmt.variable.java_name, 'type': stmt.variable.declared_type, 'iterable': self.expression(stmt.iterable), 'element_type': element_type(stmt.iterable.type), 'body': self.statement(stmt.body)})
        if isinstance(stmt, A.WhileStmt):
            return S('while', {'condition': self.value(stmt.condition, BOOL), 'constant_truth': stmt.condition.annotations.get('constant_truth'), 'body': self.statement(stmt.body)})
        if isinstance(stmt, A.DoWhileStmt):
            return S('do', {'condition': self.value(stmt.condition, BOOL), 'body': self.statement(stmt.body)})
        if isinstance(stmt, A.SwitchStmt):
            return S('select', {'value': self.expression(stmt.expression), 'cases': [{'value': case.value.annotations['constant_value'] if case.value else None, 'body': S('block', {'statements': [self.statement(s) for s in case.statements]})} for case in stmt.cases]})
        if isinstance(stmt, A.BreakStmt):
            return S('break')
        if isinstance(stmt, A.ContinueStmt):
            return S('continue')
        if isinstance(stmt, A.ReturnStmt):
            return S('return', {'value': self.value(stmt.expression, self.return_type, copy=True) if stmt.expression else None})
        fail('ir', stmt.token, f'unhandled statement {type(stmt).__name__}', 'internal')

    def expression(self, expr):
        def result(op, args=None, **data):
            return E(op, expr.type, args or [], data, expr.token.line, expr.token.column)
        if isinstance(expr, A.Literal):
            return result('literal', value=expr.value)
        if isinstance(expr, A.Name):
            if expr.type == ENDL:
                return result('newline')
            return result('load', name=expr.annotations.get('java_name', expr.name))
        if isinstance(expr, A.InitList):
            typ = expr.type
            targets = typ.args if typ.name == 'pair' else [element_type(typ)] * len(expr.values) if typ.container else [typ] * len(expr.values)
            return result('initializer', [self.value(v, t, copy=True) for v, t in zip(expr.values, targets)])
        if isinstance(expr, A.CastExpr):
            return self.value(expr.operand, expr.target_type)
        if isinstance(expr, A.ConstructExpr):
            kind, typ = expr.annotations['constructor'], expr.type
            args = expr.arguments
            if kind == 'default':
                return result('default')
            if kind == 'list':
                return self.expression(args[0])
            if kind == 'copy':
                return self.value(args[0], typ, copy=True)
            if kind == 'cast':
                return self.value(args[0], typ)
            if kind == 'fill':
                targets = [INT, typ.args[0] if typ.name == 'vector' else CHAR]
                return result('construct', [self.value(v, t, copy=True) for v, t in zip(args, targets)], kind='fill')
            return result('construct', [self.value(v, t, copy=True) for v, t in zip(args, typ.args)], kind='pair')
        if isinstance(expr, A.IndexExpr):
            owner = expr.object.type
            op = 'map_get_or_insert' if owner.name in {'map', 'unordered_map'} else 'text_at' if owner == STRING else 'array_at' if owner.name == 'array' else 'sequence_at'
            return result(op, [self.expression(expr.object), self.value(expr.index, expr.annotations['index_type'], copy=owner.name in {'map', 'unordered_map'})])
        if isinstance(expr, A.MemberExpr):
            owner = self.expression(expr.object)
            if expr.arrow:
                owner = E('iterator_get', owner.type.args[0], [owner])
            return result('pair_field', [owner], field=expr.member)
        if isinstance(expr, A.UnaryExpr):
            operand = self.expression(expr.operand)
            if expr.op in {'++', '--'}:
                return result('update', [operand, E('literal', INT, data={'value': 1})], operator='+' if expr.op == '++' else '-', postfix=expr.postfix, operation_type=operand.type if operand.type.name == 'iterator' else promote(operand.type))
            if expr.op == '*':
                return result('iterator_get', [operand])
            return result('unary', [self.converted(operand, expr.annotations['operand_type'])], operator=expr.op)
        if isinstance(expr, A.ConditionalExpr):
            return result('choose', [self.value(expr.condition, BOOL), self.value(expr.when_true, expr.type), self.value(expr.when_false, expr.type)])
        if isinstance(expr, A.BinaryExpr):
            if expr.type in {INPUT, OUTPUT}:
                fail('ir', expr.token, 'stream chains must be standalone statements', 'unsupported')
            if expr.op in ASSIGNMENTS:
                left = self.expression(expr.left)
                if left.op == 'text_at':
                    fail('ir', expr.token, 'string character writes are supported only as standalone simple assignments', 'unsupported')
                if expr.op == '=':
                    return result('store', [left, self.value(expr.right, expr.type, copy=True)])
                op_type = expr.annotations['operation_type']
                rhs_type = promote(expr.right.type) if expr.op in {'<<=', '>>='} else op_type if op_type.numeric else expr.right.type
                return result('update', [left, self.value(expr.right, rhs_type)], operator=expr.op[:-1], postfix=False, operation_type=op_type)
            if expr.op == ',':
                return result('sequence', [self.expression(expr.left), self.expression(expr.right)])
            target = expr.annotations.get('operand_type')
            left = self.value(expr.left, target)
            right = self.value(expr.right, promote(expr.right.type) if expr.op in {'<<', '>>'} else target)
            return result('binary', [left, right], operator=expr.op, division=expr.annotations.get('division'))
        if isinstance(expr, A.CallExpr):
            data = expr.annotations
            if 'resolved_target' in data:
                args = expr.arguments + data['defaults']
                return result('invoke', [self.value(v, t, copy=True) for v, t in zip(args, data['parameter_types'])], target=data['resolved_target'])
            if 'method' in data:
                owner = self.expression(expr.callee.object)
                args = [self.value(v, t, copy=True) for v, t in zip(expr.arguments, data['parameter_types'])]
                operation = {'size': 'length', 'empty': 'is_empty', 'begin': 'iterator_begin', 'end': 'iterator_end', 'find': 'lookup_iterator', 'count': 'contains_count', 'erase': 'remove_key', 'insert': 'set_insert', 'push_back': 'sequence_append', 'pop_back': 'sequence_pop', 'clear': 'clear'}[data['method']]
                return result(operation, [owner, *args])
            builtin = data['builtin']
            if builtin == 'make_pair':
                return result('construct', [self.value(v, copy=True) for v in expr.arguments], kind='pair')
            if builtin in {'begin', 'end'}:
                return result('iterator_' + builtin, [self.expression(expr.arguments[0])])
            if builtin == 'sort':
                return result('sort', [self.expression(arg) for arg in expr.arguments[:2]], element_type=data['element_type'], comparator=data.get('comparator'), comparator_parameters=data.get('comparator_parameters', []))
        fail('ir', expr.token, f'unhandled expression {type(expr).__name__}', 'internal')
