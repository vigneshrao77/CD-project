#include <iostream>
#include <unordered_map>
#include <string>
using namespace std;
int main() {
    unordered_map<string,int> m;
    m["x"]+=3; m["y"]=7; m["x"]*=2;
    cout<<m["x"]<<' '<<m["y"]<<' '<<(m.find("x")!=m.end())<<' '<<(m.find("z")==m.end())<<endl;
    cout<<m.count("y")<<' '<<m.erase("y")<<' '<<m.size()<<endl;
}
