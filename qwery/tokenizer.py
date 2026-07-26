"""Lexer: turns a SQL string into a flat list of tokens."""
import re
from dataclasses import dataclass

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "LIMIT", "JOIN",
    "INNER", "ON", "AS", "AND", "OR", "NOT", "ASC", "DESC", "NULL",
    "TRUE", "FALSE",
}

_MASTER = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<NUMBER>\d+\.\d+|\d+)
    | (?P<STRING>'(?:[^'\\]|\\.)*')
    | (?P<OP><>|!=|<=|>=|=|<|>|\+|\-|\*|/)
    | (?P<PUNCT>[(),.])
    | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    type: str
    value: str
    pos: int


def tokenize(sql: str):
    tokens = []
    i = 0
    for m in _MASTER.finditer(sql):
        if m.start() != i:
            bad = sql[i:m.start()]
            raise SyntaxError(f"Unexpected character(s) {bad!r} at position {i}")
        i = m.end()
        kind = m.lastgroup
        val = m.group()
        if kind == "WS":
            continue
        if kind == "IDENT":
            up = val.upper()
            if up in KEYWORDS:
                tokens.append(Token(up, up, m.start()))
            else:
                tokens.append(Token("IDENT", val, m.start()))
        elif kind == "STRING":
            tokens.append(Token("STRING", val[1:-1].replace("\\'", "'"), m.start()))
        else:
            tokens.append(Token(kind, val, m.start()))
    if i != len(sql):
        raise SyntaxError(f"Unexpected character(s) {sql[i:]!r} at position {i}")
    tokens.append(Token("EOF", "", len(sql)))
    return tokens
