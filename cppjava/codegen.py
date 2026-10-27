"""Pretty-prints typed IR; collects only imports/runtime support actually used."""
from .ir import IRExpr as E
from .typesys import Type, INT, LONG, SIZE, FLOAT, DOUBLE, CHAR, BOOL, STRING, VOID, promote
from .diagnostics import CompileError, Diagnostic
from . import runtime


def quote(value, character=False):
    delimiter = "'" if character else '"'
    escapes = {'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f', '\\': '\\\\', delimiter: '\\' + delimiter}
    return delimiter + ''.join(escapes.get(c, ('\\%03o' % ord(c)) if ord(c) < 32 or ord(c) == 127 else c) for c in value) + delimiter


class JavaGenerator:
    def __init__(self, class_name='Main'):
        if not class_name or not (class_name[0].isalpha() or class_name[0] in '_$') or not all(c.isascii() and (c.isalnum() or c in '_$') for c in class_name):
            raise CompileError([Diagnostic('codegen', 'class-name', 1, 1, 'Java class name must be an ASCII identifier')])
        from .semantic import JAVA_RESERVED
        if class_name in JAVA_RESERVED or class_name in {'CppPair', 'CppIterator', 'CppInput', 'String', 'System', 'Integer', 'Long', 'Float', 'Double', 'Character', 'Boolean', 'ArrayList', 'TreeMap', 'HashMap', 'TreeSet', 'HashSet', 'List', 'Map', 'Set', 'Iterator', 'Collections', 'Objects', 'Arrays', 'Locale', 'AbstractList', 'BufferedInputStream', 'IOException'}:
            raise CompileError([Diagnostic('codegen', 'class-name', 1, 1, f'{class_name!r} conflicts with Java syntax or a runtime type')])
        self.class_name = class_name
        self.imports = set()
        self.helpers = {}
        self.used_inputs = set()
        self.cache = {}
        self.counter = 0
        self.lines = []
        self.indent = 0

    def error(self, expr, message):
        raise CompileError([Diagnostic('codegen', 'unsupported', expr.line, expr.column, message)])

    def line(self, value=''):
        self.lines.append('    ' * self.indent + value if value else '')

    def need(self, feature):
        if feature in self.helpers:
            return
        self.helpers[feature] = ''
        if feature == 'input':
            self.imports.update({'java.io.BufferedInputStream', 'java.io.IOException'})
            self.helpers[feature] = '' # will be populated at the end
        elif feature == 'pair':
            self.imports.update({'java.util.Map', 'java.util.Objects'})
            self.need('compare')
            self.helpers[feature] = runtime.PAIR
        elif feature == 'compare':
            self.imports.update({'java.util.Map', 'java.util.Iterator'})
            self.helpers[feature] = runtime.COMPARE
        elif feature == 'iterator':
            self.imports.update({'java.util.List', 'java.util.function.Supplier'})
            self.helpers[feature] = runtime.ITERATOR
        elif feature == 'range':
            self.need('iterator')
            self.imports.update({'java.util.Iterator', 'java.util.NoSuchElementException'})
            self.helpers[feature] = runtime.RANGE
        elif feature == 'format':
            self.imports.add('java.util.Locale')
            self.helpers[feature] = runtime.FORMAT
        elif feature == 'discard':
            self.helpers[feature] = 'private static void __cppDiscard(Object value) {\n}'
        elif feature == 'sequence':
            self.helpers[feature] = 'private static <T> T __cppSequence(Object ignored, T value) {\n    return value;\n}'
        elif feature == 'string_write':
            self.helpers[feature] = 'private static String __cppSetChar(String text, int index, char value) {\n    StringBuilder result = new StringBuilder(text);\n    result.setCharAt(index, value);\n    return result.toString();\n}'
        elif feature == 'condition':
            self.helpers[feature] = 'private static boolean __cppCondition(boolean value) {\n    return value;\n}'

    def use_type(self, typ):
        cls = {'vector': 'ArrayList', 'map': 'TreeMap', 'unordered_map': 'HashMap', 'set': 'TreeSet', 'unordered_set': 'HashSet'}.get(typ.name)
        if cls:
            self.imports.add('java.util.' + cls)
        if typ.name in {'pair', 'iterator'}:
            self.need(typ.name)
        for arg in typ.args:
            self.use_type(arg)
        return typ.java

    def helper_name(self, key, prefix):
        if key in self.cache:
            return self.cache[key], False
        name = f'__cpp{prefix}{len(self.cache)}'
        self.cache[key] = name
        return name, True

    def generate(self, program):
        self.line(f'public class {self.class_name} {{')
        self.indent += 1
        for var in program.globals:
            self.declaration(var, global_=True)
        if program.globals:
            self.line()
        self.line('public static void main(String[] args) {')
        self.indent += 1
        entry_func = next((f for f in program.functions if f.name == program.entry), None)
        if entry_func and not self.has_operation(entry_func.body, 'select'):
            self.is_main = True
            self.block_contents(entry_func.body)
            self.is_main = False
        else:
            self.line(f'int exitCode = {program.entry}();')
            self.line('if (exitCode != 0) {')
            self.indent += 1
            self.line('System.exit(exitCode);')
            self.indent -= 1
            self.line('}')
        self.indent -= 1
        self.line('}')
        for function in program.functions:
            if function.name == program.entry and entry_func and not self.has_operation(entry_func.body, 'select'):
                continue # Inlined
            self.line()
            if self.has_operation(function.body, 'select'):
                self.line('@SuppressWarnings("fallthrough")')
            parameters = ', '.join(f'{self.use_type(p["type"])} {p["name"]}' for p in function.parameters)
            self.line(f'private static {self.use_type(function.return_type)} {function.name}({parameters}) {{')
            self.indent += 1
            self.block_contents(function.body)
            self.indent -= 1
            self.line('}')
        if 'input' in self.helpers:
            methods = []
            if 'readChar' in self.used_inputs: methods.append(runtime.INPUT_CHAR)
            if 'readInt' in self.used_inputs or 'readBool' in self.used_inputs: methods.append(runtime.INPUT_INT)
            if 'readLong' in self.used_inputs: methods.append(runtime.INPUT_LONG)
            if 'readUnsigned' in self.used_inputs: methods.append(runtime.INPUT_UNSIGNED)
            if 'readFloat' in self.used_inputs: methods.append(runtime.INPUT_FLOAT)
            if 'readDouble' in self.used_inputs: methods.append(runtime.INPUT_DOUBLE)
            if 'readBool' in self.used_inputs: methods.append(runtime.INPUT_BOOL)
            self.helpers['input'] = runtime.INPUT_BASE + '\n' + '\n'.join(methods) + '\n}'
        for helper in self.helpers.values():
            if helper:
                self.line()
                for line in helper.splitlines():
                    self.line(line)
        self.indent -= 1
        self.line('}')
        imports = ''.join(f'import {name};\n' for name in sorted(self.imports))
        return imports + ('\n' if imports else '') + '\n'.join(self.lines) + '\n'

    @classmethod
    def has_operation(cls, value, operation):
        if hasattr(value, 'op') and value.op == operation:
            return True
        if hasattr(value, 'data'):
            return cls.has_operation(value.data, operation)
        if isinstance(value, dict):
            return any(cls.has_operation(v, operation) for v in value.values())
        if isinstance(value, list):
            return any(cls.has_operation(v, operation) for v in value)
        return False

    @classmethod
    def is_side_effect_free(cls, value):
        if not hasattr(value, 'op'):
            return True
        if value.op in {'literal', 'load', 'default'}:
            return True
        if value.op in {'convert', 'copy'}:
            return cls.is_side_effect_free(value.args[0])
        return False

    def default(self, typ):
        self.use_type(typ)
        if typ.name == 'pair':
            return f'new CppPair<>({self.default(typ.args[0])}, {self.default(typ.args[1])})'
        if typ.container and typ.name != 'array':
            if typ.name in {'map', 'set'} and typ.args[0].container:
                self.need('compare')
                return 'new ' + typ.java.split('<')[0] + f'<>({self.class_name}::__cppCompare)'
            return 'new ' + typ.java.split('<')[0] + '<>()'
        if typ.name == 'array':
            return 'null'
        return {'int': '0', 'long long': '0L', 'float': '0.0f', 'double': '0.0', 'bool': 'false', 'char': "'\\0'", 'string': '""'}.get(typ.name, 'null')

    def conversion(self, text, source, target):
        if source == target:
            return text
        if target == BOOL:
            return f'({text} != 0)'
        if source == SIZE and target in {FLOAT, DOUBLE}:
            name, fresh = self.helper_name(('unsigned_float', target), 'UnsignedFloat')
            if fresh:
                self.helpers[name] = f'private static {target.java} {name}(long value) {{\n    return ({target.java}) (value >= 0 ? (double) value : (double) (value & Long.MAX_VALUE) + 0x1.0p63);\n}}'
            return f'{name}({text})'
        if source.java == target.java:
            return text
        if source == BOOL:
            text = f'({text} ? 1 : 0)'
            source = INT
            if target == INT:
                return text
        return f'(({self.use_type(target)}) {text})'

    def copy(self, text, typ):
        if typ.name == 'iterator':
            return f'{text}.copy()'
        if not typ.value_object:
            return text
        name, fresh = self.helper_name(('copy', typ), 'Copy')
        if fresh:
            java = self.use_type(typ)
            lines = [f'private static {java} {name}({java} source) {{']
            if typ.name == 'pair':
                first = self.copy('source.getFirst()', typ.args[0])
                second = self.copy('source.getSecond()', typ.args[1])
                lines.append(f'    return new CppPair<>({first}, {second});')
            elif typ.name == 'array':
                self.error(E('copy', typ), 'array copying is not a C++ value operation')
            else:
                lines.append(f'    {java} result = {self.default(typ)};')
                if typ.name in {'map', 'unordered_map'}:
                    self.imports.add('java.util.Map')
                    key, value = typ.args
                    lines.append(f'    for (Map.Entry<{key.boxed}, {value.boxed}> entry : source.entrySet()) {{')
                    lines.append(f'        result.put({self.copy("entry.getKey()", key)}, {self.copy("entry.getValue()", value)});')
                else:
                    element = typ.args[0]
                    lines.append(f'    for ({element.java} value : source) {{')
                    lines.append(f'        result.add({self.copy("value", element)});')
                lines.extend(['    }', '    return result;'])
            lines.append('}')
            self.helpers[name] = '\n'.join(lines)
        return f'{name}({text})'

    def initializer(self, expr):
        typ = expr.type
        args = [self.expr(a) for a in expr.args]
        if typ.name == 'pair':
            return 'new CppPair<>(' + ', '.join(args) + ')'
        if typ.name == 'array':
            return f'new {typ.java} {{' + ', '.join(args) + '}'
        if typ.container:
            name, fresh = self.helper_name(('init', typ, len(args)), 'Init')
            if fresh:
                java = self.use_type(typ)
                element = Type('pair', typ.args) if typ.name in {'map', 'unordered_map'} else typ.args[0]
                self.use_type(element)
                params = ', '.join(f'{element.java} value{i}' for i in range(len(args)))
                lines = [f'private static {java} {name}({params}) {{', f'    {java} result = {self.default(typ)};']
                for i in range(len(args)):
                    if typ.name in {'map', 'unordered_map'}:
                        lines.append(f'    result.putIfAbsent(value{i}.getFirst(), value{i}.getSecond());')
                    else:
                        lines.append(f'    result.add(value{i});')
                lines.extend(['    return result;', '}'])
                self.helpers[name] = '\n'.join(lines)
            return name + '(' + ', '.join(args) + ')'
        return args[0] if args else self.default(typ)

    def fill(self, expr):
        typ = expr.type
        size = self.expr(expr.args[0])
        if typ == STRING:
            char = self.expr(expr.args[1])
            return f'String.valueOf({char}).repeat({size})'
        element = typ.args[0]
        value = self.expr(expr.args[1]) if len(expr.args) == 2 else self.default(element)
        name, fresh = self.helper_name(('fill', typ), 'Fill')
        if fresh:
            java = self.use_type(typ)
            copied = self.copy('value', element)
            self.helpers[name] = '\n'.join([f'private static {java} {name}(int size, {element.java} value) {{', f'    {java} result = new ArrayList<>(size);', '    for (int index = 0; index < size; index++) {', f'        result.add({copied});', '    }', '    return result;', '}'])
        return f'{name}({size}, {value})'

    def map_get(self, owner, key, typ):
        name, fresh = self.helper_name(('map_get', typ), 'Get')
        if fresh:
            java = self.use_type(typ)
            k, v = typ.args
            self.helpers[name] = '\n'.join([f'private static {v.java} {name}({java} map, {k.java} key) {{', '    if (!map.containsKey(key)) {', f'        map.put(key, {self.default(v)});', '    }', '    return map.get(key);', '}'])
        return f'{name}({owner}, {key})'

    def iterator(self, owner_expr, mode, key_expr=None):
        typ = owner_expr.type
        self.need('iterator')
        name, fresh = self.helper_name(('iterator', typ), 'Iterator')
        element = Type('pair', typ.args) if typ.name in {'map', 'unordered_map'} else CHAR if typ == STRING else typ.args[0]
        self.use_type(element)
        if fresh:
            java = self.use_type(typ)
            self.imports.add('java.util.ArrayList')
            params = f'{java} source, int mode'
            if typ.name in {'map', 'unordered_map', 'set', 'unordered_set'}:
                params += f', {typ.args[0].boxed} key'
            lines = [f'private static CppIterator<{element.boxed}> {name}({params}) {{']
            if typ.name == 'vector':
                lines.append(f'    List<{element.boxed}> values = source;')
            elif typ.name == 'array' or typ == STRING:
                self.imports.add('java.util.AbstractList')
                length = 'source.length()' if typ == STRING else 'source.length'
                get = 'source.charAt(index)' if typ == STRING else 'source[index]'
                lines.extend([f'    List<{element.boxed}> values = new AbstractList<>() {{', '        @Override', f'        public {element.boxed} get(int index) {{ return {get}; }}', '        @Override', f'        public int size() {{ return {length}; }}'])
                if typ.name == 'array':
                    lines.extend(['        @Override', f'        public {element.boxed} set(int index, {element.boxed} value) {{', f'            {element.java} old = source[index];', '            source[index] = value;', '            return old;', '        }'])
                lines.append('    };')
            elif typ.name in {'set', 'unordered_set'}:
                lines.append(f'    List<{element.boxed}> values = new ArrayList<>(source);')
            else:
                k, v = typ.args
                lines.extend([f'    List<{element.boxed}> values = new ArrayList<>();', f'    for ({k.java} currentKey : source.keySet()) {{', '        values.add(new CppPair<>(currentKey, source.get(currentKey), source));', '    }'])
            keyed = typ.name in {'map', 'unordered_map', 'set', 'unordered_set'}
            if keyed:
                snapshot_name = name + 'Values'
                snapshot_lines = [f'private static List<{element.boxed}> {snapshot_name}({java} source) {{', *lines[1:], '    return values;', '}']
                self.helpers[snapshot_name] = '\n'.join(snapshot_lines)
                lines = [lines[0], f'    List<{element.boxed}> values = {snapshot_name}(source);']
            lines.append('    int index = mode == 1 ? values.size() : 0;')
            if typ.name in {'map', 'unordered_map'}:
                self.imports.add('java.util.Objects')
                lines.extend(['    if (mode == 2) {', '        index = 0;', '        while (index < values.size() && !Objects.equals(values.get(index).getFirst(), key)) {', '            index++;', '        }', '    }'])
            elif typ.name in {'set', 'unordered_set'}:
                lines.extend(['    if (mode == 2) {', '        index = values.indexOf(key);', '        if (index < 0) { index = values.size(); }', '    }'])
            supplier = f', () -> {snapshot_name}(source)' if keyed else ''
            lines.extend([f'    return new CppIterator<>(source, values, index{supplier});', '}'])
            self.helpers[name] = '\n'.join(lines)
        args = [self.expr(owner_expr), str(mode)]
        if typ.name in {'map', 'unordered_map', 'set', 'unordered_set'}:
            args.append(self.expr(key_expr) if key_expr else 'null')
        return f'{name}(' + ', '.join(args) + ')'

    def location_parts(self, location):
        op, args, typ = location.op, location.args, location.type
        owner_type = args[0].type
        parameters = [f'{self.use_type(owner_type)} owner']
        arguments = [self.expr(args[0])]
        if op in {'array_at', 'sequence_at', 'map_get_or_insert'}:
            index_type = args[1].type
            parameters.append(f'{self.use_type(index_type)} index')
            arguments.append(self.expr(args[1]))
        if op == 'array_at':
            get, put = 'owner[index]', 'owner[index] = value;'
        elif op == 'sequence_at':
            get, put = 'owner.get(index)', 'owner.set(index, value);'
        elif op == 'map_get_or_insert':
            get, put = self.map_get('owner', 'index', owner_type), 'owner.put(index, value);'
        elif op == 'pair_field':
            field = location.data['field'].capitalize()
            get, put = f'owner.get{field}()', f'owner.set{field}(value);'
        elif op == 'iterator_get':
            get, put = 'owner.get()', 'owner.set(value);'
        else:
            self.error(location, f'cannot render storage operation {op}')
        return parameters, arguments, get, put

    def store(self, location, value, update=None):
        if location.op == 'load':
            target = self.expr(location)
            if update:
                op, post, operation_type = update
                if location.type.name == 'iterator':
                    amount = self.expr(value)
                    return f'{target}.advance({"-" if op == "-" else ""}{amount}, {str(post).lower()})'
                if value.op == 'literal' and value.data['value'] == 1 and op in {'+', '-'} and location.type != BOOL:
                    token = '++' if op == '+' else '--'
                    return f'({target}{token})' if post else f'({token}{target})'
                if self.is_side_effect_free(value) and not (operation_type == SIZE and op in {'/', '%', '>>'}):
                    if location.type == BOOL and op in {'&', '|', '^'}:
                        # Reverse C++ integer promotion for boolean bitwise assignment
                        return f'({target} {op}= {self.expr(value)} != 0)'
                    if location.type != BOOL:
                        return f'({target} {op}= {self.expr(value)})'
                name, fresh = self.helper_name(('compound', location.type, value.type, operation_type, op), 'Compound')
                if fresh:
                    left = self.conversion('old', location.type, operation_type)
                    right_type = promote(value.type) if op in {'<<', '>>'} else operation_type
                    right = self.conversion('right', value.type, right_type) if operation_type.numeric else 'right'
                    computed = self.binary_text(op, left, right, operation_type)
                    converted = self.conversion(computed, operation_type, location.type)
                    self.helpers[name] = f'private static {location.type.java} {name}({value.type.java} right, {location.type.java} old) {{\n    return {converted};\n}}'
                return f'({target} = {name}({self.expr(value)}, {target}))'
            return f'({target} = {self.expr(value)})'
        key = ('mutate', location.op, location.type, tuple(a.type for a in location.args), location.data.get('field'), value.type, update)
        name, fresh = self.helper_name(key, 'Update' if update else 'Store')
        params, args, get, put = self.location_parts(location)
        if fresh:
            java = self.use_type(location.type)
            params.insert(0, f'{self.use_type(value.type)} right')
            lines = [f'private static {java} {name}(' + ', '.join(params) + ') {']
            if update:
                op, post, operation_type = update
                lines.append(f'    {java} old = {get};')
                a = self.conversion('old', location.type, operation_type)
                b = self.conversion('right', value.type, promote(value.type) if op in {'<<', '>>'} else operation_type) if operation_type.numeric else 'right'
                computed = self.conversion(self.binary_text(op, a, b, operation_type), operation_type, location.type)
                lines.append(f'    {java} value = {computed};')
            else:
                lines.append(f'    {java} value = right;')
            lines.extend(['    ' + put, '    return old;' if update and update[1] else '    return value;', '}'])
            self.helpers[name] = '\n'.join(lines)
        # C++17 sequences the right operand of assignment before its left operand.
        return f'{name}(' + ', '.join([self.expr(value), *args]) + ')'

    @staticmethod
    def binary_text(operator, left, right, operand_type):
        if operand_type == SIZE:
            if operator in {'<', '>', '<=', '>='}:
                return f'(Long.compareUnsigned({left}, {right}) {operator} 0)'
            if operator in {'/', '%'}:
                method = 'divideUnsigned' if operator == '/' else 'remainderUnsigned'
                return f'Long.{method}({left}, {right})'
            if operator == '>>':
                operator = '>>>'
        return f'({left} {operator} {right})'

    def expr(self, expr):
        self.use_type(expr.type)
        op, args, data, typ = expr.op, expr.args, expr.data, expr.type
        if op == 'literal':
            value = data['value']
            if typ == BOOL:
                return str(value).lower()
            if typ in {CHAR, STRING}:
                return quote(value, typ == CHAR)
            return repr(value) + ('L' if typ == LONG else 'f' if typ == FLOAT else '')
        if op == 'load':
            return data['name']
        if op == 'default':
            return self.default(typ)
        if op == 'initializer':
            return self.initializer(expr)
        if op == 'construct':
            return self.fill(expr) if data['kind'] == 'fill' else 'new CppPair<>(' + ', '.join(self.expr(a) for a in args) + ')'
        if op == 'convert':
            return self.conversion(self.expr(args[0]), args[0].type, typ)
        if op == 'copy':
            return self.copy(self.expr(args[0]), typ)
        if op in {'array_at', 'sequence_at', 'text_at', 'map_get_or_insert'}:
            owner, index = map(self.expr, args)
            if op == 'map_get_or_insert':
                return self.map_get(owner, index, args[0].type)
            return f'{owner}[{index}]' if op == 'array_at' else f'{owner}.{ "charAt" if op == "text_at" else "get"}({index})'
        if op == 'pair_field':
            return f'{self.expr(args[0])}.get{data["field"].capitalize()}()'
        if op == 'iterator_get':
            return f'{self.expr(args[0])}.get()'
        if op == 'store':
            return self.store(args[0], args[1])
        if op == 'update':
            return self.store(args[0], args[1], (data['operator'], data['postfix'], data['operation_type']))
        if op == 'unary':
            return f'({data["operator"]}{self.expr(args[0])})'
        if op == 'binary':
            a, b = map(self.expr, args)
            operator = data['operator']
            if args[0].type.name == 'iterator':
                return ('!' if operator == '!=' else '') + f'{a}.same({b})'
            if operator in {'==', '!=', '<', '>', '<=', '>='} and not args[0].type.numeric:
                if operator in {'==', '!='}:
                    self.imports.add('java.util.Objects')
                    return ('!' if operator == '!=' else '') + f'Objects.equals({a}, {b})'
                self.need('compare')
                return f'(__cppCompare({a}, {b}) {operator} 0)'
            return self.binary_text(operator, a, b, args[0].type)
        if op == 'choose':
            a, b, c = map(self.expr, args)
            return f'({a} ? {b} : {c})'
        if op == 'sequence':
            if any(a.type == VOID for a in args):
                self.error(expr, 'void comma operands are supported in statements and for updates only')
            self.need('sequence')
            return '__cppSequence(' + ', '.join(self.expr(a) for a in args) + ')'
        if op == 'invoke':
            return data['target'] + '(' + ', '.join(self.expr(a) for a in args) + ')'
        if op == 'read':
            self.need('input')
            method = {'int': 'readInt', 'long long': 'readLong', 'size_t': 'readUnsigned', 'float': 'readFloat', 'double': 'readDouble', 'char': 'readChar', 'bool': 'readBool', 'string': 'next'}[typ.name]
            self.used_inputs.add(method)
            return f'__cppInput.{method}()'
        if op in {'length', 'is_empty'}:
            owner = self.expr(args[0])
            owner_type = args[0].type
            length = f'{owner}.length' if owner_type.name == 'array' else f'{owner}.length()' if owner_type == STRING else f'{owner}.size()'
            return f'({length} == 0)' if op == 'is_empty' else f'((long) {length})'
        if op in {'iterator_begin', 'iterator_end', 'lookup_iterator'}:
            return self.iterator(args[0], {'iterator_begin': 0, 'iterator_end': 1, 'lookup_iterator': 2}[op], args[1] if len(args) > 1 else None)
        if op in {'sequence_append', 'clear'}:
            return self.expr(args[0]) + ('.add(' + self.expr(args[1]) + ')' if op == 'sequence_append' else '.clear()')
        if op == 'sequence_pop':
            name, fresh = self.helper_name(('pop', args[0].type), 'Pop')
            if fresh:
                self.helpers[name] = f'private static void {name}({self.use_type(args[0].type)} values) {{\n    values.remove(values.size() - 1);\n}}'
            return f'{name}({self.expr(args[0])})'
        if op == 'contains_count':
            method = 'containsKey' if args[0].type.name in {'map', 'unordered_map'} else 'contains'
            return f'({self.expr(args[0])}.{method}({self.expr(args[1])}) ? 1 : 0)'
        if op == 'remove_key':
            owner, key = map(self.expr, args)
            if args[0].type.name in {'map', 'unordered_map'}:
                return f'({owner}.remove({key}) != null ? 1 : 0)'
            return f'({owner}.remove({key}) ? 1 : 0)'
        if op == 'set_insert':
            owner_type = args[0].type
            name, fresh = self.helper_name(('insert', owner_type), 'Insert')
            if fresh:
                iterator = self.iterator(E('load', owner_type, data={'name': 'values'}), 2, E('load', owner_type.args[0], data={'name': 'value'}))
                self.helpers[name] = '\n'.join([f'private static {typ.java} {name}({owner_type.java} values, {owner_type.args[0].java} value) {{', '    boolean inserted = values.add(value);', f'    return new CppPair<>({iterator}, inserted);', '}'])
            return name + '(' + ', '.join(self.expr(a) for a in args) + ')'
        if op == 'sort':
            return self.sort(expr)
        self.error(expr, f'unhandled IR operation {op}')

    def sort(self, expr):
        self.imports.add('java.util.Collections')
        self.need('iterator')
        element = expr.data['element_type']
        name, fresh = self.helper_name(('sort', element, expr.data['comparator'], tuple(expr.data['comparator_parameters'])), 'Sort')
        if fresh:
            target = expr.data['comparator']
            if target:
                params = expr.data['comparator_parameters']
                a = self.copy(self.conversion('left', element, params[0]), params[0])
                b = self.copy(self.conversion('right', element, params[1]), params[1])
                reverse_a = self.copy(self.conversion('right', element, params[0]), params[0])
                reverse_b = self.copy(self.conversion('left', element, params[1]), params[1])
                comparator = f'(left, right) -> {target}({a}, {b}) ? -1 : ({target}({reverse_a}, {reverse_b}) ? 1 : 0)'
            else:
                self.need('compare')
                comparator = f'{self.class_name}::__cppCompare'
            java = f'CppIterator<{element.boxed}>'
            self.helpers[name] = '\n'.join([f'private static void {name}({java} first, {java} last) {{', '    if (first.owner != last.owner || first.index > last.index) {', '        throw new IllegalArgumentException("Invalid sort iterator range");', '    }', f'    Collections.sort(first.values.subList(first.index, last.index), {comparator});', '}'])
        return name + '(' + ', '.join(self.expr(a) for a in expr.args) + ')'

    def declaration(self, stmt, global_=False):
        d = stmt.data
        typ, init = d['type'], d['initializer']
        java = self.use_type(typ)
        if typ.name == 'array':
            dimensions = d['dimensions']
            base = typ
            while base.name == 'array':
                base = base.args[0]
            if init.op == 'default':
                value = self.new_array(typ, [self.expr(size) for size in dimensions])
            else:
                value = self.array_initializer(init, dimensions)
        else:
            value = self.expr(init)
        prefix = 'private static ' if global_ else ''
        if d['constant']:
            prefix += 'final '
        self.line(f'{prefix}{java} {d["name"]} = {value};')

    def new_array(self, typ, dimensions):
        base = typ
        while base.name == 'array':
            base = base.args[0]
        if base != STRING:
            return f'new {base.java}' + ''.join(f'[{size}]' for size in dimensions)
        name, fresh = self.helper_name(('string_array', typ), 'Strings')
        if fresh:
            self.imports.add('java.util.Arrays')
            params = ', '.join(f'int size{i}' for i in range(len(dimensions)))
            lines = [f'private static {typ.java} {name}({params}) {{', f'    {typ.java} result = new String' + ''.join(f'[size{i}]' for i in range(len(dimensions))) + ';']
            for i in range(len(dimensions) - 1):
                lines.append('    ' * (i + 1) + f'for (int i{i} = 0; i{i} < size{i}; i{i}++) {{')
            row = 'result' + ''.join(f'[i{i}]' for i in range(len(dimensions) - 1))
            lines.append('    ' * len(dimensions) + f'Arrays.fill({row}, "");')
            for i in reversed(range(len(dimensions) - 1)):
                lines.append('    ' * (i + 1) + '}')
            lines.extend(['    return result;', '}'])
            self.helpers[name] = '\n'.join(lines)
        return name + '(' + ', '.join(dimensions) + ')'

    def array_initializer(self, expr, dims):
        # Allocate zero-filled storage and assign only explicit elements. Never
        # expand a large fixed extent into Java bytecode full of literal zeros.
        name, fresh = self.helper_name(('array_init', expr.type, len(expr.args), len(dims)), 'Array')
        if fresh:
            typ = expr.type
            parameters = [f'int size{i}' for i in range(len(dims))] + [f'{a.type.java} value{i}' for i, a in enumerate(expr.args)]
            allocated = self.new_array(typ, [f'size{i}' for i in range(len(dims))])
            lines = [f'private static {typ.java} {name}(' + ', '.join(parameters) + ') {', f'    {typ.java} result = {allocated};']
            lines.extend(f'    result[{i}] = value{i};' for i in range(len(expr.args)))
            lines.extend(['    return result;', '}'])
            self.helpers[name] = '\n'.join(lines)
        return name + '(' + ', '.join([*(self.expr(d) for d in dims), *(self.array_initializer(a, dims[1:]) if len(dims) > 1 else self.expr(a) for a in expr.args)]) + ')'

    def loop_condition(self, data):
        if data.get('constant_truth') is True:
            return 'true'
        text = self.expr(data['condition'])
        if data.get('constant_truth') is False:
            self.need('condition')
            return f'__cppCondition({text})'
        return text

    def statement_expression(self, expr):
        text = self.expr(expr)
        if expr.op in {'store', 'update'}:
            return text[1:-1] if text.startswith('(') and text.endswith(')') else text
        if expr.op in {'invoke', 'sort', 'sequence_append', 'sequence_pop', 'clear', 'set_insert'}:
            return text
        self.need('discard')
        return f'__cppDiscard({text})'

    def update_expressions(self, expr):
        if expr.op == 'sequence':
            return self.update_expressions(expr.args[0]) + self.update_expressions(expr.args[1])
        return [self.statement_expression(expr)]

    def block_contents(self, stmt):
        if stmt.op in {'block', 'declarations'}:
            for child in stmt.data['statements']:
                self.statement(child)
        else:
            self.statement(stmt)

    def braced(self, prefix, body):
        self.line(prefix + ' {' if prefix else '{')
        self.indent += 1
        self.block_contents(body)
        self.indent -= 1
        self.line('}')

    def statement(self, stmt):
        op, d = stmt.op, stmt.data
        if op == 'declare':
            self.declaration(stmt)
        elif op == 'declarations':
            self.block_contents(stmt)
        elif op == 'block':
            self.braced('', stmt)
        elif op == 'empty':
            self.line(';')
        elif op == 'evaluate':
            for expression in self.update_expressions(d['value']):
                self.line(expression + ';')
        elif op == 'output':
            for expr in d['values']:
                if expr.op == 'newline':
                    self.line('System.out.println();')
                else:
                    value = self.expr(expr)
                    if expr.type == BOOL:
                        value = f'({value} ? 1 : 0)'
                    elif expr.type == SIZE:
                        value = f'Long.toUnsignedString({value})'
                    elif expr.type in {FLOAT, DOUBLE}:
                        self.need('format')
                        value = f'__cppFormat({value})'
                    self.line(f'System.out.print({value});')
        elif op == 'input':
            for location in d['values']:
                if location.op == 'text_at':
                    self.error(location, 'cin into a string character is unsupported; read a char temporary', )
                value = E('read', location.type)
                store = E('store', location.type, [location, value])
                self.line(self.statement_expression(store) + ';')
        elif op == 'string_write':
            self.need('string_write')
            target = self.expr(d['target'])
            self.line(f'{target} = __cppSetChar({target}, {self.expr(d["index"])}, {self.expr(d["value"])});')
        elif op == 'branch':
            self.braced(f'if ({self.expr(d["condition"])})', d['then'])
            if d['else']:
                self.braced('else', d['else'])
        elif op == 'loop':
            init_str = ''
            inline_init = False
            if d['initializer']:
                if d['initializer'].op == 'declarations' and len(d['initializer'].data['statements']) == 1:
                    stmt = d['initializer'].data['statements'][0]
                    if stmt.op == 'declare' and not stmt.data['dimensions']:
                        inline_init = True
                        decl = stmt.data
                        init_str = f'{self.use_type(decl["type"])} {decl["name"]}'
                        if decl['initializer']:
                            init_str += f' = {self.expr(decl["initializer"])}'
            
            if not inline_init:
                self.line('{')
                self.indent += 1
                if d['initializer']:
                    self.statement(d['initializer'])
            
            update = ', '.join(self.update_expressions(d['update'])) if d['update'] else ''
            loop_decl = f'{init_str}; ' if inline_init else '; '
            self.braced(f'for ({loop_decl}{self.loop_condition(d)}; {update})', d['body'])
            
            if not inline_init:
                self.indent -= 1
                self.line('}')
        elif op == 'block':
            for s in d['statements']:
                self.statement(s)
        elif op == 'foreach':
            owner_type = d['iterable'].type
            iterable = self.expr(d['iterable'])
            if owner_type.name in {'map', 'unordered_map', 'set', 'unordered_set'}:
                self.need('range')
                name, fresh = self.helper_name(('range_owner', owner_type), 'Range')
                if fresh:
                    owner = E('load', owner_type, data={'name': 'source'})
                    first, last = self.iterator(owner, 0), self.iterator(owner, 1)
                    element = d['element_type']
                    self.helpers[name] = f'private static Iterable<{element.boxed}> {name}({owner_type.java} source) {{\n    return __cppRange({first}, {last});\n}}'
                iterable = f'{name}({iterable})'
            elif owner_type == STRING:
                iterable += '.toCharArray()'
            self.counter += 1
            temp = f'__cppItem{self.counter}'
            element, target = d['element_type'], d['type']
            self.line(f'for ({self.use_type(element)} {temp} : {iterable}) {{')
            self.indent += 1
            value = self.copy(self.conversion(temp, element, target), target)
            self.line(f'{self.use_type(target)} {d["name"]} = {value};')
            self.block_contents(d['body'])
            self.indent -= 1
            self.line('}')
        elif op == 'while':
            self.braced(f'while ({self.loop_condition(d)})', d['body'])
        elif op == 'do':
            self.braced('do', d['body'])
            self.lines[-1] += f' while ({self.expr(d["condition"])});'
        elif op == 'select':
            value = self.expr(d['value'])
            if d['value'].type == LONG:
                self.counter += 1
                temp = f'__cppSwitch{self.counter}'
                self.line('{')
                self.indent += 1
                self.line(f'long {temp} = {value};')
                choices = [(c['value'], i) for i, c in enumerate(d['cases']) if c['value'] is not None]
                value = ''.join(f'{temp} == {v}L ? {i} : ' for v, i in choices) + '-1'
            else:
                value = self.conversion(value, d['value'].type, INT)
            self.line(f'switch ({value}) {{')
            self.indent += 1
            for i, case in enumerate(d['cases']):
                label = i if d['value'].type == LONG else case['value']
                self.line('default:' if case['value'] is None else f'case {label}:')
                self.indent += 1
                self.block_contents(case['body'])
                self.indent -= 1
            self.indent -= 1
            self.line('}')
            if d['value'].type == LONG:
                self.indent -= 1
                self.line('}')
        elif op in {'break', 'continue'}:
            self.line(op + ';')
        elif op == 'return':
            if getattr(self, 'is_main', False):
                if d['value']:
                    val = self.expr(d['value'])
                    if val != '0':
                        self.line(f'if ({val} != 0) System.exit({val});')
                self.line('return;')
            elif d['value'] and d['value'].type == VOID:
                self.line(self.statement_expression(d['value']) + ';')
                self.line('return;')
            else:
                self.line('return' + (' ' + self.expr(d['value']) if d['value'] else '') + ';')
        else:
            raise CompileError([Diagnostic('codegen', 'internal', 1, 1, f'unhandled IR statement {op}')])
