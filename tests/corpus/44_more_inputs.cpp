#include <iostream>
#include <vector>
using namespace std;
int main(){int n;cin>>n;vector<long long>v(n,0);for(int i=0;i<n;i++)cin>>v[i];long long total=0;for(auto x:v)total+=x;cout<<total<<' '<<v.empty()<<endl;}
