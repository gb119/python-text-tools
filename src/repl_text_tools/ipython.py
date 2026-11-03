"""Opt-in IPython syntax support; load with ``%load_ext repl_text_tools.ipython``.

No IPython dependency is imported until this extension is loaded.
"""

import ast
import operator
import sys
import uuid

from . import filters


_FILTERS = tuple(getattr(filters, name) for name in (
    "grep", "head", "tail", "sort", "uniq", "wc", "cut", "sed", "nl", "tac"
))
_MODULES = {"repl_text_tools", "repl_text_tools.filters"}
_STATE_ATTRIBUTE = "_repl_text_tools_extension"


def _apply(value, constructor, /, *args, **kwargs):
    """Preserve left-to-right evaluation and guard against rebound names."""
    stage = constructor(*args, **kwargs)
    if any(constructor is cls for cls in _FILTERS):
        return stage(value)
    return operator.or_(value, stage)


def _path(node):
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent = _path(node.value)
        if parent is not None:
            return parent + (node.attr,)
    return None


class _Imports(ast.NodeVisitor):
    """Collect only syntactic import aliases, without executing user code."""

    def __init__(self, candidates):
        self.candidates = candidates

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in _MODULES:
                prefix = ((alias.asname,) if alias.asname else
                          tuple(alias.name.split(".")))
                self.candidates.update(prefix + (cls.__name__,) for cls in _FILTERS)

    def visit_ImportFrom(self, node):
        if node.level or node.module not in _MODULES:
            return
        for alias in node.names:
            if alias.name == "*":
                self.candidates.update((cls.__name__,) for cls in _FILTERS)
            elif alias.name in {cls.__name__ for cls in _FILTERS}:
                self.candidates.add((alias.asname or alias.name,))
            elif node.module == "repl_text_tools" and alias.name == "filters":
                self.candidates.update((alias.asname or alias.name, cls.__name__)
                                       for cls in _FILTERS)

    # These scopes are deliberately outside the first version's contract.
    def _skip(self, node):
        return None

    visit_FunctionDef = _skip
    visit_AsyncFunctionDef = _skip
    visit_ClassDef = _skip
    visit_Lambda = _skip
    visit_ListComp = _skip
    visit_SetComp = _skip
    visit_DictComp = _skip
    visit_GeneratorExp = _skip


class _PipelineTransformer(ast.NodeTransformer):
    def __init__(self, shell, helper_name):
        self.shell = shell
        self.helper_name = helper_name
        self.candidates = set()

    def visit(self, node):
        # IPython supplies a Module for each execution. Reset recognition on
        # every cell, so stale aliases never determine later transformations.
        if isinstance(node, (ast.Module, ast.Expression)):
            self.candidates = self._candidates(node)
        return super().visit(node)

    def _candidates(self, tree):
        candidates = set()
        namespace = dict(self.shell.user_global_ns)
        namespace.update(self.shell.user_ns)
        for name, value in namespace.items():
            if any(value is cls for cls in _FILTERS):
                candidates.add((name,))
            for module_name in _MODULES:
                if value is sys.modules.get(module_name) and value is not None:
                    candidates.update((name, cls.__name__) for cls in _FILTERS)
                    if module_name == "repl_text_tools":
                        candidates.update((name, "filters", cls.__name__)
                                          for cls in _FILTERS)
        _Imports(candidates).visit(tree)
        return candidates

    def visit_BinOp(self, node):
        candidate = (isinstance(node.op, ast.BitOr)
                     and isinstance(node.right, ast.Call)
                     and _path(node.right.func) in self.candidates)
        self.generic_visit(node)
        if not candidate:
            return node
        call = node.right
        replacement = ast.Call(
            func=ast.Name(id=self.helper_name, ctx=ast.Load()),
            args=[node.left, call.func] + call.args,
            keywords=call.keywords,
        )
        return ast.fix_missing_locations(ast.copy_location(replacement, node))

    def _skip(self, node):
        return node

    visit_FunctionDef = _skip
    visit_AsyncFunctionDef = _skip
    visit_ClassDef = _skip
    visit_Lambda = _skip
    visit_ListComp = _skip
    visit_SetComp = _skip
    visit_DictComp = _skip
    visit_GeneratorExp = _skip


class _Extension:
    def __init__(self, shell):
        from IPython.core.magic import no_var_expand

        self.shell = shell
        self.helper_name = "_repl_text_tools_apply_" + uuid.uuid4().hex
        self.transformer = _PipelineTransformer(shell, self.helper_name)
        self.previous_magic = shell.find_line_magic("text_tools")
        # Python expressions passed to explain must never undergo IPython's
        # $name / {expression} interpolation, which can execute user code.
        no_var_expand(type(self).command)
        self.magic = self.command

    @property
    def enabled(self):
        return self.transformer in self.shell.ast_transformers

    def disable(self):
        self.shell.ast_transformers[:] = [
            item for item in self.shell.ast_transformers if item is not self.transformer
        ]
        if self.shell.user_ns.get(self.helper_name) is _apply:
            del self.shell.user_ns[self.helper_name]

    def command(self, line):
        """%text_tools on|off|status|explain <Python expression or statement>."""
        from IPython.core.error import UsageError

        parts = line.strip().split(maxsplit=1)
        action = parts[0] if parts else "status"
        if action == "explain":
            if len(parts) != 2:
                raise UsageError("Usage: %text_tools explain <Python code>")
            try:
                tree = ast.parse(parts[1])
            except SyntaxError as exc:
                raise UsageError(str(exc)) from exc
            # Show the same guarded rewrite even when transformation is off.
            tree = _PipelineTransformer(self.shell, "_text_tools_apply").visit(tree)
            if hasattr(ast, "unparse"):
                source = ast.unparse(tree)
            else:  # Python 3.8, installed by the ipython extra.
                import astunparse
                source = astunparse.unparse(tree).strip()
            print(source)
            return
        if len(parts) > 1 or action not in {"on", "off", "status"}:
            raise UsageError(self.command.__doc__)
        if action == "on":
            self.shell.user_ns[self.helper_name] = _apply
            if not self.enabled:
                self.shell.ast_transformers.append(self.transformer)
        elif action == "off":
            self.disable()
        print("Text pipeline transformation is " + ("on" if self.enabled else "off"))


def load_ipython_extension(ipython):
    """Register controls, leaving syntax transformation off until requested."""
    if getattr(ipython, _STATE_ATTRIBUTE, None) is not None:
        return
    extension = _Extension(ipython)
    ipython.register_magic_function(extension.magic, "line", "text_tools")
    setattr(ipython, _STATE_ATTRIBUTE, extension)


def unload_ipython_extension(ipython):
    """Remove only this extension's transformer, helper and magic."""
    extension = getattr(ipython, _STATE_ATTRIBUTE, None)
    if extension is None:
        return
    extension.disable()
    magics = ipython.magics_manager.magics["line"]
    if magics.get("text_tools") is extension.magic:
        if extension.previous_magic is None:
            magics.pop("text_tools", None)
        else:
            magics["text_tools"] = extension.previous_magic
    delattr(ipython, _STATE_ATTRIBUTE)
