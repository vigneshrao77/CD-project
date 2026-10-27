#include <iostream>
#include <vector>
#include <utility>
#include <algorithm>
using namespace std;
bool order(pair<int, int> a, pair<int, int> b) {
    if (a.second != b.second) return a.second > b.second;
    return a.first < b.first;
}
int main() {
    vector<pair<int, int>> scores = {{3, 10}, {1, 20}, {2, 20}, {4, 5}, {1, 20}};
    sort(scores.begin(), scores.end(), order);
    for (auto score : scores) cout << score.first << ',' << score.second << ' ';
    cout << endl;
}
