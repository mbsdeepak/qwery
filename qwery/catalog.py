"""Table catalog + file readers (CSV and Parquet)."""
import csv
import os


def _infer(value):
    """Coerce a CSV cell (always a string) into int/float/None when possible."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_csv(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [{k: _infer(v) for k, v in row.items()} for row in reader]


def load_parquet(path):
    try:
        import pyarrow.parquet as pq
    except ImportError as e:  # pragma: no cover - depends on env
        raise RuntimeError(
            "Reading Parquet requires pyarrow. Install it with: pip install pyarrow"
        ) from e
    return pq.read_table(path).to_pylist()


class Catalog:
    """Maps table names to a data source (a file path or in-memory rows)."""

    def __init__(self):
        self._tables = {}

    def register(self, name, path):
        self._tables[name] = path

    def register_rows(self, name, rows):
        self._tables[name] = list(rows)

    def rows(self, name):
        if name not in self._tables:
            raise KeyError(f"Unknown table: {name!r}")
        src = self._tables[name]
        if isinstance(src, list):
            return src
        ext = os.path.splitext(src)[1].lower()
        if ext == ".csv":
            return load_csv(src)
        if ext in (".parquet", ".pq"):
            return load_parquet(src)
        raise ValueError(f"Unsupported file type for {src!r}")
