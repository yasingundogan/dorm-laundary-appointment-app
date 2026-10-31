import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


def baglanti_al():
    conn = sqlite3.connect("camasirhane.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def tum_makineler():
    conn = baglanti_al()
    makineler = conn.execute(
        "select machine_type , machine_no , out_of_order from machines order by machine_no "
    ).fetchall()
    conn.close()
    return makineler

def makine_durumlari(zaman):
    conn = baglanti_al()
    makineler = conn.execute("""
        select m.machine_no, m.machine_type, m.out_of_order,
               exists (
                   select 1
                   from appointments a
                   where a.machine_id = m.machine_id
                     and a.status = 'active'
                     and a.start_time <= ?                    -- başlangıç ≤ zaman
                     and datetime(a.start_time, case when m.machine_type = 'dryer' then '+2 hours' else '+1 hour' end) > ?                    -- bitiş > zaman
               ) as dolu
        from machines m
        order by m.machine_no
    """, (zaman, zaman)).fetchall()
    conn.close()
    return makineler

def ogrenci_ekle(ad, soyad, telefon, email, oda, sifre):
    sifre_hash = generate_password_hash(sifre) 
    conn = baglanti_al()
    cursor = conn.execute(
        "insert into students (student_name , student_surname , student_phone_no , student_mail , room_no , student_password_hash) values (?,?,?,?,?,?)",
        (ad, soyad, telefon, email, oda, sifre_hash)
    )
    conn.commit()
    yeni_id = cursor.lastrowid
    conn.close()
    return yeni_id

def ogrenci_dogrula(email, sifre):
    conn = baglanti_al()
    ogrenci = conn.execute(
        "select * from students where student_mail = ?",
        (email, )
    ).fetchone()
    conn.close()

    if ogrenci is None:
        return None

    if check_password_hash(ogrenci["student_password_hash"] , sifre ):
        return ogrenci
    return None
    


if __name__ == "__main__":
    print(ogrenci_dogrula("ogrenci5@ornek.com", "test1234"))
    print(ogrenci_dogrula("ogrenci5@ornek.com", "yanlis"))
    print(ogrenci_dogrula("yok@ornek.com", "test1234"))