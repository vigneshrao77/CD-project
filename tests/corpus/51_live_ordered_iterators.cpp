#include <iostream>
#include <map>
#include <set>
using namespace std;
int main(){map<int,int>m={{2,20},{4,40}};auto it=m.begin();auto last=m.end();m[1]=10;m[3]=30;cout<<it->first<<' ';m.erase(1);while(it!=last){cout<<it->first<<' ';++it;}cout<<endl;set<int>s={1,3};for(auto x:s){cout<<x<<' ';if(x==1)s.insert(2);}cout<<endl;}
