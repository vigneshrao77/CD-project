#include <iostream>
#include <map>
#include <string>
using namespace std;
int main() {
    int n; cin >> n;
    map<string, int> frequency;
    for (int i=0; i<n; ++i) { string word; cin >> word; frequency[word]++; }
    for (auto item : frequency) cout << item.first << ':' << item.second << '\n';
    cout << frequency["missing"] << ' ' << frequency.size() << endl;
}
