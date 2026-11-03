"""Unix-like text filters usable with ``value | grep("pattern")``."""
from .filters import (Text, Filter, grep, head, tail, sort, uniq, wc, cut,
                      sed, nl, tac)

__all__ = ["Text", "Filter", "grep", "head", "tail", "sort", "uniq", "wc",
           "cut", "sed", "nl", "tac"]
__version__ = "0.1.0"
