import json
from pathlib import Path

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import DB_PATH, create_database

if not DB_PATH.exists():
    create_database()

adapter = SQLiteAdapter(DB_PATH)
mcp = FastMCP("SQLite Lab MCP Server")


def _error(message: str) -> dict:
    return {"ok": False, "error": message}


@mcp.tool(name="search")
def search(
    table: str,
    filters: dict | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict:
    """Search rows in a table with optional filters, ordering, and pagination."""
    try:
        result = adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
        return {"ok": True, **result}
    except ValidationError as exc:
        return _error(str(exc))


@mcp.tool(name="insert")
def insert(table: str, values: dict) -> dict:
    """Insert a new row into a table and return the inserted payload."""
    try:
        result = adapter.insert(table=table, values=values)
        return {"ok": True, **result}
    except ValidationError as exc:
        return _error(str(exc))


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict | None = None,
    group_by: str | None = None,
) -> dict:
    """Run COUNT, AVG, SUM, MIN, or MAX over a table with optional filters and grouping."""
    try:
        result = adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
        return {"ok": True, **result}
    except ValidationError as exc:
        return _error(str(exc))


@mcp.resource("schema://database")
def database_schema() -> str:
    """Full database schema snapshot as JSON."""
    return json.dumps(adapter.get_database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Schema for a single table as JSON."""
    try:
        return json.dumps(adapter.get_table_schema(table_name), indent=2)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run()
