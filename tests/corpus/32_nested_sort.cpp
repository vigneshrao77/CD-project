#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;
int main(){vector<vector<int>> rows={{2,1},{1,9},{1,3},{1}};sort(rows.begin(),rows.end());for(auto row:rows){for(auto n:row)cout<<n<<' ';cout<<endl;}}
