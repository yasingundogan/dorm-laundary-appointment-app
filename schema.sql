-- Yurt çamaşırhane randevu sistemi: veritabanı şeması
-- Çalıştırmak için (proje klasöründe):
--   sqlite3 camasirhane.db < schema.sql

PRAGMA foreign_keys = ON;

-- Dosya her çalıştığında tablolar sıfırdan kurulur.
-- Sıra önemli: başka tabloya bağlı olan (appointments) önce silinir.
drop table if exists appointments;
drop table if exists students;
drop table if exists machines;


-- Çamaşır ve kurutma makineleri tek tabloda, machine_type ile ayrılır.
-- "Boş / dolu" bilgisi burada saklanmaz, randevulardan hesaplanır.
-- out_of_order: görevlinin işaretlediği arıza durumu (0 = çalışıyor, 1 = arızalı).
create table machines (
    machine_id   integer primary key,
    machine_no   integer not null,
    machine_type text    not null check (machine_type in ('washer', 'dryer')),
    out_of_order integer not null default 0 check (out_of_order in (0, 1)),
    unique (machine_no, machine_type)   -- 2 nolu washer ile 2 nolu dryer ayrı makineler
);


-- Telefon ve oda numarası text: telefon 0 ile başlıyor, oda "B-204" gibi olabiliyor.
-- E-posta ve telefon ayrı ayrı benzersiz (birleşik unique değil).
create table students (
    student_id       integer primary key,
    student_name     text not null,
    student_surname  text not null,
    student_phone_no text not null,
    student_mail     text not null,
    room_no          text not null,
    student_password_hash text not null,
    unique (student_mail),
    unique (student_phone_no)
);


-- Randevular silinmez; iptal ve gelmeme durumları hak takibi ve analiz için saklanır.
-- Tarih/saat formatı: 'YYYY-MM-DD HH:MM:SS'
-- program: çamaşırda 'colored' / 'white', kurutmada NULL.
-- (Çamaşırda programın zorunlu olması makine tipine bağlı; bu kural Python tarafında kontrol edilecek.)
create table appointments (
    appointment_id integer primary key,
    student_id     integer not null references students(student_id),
    machine_id     integer not null references machines(machine_id),
    start_time     text    not null,
    created_at     text    not null default (datetime('now', 'localtime')),
    cancelled_at   text,
    program        text    check (program in ('colored', 'white')),
    status         text    not null default 'active'
                           check (status in ('active', 'cancelled', 'completed', 'no_show'))
);

-- Aynı makine + aynı başlangıç saatinde yalnızca bir AKTİF randevu olabilir.
-- İptal edilen randevular kurala dahil değil, böylece iptal edilen saat tekrar alınabilir.
create unique index one_active_appointment_per_slot
    on appointments (machine_id, start_time)
    where status = 'active';
