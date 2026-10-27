from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "resumeforge.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the app's SQLite database."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    """Commit on success and always close the SQLite connection."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Create the schema and insert demo students on the first run."""
    with db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                roll_no TEXT NOT NULL UNIQUE,
                branch TEXT NOT NULL,
                cgpa REAL NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                summary TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                project_title TEXT NOT NULL,
                project_summary TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            """
        )

        count = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            connection.executemany(
                """INSERT INTO students
                   (id, name, roll_no, branch, cgpa, email, phone, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (1, "Aarav Raman", "CSE2026-014", "Computer Science", 8.7,
                     "aarav@example.test", "+91 90000 10001",
                     "Computer Science student interested in backend development and secure software."),
                    (2, "Meera Nair", "CSE2026-027", "Computer Science", 9.1,
                     "meera@example.test", "+91 90000 10002",
                     "Computer Science student focused on data systems, Python, and application development."),
                    (3, "Kabir Shah", "ECE2026-033", "Electronics and Communication", 8.3,
                     "kabir@example.test", "+91 90000 10003",
                     "Engineering student interested in embedded systems and practical problem solving."),
                ],
            )
            connection.executemany(
                "INSERT INTO skills (student_id, skill_name) VALUES (?, ?)",
                [
                    (1, "Python"), (1, "Flask"), (1, "SQL"), (1, "Git"),
                    (2, "Python"), (2, "JavaScript"), (2, "PostgreSQL"), (2, "REST APIs"),
                    (3, "C++"), (3, "Embedded C"), (3, "Arduino"), (3, "Linux"),
                ],
            )
            connection.executemany(
                """INSERT INTO projects (student_id, project_title, project_summary)
                   VALUES (?, ?, ?)""",
                [
                    (1, "Campus Resource Portal", "A Flask application for browsing campus resources."),
                    (1, "Log Analyzer", "A Python utility that summarizes structured application logs."),
                    (2, "Study Planner", "A web app for organizing coursework and deadlines."),
                    (2, "Inventory API", "A REST API backed by a relational database."),
                    (3, "Sensor Dashboard", "A small dashboard for displaying sensor readings."),
                    (3, "Line-Following Rover", "A microcontroller project using sensor input and motor control."),
                ],
            )


def list_students() -> list[dict[str, Any]]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, roll_no, branch, cgpa FROM students ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def get_student(student_id: int) -> dict[str, Any] | None:
    with db_connection() as connection:
        student_row = connection.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        if student_row is None:
            return None

        student = dict(student_row)
        student["skills"] = [
            row[0]
            for row in connection.execute(
                "SELECT skill_name FROM skills WHERE student_id = ? ORDER BY id",
                (student_id,),
            ).fetchall()
        ]
        student["projects"] = [
            dict(row)
            for row in connection.execute(
                "SELECT project_title, project_summary FROM projects WHERE student_id = ? ORDER BY id",
                (student_id,),
            ).fetchall()
        ]
        return student
