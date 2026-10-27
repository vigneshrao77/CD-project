import unittest
from tests.test_frontend import parse
from cppjava.semantic import SemanticAnalyzer
from cppjava.lowering import Lowerer
from cppjava.typesys import INT, LONG, SIZE, BOOL, Type
from cppjava.diagnostics import CompileError


def analyze(source):
    return SemanticAnalyzer().analyze(parse(source))


class SemanticTests(unittest.TestCase):
    def test_size_has_unsigned_semantics(self):
        tree = analyze('int main(){vector<int>v;auto n=v.size();bool b=-1<n;}')
        body = tree.declarations[0].body.statements
        self.assertEqual(body[1].declarations[0].declared_type, SIZE)
        self.assertEqual(body[2].declarations[0].initializer.annotations['operand_type'], SIZE)

    def test_missing_return(self):
        with self.assertRaisesRegex(CompileError, 'not all paths'):
            analyze('int f(int n){if(n)return 2;}int main(){}')

    def test_prototype_defaults(self):
        tree = analyze('int f(int n=2);int f(int n){return n;}int main(){cout<<f();}')
        self.assertEqual(len(tree.declarations[-1].body.statements[0].expression.right.annotations['defaults']), 1)

    def test_undeclared(self):
        with self.assertRaisesRegex(CompileError, 'undeclared identifier x'):
            analyze('int main(){cout<<x;}')

    def test_mismatch(self):
        with self.assertRaisesRegex(CompileError, 'cannot convert string to int'):
            analyze('int main(){int x="bad";}')

    def test_redeclaration(self):
        with self.assertRaisesRegex(CompileError, 'redeclaration'):
            analyze('int main(){int x; double x;}')

    def test_shadowing_renames(self):
        tree = analyze('int main(){int x=1; {int x=2; cout<<x;} cout<<x;}')
        statements = tree.declarations[0].body.statements
        self.assertNotEqual(statements[0].declarations[0].java_name, statements[1].statements[0].declarations[0].java_name)

    def test_overloads_and_defaults(self):
        tree = analyze('int f(int x,int y=2){return x+y;} double f(double x){return x;} int main(){cout<<f(1)<<f(2.5);}')
        expr = tree.declarations[-1].body.statements[0].expression
        self.assertNotEqual(expr.right.annotations['resolved_target'], expr.left.right.annotations['resolved_target'])
        self.assertEqual(len(expr.left.right.annotations['defaults']), 1)

    def test_wrong_overload(self):
        with self.assertRaisesRegex(CompileError, 'no matching overload'):
            analyze('int f(int x){return x;} int main(){f("s");}')

    def test_ambiguous_overload(self):
        with self.assertRaisesRegex(CompileError, 'ambiguous overload'):
            analyze('int f(int x,double y){return x;} int f(double x,int y){return y;} int main(){f(1,1);}')

    def test_promotions_and_division(self):
        tree = analyze('int main(){char c=3; long long x=c+2LL; int d=-7/3; bool b=x;}')
        stmts = tree.declarations[0].body.statements
        self.assertEqual(stmts[1].declarations[0].initializer.type, LONG)
        self.assertIn('truncate-toward-zero', stmts[2].declarations[0].initializer.annotations['division'])
        self.assertIn(BOOL, stmts[3].declarations[0].initializer.annotations['conversions'])

    def test_nested_java_types(self):
        typ = Type('vector', (Type('vector', (INT,)),))
        self.assertEqual(typ.java, 'ArrayList<ArrayList<Integer>>')

    def test_const_write(self):
        with self.assertRaisesRegex(CompileError, 'cannot modify const'):
            analyze('int main(){const int n=3;n++;}')

    def test_bad_comparator(self):
        with self.assertRaisesRegex(CompileError, 'comparator must return bool'):
            analyze('int cmp(int a,int b){return a-b;} int main(){vector<int> v;sort(v.begin(),v.end(),cmp);}')

    def test_ir_has_explicit_operations(self):
        tree = analyze('int main(){vector<int> v;v.push_back(3);cout<<v[0]<<endl;}')
        ir = Lowerer().lower(tree)
        statements = ir.functions[0].body.data['statements']
        self.assertEqual(statements[1].data['value'].op, 'sequence_append')
        self.assertEqual(statements[2].op, 'output')
        self.assertEqual(statements[2].data['values'][0].op, 'sequence_at')


if __name__ == '__main__':
    unittest.main()
