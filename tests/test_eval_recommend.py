import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from eval_recommend import verdict  # ty: ignore[unresolved-import]


def test_verdict():
    assert verdict("a/b", "a/b") == "exact"
    assert verdict("a/b", "a/b/c") == "related"  # descendant
    assert verdict("a/b/c", "a/b") == "related"  # ancestor
    assert verdict("a/b", "a/c") == "related"  # sibling
    assert verdict("a/b", "x/b") == "miss"
    assert verdict("a/bc", "a/b") == "related"  # same parent, not a prefix trap
    assert verdict("a/b/x", "a/bc") == "miss"
