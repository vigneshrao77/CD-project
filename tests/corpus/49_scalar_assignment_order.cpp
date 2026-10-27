#include <iostream>
#include <vector>
using namespace std;
int main(){int x=3;x+=(x=2);cout<<x<<endl;vector<int>v={1};auto n=v.size()-3;n/=2;cout<<n<<' ';n>>=60;cout<<n<<endl;int a=-1;a/=v.size()+2;cout<<a<<endl;}
