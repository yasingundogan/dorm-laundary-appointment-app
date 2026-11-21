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
        select m.machine_id, m.machine_no, m.machine_type, m.out_of_order,
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
    try:
        cursor = conn.execute(
            "insert into students (student_name , student_surname , student_phone_no , student_mail , room_no , student_password_hash) values (?,?,?,?,?,?)",
            (ad, soyad, telefon, email, oda, sifre_hash)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

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
    

def haftalik_camasir_sayisi(student_id, zaman):
    conn = baglanti_al()
    try:
        sonuc = conn.execute("""
            select count(*)
            from appointments a
            join machines m on a.machine_id = m.machine_id
            where a.student_id = ?
              and a.status != 'cancelled'
              and m.machine_type = 'washer'
              and a.start_time >= date(?, 'weekday 0', '-6 days')
              and a.start_time <  date(?, 'weekday 0', '+1 days')
        """, (student_id, zaman , zaman)).fetchone()
        return sonuc[0]
    finally:
        conn.close()

def makine_musait_mi(machine_id, baslangic, bitis):
    conn = baglanti_al()
    try:
        cakisan = conn.execute("""
            select count(*)
            from appointments a
            join machines m on a.machine_id = m.machine_id
            where a.machine_id = ?
              and a.status = 'active'
              and a.start_time < ?
              and datetime(a.start_time, case when m.machine_type = 'dryer' then '+2 hours' else '+1 hour' end) > ?
        """, (machine_id, bitis, baslangic)).fetchone()[0]
        return cakisan == 0
    finally:
        conn.close()

def ogrenci_musait_mi(student_id, baslangic, bitis):
    conn = baglanti_al()
    try:
        cakisan = conn.execute("""
            select count(*)
            from appointments a
            join machines m on a.machine_id = m.machine_id
            where a.student_id = ?
              and a.status = 'active'
              and a.start_time < ?
              and datetime(a.start_time, case when m.machine_type = 'dryer' then '+2 hours' else '+1 hour' end) > ?
        """, (student_id, bitis, baslangic)).fetchone()[0]
        return cakisan == 0
    finally:
        conn.close()


def makine_getir(machine_id):
    conn = baglanti_al()
    makine = conn.execute(
        "select * from machines where machine_id = ?",
        (machine_id, )
    ).fetchone()
    conn.close()
    return makine

def randevu_ekle(student_id, machine_id, start_time, program):
    
    conn = baglanti_al()
    try:
        cursor = conn.execute(
            "insert into appointments (student_id, machine_id, start_time, program) values (?,?,?,?)",
            (student_id, machine_id, start_time, program)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


if __name__ == "__main__":
    print(makine_musait_mi(3, "2026-10-07 14:00:00", "2026-10-07 15:00:00"))  # aynı saat
    print(makine_musait_mi(3, "2026-10-07 15:00:00", "2026-10-07 16:00:00"))  # hemen sonrası
    print(makine_musait_mi(3, "2026-10-07 13:00:00", "2026-10-07 14:00:00"))  # hemen öncesi
    print(makine_musait_mi(3, "2026-10-07 13:00:00", "2026-10-07 15:00:00"))  # yarısı çakışıyor
    print(ogrenci_musait_mi(3, "2026-10-08 10:00:00", "2026-10-08 11:00:00")) # öğrenci 3'ün o saatte randevusu var
    print(ogrenci_musait_mi(3, "2026-10-08 12:00:00", "2026-10-08 13:00:00")) # yok