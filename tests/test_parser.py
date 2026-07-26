from qwery import nodes
from qwery.parser import parse_sql


def test_simple_select():
    q = parse_sql("SELECT name, age FROM users")
    assert q.from_table.name == "users"
    assert [i.expr.name for i in q.select] == ["name", "age"]


def test_star():
    q = parse_sql("SELECT * FROM users")
    assert q.select[0].star is True


def test_where_precedence():
    # a OR b AND c  ==  a OR (b AND c)
    q = parse_sql("SELECT * FROM t WHERE a = 1 OR b = 2 AND c = 3")
    assert isinstance(q.where, nodes.BinaryOp)
    assert q.where.op == "OR"
    assert q.where.right.op == "AND"


def test_join_and_alias():
    q = parse_sql(
        "SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id"
    )
    assert q.from_table.alias == "u"
    assert q.joins[0].table.alias == "o"
    assert q.joins[0].condition.op == "="


def test_group_order_limit():
    q = parse_sql(
        "SELECT city, count(*) c FROM users GROUP BY city ORDER BY c DESC LIMIT 5"
    )
    assert [g.name for g in q.group_by] == ["city"]
    assert q.order_by[0].desc is True
    assert q.limit == 5
    assert q.select[1].alias == "c"
