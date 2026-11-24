import sqlite3
import pytest


def test_g_database_constraints(test_db):
    # Invalid machine_type must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        test_db.execute(
            "INSERT INTO machines (machine_no, machine_type) VALUES (1, 'iron')"
        )

    test_db.execute(
        "INSERT INTO machines (machine_no, machine_type) VALUES (1, 'washer')"
    )
    test_db.execute(
        """
        INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no, student_password_hash)
        VALUES ('Ece', 'Demir', '05551234567', 'ece@ogrenci.edu.tr', 'C-301', 'scrypt:123')
        """
    )

    # Invalid program ('mixed') must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        test_db.execute(
            """
            INSERT INTO appointments (student_id, machine_id, start_time, program, status)
            VALUES (1, 1, '2026-12-01 10:00:00', 'mixed', 'active')
            """
        )

    # Duplicate active appointment on same machine and start_time must raise IntegrityError
    test_db.execute(
        """
        INSERT INTO appointments (student_id, machine_id, start_time, program, status)
        VALUES (1, 1, '2026-12-01 10:00:00', 'colored', 'active')
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        test_db.execute(
            """
            INSERT INTO appointments (student_id, machine_id, start_time, program, status)
            VALUES (1, 1, '2026-12-01 10:00:00', 'white', 'active')
            """
        )

    # Re-booking the same slot after cancellation must succeed
    test_db.execute("UPDATE appointments SET status = 'cancelled'")
    test_db.execute(
        """
        INSERT INTO appointments (student_id, machine_id, start_time, program, status)
        VALUES (1, 1, '2026-12-01 10:00:00', 'white', 'active')
        """
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 2