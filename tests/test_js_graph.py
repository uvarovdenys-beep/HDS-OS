"""JS/TS code graph — the half of the mirror that used to be blind.

Regex, not a parser, by the same reasoning as lang/_locate: the kernel stays
stdlib. A miss must surface as "unparsed", never as a false "unimplemented".
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import js_graph as j


# ── strip_noise: length and lines must survive ──────────────────────────
def test_strip_preserves_length_and_hides_content():
    src = 'a = "xx"; // gone'
    out = j.strip_noise(src)
    assert len(out) == len(src)
    assert "xx" not in out and "gone" not in out


def test_strip_preserves_line_numbers():
    assert j.strip_noise("a // c\nb").splitlines()[1] == "b"


def test_strip_handles_block_comments_and_escapes():
    assert "gone" not in j.strip_noise("/* gone */ x")
    assert len(j.strip_noise(r'"a\"b"')) == len(r'"a\"b"')


def test_strip_leaves_code_untouched():
    assert j.strip_noise("f(1)") == "f(1)"


# ── params_of: types and defaults are not part of the name ──────────────
def test_params_drops_types_and_defaults():
    assert j.params_of("a, b: number, x = 5") == ["a", "b", "x"]


def test_params_keeps_generics_as_one_parameter():
    assert j.params_of("a: Map<string, number>, b") == ["a", "b"]


def test_params_handles_rest_and_empty():
    assert j.params_of("...rest") == ["rest"]
    assert j.params_of("") == []


# ── symbols: every declaration form HDS actually generates ──────────────
TS = """export function activate(context: vscode.ExtensionContext): void {
  registerCommands(context);
  initializeMcpClient();
}
const helper = (a: number, b: number): number => {
  return compute(a, b);
};
const plain = (x) => { return twice(x); };"""


def test_finds_function_arrow_and_typed_arrow():
    assert sorted(j.symbols(TS)) == ["activate", "helper", "plain"]


def test_records_params_and_calls():
    sym = j.symbols(TS)
    assert sym["activate"]["params"] == ["context"]
    assert sym["activate"]["calls"] == ["initializeMcpClient", "registerCommands"]
    assert sym["helper"]["calls"] == ["compute"]


def test_control_flow_is_not_a_call():
    sym = j.symbols("function f(x) {\n  if (x) { return g(x); }\n}")
    assert sym["f"]["calls"] == ["g"]
