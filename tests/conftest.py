import sqlite3
from datetime import datetime

import pytest

from app import app
import db
import kurallar
import migrations
import zaman
from web import auth

# Bütün testlerde "şimdi" sabittir: 25 Kasım 2026 Çarşamba 12:00 (İstanbul).
# Böylece tarih içeren testler takvim ilerledikçe bozulmaz. Randevu penceresi bu anda 6 Aralık Pazar'a kadar açık.
SABIT_AN = datetime(2026, 11, 25, 12, 0, 0)


@pytest.fixture(autouse=True)
def sabit_zaman(monkeypatch):
    monkeypatch.setattr(zaman, "simdi", lambda: SABIT_AN)


def randevu_ekle(conn, student_id, machine_id, baslangic, program=None, status="active"):
    """Testler için doğrudan SQL ile randevu: bitiş, uygulamadaki gibi kurallar.bitis_saati ile hesaplanır."""
    tip = conn.execute("SELECT machine_type FROM machines WHERE machine_id = ?", (machine_id,)).fetchone()[0]
    bitis = kurallar.bitis_saati(baslangic, tip, program)
    rid = conn.execute(
        "INSERT INTO appointments (student_id, machine_id, start_time, end_time, program, status) VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, machine_id, zaman.metin(baslangic), zaman.metin(bitis), program, status)).lastrowid
    conn.commit()
    return rid


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_camasirhane.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    if hasattr(db, "DB_PATH"):
        monkeypatch.setattr(db, "DB_PATH", str(db_file))

    migrations.uygula(str(db_file), sessiz=True)  # test veritabanı da gerçek kurulum yoluyla kurulur
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    yield conn
    conn.close()


@pytest.fixture
def client(test_db):
    app.config["TESTING"] = True
    app.config["CSRF_ACIK"] = False  # CSRF test_guvenlik.py'de ayrıca açılıp denenir
    app.secret_key = "test-secret-key"
    auth._hatali_girisler.clear()
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