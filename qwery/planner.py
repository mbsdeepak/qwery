"""Turns a Query AST into a tree of physical operators.

Pipeline shape:
    Scan -> (HashJoin)* -> Filter -> [Aggregate | Sort+Project] -> Limit

For non-aggregate queries Sort runs *before* Project so that ORDER BY can
reference any source column (not only projected ones). For aggregate queries
Sort runs *after* Aggregate so ORDER BY can reference aggregate outputs.
"""
from . import nodes
from . import operators as ops

_AGG_FUNCS = ("count", "sum", "avg", "min", "max")


def _has_aggregate(query) -> bool:
    if query.group_by:
        return True
    return any(
        isinstance(it.expr, nodes.FuncCall) and it.expr.name in _AGG_FUNCS
        for it in query.select
        if not it.star
    )


def build_plan(query, catalog):
    node = ops.Scan(query.from_table.alias, catalog.rows(query.from_table.name))

    for j in query.joins:
        right = ops.Scan(j.table.alias, catalog.rows(j.table.name))
        node = ops.HashJoin(node, right, j.condition, j.table.alias)

    if query.where is not None:
        node = ops.Filter(node, query.where)

    if _has_aggregate(query):
        node = ops.Aggregate(node, query.group_by, query.select)
        if query.order_by:
            node = ops.Sort(node, query.order_by)
    else:
        if query.order_by:
            node = ops.Sort(node, query.order_by)
        node = ops.Project(node, query.select)

    if query.limit is not None:
        node = ops.Limit(node, query.limit)

    return node
