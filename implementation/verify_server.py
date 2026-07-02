#!/usr/bin/env python3
"""Repeatable smoke checks for the SQLite Lab MCP server."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import SQLiteAdapter, ValidationError
from init_db import DB_PATH, create_database


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
    if not condition:
        raise SystemExit(1)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    create_database()
    adapter = SQLiteAdapter(DB_PATH)

    check("database initialized", DB_PATH.exists())
    check("tables created", set(adapter.list_tables()) == {"courses", "enrollments", "students"})

    search_result = adapter.search("students", filters={"cohort": "A1"}, order_by="score", descending=True)
    check("search returns rows", search_result["count"] > 0)
    check("search ordering", search_result["rows"][0]["name"] == "Em Vu")

    inserted = adapter.insert("students", {"name": "Test User", "cohort": "C3", "score": 70.0})
    check("insert returns payload", inserted["inserted"]["name"] == "Test User")

    agg = adapter.aggregate("students", metric="avg", column="score", group_by="cohort")
    check("aggregate grouped results", len(agg["results"]) >= 2)

    schema = adapter.get_database_schema()
    check("database schema resource", len(schema["tables"]) == 3)

    table_schema = adapter.get_table_schema("students")
    check("table schema resource", table_schema["table"] == "students")

    try:
        adapter.search("missing_table")
        check("invalid table rejected", False)
    except ValidationError as exc:
        check("invalid table rejected", "Unknown table" in str(exc), str(exc))

    try:
        adapter.search("students", filters={"bad_column": "x"})
        check("invalid column rejected", False)
    except ValidationError as exc:
        check("invalid column rejected", "Unknown column" in str(exc), str(exc))

    try:
        adapter.insert("students", {})
        check("empty insert rejected", False)
    except ValidationError as exc:
        check("empty insert rejected", "at least one" in str(exc), str(exc))

    print("\nAll verification checks passed.")
    print(json.dumps({"database": str(DB_PATH), "tables": adapter.list_tables()}, indent=2))


if __name__ == "__main__":
    main()
