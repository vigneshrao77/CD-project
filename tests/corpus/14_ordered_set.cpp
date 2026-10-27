#include <iostream>
#include <set>
using namespace std;
int main() {
    set<int> s={7,1,4,1};
    auto inserted=s.insert(3); auto duplicate=s.insert(4);
    cout<<inserted.second<<' '<<duplicate.second<<' '<<*inserted.first<<endl;
    for(auto x:s) cout<<x<<' ';
    cout<<endl<<(s.find(7)!=s.end())<<' '<<s.count(8)<<' '<<s.erase(1)<<endl;
}
