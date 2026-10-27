from pathlib import Path
import unittest
from cppjava.compiler import compile_source
from cppjava.diagnostics import CompileError


class NegativeTests(unittest.TestCase):
    def test_unsupported_corpus(self):
        sources = sorted((Path(__file__).parent / 'negative').glob('*.cpp'))
        self.assertGreaterEqual(len(sources), 10)
        for source in sources:
            with self.subTest(source=source.name):
                with self.assertRaises(CompileError) as raised:
                    compile_source(source.read_text(encoding='utf-8'))
                diagnostic = raised.exception.diagnostics[0]
                self.assertEqual(diagnostic.code, 'unsupported')
                self.assertIn(diagnostic.phase, {'lexer', 'preprocessor', 'parser', 'semantic', 'ir', 'codegen'})
                self.assertGreater(diagnostic.line, 0)
                self.assertGreater(diagnostic.column, 0)
                self.assertNotIn('Traceback', str(raised.exception))

    def test_const_map_key_and_set_element(self):
        for source in ('int main(){map<int,int> m;auto it=m.begin();it->first=3;}', 'int main(){set<int> s;auto it=s.begin();*it=3;}'):
            with self.subTest(source=source):
                with self.assertRaisesRegex(CompileError, 'cannot modify const'):
                    compile_source(source)
