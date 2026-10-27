#include <iostream>
using namespace std;
int scale(int x, int amount=3) { return x*amount; }
double scale(double x) { return x/2; }
long long scale(long long x) { return x+10000000000LL; }
int main() {
    cout<<scale(4)<<' '<<scale(4,2)<<' '<<scale(5.0)<<' '<<scale(7LL)<<endl;
    float x=3.5f; cout<<scale(x)<<endl;
}
