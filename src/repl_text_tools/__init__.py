"""Unix-like text filters usable with ``value | grep("pattern")``."""
from importlib.metadata import version as _distribution_version

from .filters import (Text, Filter, grep, head, tail, sort, uniq, wc, cut,
                      sed, nl, tac)

__all__ = ["Text", "Filter", "grep", "head", "tail", "sort", "uniq", "wc",
           "cut", "sed", "nl", "tac"]
__version__ = _distribution_version("repl-text-tools")
