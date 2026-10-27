#include <iostream>
#include <vector>
#include <map>
using namespace std;
vector<int> make(int n){return vector<int>(n,4);}
map<int,int> bump(map<int,int>m){m[1]++;return m;}
int main(){auto v=make(3);map<int,int>m={{1,2}};auto changed=bump(m);cout<<v[2]<<' '<<m[1]<<' '<<changed[1]<<endl;}
