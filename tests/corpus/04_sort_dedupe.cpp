#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;
int main() {
    int n; cin >> n;
    vector<int> values;
    for (int i = 0; i < n; i++) { int x; cin >> x; values.push_back(x); }
    sort(values.begin(), values.end());
    vector<int> unique;
    for (auto x : values) {
        if (unique.empty() || unique[unique.size() - 1] != x) unique.push_back(x);
    }
    unique.push_back(999); unique.pop_back();
    for (int x : unique) cout << x << ' ';
    cout << endl;
}
