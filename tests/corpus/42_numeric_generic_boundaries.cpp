#include <iostream>
#include <vector>
#include <map>
using namespace std;
int main(){vector<long long>v;v.push_back(3);v.push_back(4000000000LL);map<long long,float>m;m[2]=3;m[2]+=0.5;vector<char>c={65,66};c[0]+=2;vector<bool>b={true,false};b[1]=7;cout<<v[0]+v[1]<<' '<<m[2]<<' '<<c[0]<<' '<<b[1]<<endl;}
