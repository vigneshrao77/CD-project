# Build report

All seven compiler phases are implemented as separate inspectable components.
Source, grammar, unit/golden/negative tests, the differential harness, a 52-program
corpus, run instructions, and precise scope decisions are included in the repository.

## Verified exit criteria

| Check | Result |
|---|---:|
| Unit, semantic, parser, lexer, preprocessor, IR, codegen, and CLI test methods | **43 / 43 — 100%** |
| Dedicated unsupported-input fixtures, exercised as subtests | **12 / 12 — 100%** |
| C++ programs compiled with GCC 13.3.0 | **52 / 52 — 100%** |
| Generated Java files compiled with JDK 21.0.12, `-Xlint:all -Werror` | **52 / 52 — 100%** |
| C++/Java output and exit-status comparisons, including multiple input files | **54 / 54 — 100%** |

Run `python scripts/test_all.py` to reproduce the complete suite. The full machine
report is retained in `.build/e2e/report.json`, with a portable recorded copy in
[verification.json](verification.json). Original executables, generated Java,
class files and stdout captures remain under `.build/e2e/<program>/`.

Comparison normalizes **only CRLF to LF** for Windows text-mode compatibility.
There is no floating-point tolerance, space trimming, element reordering, skipped
test, or weakened input. Both compiler exit statuses and process outputs are
checked. Golden snapshots are fixed expectations; the test runner never rewrites
them. Dedicated cases cover classic array sums, reverse string, sort/dedupe, map
word counts, custom pair comparators, recursion, overloads/defaults, nested
containers, copies, unsigned sizes, iterator mutation rules, and C++17 sequencing.

## Hardest issues by phase

| Phase | Issue and resolution |
|---|---|
| Lexer | Escaped quotes must stay inside literals while comment delimiters outside them affect scanning. Dedicated states and maximal munch preserve that boundary. The first scanner-test failure was an incorrectly hand-counted expected character column (11 rather than 10); counting the unchanged input confirmed the scanner and corrected the fixture. Independent bad characters are aggregated. |
| Preprocessor | Expanding text indiscriminately would alter string contents and lose source positions. Token-aware object expansion preserves replacement boundaries, recursively expands names, detects cycles, and relocates expanded tokens to the invocation. No separate failing implementation defect surfaced in the initial preprocessing tests; malformed directives, function macros and unknown includes are explicitly covered. |
| Parser | Nested `vector<vector<int>>` closers must coexist with right-shift expressions and right-associative assignment. The type parser alone splits template closers; the precedence table handles expressions. Inspection also found that a decimal exponent could become Python infinity and then invalid Java; out-of-range floating literals now produce a located parser diagnostic. |
| Semantic analysis | Modeling `.size()` as signed int gives wrong negative comparisons and unsigned wraparound. It is now an internal unsigned 64-bit type with explicit conversion/operator annotations. Overloads resolve before code generation, generic erasure gets unique targets, and iterator origin information enforces map-key/set-element constness. |
| IR / transformations | Value semantics and sequencing must survive mutable Java collections. Recursive copies are explicit at C++ value boundaries, mutable map keys are copied, and storage helpers evaluate assignment RHS before reading/addressing the destination. A returned associative range must be evaluated once; a dedicated range helper now receives that owner once. Regression cases verify both behaviors. |
| Java generation | A 100,000-element partial array initializer exceeded Java method/constant-pool limits when implicit zeros were emitted individually. Allocation plus explicit-element writes fixes the actual failing test. String arrays receive empty-string defaults. Completion analysis removes checked-but-unreachable C++ tails and handles Java's rejection of constant-false while bodies. Intended switch fallthrough is explicitly annotated without disabling other lint checks. |
| Diagnostic layer | Deep malformed nesting could otherwise escape as a Python recursion traceback. The driver reports a structured resource-limit error for the active phase. Source errors retain their phase and location; parser/semantic failures stop before cascading noise, while lexical errors are accumulated. |

The differential harness exposed a separate **oracle toolchain** defect: the
installed GCC 6.3 accepted `-std=c++17` but evaluated chained output operands using
older rules. The unchanged map and shadowing tests demonstrated the discrepancy.
A checksum-verified, workspace-local GCC 13.3 toolchain fixed the oracle; GCC's
[C++ support table](https://gcc.gnu.org/projects/cxx-status.html) documents the
relevant support beginning in GCC 7. The modern UCRT also resolved the older
runtime's three-digit scientific exponents. No transpiler semantics were changed
to reproduce obsolete compiler behavior.

## Explicit exclusions and reductions

The mission's exclusions remain enforced: pointers/references, manual allocation,
user templates/classes/inheritance/operator overloads, complex preprocessing,
multi-file input, lambdas, and algorithms beyond `sort`. These are **not** partially
translated. Standard-library iterator dereference is independently typed and does
not enable raw pointers.

Additional v1 boundaries are documented in detail, with reasons, in
[README.md — out of scope and deliberate reductions](../README.md#out-of-scope-and-deliberate-v1-reductions):

- ASCII character/text data; scalar char values remain in the ASCII range.
- Standalone stream chains; extraction conditions and advanced stream state or
  formatting controls are excluded.
- Scalar/string fixed arrays with explicitly nested multidimensional braces;
  STL-object arrays and array-parameter pointer decay are excluded.
- String character writes are standalone simple assignments to a named string;
  iterator traversal of strings assumes the string is unchanged.
- Basic typed STL cursors; full-range sort with direct begin/end endpoints;
  pointer/iterator arithmetic and a complete iterator-category system are excluded.
- Typed function arguments, without untyped braced overload ranking or
  cross-instantiation converting pair constructors; void comma operands only in
  expression statements and for updates.
- Source types are exactly the listed grammar. Other numeric declaration forms,
  named casts and hex floating literals are excluded. Internal unsigned `size_t`
  is supported through `.size()` and `auto`.

There are practical limits: the target assumes 32-bit int, 64-bit long long and
64-bit size_t; Java's array indexing bounds apply; associative cursor refresh
can be O(n); unordered iteration order and comparator-equivalent element order
are not cross-library output guarantees. Programs must have defined C++ behavior
and valid, sufficient ASCII input. Floating text matches every corpus case;
arbitrary platform-specific halfway formatting is not promised. These boundaries
do not remove any failing corpus input and are not claims of full C++ conformance.
