#include <iostream>
using namespace std;
int main() {
    int x=0,y=2;
    bool a=false && ++x; bool b=true || ++x;
    int result=y>0 ? ++y : ++x;
    int choose=x ? 10 : y ? 20 : 30;
    cout<<x<<' '<<y<<' '<<a<<' '<<b<<' '<<result<<' '<<choose<<endl;
    for(int i=0,j=4;i<3;i++,j--)cout<<i+j<<' ';
    cout<<endl;
}
