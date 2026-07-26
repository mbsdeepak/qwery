import pytest

from qwery.tokenizer import tokenize


def types(sql):
    return [t.type for t in tokenize(sql)]


def test_keywords_and_idents():
    toks = tokenize("SELECT name FROM users")
    assert [(t.type, t.value) for t in toks] == [
        ("SELECT", "SELECT"),
        ("IDENT", "name"),
        ("FROM", "FROM"),
        ("IDENT", "users"),
        ("EOF", ""),
    ]


def test_operators_and_numbers():
    toks = tokenize("age >= 30 AND amount < 12.5")
    vals = [t.value for t in toks[:-1]]
    assert vals == ["age", ">=", "30", "AND", "amount", "<", "12.5"]


def test_string_literal():
    toks = tokenize("city = 'New York'")
    assert toks[2].type == "STRING"
    assert toks[2].value == "New York"


def test_invalid_char():
    with pytest.raises(SyntaxError):
        tokenize("SELECT ~ FROM t")
