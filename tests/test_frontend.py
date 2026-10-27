import unittest

from cppjava.lexer import Lexer
from cppjava.preprocess import Preprocessor
from cppjava.parser import Parser
from cppjava.diagnostics import CompileError
from cppjava import ast as A


def parse(source):
    return Parser(Preprocessor().process(Lexer(source).tokenize())).parse()


class LexerTests(unittest.TestCase):
    def test_maximal_munch(self):
        tokens = Lexer('a<b>c; a>>=2; b++ != --c && x::y->z;').tokenize()
        self.assertEqual([t.lexeme for t in tokens], ['a', '<', 'b', '>', 'c', ';', 'a', '>>=', '2', ';', 'b', '++', '!=', '--', 'c', '&&', 'x', '::', 'y', '->', 'z', ';', '<eof>'])

    def test_comments_and_literals(self):
        tokens = Lexer('/* a **/\n"a\\\"//b" \'\\n\' // tail\n42').tokenize()
        self.assertEqual([(t.kind, t.lexeme, t.line, t.column) for t in tokens[:-1]], [('string', '"a\\\"//b"', 2, 1), ('char', "'\\n'", 2, 10), ('integer', '42', 3, 1)])

    def test_aggregate_errors(self):
        with self.assertRaises(CompileError) as error:
            Lexer('@ $').tokenize()
        self.assertEqual(len(error.exception.diagnostics), 2)
        self.assertEqual(error.exception.diagnostics[1].column, 3)

    def test_unterminated_comment(self):
        with self.assertRaisesRegex(CompileError, 'unterminated block comment'):
            Lexer('/* never closed').tokenize()

    def test_invalid_escape(self):
        with self.assertRaisesRegex(CompileError, 'invalid escape'):
            Lexer('"\\q"').tokenize()

    def test_numeric_literals(self):
        self.assertEqual([t.kind for t in Lexer('0xff 0b10 075 10LL .25f 1.5e-2').tokenize()[:-1]], ['integer'] * 4 + ['floating'] * 2)


class PreprocessorTests(unittest.TestCase):
    def test_recursive_macro_rejected(self):
        with self.assertRaisesRegex(CompileError, 'recursive macro'):
            parse('#define A B\n#define B A\nint main(){int x=A;}')

    def test_macros_are_token_aware(self):
        tokens = Preprocessor().process(Lexer('#include <vector>\n#define N (2+3)\nint n=N; string s="N";').tokenize())
        self.assertEqual([t.lexeme for t in tokens], ['int', 'n', '=', '(', '2', '+', '3', ')', ';', 'string', 's', '=', '"N"', ';', '<eof>'])
        self.assertEqual(tokens[3].line, 3)

    def test_function_macro_rejected(self):
        with self.assertRaisesRegex(CompileError, 'function-like macros'):
            parse('#define F(x) x\nint main() {}')

    def test_header_rejected(self):
        with self.assertRaisesRegex(CompileError, 'unsupported include'):
            parse('#include "private.h"\nint main() {}')


class ParserTests(unittest.TestCase):
    def expr(self, source):
        return parse('int main(){' + source + ';}').declarations[0].body.statements[0].expression

    def test_precedence(self):
        expr = self.expr('a+b*c')
        self.assertEqual(expr.op, '+')
        self.assertEqual(expr.right.op, '*')

    def test_associativity(self):
        expr = self.expr('a-b-c')
        self.assertEqual(expr.left.op, '-')
        expr = self.expr('a=b=c')
        self.assertEqual(expr.right.op, '=')

    def test_ternary_and_comma(self):
        expr = self.expr('a?b:c?d:e')
        self.assertIsInstance(expr.when_false, A.ConditionalExpr)
        self.assertEqual(self.expr('a=1,b=2').op, ',')

    def test_nested_template_and_shift(self):
        tree = parse('int main(){vector<vector<int>> v; int a=8>>1;}')
        self.assertEqual(str(tree.declarations[0].body.statements[0].declarations[0].declared_type), 'vector<vector<int>>')
        self.assertEqual(tree.declarations[0].body.statements[1].declarations[0].initializer.op, '>>')

    def test_declarations_calls_and_postfix(self):
        tree = parse('int f(int n=2){return n;} int main(){int a[3]={1,2};vector<int>v(3,0);auto p=make_pair(1,2);v[0]++;int x=(int)f(p.first);}')
        body = tree.declarations[1].body.statements
        self.assertIsInstance(body[0].declarations[0].initializer, A.InitList)
        self.assertIsInstance(body[1].declarations[0].initializer, A.ConstructExpr)
        self.assertTrue(body[3].expression.postfix)
        self.assertIsInstance(body[4].declarations[0].initializer, A.CastExpr)

    def test_control_flow_shapes(self):
        tree = parse('int main(){if(1){} else if(0){} for(int i=0;i<2;i++){} for(auto x:v){} while(1)break; do{}while(0); switch(x){case 1:continue; default:return 0;}}')
        self.assertEqual([type(s).__name__ for s in tree.declarations[0].body.statements], ['IfStmt', 'ForStmt', 'RangeForStmt', 'WhileStmt', 'DoWhileStmt', 'SwitchStmt'])

    def test_expected_diagnostic(self):
        with self.assertRaisesRegex(CompileError, "expected ';', found '}'"):
            parse('int main(){int x=1}')

    def test_unsupported_pointer(self):
        with self.assertRaisesRegex(CompileError, 'pointer/reference'):
            parse('int main(){int *p;}')


if __name__ == '__main__':
    unittest.main()
