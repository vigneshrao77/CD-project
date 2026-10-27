#include <iostream>
#include <vector>
using namespace std;
int main(){vector<int>v={1,2,3};int negative=-1;auto n=v.size();cout<<(negative<n)<<' '<<(n>negative)<<' '<<(n-5)<<' '<<((n-5)/2)<<' '<<((n-5)%2)<<' '<<((n-5)>>60)<<endl;int count=n-1;cout<<count<<' '<<(n+2)<<endl;}
