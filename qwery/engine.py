"""Public entry point: register tables, run SQL, get back rows (list of dicts)."""
from .catalog import Catalog
from .parser import Parser
from .planner import build_plan


class Engine:
    def __init__(self):
        self.catalog = Catalog()

    def register(self, name, path):
        """Register a table backed by a CSV/Parquet file."""
        self.catalog.register(name, path)
        return self

    def register_rows(self, name, rows):
        """Register a table backed by an in-memory list of dict rows."""
        self.catalog.register_rows(name, rows)
        return self

    def execute(self, sql):
        """Run a query and return the result rows as a list of dicts."""
        query = Parser(sql).parse()
        plan = build_plan(query, self.catalog)
        return list(plan)
