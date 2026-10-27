#include <iostream>
#include <map>
using namespace std;
int calls=0;
map<int,int> make(){calls++;return map<int,int>{{1,2},{3,4}};}
int main(){for(auto item:make())cout<<item.first<<':'<<item.second<<' ';cout<<calls<<endl;}
