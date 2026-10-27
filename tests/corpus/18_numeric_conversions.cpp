#include <iostream>
using namespace std;
int main() {
    double d=7.9; int n=d; float f=2.25; bool b=42; char c=65;
    cout<<n<<' '<<f<<' '<<b<<' '<<c<<' '<<(c+true)<<endl;
    int zero=false; bool no=0; long long big=3000000000LL;
    cout<<zero<<' '<<no<<' '<<(big/2)<<' '<<int(d)<<' '<<(double)n/2<<endl;
    c+=2; b+=1; cout<<c<<' '<<b<<endl;
}
