#include <iostream>
#include <map>
#include <string>
using namespace std;
int main() {
    map<string,int> m={{"z",9},{"a",1},{"k",4}};
    auto found=m.find("k");
    if(found!=m.end())found->second+=6;
    for(auto it=m.begin();it!=m.end();++it)cout<<it->first<<':'<<it->second<<' ';
    cout<<endl<<m["k"]<<endl;
}
