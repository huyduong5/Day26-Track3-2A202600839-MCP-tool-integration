import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "lab.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    grade REAL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, score) VALUES
    ('An Nguyen', 'A1', 88.5),
    ('Binh Tran', 'A1', 92.0),
    ('Chi Le', 'B2', 76.5),
    ('Dung Pham', 'B2', 84.0),
    ('Em Vu', 'A1', 95.5);

INSERT INTO courses (code, title, credits) VALUES
    ('CS101', 'Intro to Programming', 3),
    ('CS201', 'Data Structures', 4),
    ('MATH110', 'Discrete Math', 3);

INSERT INTO enrollments (student_id, course_id, grade) VALUES
    (1, 1, 90.0),
    (1, 2, 87.0),
    (2, 1, 94.0),
    (3, 3, 78.0),
    (4, 2, 82.0),
    (5, 1, 96.0);
"""


def create_database(db_path: Path | None = None) -> Path:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    database_path = create_database()
    print(f"Database created at {database_path}")
