#include <iostream>
#include <vector>
using namespace std;
int main() {
    vector<int> values={2,4,6};
    for(auto it=values.begin();it!=values.end();it++) { *it+=1; cout<<*it<<' '; }
    auto a=values.begin(); auto b=a; ++b;
    cout<<endl<<*a<<' '<<*b<<' '<<(a==b)<<endl;
}
