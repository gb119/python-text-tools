from repl_text_tools import grep, head, tail, sort, uniq, wc, cut, sed, nl, tac


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
