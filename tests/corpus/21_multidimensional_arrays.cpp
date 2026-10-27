#include <iostream>
using namespace std;
int main() {
    int matrix[2][3]={{1,2},{3}};
    int values[]={8,4,2};
    matrix[1][2]=9;
    for(int i=0;i<2;i++){for(int j=0;j<3;j++)cout<<matrix[i][j]<<' ';cout<<endl;}
    for(auto x:values)cout<<x<<' '; cout<<endl;
}
