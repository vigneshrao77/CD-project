#include <iostream>
using namespace std;
int main() {
    int a=5,b=3,c=2;
    cout<<a+b*c<<' '<<a-b-c<<' '<<((a<b)||(b>=c&&a!=0))<<endl;
    cout<<(a&b)<<' '<<(a|b)<<' '<<(a^b)<<' '<<~a<<' '<<(a<<2)<<' '<<(32>>2)<<endl;
    a+=4; a-=1; a*=3; a/=2; a%=7; a<<=2; a>>=1; a|=8; a&=15; a^=3;
    cout<<a<<' '<<-7/3<<' '<<-7%3<<' '<<+c<<' '<<!0<<endl;
    a=b=c=9; cout<<a<<' '<<b<<' '<<c<<endl;
}
