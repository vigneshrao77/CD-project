# cppjava

A working, hand-written source-to-source compiler for a defined C++17 subset.
It produces one formatted Java source file with a matching public class name.
The compiler has no dependencies beyond Python's standard library. It does not
use regular-expression translation, a C++ parsing library, an LLM, a parser
generator, or an external transpiler. Native compilers are used **only by tests**.

## Run

Requirements: Python 3.11+, JDK 17+ (`javac` and `java`), and GCC 11+ for
differential testing. Development verification used Python 3.12.10, GCC 13.3.0
(64-bit WinLibs/UCRT), and JDK 21.0.12 on Windows.

From the repository root:

```text
python -m cppjava tests/corpus/06_custom_comparator.cpp -o Main.java
javac Main.java
java Main
```

Choose another class by choosing another output filename:

```text
python -m cppjava program.cpp -o Solution.java --dump-dir .build/dumps --json-errors
```

`--dump-dir` writes `tokens.json`, `preprocessed_tokens.json`, `ast.json`,
`annotated_ast.json`, and `ir.json` after a successful compilation. Each stage
also has a directly callable API for debugging a failed compilation. The plain
AST dump is captured before semantic mutation. Java output is replaced atomically
after successful compilation; a source error does not overwrite an existing file.
`--class-name`, if supplied, must agree with the output filename stem.

The public Python entry point is `cppjava.compiler.compile_source(source,
class_name="Main")`. Its `Compilation` result exposes every intermediate artifact
and the generated Java. Failures raise `CompileError` containing `Diagnostic`
records with `phase`, `code`, `line`, `column`, and `message`. CLI errors go to
stderr and return status 1; successful translation returns status 0.

## Test

```text
python scripts/test_all.py
```

This runs unit, negative, and golden tests, then every C++ corpus program through
`g++ -std=c++17`, the transpiler, `javac -Xlint:all -Werror`, and `java`. Native
processes have timeouts, and failures retain source, class files, executable,
stdout captures, and a JSON report under `.build/e2e/`. No failed program is
skipped, and no golden file is automatically updated.

Individual entry points:

```text
python -m unittest discover -v
python -m tests.e2e
python -m tests.e2e --case custom_comparator --jobs 1
```

The harness compares exit status and stdout. **Only CRLF is normalized to LF**:
MinGW text stdout and Java `println` can introduce Windows line endings, whereas
Java `print("\n")` writes LF. Every other byte must match, including floating-point
text, spaces, and element order. There is no approximate numeric comparison.
Input files with the same program stem provide independently compared runs.

The compiler targets a data model with 32-bit `int`, 64-bit `long long`, and
64-bit `size_t`. A 64-bit GCC oracle is needed for `.size()` signedness tests.
GCC 6.3, present in the original PATH, cannot serve as this project's C++17 oracle:
GCC introduced the relevant stream/assignment evaluation-order rules in GCC 7.
The harness requires GCC 11+ to include subsequent fixes. See
[GCC's C++ standards support](https://gcc.gnu.org/projects/cxx-status.html).

On Windows, an optional pinned portable toolchain can be installed entirely
inside `.build/toolchain`:

```text
python scripts/bootstrap_gcc.py
```

This downloads the 217 MiB GCC 13.3 WinLibs archive, verifies its pinned SHA-256,
checks archive paths, and extracts it without changing system installations or
PATH. The harness automatically uses it. An explicit `CXX` environment variable
takes precedence. The pinned archive and provenance are recorded in
`scripts/bootstrap_gcc.py`; its source is the [WinLibs release site](https://winlibs.com/).

The managed Windows sandbox used during development prevents javac's
`output-file-clash` lint check from inspecting/writing class files. Tests were run
with normal Windows file access, retaining **all** javac lint checks. Running the
commands from an ordinary terminal avoids that environment restriction.

## Pipeline and design

Python was chosen for explicit dataclasses, structural type values, readable
recursive descent, and standard-library testing/process orchestration. No C++
parser or translation dependency is involved. Runtime fragments in `runtime.py`
are helper implementations emitted on demand, not a translation engine.

| Phase | Implementation | Input → output |
|---|---|---|
| Lexing | `cppjava/lexer.py` | Characters → located maximal-munch tokens |
| Preprocessing | `cppjava/preprocess.py` | Raw tokens → standard-header removal and object-macro expansion |
| Parsing | `cppjava/parser.py`, `ast.py` | Tokens → distinct typed node classes |
| Semantics | `cppjava/semantic.py`, `typesys.py`, `controlflow.py` | AST → scoped, typed, conversion-annotated AST with resolved call targets |
| IR and transformation | `cppjava/ir.py`, `lowering.py` | Annotated AST → language-neutral operations, explicit copies, conversions, storage updates and control flow |
| Code generation | `cppjava/codegen.py`, `runtime.py` | Typed IR → Java, required imports and required helper methods |
| Diagnostics | `cppjava/diagnostics.py`, `compiler.py`, `cli.py` | Phase failures → located text/JSON diagnostics |

The grammar in [docs/grammar.ebnf](docs/grammar.ebnf) was written before the
parser. The lexer uses character-state scanning, not regular expressions.
Preprocessing operates on lexical tokens, which correctly preserves macro token
boundaries and leaves string contents untouched. Expansion carries the macro
invocation's source position. Parsing uses precedence climbing with explicit
right associativity for assignment and conditional expressions. Only type-argument
parsing splits a `>>` token; expression parsing retains right shift.

Semantic scopes distinguish redeclarations from shadowing. Java names are made
unique because Java disallows some C++ local shadowing patterns. Overload
resolution uses per-argument conversion ranks and a nondominance comparison,
diagnoses ambiguity, and records the selected function. Default arguments are
typed in declaration scope and inserted at resolved call sites. Distinct Java
names also preserve overloads whose generic parameter types would otherwise
erase to the same Java signature.

The IR exposes operations such as `convert`, `copy`, `map_get_or_insert`,
`sequence_append`, `store`, `update`, `sort`, `foreach`, `input`, and `output`.
It contains no Java source fragments. Nested containers are copied recursively
at C++ value boundaries: assignment, parameter passing, return, range variables,
container insertion and fill construction. Key insertion copies mutable keys.
Assignment helpers evaluate the right operand before the left storage address,
and evaluate indexed storage once, as C++17 requires.

| C++ type/operation | Java representation |
|---|---|
| `int`, `long long`, `double`, `float`, `char`, `bool` | `int`, `long`, `double`, `float`, `char`, `boolean` |
| `string` | `String` |
| `vector<T>` | `ArrayList<BoxedT>` |
| `map<K,V>` | `TreeMap<BoxedK,BoxedV>`; ordered traversal is preserved |
| `unordered_map<K,V>` | `HashMap<BoxedK,BoxedV>` |
| `set<T>`, `unordered_set<T>` | `TreeSet<BoxedT>`, `HashSet<BoxedT>` |
| `pair<A,B>` | Generated mutable `CppPair<BoxedA,BoxedB>` |
| Fixed arrays | Native Java arrays with C++ aggregate zero/string initialization |
| `.size()` | Internal unsigned 64-bit type stored in Java `long`; unsigned compare/divide/remainder/printing are explicit |
| `sort(begin,end,cmp)` | `Collections.sort` on a backed range, with a Java comparator adapter |

`CppPair` was chosen over `SimpleEntry` to preserve mutable `first` and `second`,
lexicographic comparison, recursive copies, and map-entry views with read-only
keys. A comparator's C++ less-than predicate becomes `-1` when `cmp(a,b)` holds,
`1` when `cmp(b,a)` holds, and `0` otherwise; ties are not incorrectly reported
as greater. Comparator functions must obey strict weak ordering, and their call
counts/order are not portable observable behavior across sort implementations.

Range loops emit Java enhanced-for loops. Associative ranges use an adapter that
preserves live ordered map/set cursors across insertion or erasure of **other**
elements. Vector and array iterators use backed storage. Associative iterator
refreshing uses snapshots and can cost O(n) per operation; this v1 favors
correctness over STL iterator performance. Map element updates write through to
the map; const keys and set elements cannot be assigned.

Integer division is explicitly annotated as truncation toward zero for both
C++17 and Java. Boolean numeric promotions, char promotions, narrowing numeric
assignments, float precision boundaries, unsigned size operations, generic
boxing and value copies are explicit transformations. Output prints booleans as
`0`/`1` and formats floating values to C++'s default six significant digits using
the root locale.

## Exact supported surface

- One translation unit; standard includes listed in `preprocess.HEADERS`;
  `using namespace std`, `using std::name`, and explicit `std::` qualification.
  Object-like value macros, nested expansion, comments, adjacent string literals,
  decimal/hex/binary/octal integer literals, digit separators, `LL` and `f`
  suffixes, decimal floating exponents, and ASCII literal escapes.
- The scalar types listed above; const declarations; local/global variables;
  comma-separated declarators; fixed one- or multi-dimensional scalar/string
  arrays with constant extents and nested aggregate initialization, including
  partial initialization and inferred first extents. `auto` from a typed value.
- The listed vector, pair, map and set instantiations, including nested vectors
  and ordered container keys with lexicographic comparison. Default, copy,
  initializer-list, vector count/fill, string count/character, and pair
  two-argument construction; `make_pair`.
- `if`/`else if`/`else`, classic and value range-for, while, do-while, switch with
  fallthrough/default/grouped cases, break, continue, early returns, recursion,
  free functions, prototypes with definitions, overloads and trailing defaults.
- Unary/binary arithmetic, logical, relational, bitwise and shift operators;
  pre/post increment/decrement; all compound assignments; ternary and comma
  expressions; C-style and single-type functional numeric casts. String plus
  string/char concatenation and comparisons. Short circuiting is preserved.
- Standalone chained `cin >>` and `cout <<`, `endl`; whitespace-delimited scalar
  input and character-at-a-time extraction. Input must be valid and sufficient
  for the declared reads.
- Vector `push_back`, `pop_back`, indexing, `size`, `empty`; container `begin`,
  `end`, range traversal; map default-inserting indexing; map/set `find`, `count`,
  key `erase`; set `insert` (including its pair return); container `clear`.
  Pair `first`/`second`; iterator copies, equality/inequality, dereference,
  increments/decrements, and map iterator arrow access.
- Default and free-function-comparator `sort` over an entire vector or fixed
  scalar array. Arrays use `begin(array)` / `end(array)` without pointer syntax.
  String indexing and standalone `named_string[index] = char` writes.

## Out of scope and deliberate v1 reductions

The mission's explicit exclusions remain excluded: **pointers and references;
manual `new`/`delete`; user templates; user classes/inheritance (including
multiple inheritance); user-defined operator overloads; function-like macros,
conditional/token-pasting/stringification preprocessing; multi-file programs;
lambdas; and `<algorithm>` operations other than `sort`.** Array parameters are
rejected because they decay to pointers. Iterator `*`/`->` are typed STL
operations, not raw pointer support.

Additional precise reductions, made explicit rather than implied full C++ support:

| Reduction | Reason and diagnostic behavior |
|---|---|
| Streams are standalone chains; no `while(cin >> x)`, stream flags, manipulators other than `endl`, ties or fast-I/O setup | Correct formatted-stream fail states and arbitrary expression-side extraction require a larger I/O model. Conditions/embedded chains and unknown methods are rejected. |
| Character/text data is ASCII; char arithmetic/storage must remain in the ASCII range | C++ narrow-byte encodings and implementation-defined signed char differ from Java UTF-16. Non-ASCII literals/escapes are rejected. Non-ASCII runtime data is outside the input contract. |
| Fixed arrays contain scalars or strings; multi-dimensional initializers use explicit nested braces | Generic Java arrays and C++ flattened aggregate brace elision require additional rules. STL-object arrays and pointer-decaying uses are rejected. |
| String character assignment is a standalone simple assignment to a named string; no character writes through string iterators | Java String is immutable. Value-producing/compound/indexed-string-location writes are rejected rather than generating incorrect value semantics. String iterator traversal assumes the source string is unchanged. |
| Sort endpoints must directly name full vector/array begin/end ranges; iterator arithmetic, reverse iterators, and named iterator type declarations are excluded | This keeps pointer arithmetic and a complete STL iterator category system outside v1. Unsupported forms produce diagnostics. |
| Braced function arguments need explicit typed construction; cross-instantiation pair conversions are excluded | Overload resolution operates on typed values; untyped brace overload ranking and converting pair constructors are not implemented. Type diagnostics identify these forms. |
| Comma operands that return void are supported in standalone expressions and for updates, not inside value expressions | General statement-to-expression lifting needs a broader IR. Such value expressions produce an unsupported diagnostic. |
| Unsigned declarations, `short`, standalone `long`, `long double`, hex floating literals, named C++ casts and other unlisted declarations are excluded | The source type grammar is closed. Unsigned 64-bit `.size()` results are nevertheless modeled internally and supported through `auto`. |

Programs must have defined behavior: no uninitialized reads, invalid indexes,
empty pops, invalidated iterator use, integer division by zero, signed overflow,
invalid shift counts, or out-of-range floating-to-integral conversion. Allocatable
containers/arrays must fit Java's signed-int indexing limits. The compiler is not
a full C++ undefined-behavior detector. Unordered container iteration order and
ordering among comparator-equivalent values are implementation-dependent; exact
output comparisons must not depend on either. The corpus tests unordered
membership/counts and uses deterministic sort observables. Floating formatting
is verified exactly for the corpus; platform-specific halfway rounding and
nonfinite input formatting are not a general cross-runtime portability promise.

Lexical scanning aggregates independently recoverable errors. Preprocessing,
parsing and semantic checking stop on the first failure to avoid cascades from a
bad type or grammar boundary. Excessive source nesting produces a structured
resource-limit diagnostic. Unreachable statements are still checked semantically
before proven unreachable code is removed for Java's stricter reachability rules.

See [docs/BUILD_REPORT.md](docs/BUILD_REPORT.md) for verification results and the
hardest correctness issue encountered in each phase.
