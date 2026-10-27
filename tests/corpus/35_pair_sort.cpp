#include <iostream>
#include <vector>
#include <utility>
#include <algorithm>
using namespace std;
int main(){vector<pair<int,int>>p={{2,1},{1,5},{1,3}};sort(p.begin(),p.end());for(auto x:p)cout<<x.first<<':'<<x.second<<' ';cout<<endl;}
