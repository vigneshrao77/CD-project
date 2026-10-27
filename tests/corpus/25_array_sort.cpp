#include <iostream>
#include <algorithm>
#include <iterator>
using namespace std;
bool descending(int a,int b){return a>b;}
int main() {
    int values[6]={3,-1,7,3,0,5};
    sort(begin(values),end(values));
    for(auto x:values)cout<<x<<' '; cout<<endl;
    sort(begin(values),end(values),descending);
    for(auto x:values)cout<<x<<' '; cout<<endl;
}
