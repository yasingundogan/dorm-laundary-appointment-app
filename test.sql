-- Örnek veriler ve kural testleri
-- Çalıştırmak için (her seferinde şemayı sıfırdan kurup testleri çalıştır):
--   sqlite3 camasirhane.db < schema.sql && sqlite3 camasirhane.db < test.sql
--
-- Beklenen çıktı: 5 hata (aşağıda "BEKLENEN: HATA" yazan senaryolar), başka hata olmamalı.
-- Her test tek bir kuralı ihlal eder; diğer değerler geçerlidir.

PRAGMA foreign_keys = ON;   -- SQLite'ta foreign key kontrolü her bağlantıda ayrıca açılmalı
.headers on
.mode column


-- ========== 1. ÖRNEK VERİLER (hatasız eklenmeli) ==========

-- machine_id yazılmadı: SQLite 1, 2, 3, 4 diye kendisi verir.
-- out_of_order yazılmadı: default 0 olur.
insert into machines (machine_no, machine_type) values
    (1, 'washer'),
    (2, 'washer'),
    (3, 'washer'),
    (1, 'dryer');

insert into students (student_name, student_surname, student_phone_no, student_mail, room_no) values
    ('Ayse',   'Yilmaz', '05321234567', 'ayse@ornek.com',   'B-204'),
    ('Zeynep', 'Kaya',   '05559876543', 'zeynep@ornek.com', 'A-112');

-- Ayşe (student_id 1), 1 nolu çamaşır makinesi (machine_id 1), renkli.
-- status ve created_at yazılmadı: default değerler devreye girer.
insert into appointments (student_id, machine_id, start_time, program) values
    (1, 1, '2026-09-30 14:00:00', 'colored');


-- ========== 2. ÇAKIŞMA KURALI ==========

-- Zeynep, Ayşe'nin aktif randevusu varken aynı makine + aynı saati almaya çalışıyor.
-- BEKLENEN: HATA (one_active_appointment_per_slot)
insert into appointments (student_id, machine_id, start_time, program) values
    (2, 1, '2026-09-30 14:00:00', 'white');


-- ========== 3. SENARYOLAR ==========

-- a) Ayşe randevusunu iptal ediyor.
-- BEKLENEN: BAŞARILI (kayıt silinmez, status ve cancelled_at güncellenir)
update appointments
set status = 'cancelled',
    cancelled_at = datetime('2026-09-29 20:00:00')
where appointment_id = 1;

-- b) Zeynep aynı makine + aynı saati tekrar deniyor.
-- BEKLENEN: BAŞARILI (iptal edilen randevu index'e dahil değil)
insert into appointments (student_id, machine_id, start_time, program) values
    (2, 1, '2026-09-30 14:00:00', 'white');

-- c) Olmayan bir öğrenciye (student_id 99) randevu.
-- BEKLENEN: HATA (foreign key)
insert into appointments (student_id, machine_id, start_time, program) values
    (99, 3, '2026-10-05 14:00:00', 'white');

-- d) Kurutma makinesine (machine_id 4) programsız randevu.
-- BEKLENEN: BAŞARILI (program NULL kalır, check NULL'u reddetmez)
insert into appointments (student_id, machine_id, start_time) values
    (2, 4, '2026-10-05 14:00:00');

-- e) Geçersiz program değeri.
-- BEKLENEN: HATA (check: program)
insert into appointments (student_id, machine_id, start_time, program) values
    (2, 2, '2026-10-05 14:00:00', 'mixed');

-- f) Ayşe'nin e-postasıyla yeni öğrenci (telefon farklı).
-- BEKLENEN: HATA (unique: student_mail)
insert into students (student_name, student_surname, student_phone_no, student_mail, room_no) values
    ('Fatma', 'Yilmaz', '05321234569', 'ayse@ornek.com', 'B-204');

-- g) Ayşe'nin telefonuyla yeni öğrenci (e-posta farklı).
-- BEKLENEN: HATA (unique: student_phone_no)
insert into students (student_name, student_surname, student_phone_no, student_mail, room_no) values
    ('Fatma', 'Yilmaz', '05321234567', 'ayse.yilmaz@ornek.com', 'B-204');

--test için eklenen iptaller
insert into appointments (student_id , machine_id, start_time , cancelled_at , status ) values ( 1 , 2 , '2026-10-06 10:00:00' , '2026-10-06 09:00:00' , 'cancelled' );
insert into appointments (student_id , machine_id, start_time , cancelled_at , status ) values ( 2 , 3 , '2026-10-06 11:00:00' , '2026-10-06 10:50:00'  , 'cancelled' );

-- ========== 4. SON DURUM ==========
-- Beklenen: 2 öğrenci; 5 randevu (3 iptal, Zeynep aktif, Zeynep kurutma aktif)

select * from students;
select appointment_id, student_id, machine_id, start_time, program, status from appointments;
