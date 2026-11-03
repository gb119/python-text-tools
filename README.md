# python-text-tools
A set of utilities that emulate the common unix text processing commands in an ipython console

## repl-text-tools

Install with `pip install .` (or build a conda package with `conda build conda`).
Filters apply to the repr of any value via `|`:

```python
from repl_text_tools import grep, head, sort
anything | grep("search string")
anything | grep("x", invert=True) | sort() | head(5)
```

Available: `grep head tail sort uniq wc cut sed nl tac`.
