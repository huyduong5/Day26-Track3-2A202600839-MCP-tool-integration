import re
import sqlite3
from pathlib import Path
from typing import Any

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}
ALLOWED_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "like", "in"}
OPERATOR_SQL = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
}


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _validate_identifier(self, name: str, kind: str) -> str:
        if not name or not IDENTIFIER_RE.match(name):
            raise ValidationError(f"Invalid {kind}: {name!r}")
        return name

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def _ensure_table(self, table: str) -> str:
        table = self._validate_identifier(table, "table")
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table!r}")
        return table

    def _table_columns(self, table: str) -> list[str]:
        table = self._ensure_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row["name"] for row in rows]

    def _ensure_columns(self, table: str, columns: list[str]) -> list[str]:
        valid = set(self._table_columns(table))
        validated = []
        for column in columns:
            column = self._validate_identifier(column, "column")
            if column not in valid:
                raise ValidationError(f"Unknown column {column!r} in table {table!r}")
            validated.append(column)
        return validated

    def get_table_schema(self, table: str) -> dict[str, Any]:
        table = self._ensure_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ],
        }

    def get_database_schema(self) -> dict[str, Any]:
        return {
            "tables": [self.get_table_schema(table) for table in self.list_tables()],
        }

    def _normalize_filter(self, column: str, spec: Any) -> tuple[str, str, Any]:
        column = self._validate_identifier(column, "column")
        if isinstance(spec, dict):
            operator = spec.get("op", "eq")
            value = spec.get("value")
        else:
            operator = "eq"
            value = spec

        if operator not in ALLOWED_OPERATORS:
            raise ValidationError(f"Unsupported operator: {operator!r}")

        if operator == "in":
            if not isinstance(value, (list, tuple)) or not value:
                raise ValidationError("Operator 'in' requires a non-empty list value")

        return column, operator, value

    def _build_where(self, table: str, filters: dict[str, Any] | None) -> tuple[str, list[Any]]:
        if not filters:
            return "", []

        self._ensure_columns(table, list(filters.keys()))
        clauses: list[str] = []
        params: list[Any] = []

        for column, spec in filters.items():
            col, operator, value = self._normalize_filter(column, spec)
            if operator == "in":
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{col} {OPERATOR_SQL[operator]} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table = self._ensure_table(table)
        selected = self._ensure_columns(table, columns) if columns else self._table_columns(table)

        where_sql, params = self._build_where(table, filters)
        select_sql = ", ".join(selected)
        sql = f"SELECT {select_sql} FROM {table}{where_sql}"

        if order_by:
            order_col = self._ensure_columns(table, [order_by])[0]
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {order_col} {direction}"

        if limit < 0 or offset < 0:
            raise ValidationError("limit and offset must be non-negative")

        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table,
            "columns": selected,
            "count": len(rows),
            "rows": [dict(row) for row in rows],
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table = self._ensure_table(table)
        if not values:
            raise ValidationError("Insert requires at least one column value")

        columns = self._ensure_columns(table, list(values.keys()))
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.connect() as conn:
            cursor = conn.execute(sql, [values[col] for col in columns])
            conn.commit()
            row_id = cursor.lastrowid
            if row_id:
                row = conn.execute(f"SELECT * FROM {table} WHERE rowid = ?", (row_id,)).fetchone()
                return {"table": table, "inserted": dict(row) if row else {"id": row_id, **values}}

        return {"table": table, "inserted": values}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        table = self._ensure_table(table)
        metric = metric.lower()
        if metric not in ALLOWED_METRICS:
            raise ValidationError(f"Unsupported metric: {metric!r}")

        if metric == "count":
            target = "*"
        else:
            if not column:
                raise ValidationError(f"Metric {metric!r} requires a column")
            target = self._ensure_columns(table, [column])[0]

        where_sql, params = self._build_where(table, filters)
        select_parts = []
        group_sql = ""

        if group_by:
            group_col = self._ensure_columns(table, [group_by])[0]
            select_parts.append(group_col)
            group_sql = f" GROUP BY {group_col}"

        if metric == "count":
            select_parts.append("COUNT(*) AS value")
        else:
            select_parts.append(f"{metric.upper()}({target}) AS value")

        sql = f"SELECT {', '.join(select_parts)} FROM {table}{where_sql}{group_sql}"

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            item = {"value": row["value"]}
            if group_by:
                item["group"] = row[group_by]
            results.append(item)

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "results": results,
        }
