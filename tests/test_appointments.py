import pytest


@pytest.fixture
def logged_in_client(client, registered_student, test_db):
    client.post(
        "/giris",
        data={
            "email": registered_student["email"],
            "password": registered_student["password"],
        },
    )
    cur = test_db.cursor()
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
    b_id = cur.lastrowid
    test_db.commit()
    return client, {"washer": w_id, "dryer": d_id, "broken": b_id}


def test_f1_book_without_login(client, test_db):
    res = client.post(
        "/randevu",
        data={
            "machine_id": 1,
            "start_time": "2026-12-02 10:00:00",
            "program": "colored",
        },
    )
    assert res.status_code == 302
    assert "/giris" in res.headers.get("Location", "")
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0


def test_f2_valid_washer_appointment(logged_in_client, test_db):
    client, m = logged_in_client
    res = client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-02 10:00:00",
            "program": "colored",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    record = test_db.execute(
        "SELECT * FROM appointments WHERE machine_id = ?", (m["washer"],)
    ).fetchone()
    assert record is not None
    assert record["program"] == "colored"


def test_f3_valid_dryer_appointment(logged_in_client, test_db):
    client, m = logged_in_client
    client.post(
        "/randevu",
        data={"machine_id": m["dryer"], "start_time": "2026-12-02 10:00:00"},
    )
    record = test_db.execute(
        "SELECT * FROM appointments WHERE machine_id = ?", (m["dryer"],)
    ).fetchone()
    assert record is not None
    assert record["program"] is None


@pytest.mark.parametrize(
    "timestamp, machine_type, program",
    [
        ("2020-01-01 10:00:00", "washer", "colored"),  # F4: Past timestamp
        ("2026-12-02 07:00:00", "washer", "colored"),  # F5: Weekday too early
        ("2026-12-02 20:00:00", "washer", "colored"),  # F5: Weekday too late
        ("2026-12-02 19:00:00", "dryer", None),        # F6: Weekday 19:00 dryer (ends at 21:00)
        ("2026-12-05 08:00:00", "washer", "colored"),  # F7: Weekend too early
        ("2026-12-05 16:00:00", "dryer", None),        # F7: Weekend 16:00 dryer
        ("2026-12-02 10:00:00", "broken", "colored"),  # F8: Out-of-order machine
        ("2026-12-02 10:00:00", "washer", ""),         # F9: Missing program
        ("2026-12-02 10:00:00", "washer", "mixed"),    # F9: Invalid program ('mixed')
    ],
)
def test_f4_f9_rule_violations(
    logged_in_client, test_db, timestamp, machine_type, program
):
    client, m = logged_in_client
    payload = {"machine_id": m[machine_type], "start_time": timestamp}
    if program is not None:
        payload["program"] = program

    client.post("/randevu", data=payload)
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0


def test_f10_f11_weekly_quota_rules(logged_in_client, test_db):
    client, m = logged_in_client
    client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-01 10:00:00",
            "program": "colored",
        },
    )
    client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-02 10:00:00",
            "program": "white",
        },
    )

    # F10: 3rd washer appointment in the same week must be rejected
    client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-03 10:00:00",
            "program": "colored",
        },
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 2

    # F11: 3rd appointment as a dryer must be accepted
    client.post(
        "/randevu",
        data={"machine_id": m["dryer"], "start_time": "2026-12-03 10:00:00"},
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 3


def test_f12_f15_conflict_scenarios(logged_in_client, test_db):
    client, m = logged_in_client
    # Dryer booked at 14:00 (ends at 16:00)
    client.post(
        "/randevu",
        data={"machine_id": m["dryer"], "start_time": "2026-12-02 14:00:00"},
    )

    # F12/F13: Same dryer at 15:00 -> Must be rejected (2-hour overlap)
    client.post(
        "/randevu",
        data={"machine_id": m["dryer"], "start_time": "2026-12-02 15:00:00"},
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 1

    # F14: Student has dryer 14:00-16:00, tries booking washer at 15:00 -> Must be rejected
    client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-02 15:00:00",
            "program": "colored",
        },
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 1

    # F15: Washer at 16:00 (exact end time) -> Must be accepted
    client.post(
        "/randevu",
        data={
            "machine_id": m["washer"],
            "start_time": "2026-12-02 16:00:00",
            "program": "colored",
        },
    )
    assert test_db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 2


def test_f16_invalid_machine_and_malformed_time(logged_in_client):
    client, _ = logged_in_client
    res1 = client.post(
        "/randevu",
        data={
            "machine_id": 999,
            "start_time": "2026-12-02 10:00:00",
            "program": "colored",
        },
        follow_redirects=True,
    )
    assert res1.status_code == 200

    res2 = client.post(
        "/randevu",
        data={
            "machine_id": 1,
            "start_time": "invalid-timestamp",
            "program": "colored",
        },
        follow_redirects=True,
    )
    assert res2.status_code == 200