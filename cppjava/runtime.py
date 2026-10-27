"""Small on-demand Java runtime fragments (never used to parse C++)."""

INPUT_BASE = r'''private static final CppInput __cppInput = new CppInput();

private static final class CppInput {
    private final BufferedInputStream input = new BufferedInputStream(System.in);
    private int pending = -2;

    private int read() {
        if (pending != -2) {
            int value = pending;
            pending = -2;
            return value;
        }
        try {
            return input.read();
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to read standard input", exception);
        }
    }

    private int nonspace() {
        int value;
        do {
            value = read();
        } while (value >= 0 && value <= 32);
        if (value < 0) {
            throw new IllegalStateException("Unexpected end of input");
        }
        return value;
    }

    String next() {
        StringBuilder token = new StringBuilder();
        int value = nonspace();
        while (value > 32) {
            token.append((char) value);
            value = read();
        }
        return token.toString();
    }
'''

INPUT_CHAR = r'''    char readChar() {
        return (char) nonspace();
    }'''

INPUT_INT = r'''    int readInt() { return Integer.parseInt(next()); }'''
INPUT_LONG = r'''    long readLong() { return Long.parseLong(next()); }'''
INPUT_UNSIGNED = r'''    long readUnsigned() { return Long.parseUnsignedLong(next()); }'''
INPUT_FLOAT = r'''    float readFloat() { return Float.parseFloat(next()); }'''
INPUT_DOUBLE = r'''    double readDouble() { return Double.parseDouble(next()); }'''
INPUT_BOOL = r'''    boolean readBool() { return readInt() != 0; }'''


PAIR = r'''private static final class CppPair<A, B> implements Comparable<CppPair<A, B>> {
    private A first;
    private B second;
    private final Map<A, B> backing;

    CppPair(A first, B second) {
        this(first, second, null);
    }

    CppPair(A first, B second, Map<A, B> backing) {
        this.first = first;
        this.second = second;
        this.backing = backing;
    }

    A getFirst() { return first; }
    B getSecond() { return backing == null ? second : backing.get(first); }
    void setFirst(A value) { first = value; }
    void setSecond(B value) {
        second = value;
        if (backing != null) {
            backing.put(first, value);
        }
    }

    @Override
    public int compareTo(CppPair<A, B> other) {
        int firstOrder = __cppCompare(getFirst(), other.getFirst());
        return firstOrder != 0 ? firstOrder : __cppCompare(getSecond(), other.getSecond());
    }

    @Override
    public boolean equals(Object other) {
        if (!(other instanceof CppPair<?, ?>)) {
            return false;
        }
        CppPair<?, ?> pair = (CppPair<?, ?>) other;
        return Objects.equals(getFirst(), pair.getFirst()) && Objects.equals(getSecond(), pair.getSecond());
    }

    @Override
    public int hashCode() {
        return Objects.hash(getFirst(), getSecond());
    }
}'''

COMPARE = r'''@SuppressWarnings("unchecked")
private static int __cppCompare(Object left, Object right) {
    if (left instanceof Map<?, ?> && right instanceof Map<?, ?>) {
        return __cppCompare(((Map<?, ?>) left).entrySet(), ((Map<?, ?>) right).entrySet());
    }
    if (left instanceof Map.Entry<?, ?> && right instanceof Map.Entry<?, ?>) {
        Map.Entry<?, ?> a = (Map.Entry<?, ?>) left;
        Map.Entry<?, ?> b = (Map.Entry<?, ?>) right;
        int keyOrder = __cppCompare(a.getKey(), b.getKey());
        return keyOrder != 0 ? keyOrder : __cppCompare(a.getValue(), b.getValue());
    }
    if (left instanceof Iterable<?> && right instanceof Iterable<?>) {
        Iterator<?> a = ((Iterable<?>) left).iterator();
        Iterator<?> b = ((Iterable<?>) right).iterator();
        while (a.hasNext() && b.hasNext()) {
            int order = __cppCompare(a.next(), b.next());
            if (order != 0) {
                return order;
            }
        }
        return Boolean.compare(a.hasNext(), b.hasNext());
    }
    return ((Comparable<Object>) left).compareTo(right);
}'''

ITERATOR = r'''private static final class CppIterator<T> {
    private final Object owner;
    private List<T> values;
    private int index;
    private final Supplier<List<T>> snapshot;

    CppIterator(Object owner, List<T> values, int index) {
        this(owner, values, index, null);
    }

    CppIterator(Object owner, List<T> values, int index, Supplier<List<T>> snapshot) {
        this.owner = owner;
        this.values = values;
        this.index = index;
        this.snapshot = snapshot;
    }

    private void refresh() {
        if (snapshot == null) {
            return;
        }
        boolean atEnd = index == values.size();
        T anchor = atEnd ? null : values.get(index);
        List<T> updated = snapshot.get();
        index = atEnd ? updated.size() : updated.indexOf(anchor);
        if (index < 0) {
            throw new IllegalStateException("Dereference of an erased C++ iterator");
        }
        values = updated;
    }

    CppIterator<T> copy() { return new CppIterator<>(owner, values, index, snapshot); }
    T get() { refresh(); return values.get(index); }
    void set(T value) { values.set(index, value); }
    boolean same(CppIterator<?> other) {
        refresh();
        other.refresh();
        return owner == other.owner && index == other.index;
    }

    CppIterator<T> advance(int amount, boolean postfix) {
        refresh();
        CppIterator<T> old = copy();
        index += amount;
        return postfix ? old : this;
    }
}'''

RANGE = r'''private static <T> Iterable<T> __cppRange(CppIterator<T> first, CppIterator<T> last) {
    return () -> new Iterator<T>() {
        private final CppIterator<T> current = first.copy();
        private boolean advancePending;

        @Override
        public boolean hasNext() {
            if (advancePending) {
                current.advance(1, false);
                advancePending = false;
            }
            return !current.same(last);
        }

        @Override
        public T next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            T value = current.get();
            advancePending = true;
            return value;
        }
    };
}'''

FORMAT = r'''private static String __cppFormat(double value) {
    if (Double.isNaN(value)) {
        return "nan";
    }
    if (Double.isInfinite(value)) {
        return value < 0 ? "-inf" : "inf";
    }
    String formatted = String.format(Locale.ROOT, "%.6g", value);
    int exponent = formatted.indexOf('e');
    String mantissa = exponent < 0 ? formatted : formatted.substring(0, exponent);
    String suffix = exponent < 0 ? "" : formatted.substring(exponent);
    if (mantissa.indexOf('.') >= 0) {
        while (mantissa.endsWith("0")) {
            mantissa = mantissa.substring(0, mantissa.length() - 1);
        }
        if (mantissa.endsWith(".")) {
            mantissa = mantissa.substring(0, mantissa.length() - 1);
        }
    }
    return mantissa + suffix;
}'''
