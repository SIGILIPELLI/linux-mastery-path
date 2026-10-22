import pytest
from debver import compare
@pytest.mark.parametrize("a,b,expected", [
    ("1.0", "1.0", 0), ("1.0", "1.1", -1), ("1.10", "1.9", 1),                  # numeric, not lexical
    ("1.0~rc1", "1.0", -1),                                                      # tilde sorts before release
    ("1.0~rc1", "1.0~rc2", -1), ("1.0", "1.0+dfsg", -1),
    ("2:0.9", "1:9.9", 1),                                                       # epoch dominates
    ("1.0-1", "1.0-2", -1), ("1.0-1ubuntu1", "1.0-1", 1), ("1.0-1+deb12u1", "1.0-1", 1),
    ("1.0a", "1.0", 1), ("1.0", "1.0.0", -1),
    ("3.4.10-1", "3.4.9-1", 1), ("1.0-0", "1.0", 0),
])
def test_compare(a, b, expected):
    assert compare(a, b) == expected and compare(b, a) == -expected
def test_security_update_ordering():
    seq = ["1.24.0-1", "1.24.0-1+deb12u1", "1.24.0-1+deb12u2", "1.24.0-2", "1.26.0~rc1-1", "1.26.0-1"]
    assert sorted(seq, key=__import__("functools").cmp_to_key(compare)) == seq
