#include <iostream>
using namespace std;
void emit(int n){if(n<0)return;cout<<n<<' ';}
void finish(){return emit(9);}
int main(){int a=0,b=0;a=1,b=2;int c=(a+=2,b+=3);emit(a);emit(b);emit(c);finish();cout<<endl;}
