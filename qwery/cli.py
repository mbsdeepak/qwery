"""Command-line interface + REPL for qwery."""
import argparse
import os
import sys

from .engine import Engine


def _auto_register(engine, paths):
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        engine.register(name, p)


def format_table(rows):
    if not rows:
        return "(0 rows)"
    cols = list(rows[0].keys())
    widths = {
        c: max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows))
        for c in cols
    }
    header = " | ".join(str(c).ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    body = [
        " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        for r in rows
    ]
    return "\n".join([header, sep, *body, f"({len(rows)} rows)"])


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="qwery", description="A tiny SQL query engine over CSV/Parquet files"
    )
    ap.add_argument(
        "-f", "--file", action="append", default=[], metavar="PATH",
        help="register a data file; table name = the file's basename",
    )
    ap.add_argument(
        "-q", "--query", help="SQL to run; if omitted, starts an interactive REPL"
    )
    args = ap.parse_args(argv)

    engine = Engine()
    _auto_register(engine, args.file)

    if args.query:
        print(format_table(engine.execute(args.query)))
        return

    print("qwery REPL — enter SQL (blank line or Ctrl-D to exit)")
    while True:
        try:
            sql = input("qwery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not sql:
            break
        try:
            print(format_table(engine.execute(sql)))
        except Exception as e:  # noqa: BLE001 - REPL should not crash on bad input
            print(f"error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
