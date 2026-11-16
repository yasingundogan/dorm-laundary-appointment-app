import pytest


def valid_form(**overrides):
    data = {
        "first_name": "Ali",
        "last_name": "Veli",
        "email": "ali@ogrenci.edu.tr",
        "phone": "05559998877",
        "room": "A-102",
        "password": "strongpassword1",
        "confirm_password": "strongpassword1",
    }
    data.update(overrides)
    return data


def test_a1_valid_registration(client, test_db):
    res = client.post("/kayit", data=valid_form())
    assert res.status_code == 302
    assert "/giris" in res.headers.get("Location", "")

    student = test_db.execute(
        "SELECT * FROM students WHERE student_mail = ?", ("ali@ogrenci.edu.tr",)
    ).fetchone()
    assert student is not None
    assert student["student_name"] == "Ali"
    assert student["student_surname"] == "Veli"
    assert student["student_phone_no"] == "05559998877"
    assert student["room_no"] == "A-102"


def test_a2_password_is_hashed(client, test_db):
    client.post("/kayit", data=valid_form())
    student = test_db.execute(
        "SELECT student_password_hash FROM students WHERE student_mail = ?",
        ("ali@ogrenci.edu.tr",),
    ).fetchone()
    assert student is not None
    assert student["student_password_hash"].startswith("scrypt:")
    assert student["student_password_hash"] != "strongpassword1"


def test_a3_duplicate_email(client, registered_student):
    res = client.post(
        "/kayit",
        data=valid_form(email=registered_student["email"], phone="05000000000"),
    )
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "Bu e-posta veya telefon numarası zaten kayıtlı" in html
    assert registered_student["email"] in html


def test_a4_duplicate_phone(client, registered_student):
    res = client.post(
        "/kayit",
        data=valid_form(
            email="different@ogrenci.edu.tr", phone=registered_student["phone"]
        ),
    )
    assert res.status_code == 200
    assert "Bu e-posta veya telefon numarası zaten kayıtlı" in res.get_data(
        as_text=True
    )


def test_a5_short_password(client):
    res = client.post(
        "/kayit", data=valid_form(password="1234567", confirm_password="1234567")
    )
    assert res.status_code == 200
    assert "Şifre 8 karakterden az olamaz." in res.get_data(as_text=True)


def test_a6_mismatched_passwords(client):
    res = client.post(
        "/kayit", data=valid_form(password="password123", confirm_password="password456")
    )
    assert res.status_code == 200
    assert "Şifreler eşleşmiyor." in res.get_data(as_text=True)


@pytest.mark.parametrize(
    "missing_fields",
    [
        {"phone": None},     # A7: phone omitted
        {"phone": ""},       # A8: phone empty string
        {"phone": "   "},    # A9: phone whitespace only
        {"first_name": ""},  # A10: first_name empty
    ],
)
def test_a7_a10_empty_fields(client, missing_fields):
    form = valid_form()
    for key, val in missing_fields.items():
        if val is None:
            form.pop(key, None)
        else:
            form[key] = val
    res = client.post("/kayit", data=form)
    assert res.status_code == 200
    assert "Boş alan bırakılamaz." in res.get_data(as_text=True)


def test_a11_valid_registration_after_error(client):
    client.post(
        "/kayit", data=valid_form(password="short", confirm_password="short")
    )
    res = client.post("/kayit", data=valid_form())
    assert res.status_code == 302


def test_a12_get_registration_page(client):
    res = client.get("/kayit")
    assert res.status_code == 200
    assert "<form" in res.get_data(as_text=True)