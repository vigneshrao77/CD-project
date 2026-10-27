#include <iostream>
#include <map>
#include <set>
#include <vector>
#include <utility>
using namespace std;
int main(){map<pair<int,int>,vector<int>> m;m[make_pair(1,2)].push_back(3);m[make_pair(1,2)].push_back(4);auto c=m;c[make_pair(1,2)][0]=8;cout<<m[make_pair(1,2)][0]<<' '<<c[make_pair(1,2)][0]<<endl;set<pair<int,int>> s={{2,1},{1,4},{1,2}};for(auto p:s)cout<<p.first<<':'<<p.second<<' ';cout<<endl;}
