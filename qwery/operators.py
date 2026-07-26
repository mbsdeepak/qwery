"""Physical operators, implemented as pull-based (Volcano-model) iterators.

Each operator is iterable and yields rows (dicts of qualified column ->
value). Operators compose into a tree; iterating the root pulls rows through
the whole pipeline lazily.
"""
from itertools import islice

from . import nodes
from .evaluator import evaluate, render_name

_AGG_FUNCS = ("count", "sum", "avg", "min", "max")


class Scan:
    """Reads a table's rows and qualifies every column with the table alias."""

    def __init__(self, alias, rows):
        self.alias = alias
        self.rows = rows

    def __iter__(self):
        prefix = self.alias + "."
        for row in self.rows:
            yield {prefix + k: v for k, v in row.items()}


class Filter:
    def __init__(self, child, predicate):
        self.child = child
        self.predicate = predicate

    def __iter__(self):
        for row in self.child:
            if evaluate(self.predicate, row):
                yield row


def _refs_alias(expr, alias) -> bool:
    if isinstance(expr, nodes.Column):
        return expr.table == alias
    if isinstance(expr, nodes.BinaryOp):
        return _refs_alias(expr.left, alias) or _refs_alias(expr.right, alias)
    if isinstance(expr, nodes.UnaryOp):
        return _refs_alias(expr.operand, alias)
    if isinstance(expr, nodes.FuncCall) and expr.arg is not None:
        return _refs_alias(expr.arg, alias)
    return False


class HashJoin:
    """Inner equi-join. Builds a hash table on the right input, probes with left."""

    def __init__(self, left, right, condition, right_alias):
        self.left = left
        self.right = right
        self.condition = condition
        self.right_alias = right_alias

    def _split_keys(self):
        c = self.condition
        if not (isinstance(c, nodes.BinaryOp) and c.op == "="):
            raise ValueError("JOIN ... ON must be a single equality condition")
        # Figure out which operand belongs to the right (build) side.
        if _refs_alias(c.right, self.right_alias):
            return c.left, c.right
        if _refs_alias(c.left, self.right_alias):
            return c.right, c.left
        return c.left, c.right  # best effort when unqualified

    def __iter__(self):
        left_key, right_key = self._split_keys()
        buckets = {}
        for rrow in self.right:
            buckets.setdefault(evaluate(right_key, rrow), []).append(rrow)
        for lrow in self.left:
            k = evaluate(left_key, lrow)
            for rrow in buckets.get(k, ()):
                merged = dict(lrow)
                merged.update(rrow)
                yield merged


class Project:
    """Evaluates the SELECT list, producing output rows keyed by output name."""

    def __init__(self, child, items):
        self.child = child
        self.items = items

    def __iter__(self):
        for row in self.child:
            out = {}
            for item in self.items:
                if item.star:
                    for k, v in row.items():
                        bare = k.split(".", 1)[-1]
                        out[bare if bare not in out else k] = v
                else:
                    name = item.alias or render_name(item.expr)
                    out[name] = evaluate(item.expr, row)
            yield out


def _is_aggregate(item) -> bool:
    return (
        not item.star
        and isinstance(item.expr, nodes.FuncCall)
        and item.expr.name in _AGG_FUNCS
    )


def _new_acc():
    return {"count": 0, "sum": 0, "n": 0, "min": None, "max": None}


def _update_acc(acc, func, row):
    if func.star:
        acc["count"] += 1
        return
    val = evaluate(func.arg, row)
    if val is None:  # SQL aggregates skip NULLs
        return
    acc["count"] += 1
    acc["n"] += 1
    acc["sum"] += val
    acc["min"] = val if acc["min"] is None else min(acc["min"], val)
    acc["max"] = val if acc["max"] is None else max(acc["max"], val)


def _finalize(acc, func):
    name = func.name
    if name == "count":
        return acc["count"]
    if name == "sum":
        return acc["sum"]
    if name == "avg":
        return acc["sum"] / acc["n"] if acc["n"] else None
    if name == "min":
        return acc["min"]
    if name == "max":
        return acc["max"]
    raise ValueError(f"Unknown aggregate {name!r}")


class Aggregate:
    """Hash aggregation with GROUP BY. Emits one output row per group,
    keyed by the SELECT-list output names."""

    def __init__(self, child, group_exprs, items):
        self.child = child
        self.group_exprs = group_exprs
        self.items = items

    def __iter__(self):
        agg_items = [(i, it) for i, it in enumerate(self.items) if _is_aggregate(it)]
        groups = {}   # group key -> (sample_row, {item_index: acc})
        order = []    # preserve first-seen group order

        for row in self.child:
            key = tuple(evaluate(g, row) for g in self.group_exprs)
            if key not in groups:
                groups[key] = (row, {i: _new_acc() for i, _ in agg_items})
                order.append(key)
            _, accs = groups[key]
            for i, it in agg_items:
                _update_acc(accs[i], it.expr, row)

        # aggregate over an empty input with no GROUP BY -> single row
        if not order and not self.group_exprs:
            groups[()] = (None, {i: _new_acc() for i, _ in agg_items})
            order.append(())

        for key in order:
            sample, accs = groups[key]
            out = {}
            for i, it in enumerate(self.items):
                name = it.alias or render_name(it.expr)
                if i in accs:
                    out[name] = _finalize(accs[i], it.expr)
                else:
                    out[name] = evaluate(it.expr, sample) if sample is not None else None
            yield out


def _sort_key(value):
    # None sorts first within an ascending pass; the (bool, value) tuple keeps
    # comparisons total even when a column has mixed/None values.
    return (value is None, value)


class Sort:
    def __init__(self, child, order_items):
        self.child = child
        self.order_items = order_items

    def __iter__(self):
        rows = list(self.child)
        # apply keys right-to-left so the first ORDER BY key is most significant
        for item in reversed(self.order_items):
            rows.sort(key=lambda r, e=item.expr: _sort_key(evaluate(e, r)),
                      reverse=item.desc)
        return iter(rows)


class Limit:
    def __init__(self, child, n):
        self.child = child
        self.n = n

    def __iter__(self):
        return islice(iter(self.child), self.n)
