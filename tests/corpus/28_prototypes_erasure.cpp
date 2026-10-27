#include <iostream>
#include <vector>
using namespace std;
int sum(vector<int> v);
double sum(vector<double> v);
int sum(vector<int> v){int s=0;for(auto x:v)s+=x;return s;}
double sum(vector<double> v){double s=0;for(auto x:v)s+=x;return s;}
int main(){vector<int>a={1,2};vector<double>b={1.25,2.5};cout<<sum(a)<<' '<<sum(b)<<endl;}
