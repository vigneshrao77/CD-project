#include <iostream>
#include <unordered_set>
using namespace std;
int main() {
    unordered_set<int> s;
    s.insert(9); s.insert(2); s.insert(9);
    cout<<s.size()<<' '<<(s.find(9)!=s.end())<<' '<<(s.find(5)==s.end())<<endl;
    s.clear(); cout<<s.empty()<<endl;
}
