#include <iostream>
#include <string>
using namespace std;
int main() {
    string a="alpha", b="beta"; string empty;
    string c=a+'-'+b; c+='!';
    string repeated(4,'x');
    cout<<c<<' '<<repeated<<' '<<a.size()<<' '<<empty.empty()<<endl;
    cout<<(a<b)<<' '<<(a==string("alpha"))<<' '<<(a!=b)<<endl;
    for(auto ch:a)cout<<ch<<'.'; cout<<endl;
}
