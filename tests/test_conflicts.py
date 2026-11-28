import pytest
import db


@pytest.fixture
def conflict_data(test_db):
    cur = test_db.cursor()
    cur.execute(
        """
        INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no, student_password_hash)
        VALUES ('Ali', 'Kaya', '05550000002', 'ali.kaya@ogrenci.edu.tr', 'A-101', 'scrypt:x')
        """
    )
    s_id = cur.lastrowid
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (1, 'washer', 0)"
    )
    m_id = cur.lastrowid

    # Active washer appointment from 14:00:00 to 15:00:00
    cur.execute(
        """
        INSERT INTO appointments (student_id, machine_id, start_time, end_time, program, status)
        VALUES (?, ?, '2026-11-18 14:00:00', '2026-11-18 15:00:00', 'colored', 'active')
        """,
        (s_id, m_id),
    )
    test_db.commit()
    return s_id, m_id


@pytest.mark.parametrize(
    "start_time, end_time, expected",
    [
        ("2026-11-18 14:00:00", "2026-11-18 15:00:00", False),  # D1: Exact overlap
        ("2026-11-18 13:00:00", "2026-11-18 14:00:00", True),   # D2: Immediately before
        ("2026-11-18 15:00:00", "2026-11-18 16:00:00", True),   # D3: Immediately after
        ("2026-11-18 13:00:00", "2026-11-18 15:00:00", False),  # D4: Partial overlap
        ("2026-11-18 14:30:00", "2026-11-18 14:45:00", False),  # D5: Nested inside
        ("2026-11-18 12:00:00", "2026-11-18 17:00:00", False),  # D6: Fully encloses
    ],
)
def test_d1_d6_availability_checks(conflict_data, start_time, end_time, expected):
    s_id, m_id = conflict_data
    assert db.makine_musait_mi(m_id, start_time, end_time) is expected
    assert db.ogrenci_musait_mi(s_id, start_time, end_time) is expected


def test_d7_cancelled_appointment_does_not_conflict(test_db, conflict_data):
    s_id, m_id = conflict_data
    test_db.execute("UPDATE appointments SET status = 'cancelled'")
    test_db.commit()
    assert db.makine_musait_mi(m_id, "2026-11-18 14:00:00", "2026-11-18 15:00:00") is True
    assert db.ogrenci_musait_mi(s_id, "2026-11-18 14:00:00", "2026-11-18 15:00:00") is True


def test_e1_e4_weekly_washer_quota(test_db):
    cur = test_db.cursor()
    cur.execute(
        """
        INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no, student_password_hash)
        VALUES ('Ali', 'Kaya', '05550000003', 'quota@ogrenci.edu.tr', 'A-101', 'scrypt:x')
        """
    )
    s_id = cur.lastrowid
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (1, 'washer', 0)"
    )
    w_id = cur.lastrowid
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (1, 'dryer', 0)"
    )
    d_id = cur.lastrowid

    appointments = [
        (s_id, w_id, "2026-11-16 10:00:00", "2026-11-16 11:00:00", "colored", "active"),     # Mon washer (counted)
        (s_id, w_id, "2026-11-18 10:00:00", "2026-11-18 12:00:00", "white", "active"),       # Wed washer (counted)
        (s_id, d_id, "2026-11-17 10:00:00", "2026-11-17 12:00:00", None, "active"),          # Tue dryer (not counted)
        (s_id, w_id, "2026-11-19 10:00:00", "2026-11-19 11:00:00", "colored", "cancelled"),  # Thu cancelled (not counted)
    ]
    cur.executemany(
        "INSERT INTO appointments (student_id, machine_id, start_time, end_time, program, status) VALUES (?, ?, ?, ?, ?, ?)",
        appointments,
    )
    test_db.commit()

    assert db.haftalik_camasir_sayisi(s_id, "2026-11-18 12:00:00") == 2  # E1
    assert db.haftalik_camasir_sayisi(s_id, "2026-11-22 16:00:00") == 2  # E2 (Sunday, same week)
    assert db.haftalik_camasir_sayisi(s_id, "2026-11-23 09:00:00") == 0  # E3 (Monday, next week)
    assert db.haftalik_camasir_sayisi(s_id, "2026-11-15 20:00:00") == 0  # E4 (Previous week)