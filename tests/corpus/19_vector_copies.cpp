#include <iostream>
#include <vector>
using namespace std;
vector<int> changed(vector<int> values) { values[0]=99; values.push_back(5); return values; }
int main() {
    vector<int> original={1,2}; vector<int> copy=original; copy[0]=8;
    auto result=changed(original);
    vector<vector<int>> rows(2,original); rows[0][0]=7;
    auto other=rows; other[1][1]=6;
    for(auto row:rows) { row[0]=50; }
    cout<<original[0]<<' '<<copy[0]<<' '<<result[0]<<' '<<result.size()<<' '<<rows[1][0]<<' '<<rows[1][1]<<' '<<other[1][1]<<endl;
}
