"""Filter classes that manipulate the repr of a value via ``__ror__``."""
import re


class Text(str):
    """A string whose repr is its own content, so REPLs show it as printed."""

    def __repr__(self):
        return str(self)


def _to_lines(value):
    if isinstance(value, str):
        text = str(value)
    else:
        text = repr(value)
    return text.splitlines()


class Filter:
    """Base class: ``value | Filter(...)`` applies :meth:`process` to the
    lines of ``repr(value)`` (or the string itself for strings)."""

    def process(self, lines):
        raise NotImplementedError

    def __ror__(self, other):
        result = self.process(_to_lines(other))
        if isinstance(result, str):
            return Text(result)
        return Text("\n".join(result))

    def __call__(self, value):
        return value | self


class grep(Filter):
    """Keep lines matching a regex (``invert`` keeps non-matching lines)."""

    def __init__(self, pattern, invert=False, ignore_case=False, fixed=False):
        if fixed:
            pattern = re.escape(pattern)
        self.regex = re.compile(pattern, re.I if ignore_case else 0)
        self.invert = invert

    def process(self, lines):
        return [l for l in lines if bool(self.regex.search(l)) != self.invert]


class head(Filter):
    def __init__(self, n=10):
        self.n = n

    def process(self, lines):
        return lines[:self.n]


class tail(Filter):
    def __init__(self, n=10):
        self.n = n

    def process(self, lines):
        return lines[-self.n:] if self.n > 0 else []


class sort(Filter):
    def __init__(self, reverse=False, key=None, numeric=False):
        self.reverse = reverse
        self.key = key
        self.numeric = numeric

    def process(self, lines):
        key = self.key
        if key is None and self.numeric:
            def key(l):
                m = re.match(r"\s*-?\d+(\.\d+)?", l)
                return float(m.group()) if m else 0.0
        return sorted(lines, key=key, reverse=self.reverse)


class uniq(Filter):
    """Collapse adjacent duplicate lines (``count`` prefixes counts)."""

    def __init__(self, count=False):
        self.count = count

    def process(self, lines):
        out = []
        for l in lines:
            if out and out[-1][0] == l:
                out[-1][1] += 1
            else:
                out.append([l, 1])
        if self.count:
            return ["%7d %s" % (c, l) for l, c in out]
        return [l for l, _ in out]


class wc(Filter):
    """Count lines, words and characters (or just one of them)."""

    def __init__(self, lines=False, words=False, chars=False):
        self.sel = (lines, words, chars)

    def process(self, lines):
        counts = (len(lines),
                  sum(len(l.split()) for l in lines),
                  sum(len(l) + 1 for l in lines))
        if not any(self.sel):
            return " ".join(str(c) for c in counts)
        return " ".join(str(c) for c, s in zip(counts, self.sel) if s)


class cut(Filter):
    """Select 1-based fields split on ``delimiter`` (whitespace by default)."""

    def __init__(self, *fields, delimiter=None, joiner=None):
        self.fields = fields
        self.delimiter = delimiter
        self.joiner = joiner if joiner is not None else (delimiter or " ")

    def process(self, lines):
        out = []
        for l in lines:
            parts = l.split(self.delimiter)
            out.append(self.joiner.join(
                parts[f - 1] for f in self.fields if 0 < f <= len(parts)))
        return out


class sed(Filter):
    """Regex substitution on each line."""

    def __init__(self, pattern, repl, count=0):
        self.regex = re.compile(pattern)
        self.repl = repl
        self.count = count

    def process(self, lines):
        return [self.regex.sub(self.repl, l, count=self.count) for l in lines]


class nl(Filter):
    """Number lines."""

    def __init__(self, start=1):
        self.start = start

    def process(self, lines):
        return ["%6d  %s" % (i, l) for i, l in enumerate(lines, self.start)]


class tac(Filter):
    """Reverse line order."""

    def process(self, lines):
        return lines[::-1]
