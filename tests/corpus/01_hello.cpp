#include <iostream>
using namespace std;
// Comments containing "strings" do not become tokens.
int main() {
    cout << "Hello, compiler!\n" << "quote: \" slash: \\" << endl;
    cout << 'A' << '\t' << true << ' ' << false << endl;
    return 0;
}
