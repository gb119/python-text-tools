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

Strings are processed as their contents; other objects use `repr(value)`.
For example, an ordinary list has a one-line representation, so `head(5)`
does not select five list elements. Results are strings that display without
quotes in a standard Python REPL and can be piped into another filter.

If an object defines its own `|` operation (for example, a NumPy array), use
the callable form to process the representation of the whole object:

```python
head(5)(anything)
```

`head(n)` and `tail(n)` require non-negative integer counts; zero returns an
empty string. Line filters normalize line endings to `\n` and omit the final
line ending. `wc()` counts split lines, whitespace-separated words and exact
source characters, including original line endings. Its line count includes
an unterminated final line, unlike Unix `wc -l`. After another filter, it
counts that filter's output, including any newline normalization.

`sort(numeric=True)` sorts by a leading signed decimal number without losing
precision; lines without a numeric prefix count as zero. Exponent notation
is not interpreted. An explicit `key` takes precedence over `numeric`.

To build and test a wheel with Python 3.8 or newer:

```sh
python -m pip install build pytest
python -m build
python -m pip install dist/*.whl
python -m pytest --import-mode=importlib
```

## Release builds

The package version is defined only in `pyproject.toml` under `[project]`.
The wheel and Conda recipe use this value, and `repl_text_tools.__version__`
reads it from installed distribution metadata. Change that one value before
a new release. For source development, install with `python -m pip install -e .`
and repeat the installation after changing the version to refresh metadata.

The GitHub Actions `build` workflow runs when a release is published or when
started manually through **Actions → build → Run workflow**. It builds and
tests the wheel across the Python version matrix, then publishes the wheel
and source distribution built with Python 3.12 to PyPI using Twine. It also
uploads the tested noarch Conda package to the `phygbu` Anaconda channel under
the `main` label. Re-running a build replaces an existing Conda artifact with
the same filename; PyPI requires a new version for changed distributions.

Add an Actions secret named `ANACONDA` to this repository (or grant it access
to an organisation secret with that name). Its token must have upload access
to `phygbu`. Add a `PYPI_TOKEN` Actions secret containing a PyPI API token
with publishing access to `repl-text-tools`. PyPI publishing runs once, after
all wheel test jobs succeed. The workflow follows the upload configuration used by
[stonerplots](https://github.com/stonerlab/stonerplots/blob/main/.github/workflows/build_conda.yaml).
Wheel and Conda files are also retained as GitHub Actions artifacts.

After publication, install the Conda package with:

```sh
conda install -c phygbu repl-text-tools
```

## Optional IPython pipeline syntax

Install the IPython extra into the environment running your console or notebook:

```sh
python -m pip install 'repl-text-tools[ipython]'
```

Load the extension, then enable transformation in a separate input cell:

```ipython
%load_ext repl_text_tools.ipython
%text_tools on
```

Import filters normally; the extension does not import names into your session:

```python
from repl_text_tools import grep, head

result = my_object | grep("error", ignore_case=True) | head(5)

import repl_text_tools as tt
result = my_object | tt.head(5)
```

The transformer recognises direct calls to the built-in filter classes,
including import aliases and qualified module references. It applies each
filter to the whole preceding object, bypassing that object's `|` operator.
Parenthesized, multiline pipelines and assignments work. Source values,
constructors and arguments are evaluated once in their original left-to-right
order. Ordinary bitwise operations, set/dictionary unions and unrelated calls
keep their Python behaviour. If a recognised name is rebound to another
callable, a runtime identity check falls back to the normal `|` operation.

Controls:

```ipython
%text_tools status
%text_tools explain my_object | grep("error") | head(5)
%text_tools off
%unload_ext repl_text_tools.ipython
```

`explain` shows the guarded rewrite without evaluating the expression, even
when transformation is off. `_text_tools_apply(value, constructor, ...)` in
that output means: construct the filter, check constructor identity, then
apply it or fall back to ordinary `|`. The live helper has a unique private
name to avoid collisions; it is removed when transformation is disabled.

This first version transforms interactive statements, including top-level
control-flow blocks. It leaves function definitions, classes, lambdas and
comprehensions unchanged, including their defaults and decorators. Stored
filter instances (`value | stage`), dynamically obtained constructors and
arbitrary attribute access are outside its recognition rules; use
`stage(value)` for those cases. New aliases created by assignments are
recognised on the next input cell. Imports can be recognised in the same
cell as a pipeline. Transformations apply to cells compiled after activation;
use separate input cells for enabling/disabling and subsequent Python code.
Reloading the extension resets transformation to off. Without the extension,
the original portable Python API remains available.

### Worked IPython example

After loading the extension and running `%text_tools on`, enter this setup:

```python
from repl_text_tools import grep, head, tail, sort, uniq, wc

class Example:
    def __repr__(self):
        return "INFO starting\nERROR disk full\nINFO retrying\nERROR timeout\nINFO finished"

    def __or__(self, other):
        raise RuntimeError("The transformer should bypass this")

example = Example()
```

Run each pipeline as a separate input. Comments show the expected output:

```python
example | grep("ERROR")
# ERROR disk full
# ERROR timeout

example | head(2)
# INFO starting
# ERROR disk full

example | tail(2)
# ERROR timeout
# INFO finished

example | grep("INFO") | head(2)
# INFO starting
# INFO retrying

example | wc(lines=True)
# 5
```

The class deliberately defines a conflicting `__or__`. These pipelines
should work without raising `RuntimeError`, demonstrating that the
transformer bypasses the object's own `|` operation.

Strings and assignments work too:

```python
result = "pear\napple\npear\nbanana" | sort() | uniq()
print(result)
# apple
# banana
# pear
```

Inspect the transformation without executing the pipeline, and check its
current status:

```ipython
%text_tools explain example | grep("ERROR") | head(1)
%text_tools status
```
