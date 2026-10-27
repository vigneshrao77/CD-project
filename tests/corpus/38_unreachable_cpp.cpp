#include <iostream>
using namespace std;
int value(int n){if(n)return 3;else return 4;cout<<"unreachable";}
int main(){cout<<value(1)<<' '<<value(0)<<endl;return 0;cout<<"unreachable";}
