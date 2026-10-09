import sqlite3
import random

random.seed(48)

conn = sqlite3.connect("camasirhane.db")   # veritabanı dosyasına bağlan
conn.execute("PRAGMA foreign_keys = ON")    # foreign key kontrolünü aç

with open("schema.sql", encoding="utf-8") as f:
    conn.executescript(f.read())



for num in range(1,31):
    conn.execute(
        "insert into machines (machine_no, machine_type) values (?, ?)",
        (num, "washer")
    )

for num in range(1,16):
    conn.execute(
        "insert into machines (machine_no, machine_type) values (?, ?)",
        (num, "dryer")
    )

first_names = ["Ayse", "Zeynep", "Elif", "Nisa", "Eylul", "Fatma" , "Busra" , "Maya"]
last_names = ["Yilmaz", "Kaya", "Demir", "Celik", "Sahin" , "Yildiz" , "Kara" , "Yildirim"]

for i in range(1, 1001):
    ad = random.choice(first_names)
    soyad = random.choice(last_names)
    email = f"ogrenci{i}@ornek.com"
    telefon = f"0532{i:07d}"

    blok = random.choice(["A", "B", "C", "D"])
    kat = random.randint(1, 5)
    oda = random.randint(1, 20)
    oda_no = f"{blok}-{kat}{oda:02d}"      # örnek: "B-204"

    conn.execute(
        "insert into students (student_name, student_surname, student_mail , student_phone_no , room_no ) values (?, ?, ?, ?, ?)",
        (ad , soyad , email , telefon , oda_no )
    )

gunler = [
    ("2026-10-05", False),   # pazartesi
    ("2026-10-06", False),
    ("2026-10-07", False),
    ("2026-10-08", False),
    ("2026-10-09", False),   # cuma
    ("2026-10-10", True),    # cumartesi
    ("2026-10-11", True),    # pazar
]



eklenen = 0
atlanan = 0

for student_id in range(1, 1001):
    yikama_sayisi = random.choice([0, 1, 2])
    for _ in range(yikama_sayisi):
        gun, hafta_sonu = random.choice(gunler)

        if hafta_sonu:
            saat = random.randint(9, 16)
        else:
            saat = random.randint(8 , 19)

        start_time = f"{gun} {saat:02d}:00:00"
        machine_id = random.randint(1 ,30)                            # 1-30 arası çamaşır makinesi
        program = random.choice(['white' , 'colored'])                               # "colored" ya da "white"

        try:
            conn.execute(
                "insert into appointments (student_id, machine_id, start_time, program) values (?, ?, ?, ?)",
                (student_id , machine_id , start_time , program)
            )
            eklenen += 1
        except sqlite3.IntegrityError:
            atlanan += 1

print("Eklenen randevu:", eklenen)
print("Çakışma yüzünden atlanan:", atlanan)

sonuc = conn.execute("select count(*) from machines").fetchone()
print(sonuc)

ogrenciler = conn.execute("select student_name from students limit 5").fetchall()
for ogrenci in ogrenciler:
    print(ogrenci)

print(conn.execute("select min(start_time), max(start_time) from appointments").fetchone())




conn.commit()   # değişiklikleri kaydet
conn.close()    # bağlantıyı kapat

