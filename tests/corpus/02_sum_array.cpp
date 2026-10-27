#include <iostream>
using namespace std;
const int CAPACITY = 10;
int main() {
    int n; cin >> n;
    int arr[CAPACITY] = {0};
    long long total = 0;
    for (int i = 0; i < n; ++i) { cin >> arr[i]; total += arr[i]; }
    cout << total << endl;
}
