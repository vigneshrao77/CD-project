#include <iostream>
#include <vector>
using namespace std;
int main(){vector<int>v={10,20,30};int i=0;v[i++]=i+4;cout<<i<<' '<<v[0]<<endl;i=0;v[i++]+=(i=1);cout<<i<<' '<<v[1]<<endl;}
