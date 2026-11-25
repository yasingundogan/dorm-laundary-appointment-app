import db


def setup_machines_and_appointments(conn):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no, student_password_hash)
        VALUES ('Test', 'Student', '05550000001', 'test@ogrenci.edu.tr', 'B-101', 'scrypt:test')
        """
    )
    s_id = cur.lastrowid

    # Washer #1, Dryer #1, and Out-of-Order Washer #2
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (1, 'washer', 0)"
    )
    w_id = cur.lastrowid
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (1, 'dryer', 0)"
    )
    d_id = cur.lastrowid
    cur.execute(
        "INSERT INTO machines (machine_no, machine_type, out_of_order) VALUES (2, 'washer', 1)"
    )

    # Active appointments at 14:00:00 (end_time is stored: +1h for colored washer, +2h for dryer)
    cur.execute(
        """
        INSERT INTO appointments (student_id, machine_id, start_time, end_time, program, status)
        VALUES (?, ?, '2026-11-18 14:00:00', '2026-11-18 15:00:00', 'colored', 'active')
        """,
        (s_id, w_id),
    )
    cur.execute(
        """
        INSERT INTO appointments (student_id, machine_id, start_time, end_time, program, status)
        VALUES (?, ?, '2026-11-18 14:00:00', '2026-11-18 16:00:00', NULL, 'active')
        """,
        (s_id, d_id),
    )
    conn.commit()
    return w_id, d_id


def status_map(timestamp):
    return {
        (m["machine_type"], m["machine_no"]): m["dolu"]
        for m in db.makine_durumlari(timestamp)
    }


def test_c1_c4_status_by_time(test_db):
    setup_machines_and_appointments(test_db)

    # C1: 14:00:00 -> Both busy
    s_1400 = status_map("2026-11-18 14:00:00")
    assert s_1400[("washer", 1)] == 1
    assert s_1400[("dryer", 1)] == 1

    # C2: 14:30:00 -> Both busy
    s_1430 = status_map("2026-11-18 14:30:00")
    assert s_1430[("washer", 1)] == 1
    assert s_1430[("dryer", 1)] == 1

    # C3: 15:00:00 -> Washer free (0), Dryer busy (1)
    s_1500 = status_map("2026-11-18 15:00:00")
    assert s_1500[("washer", 1)] == 0
    assert s_1500[("dryer", 1)] == 1

    # C4: 16:00:00 -> Both free
    s_1600 = status_map("2026-11-18 16:00:00")
    assert s_1600[("washer", 1)] == 0
    assert s_1600[("dryer", 1)] == 0


def test_c5_cancelled_appointment_shows_available(test_db):
    w_id, _ = setup_machines_and_appointments(test_db)
    test_db.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE machine_id = ?", (w_id,)
    )
    test_db.commit()

    s_1415 = status_map("2026-11-18 14:15:00")
    assert s_1415[("washer", 1)] == 0


def test_c6_out_of_order_machine_on_page(client, test_db):
    setup_machines_and_appointments(test_db)
    res = client.get("/makineler")
    assert res.status_code == 200
    assert "Arızalı" in res.get_data(as_text=True)


def test_c7_sql_injection_protection(client, test_db):
    res = client.get("/makineler?zaman=' or '1'='1")
    assert res.status_code == 200


def test_c8_no_book_button_when_logged_out(client, test_db):
    setup_machines_and_appointments(test_db)
    res = client.get("/makineler")
    assert "Randevu al" not in res.get_data(as_text=True)