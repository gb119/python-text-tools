"""Exercise actual IPython cells rather than only inspecting generated ASTs."""

import ast
import contextlib
import io
import sys
import unittest

try:
    from IPython.core.interactiveshell import InteractiveShell
except ImportError:
    InteractiveShell = None

from repl_text_tools import head
from repl_text_tools.ipython import load_ipython_extension, unload_ipython_extension


class OwnOr:
    def __repr__(self):
        return "alpha\nbeta\ngamma"

    def __or__(self, other):
        return "left operator"


@unittest.skipIf(InteractiveShell is None, "install repl-text-tools[ipython] to test the extension")
class IPythonTests(unittest.TestCase):
    def setUp(self):
        self.shell = InteractiveShell(user_ns={"value": OwnOr()})
        self.addCleanup(self.shell.history_manager.end_session)
        self.addCleanup(unload_ipython_extension, self.shell)
        self.run_cell("%load_ext repl_text_tools.ipython")

    def run_cell(self, source):
        result = self.shell.run_cell(source, store_history=False)
        error = result.error_before_exec or result.error_in_exec
        if error is not None:
            raise error
        return result.result

    def enable(self):
        self.run_cell("%text_tools on")

    def test_opt_in_and_whole_object_pipeline(self):
        self.run_cell("from repl_text_tools import head, grep")
        self.assertEqual(self.run_cell("value | head(1)"), "left operator")
        self.enable()
        self.assertEqual(self.run_cell('value | grep("a") | head(2)'), "alpha\nbeta")
        self.run_cell("answer = (\n value\n | head(2)\n)")
        self.assertEqual(self.shell.user_ns["answer"], "alpha\nbeta")
        self.assertEqual(self.run_cell('value | grep("missing")'), "")
        self.run_cell("%text_tools off")
        self.assertEqual(self.run_cell("value | head(1)"), "left operator")

    def test_same_cell_imports_and_aliases(self):
        self.enable()
        for source in (
            "from repl_text_tools import head as h; answer = value | h(1)",
            "import repl_text_tools as tt; answer = value | tt.head(1)",
            "import repl_text_tools.filters as f; answer = value | f.head(1)",
            "import repl_text_tools.filters; answer = value | repl_text_tools.filters.head(1)",
            "from repl_text_tools import filters as fs; answer = value | fs.head(1)",
            "from repl_text_tools import *; answer = value | head(1)",
        ):
            with self.subTest(source=source):
                self.run_cell(source)
                self.assertEqual(self.shell.user_ns["answer"], "alpha")

    def test_existing_namespace_alias(self):
        self.shell.user_ns["first"] = head
        self.enable()
        self.assertEqual(self.run_cell("value | first(1)"), "alpha")

    def test_evaluation_order_and_single_evaluation(self):
        self.run_cell("from repl_text_tools import head, tail")
        events = []

        def source():
            events.append("source")
            return OwnOr()

        def count(label):
            events.append(label)
            return 2 if label == "head" else 1

        self.shell.user_ns.update(source=source, count=count)
        self.enable()
        self.assertEqual(self.run_cell('source() | head(count("head")) | tail(count("tail"))'), "beta")
        self.assertEqual(events, ["source", "head", "tail"])
        events.clear()
        self.assertEqual(self.run_cell('source() | head(*[count("head")])'), "alpha\nbeta")
        self.assertEqual(events, ["source", "head"])
        self.assertEqual(self.run_cell('value | head(**{"n": 1})'), "alpha")

    def test_rebinding_uses_original_operator_semantics(self):
        self.run_cell("from repl_text_tools import head")
        self.enable()
        # Recognition occurs before this cell executes. Runtime identity must
        # catch the subsequent rebinding and preserve the original operation.
        self.run_cell("head = lambda n: 2; answer = 1 | head(1)")
        self.assertEqual(self.shell.user_ns["answer"], 3)
        self.assertEqual(self.run_cell("1 | head(1)"), 3)
        self.run_cell("from repl_text_tools import head; head = lambda n: 2; answer = value | head(1)")
        self.assertEqual(self.shell.user_ns["answer"], "left operator")

    def test_unrelated_operations_and_stored_instances(self):
        self.enable()
        self.assertEqual(self.run_cell("1 | 2"), 3)
        self.assertEqual(self.run_cell("{1} | {2}"), {1, 2})
        if sys.version_info >= (3, 9):
            self.assertEqual(self.run_cell('{"a": 1} | {"b": 2}'), {"a": 1, "b": 2})
        self.run_cell("other = lambda: 2")
        self.assertEqual(self.run_cell("1 | other()"), 3)
        self.run_cell("from repl_text_tools import head; stage = head(1)")
        self.assertEqual(self.run_cell("value | stage"), "left operator")

    def test_scopes_are_left_unchanged(self):
        self.run_cell("from repl_text_tools import head")
        self.enable()
        self.run_cell("def f():\n    return value | head(1)")
        self.assertEqual(self.run_cell("f()"), "left operator")
        self.assertEqual(self.run_cell("(lambda: value | head(1))()"), "left operator")
        self.assertEqual(self.run_cell("[value | head(1) for _ in range(1)]"), ["left operator"])
        self.run_cell("class C:\n    result = value | head(1)")
        self.assertEqual(self.run_cell("C.result"), "left operator")
        self.run_cell("%text_tools off")
        self.assertEqual(self.run_cell("f()"), "left operator")

    def test_explain_has_no_side_effects(self):
        self.run_cell("from repl_text_tools import head")
        calls = []
        self.shell.user_ns["source"] = lambda: calls.append(1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_cell("%text_tools explain source() | head(1)")
            self.run_cell('%text_tools explain "{source()} $value" | head(1)')
        self.assertIn("_text_tools_apply(source(), head, 1)", output.getvalue())
        self.assertIn("{source()} $value", output.getvalue())
        self.assertEqual(calls, [])
        self.assertFalse(self.shell._repl_text_tools_extension.enabled)

    def test_rebound_module_attributes_and_operator_fallback(self):
        import types

        self.run_cell("import repl_text_tools as tt")
        self.enable()
        # Replace the alias, rather than changing the actual library module.
        replacement = types.SimpleNamespace(head=lambda n: 2)
        self.shell.user_ns["replacement"] = replacement
        self.run_cell("tt = replacement; answer = 1 | tt.head(1)")
        self.assertEqual(self.shell.user_ns["answer"], 3)

    def test_unrecognised_attribute_access_is_not_evaluated_by_explain(self):
        class Dynamic:
            @property
            def head(self):
                raise AssertionError("attribute should not be inspected")

        self.shell.user_ns["dynamic"] = Dynamic()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_cell("%text_tools explain value | dynamic.head(1)")
        self.assertIn("value | dynamic.head(1)", output.getvalue())

    def test_usage_and_errors(self):
        from IPython.core.error import UsageError

        for command in ("nonsense", "on extra", "explain", "explain ("):
            with self.subTest(command=command), self.assertRaises(UsageError):
                self.shell.run_line_magic("text_tools", command)
        self.run_cell("from repl_text_tools import head")
        self.enable()
        with contextlib.redirect_stdout(io.StringIO()):
            result = self.shell.run_cell("value | head(-1)")
        self.assertIsInstance(result.error_in_exec, ValueError)
        self.assertIn(1, [frame.lineno for frame in __import__("traceback").extract_tb(
            result.error_in_exec.__traceback__)])
        self.assertTrue(self.shell._repl_text_tools_extension.enabled)

    def test_lifecycle_is_idempotent_and_preserves_other_hooks(self):
        original = lambda line: "original"
        unload_ipython_extension(self.shell)
        self.shell.register_magic_function(original, "line", "text_tools")
        sentinel = ast.NodeTransformer()
        self.shell.ast_transformers.append(sentinel)
        load_ipython_extension(self.shell)
        load_ipython_extension(self.shell)
        self.enable()
        self.enable()
        extension = self.shell._repl_text_tools_extension
        self.assertEqual(self.shell.ast_transformers.count(extension.transformer), 1)
        self.run_cell("%reload_ext repl_text_tools.ipython")
        self.assertNotIn(extension.transformer, self.shell.ast_transformers)
        self.assertNotIn(extension.helper_name, self.shell.user_ns)
        self.assertFalse(self.shell._repl_text_tools_extension.enabled)
        self.enable()
        self.run_cell("%unload_ext repl_text_tools.ipython")
        self.assertIn(sentinel, self.shell.ast_transformers)
        self.assertIs(self.shell.find_line_magic("text_tools"), original)
        unload_ipython_extension(self.shell)

    def test_status_and_no_filter_namespace_injection(self):
        self.assertNotIn("head", self.shell.user_ns)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_cell("%text_tools status")
        self.assertIn("off", output.getvalue())

    def test_numpy_whole_array(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional")
        self.shell.user_ns.update(array=np.array([1, 2]), np=np)
        self.run_cell("from repl_text_tools import head")
        self.enable()
        self.assertEqual(self.run_cell("array | head(1)"), repr(np.array([1, 2])))
