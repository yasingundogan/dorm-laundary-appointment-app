def test_b1_valid_login(client, registered_student):
    res = client.post(
        "/giris",
        data={
            "email": registered_student["email"],
            "password": registered_student["password"],
        },
    )
    assert res.status_code == 302
    assert "/makineler" in res.headers.get("Location", "")

    with client.session_transaction() as sess:
        assert "student_id" in sess
        assert sess["student_name"] == registered_student["first_name"]


def test_b2_wrong_password(client, registered_student):
    res = client.post(
        "/giris",
        data={"email": registered_student["email"], "password": "wrongpassword"},
    )
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "Giriş bilgileri hatalı." in html
    assert registered_student["email"] in html

    with client.session_transaction() as sess:
        assert "student_id" not in sess  # formun CSRF anahtarı oturumda kalabilir


def test_b3_nonexistent_email(client):
    res = client.post(
        "/giris",
        data={"email": "unknown@ogrenci.edu.tr", "password": "anypassword"},
    )
    assert res.status_code == 200
    assert "Giriş bilgileri hatalı." in res.get_data(as_text=True)


def test_b4_empty_form(client):
    res = client.post("/giris", data={"email": "", "password": ""})
    assert res.status_code == 200
    assert "Giriş bilgileri hatalı." in res.get_data(as_text=True)


def test_b5_logout(client, registered_student):
    client.post(
        "/giris",
        data={
            "email": registered_student["email"],
            "password": registered_student["password"],
        },
    )
    res = client.post("/cikis")
    assert res.status_code == 302
    assert "/giris" in res.headers.get("Location", "")

    with client.session_transaction() as sess:
        assert len(sess) == 0


def test_b6_session_contains_only_id_and_name(client, registered_student):
    client.post(
        "/giris",
        data={
            "email": registered_student["email"],
            "password": registered_student["password"],
        },
    )
    with client.session_transaction() as sess:
        assert set(sess.keys()) == {"student_id", "student_name"}