#include <iostream>
#include <vector>
using namespace std;
int main() {
    vector<vector<int>> grid(3, vector<int>(4, 0));
    for(int i=0;i<3;i++) for(int j=0;j<4;j++) grid[i][j]=i*10+j;
    grid[1][2]+=5; grid[2][1]++;
    for(auto row:grid) { for(auto x:row) cout<<x<<' '; cout<<endl; }
    cout<<grid.size()<<' '<<grid[0].size()<<endl;
}
