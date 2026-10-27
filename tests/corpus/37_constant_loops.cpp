#include <iostream>
using namespace std;
int answer(){while(true){return 42;}}
int main(){int n=0;while(false){n++;}for(;false;){n++;}do{n++;}while(false);cout<<n<<' '<<answer()<<endl;}
