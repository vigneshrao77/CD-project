#include <iostream>
#include <utility>
#include <string>
using namespace std;
pair<int,string> change(pair<int,string> p) { p.first+=10; p.second=p.second+"!"; return p; }
int main() {
    pair<int,string> a=make_pair(2,string("hi"));
    pair<int,string> b=a;
    b.first++; b.second="bye";
    auto c=change(a);
    cout<<a.first<<' '<<a.second<<' '<<b.first<<' '<<b.second<<' '<<c.first<<' '<<c.second<<endl;
}
