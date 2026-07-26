"""Scalar expression evaluation over a single row.

A row is a dict whose keys are qualified column names ("table.col").
Bare column references resolve against the unqualified part of the key.
"""
from . import nodes

_CMP = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def render_name(expr) -> str:
    """Human-readable name for an expression (used as an output column name)."""
    if isinstance(expr, nodes.Column):
        return expr.name
    if isinstance(expr, nodes.FuncCall):
        inner = "*" if expr.star else render_name(expr.arg)
        return f"{expr.name}({inner})"
    if isinstance(expr, nodes.Literal):
        return repr(expr.value)
    if isinstance(expr, nodes.BinaryOp):
        return f"{render_name(expr.left)} {expr.op} {render_name(expr.right)}"
    if isinstance(expr, nodes.UnaryOp):
        return f"{expr.op} {render_name(expr.operand)}"
    return "expr"


def resolve_column(row, col: "nodes.Column"):
    if col.table is not None:
        key = f"{col.table}.{col.name}"
        if key in row:
            return row[key]
        raise KeyError(f"Unknown column {key!r}")
    # bare column: exact key wins (post-projection rows), else match suffix
    if col.name in row:
        return row[col.name]
    matches = [k for k in row if k.split(".", 1)[-1] == col.name]
    if len(matches) == 1:
        return row[matches[0]]
    if not matches:
        raise KeyError(f"Unknown column {col.name!r}")
    raise KeyError(f"Ambiguous column {col.name!r}: matches {matches}")


def evaluate(expr, row):
    if isinstance(expr, nodes.Literal):
        return expr.value

    if isinstance(expr, nodes.Column):
        return resolve_column(row, expr)

    if isinstance(expr, nodes.FuncCall):
        # Aggregates are pre-computed by the Aggregate operator and stored in
        # the row under their rendered name; here we just read that value.
        key = render_name(expr)
        if key in row:
            return row[key]
        raise ValueError(f"Aggregate {key!r} used outside of an aggregation")

    if isinstance(expr, nodes.UnaryOp):
        if expr.op == "NOT":
            return not bool(evaluate(expr.operand, row))
        if expr.op == "-":
            return -evaluate(expr.operand, row)

    if isinstance(expr, nodes.BinaryOp):
        op = expr.op
        if op == "AND":
            return bool(evaluate(expr.left, row)) and bool(evaluate(expr.right, row))
        if op == "OR":
            return bool(evaluate(expr.left, row)) or bool(evaluate(expr.right, row))
        left = evaluate(expr.left, row)
        right = evaluate(expr.right, row)
        if op in _CMP:
            if left is None or right is None:
                return False
            try:
                return _CMP[op](left, right)
            except TypeError:
                # cross-type comparison: fall back to string ordering
                return _CMP[op](str(left), str(right))
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right

    raise ValueError(f"Cannot evaluate expression: {expr!r}")
