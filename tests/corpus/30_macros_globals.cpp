#include <bits/stdc++.h>
#define BASE 3
#define COUNT (BASE+2)
using namespace std;
const int N=COUNT;
vector<int> values(N, BASE);
int total(int extra=COUNT){int s=extra;for(auto x:values)s+=x;return s;}
int main(){cout<<total()<<' '<<"COUNT"<<endl;}
