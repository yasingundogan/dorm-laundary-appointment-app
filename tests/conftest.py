import sqlite3
import pytest
from app import app
import db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_camasirhane.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    if hasattr(db, "DB_PATH"):
        monkeypatch.setattr(db, "DB_PATH", str(db_file))

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    yield conn
    conn.close()


@pytest.fixture
def client(test_db):
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"
    with app.test_client() as c:
        yield c


@pytest.fixture
def registered_student(client):
    data = {
        "first_name": "Emre",
        "last_name": "Kahraman",
        "email": "emre@ogrenci.edu.tr",
        "phone": "05551112233",
        "room": "B-204",
        "password": "password123",
        "confirm_password": "password123",
    }
    client.post("/kayit", data=data)
    return data