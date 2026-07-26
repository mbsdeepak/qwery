import os

import pytest

from qwery import Engine

DATA = os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture
def engine():
    e = Engine()
    e.register("users", os.path.join(DATA, "users.csv"))
    e.register("orders", os.path.join(DATA, "orders.csv"))
    return e


def test_select_all(engine):
    assert len(engine.execute("SELECT * FROM users")) == 5


def test_projection(engine):
    rows = engine.execute("SELECT name, age FROM users")
    assert rows[0] == {"name": "Alice", "age": 30}


def test_where_comparison(engine):
    rows = engine.execute("SELECT name FROM users WHERE age > 30")
    assert {r["name"] for r in rows} == {"Carol", "Eve"}


def test_where_and(engine):
    rows = engine.execute(
        "SELECT name FROM users WHERE city = 'NYC' AND age > 30"
    )
    assert [r["name"] for r in rows] == ["Carol"]


def test_order_by_and_limit(engine):
    rows = engine.execute("SELECT name, age FROM users ORDER BY age DESC LIMIT 2")
    assert [r["name"] for r in rows] == ["Eve", "Carol"]


def test_group_by_count(engine):
    rows = engine.execute(
        "SELECT city, count(*) c FROM users GROUP BY city ORDER BY c DESC"
    )
    assert {r["city"]: r["c"] for r in rows} == {"NYC": 2, "LA": 2, "SF": 1}


def test_aggregate_sum(engine):
    rows = engine.execute(
        "SELECT sum(amount) total FROM orders WHERE status = 'paid'"
    )
    assert rows[0]["total"] == 250 + 80 + 500 + 300


def test_aggregate_avg_min_max(engine):
    rows = engine.execute(
        "SELECT min(age) lo, max(age) hi, avg(age) mean FROM users"
    )
    assert rows[0]["lo"] == 25
    assert rows[0]["hi"] == 42
    assert rows[0]["mean"] == (30 + 25 + 35 + 28 + 42) / 5


def test_inner_join(engine):
    rows = engine.execute(
        "SELECT u.name, o.amount FROM users u "
        "JOIN orders o ON u.id = o.user_id "
        "WHERE o.status = 'paid' ORDER BY o.amount DESC"
    )
    assert len(rows) == 4
    assert rows[0] == {"name": "Carol", "amount": 500}


def test_join_with_group_by(engine):
    rows = engine.execute(
        "SELECT u.name name, sum(o.amount) spent FROM users u "
        "JOIN orders o ON u.id = o.user_id "
        "GROUP BY u.name ORDER BY spent DESC"
    )
    assert rows[0] == {"name": "Carol", "spent": 560}
    assert {r["name"] for r in rows} == {"Alice", "Bob", "Carol", "Eve"}


def test_arithmetic_in_projection(engine):
    rows = engine.execute("SELECT name, age + 1 next_year FROM users WHERE name = 'Bob'")
    assert rows[0] == {"name": "Bob", "next_year": 26}


def test_register_rows_in_memory():
    e = Engine()
    e.register_rows("t", [{"x": 1}, {"x": 2}, {"x": 3}])
    rows = e.execute("SELECT sum(x) s FROM t WHERE x >= 2")
    assert rows[0]["s"] == 5


def test_parquet_roundtrip(tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    import pyarrow as pa

    path = tmp_path / "nums.parquet"
    pq.write_table(pa.table({"n": [1, 2, 3, 4], "grp": ["a", "a", "b", "b"]}), path)

    e = Engine()
    e.register("nums", str(path))
    rows = e.execute("SELECT grp, sum(n) s FROM nums GROUP BY grp ORDER BY grp")
    assert rows == [{"grp": "a", "s": 3}, {"grp": "b", "s": 7}]
