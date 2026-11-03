import unittest

from repl_text_tools import Text, Filter, grep, head, tail, sort, uniq, wc, cut, sed, nl, tac


class Thing:
    def __repr__(self):
        return "alpha\nbeta\ngamma\nbeta"


def test_grep_on_repr():
    assert str(Thing() | grep("a$")) == "alpha\nbeta\ngamma\nbeta"
    assert str(Thing() | grep("^b")) == "beta\nbeta"
    assert str(Thing() | grep("^b", invert=True)) == "alpha\ngamma"


def test_chain():
    assert str(Thing() | grep("a") | head(2) | tac()) == "beta\nalpha"
    assert repr(Thing() | head(1)) == "alpha"


def test_misc():
    assert str(Thing() | tail(1)) == "beta"
    assert str(Thing() | sort() | uniq()) == "alpha\nbeta\ngamma"
    assert str(Thing() | wc(lines=True)) == "4"
    assert str("a b c\nd e f" | cut(2, 3)) == "b c\ne f"
    assert str("abc" | sed("b", "X")) == "aXc"
    assert str("x\ny" | nl()) == "     1  x\n     2  y"
    assert str([1, 2] | grep("1")) == "[1, 2]"


class RegressionTests(unittest.TestCase):
    def test_callable_bypasses_left_operator(self):
        class OwnOr(Thing):
            def __or__(self, other):
                raise AssertionError("left operator should not be called")

        self.assertEqual(head(1)(OwnOr()), "alpha")
        self.assertEqual(wc(chars=True)(OwnOr()), str(len(repr(OwnOr()))))

    def test_counts_preserve_source_characters(self):
        cases = [
            ("", "0 0 0"),
            ("abc", "1 1 3"),
            ("abc\n", "1 1 4"),
            ("a\r\nb\r\n", "2 2 6"),
            ("\n\n", "2 0 2"),
            ("a\tb", "1 2 3"),
            ("é🙂", "1 1 2"),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(source | wc(), expected)
                self.assertEqual(source | wc(chars=True), str(len(source)))
        self.assertEqual(Thing() | wc(chars=True), str(len(repr(Thing()))))
        self.assertEqual("a\r\nb\r\n" | head(2) | wc(), "2 2 3")

    def test_numeric_sort_precision_and_prefixes(self):
        source = "9007199254740993\n9007199254740992"
        self.assertEqual(source | sort(numeric=True), "9007199254740992\n9007199254740993")
        self.assertEqual(source | sort(numeric=True, reverse=True), source)
        self.assertEqual("0.10000000000000000002\n0.10000000000000000001" | sort(numeric=True),
                         "0.10000000000000000001\n0.10000000000000000002")
        self.assertEqual("+2 apples\n-.5\ntext\n  .25" | sort(numeric=True),
                         "-.5\ntext\n  .25\n+2 apples")
        self.assertEqual("10\n2" | sort(numeric=True, key=len), "2\n10")

    def test_line_count_boundaries(self):
        for cls in (head, tail):
            with self.subTest(filter=cls.__name__):
                self.assertEqual("a\nb" | cls(0), "")
                self.assertEqual("a\nb" | cls(20), "a\nb")
                self.assertEqual("" | cls(1), "")
                with self.assertRaises(ValueError):
                    cls(-1)
                for invalid in (1.5, "2", None):
                    with self.assertRaises(TypeError):
                        cls(invalid)
        self.assertEqual("a\nb\nc" | head(2), "a\nb")
        self.assertEqual("a\nb\nc" | tail(2), "b\nc")

    def test_line_subclasses_and_text_results(self):
        class FirstLine(Filter):
            def process(self, lines):
                return lines[:1]

        result = "a\nb" | FirstLine()
        self.assertIsInstance(result, Text)
        self.assertEqual(repr(result), "a")
        self.assertEqual(result | wc(chars=True), "1")

    def test_existing_examples(self):
        test_grep_on_repr()
        test_chain()
        test_misc()
