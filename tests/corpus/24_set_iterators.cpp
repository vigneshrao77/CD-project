#include <iostream>
#include <set>
using namespace std;
int main() {
    set<int> s={5,2,8};
    for(auto it=s.begin();it!=s.end();++it)cout<<*it<<' ';
    auto found=s.find(5); if(found!=s.end())cout<<*found;
    cout<<endl;
}
