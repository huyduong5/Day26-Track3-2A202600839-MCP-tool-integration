import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SQLiteAdapter, ValidationError
from init_db import create_database


@pytest.fixture
def adapter(tmp_path):
    db_path = tmp_path / "test.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_list_tables(adapter):
    assert set(adapter.list_tables()) == {"students", "courses", "enrollments"}


def test_search_with_filter(adapter):
    result = adapter.search("students", filters={"cohort": "A1"})
    assert result["count"] == 3
    assert all(row["cohort"] == "A1" for row in result["rows"])


def test_search_pagination(adapter):
    result = adapter.search("students", limit=2, offset=1, order_by="id")
    assert result["count"] == 2


def test_insert_student(adapter):
    result = adapter.insert("students", {"name": "New Student", "cohort": "Z9", "score": 66.0})
    assert result["inserted"]["name"] == "New Student"
    assert result["inserted"]["id"] is not None


def test_aggregate_count(adapter):
    result = adapter.aggregate("students", metric="count")
    assert result["results"][0]["value"] == 5


def test_aggregate_avg_grouped(adapter):
    result = adapter.aggregate("students", metric="avg", column="score", group_by="cohort")
    groups = {item["group"]: item["value"] for item in result["results"]}
    assert "A1" in groups
    assert "B2" in groups


def test_unknown_table(adapter):
    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.search("does_not_exist")


def test_unknown_column(adapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.search("students", filters={"missing": "x"})


def test_empty_insert(adapter):
    with pytest.raises(ValidationError, match="at least one"):
        adapter.insert("students", {})


def test_invalid_operator(adapter):
    with pytest.raises(ValidationError, match="Unsupported operator"):
        adapter.search("students", filters={"cohort": {"op": "regex", "value": "A%"}})


def test_database_schema(adapter):
    schema = adapter.get_database_schema()
    assert len(schema["tables"]) == 3


def test_table_schema(adapter):
    schema = adapter.get_table_schema("courses")
    assert schema["table"] == "courses"
    assert any(col["name"] == "code" for col in schema["columns"])
