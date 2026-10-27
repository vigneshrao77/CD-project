#include <iostream>
#include <map>
#include <utility>
using namespace std;
int main(){pair<int,int>key={1,2};map<pair<int,int>,int>m;m[key]=7;key.first=5;cout<<m[make_pair(1,2)]<<' '<<m[key]<<' '<<m.size()<<endl;}
