import json
from pathlib import Path
import tempfile
import unittest
from cppjava.codegen import JavaGenerator
from cppjava.ir import IRExpr as E, IRStmt as S, IRProgram, IRFunction
from cppjava.typesys import INT, BOOL, STRING, VOID, Type
from cppjava.compiler import compile_source
from cppjava.cli import main
from cppjava.diagnostics import CompileError


class CodegenTests(unittest.TestCase):
    def test_vector_ir_golden(self):
        vector = Type('vector', (INT,))
        owner = E('load', vector, data={'name': 'values'})
        zero = E('literal', INT, data={'value': 0})
        body = S('block', {'statements': [
            S('declare', {'name': 'values', 'type': vector, 'constant': False, 'initializer': E('default', vector), 'dimensions': []}),
            S('evaluate', {'value': E('sequence_append', VOID, [owner, E('literal', INT, data={'value': 3})])}),
            S('output', {'values': [E('sequence_at', INT, [owner, zero]), E('newline', Type('endl'))]}),
            S('return', {'value': zero}),
        ]})
        expected = (Path(__file__).parent / 'golden' / 'vector.java.golden').read_text(encoding='utf-8')
        self.assertEqual(JavaGenerator().generate(IRProgram([], [IRFunction('entry', INT, [], body)], 'entry')), expected)

    def test_fixed_ir_golden(self):
        count = E('load', INT, data={'name': 'count'})
        zero = E('literal', INT, data={'value': 0})
        body = S('block', {'statements': [
            S('declare', {'name': 'count', 'type': INT, 'constant': False, 'initializer': E('literal', INT, data={'value': 3}), 'dimensions': []}),
            S('branch', {'condition': E('binary', BOOL, [count, zero], {'operator': '>'}), 'then': S('output', {'values': [count, E('newline', Type('endl'))]}), 'else': S('output', {'values': [E('literal', STRING, data={'value': 'empty'})]})}),
            S('return', {'value': zero}),
        ]})
        ir = IRProgram([], [IRFunction('entry', INT, [], body)], 'entry')
        expected = (Path(__file__).parent / 'golden' / 'basic.java.golden').read_text(encoding='utf-8')
        self.assertEqual(JavaGenerator().generate(ir), expected)

    def test_imports_are_demand_driven(self):
        self.assertNotIn('import ', compile_source('int main(){return 0;}').java)
        java = compile_source('int main(){vector<int> v;v.push_back(2);cout<<v[0];}').java
        self.assertIn('import java.util.ArrayList;', java)
        self.assertNotIn('import java.util.Map;', java)
        self.assertNotIn('import java.util.*;', java)

    def test_all_phase_dumps_serializable(self):
        compilation = compile_source('int f(int n=2){return n;} int main(){cout<<f();}')
        for phase in ('tokens', 'preprocessed_tokens', 'ast', 'annotated_ast', 'ir'):
            dumped = json.dumps(compilation.dump(phase))
            self.assertTrue(dumped)
        self.assertNotIn('annotations', json.dumps(compilation.ast))
        self.assertIn('resolved_target', json.dumps(compilation.dump('annotated_ast')))

    def test_class_name_validation(self):
        for name in ('wrong-name', 'public', 'String', '123'):
            with self.subTest(name=name), self.assertRaises(CompileError):
                compile_source('int main(){}', name)

    def test_resource_limit_is_structured(self):
        with self.assertRaises(CompileError) as raised:
            compile_source('int main(){int x=' + '(' * 2000 + '1' + ')' * 2000 + ';}')
        self.assertEqual(raised.exception.diagnostics[0].code, 'resource-limit')

    def test_nonfinite_literal_rejected(self):
        with self.assertRaisesRegex(CompileError, 'representable range'):
            compile_source('int main(){double x=1e999;}')

    def test_cli_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source, output, dumps = folder/'source.cpp', folder/'Example.java', folder/'dumps'
            source.write_text('int main(){cout<<42;}', encoding='utf-8')
            self.assertEqual(main([str(source), '-o', str(output), '--dump-dir', str(dumps)]), 0)
            self.assertIn('public class Example', output.read_text())
            self.assertEqual(len(list(dumps.glob('*.json'))), 5)
