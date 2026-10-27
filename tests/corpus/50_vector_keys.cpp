#include <iostream>
#include <vector>
#include <map>
#include <set>
using namespace std;
int main(){map<vector<int>,int>m;vector<int>k={1,2};m[k]=7;k[0]=3;cout<<m[vector<int>{1,2}]<<' '<<m[k]<<endl;set<vector<int>>s={{2},{1,3},{1}};for(auto row:s){for(auto x:row)cout<<x<<' ';cout<<endl;}}
