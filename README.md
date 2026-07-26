# qwery

A tiny SQL query engine that runs `SELECT` queries directly over **CSV and Parquet**
files — no database, no server. Written from scratch in pure Python: a hand-written
tokenizer and recursive-descent parser feed a **Volcano-model** (pull-based iterator)
execution engine, the same architecture used by production engines like DuckDB and
Apache DataFusion.

```sql
SELECT u.name, sum(o.amount) AS spent
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid'
GROUP BY u.name
ORDER BY spent DESC
LIMIT 10;
```

```
$ qwery -f users.csv -f orders.csv -q "SELECT u.name, sum(o.amount) spent
    FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name ORDER BY spent DESC"
name  | spent
------+------
Carol | 560
Alice | 330
Eve   | 300
Bob   | 120
(4 rows)
```

## Features

- `SELECT` with projections, `*`, aliases (`AS` optional), and arithmetic (`age + 1`)
- `WHERE` with `AND` / `OR` / `NOT`, comparisons (`= != <> < <= > >=`), and parentheses
- `INNER JOIN ... ON` (hash join)
- `GROUP BY` with `COUNT`, `SUM`, `AVG`, `MIN`, `MAX` (NULLs skipped, SQL-style)
- `ORDER BY` (`ASC`/`DESC`, multiple keys) and `LIMIT`
- Reads **CSV** (stdlib, zero deps) and **Parquet** (via `pyarrow`, lazily imported)
- Lazy, streaming execution — rows are pulled through the operator tree on demand
- An interactive REPL and a one-shot `-q` mode

## How it works

The engine is a classic four-stage compiler-to-executor pipeline:

```
SQL text
   │  tokenizer.py      regex lexer → tokens
   ▼
tokens
   │  parser.py         recursive-descent → AST (nodes.py)
   ▼
Query AST
   │  planner.py        AST → tree of physical operators
   ▼
operator tree
   │  operators.py      Volcano-model iterators, pulled lazily
   ▼
result rows (list of dicts)
```

**Execution — the Volcano model.** Every operator (`Scan`, `Filter`, `HashJoin`,
`Aggregate`, `Sort`, `Limit`, `Project`) is a Python iterator. Iterating the root
operator pulls rows up through the whole tree one at a time, so `Filter` and `Limit`
never materialize more than they need. Only the blocking operators (`HashJoin` builds
its hash table, `Sort` and `Aggregate` accumulate) buffer rows — exactly as a real
engine does.

```
Limit → Project → Sort → Filter → HashJoin → Scan(users)
                                         └──→ Scan(orders)
```

The planner places `Sort` before `Project` for plain queries (so `ORDER BY` can use any
source column) and after `Aggregate` for grouped queries (so it can sort on aggregates).

## Install

```bash
git clone <your-repo-url> qwery && cd qwery
pip install -e .            # core (CSV only)
pip install -e ".[parquet]" # add Parquet support
pip install -e ".[dev]"     # add pytest
```

## Usage

**CLI** — the table name is the file's basename (`users.csv` → table `users`):

```bash
qwery -f users.csv -q "SELECT * FROM users WHERE age > 30"
qwery -f users.csv -f orders.csv          # no -q → interactive REPL
```

**Library:**

```python
from qwery import Engine

e = Engine()
e.register("users", "users.csv")
e.register("events", "events.parquet")
for row in e.execute("SELECT city, count(*) c FROM users GROUP BY city"):
    print(row)                # {'city': 'NYC', 'c': 2}

# in-memory tables work too
e.register_rows("t", [{"x": 1}, {"x": 2}])
```

## Project layout

| File | Responsibility |
|------|----------------|
| `tokenizer.py` | Regex lexer: SQL string → tokens |
| `nodes.py`     | AST dataclasses |
| `parser.py`    | Recursive-descent parser with correct operator precedence |
| `catalog.py`   | Table registry + CSV/Parquet readers, type inference |
| `evaluator.py` | Scalar expression evaluation over a row |
| `operators.py` | Volcano-model physical operators |
| `planner.py`   | AST → operator tree |
| `engine.py`    | Public `Engine` API |
| `cli.py`       | CLI + REPL |

## Tests

```bash
pytest            # 22 tests: tokenizer, parser, and end-to-end queries
```

## Design notes & limitations

Deliberately scoped to keep the core sharp:

- Inner equi-joins only; join `ON` must be a single `a.x = b.y` equality.
- No subqueries, `HAVING`, `DISTINCT`, or window functions.
- Aggregate SELECT items must be a direct call (`sum(x)`), not nested (`sum(x)/count(*)`).
- CSV values are type-inferred (int → float → string); Parquet keeps native types.

Each of these is a natural next-weekend extension — the operator/planner split makes
them additive rather than invasive.

## License

MIT
