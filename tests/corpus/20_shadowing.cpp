#include <iostream>
using namespace std;
int value=10;
int twice(int value) { { int value=3; cout<<value<<' '; } return value*2; }
int main() {
    int native=4; int value=5;
    { int value=7; cout<<value<<' '; }
    for(int value=0;value<2;value++)cout<<value<<' ';
    cout<<value<<' '<<twice(native)<<endl;
}
