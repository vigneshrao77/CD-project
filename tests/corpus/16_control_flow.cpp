#include <iostream>
using namespace std;
int classify(int n) { if(n<0)return -1; else if(n==0)return 0; else return 1; }
int main() {
    int i=0,total=0;
    do { i++; if(i==2)continue; switch(i) { case 1: total+=10; break; case 3: case 4: total+=i; break; default: total--; } } while(i<6);
    for(int a=0;a<4;a++) { for(int b=0;b<4;b++) { if(b==2)break; total+=a+b; } }
    cout<<total<<' '<<classify(-3)<<' '<<classify(0)<<' '<<classify(5)<<endl;
}
