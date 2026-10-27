#include <iostream>
#include <string>
using namespace std;
int main() {
    string text; cin >> text;
    int left = 0, right = text.size() - 1;
    while (left < right) {
        char saved = text[left];
        text[left] = text[right];
        text[right] = saved;
        ++left; --right;
    }
    cout << text << endl;
}
