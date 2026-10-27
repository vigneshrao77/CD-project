#include <iostream>
#include <vector>
#include <map>
using namespace std;
int main(){vector<int>v={3,5};map<int,int>m;int a=v[0]++;int b=++v[1];int c=(m[7]+=4);int d=(v[0]=9);cout<<a<<' '<<b<<' '<<c<<' '<<d<<' '<<v[0]<<' '<<m[7]<<endl;}
