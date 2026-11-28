-- 001: Başlangıç şeması (eski schema.sql'in tamamı).
-- Bu dosya bir kez uygulandıktan sonra DEĞİŞTİRİLMEZ. Şema değişikliği = yeni numaralı dosya (002_..., 003_...).
-- Uygulamak için: python migrations.py

-- Yurt / blok çamaşırhaneleri. Devlet yurtlarında her bloğun (ya da yurdun) kendi çamaşırhanesi olur;
-- öğrenci yalnızca kendi çamaşırhanesinin makinelerini görür ve onlara randevu alır.
-- 1 numaralı çamaşırhane her kurulumda vardır: tek çamaşırhaneli yurtlar ek ayar gerektirmez.
create table laundry_rooms (
    laundry_room_id integer primary key,
    dorm_name       text not null,
    block_name      text not null,
    unique (dorm_name, block_name)
);
insert into laundry_rooms (laundry_room_id, dorm_name, block_name) values (1, 'Merkez Yurdu', 'A Blok');


-- Çamaşır ve kurutma makineleri tek tabloda, machine_type ile ayrılır.
-- "Boş / dolu" bilgisi burada saklanmaz, randevulardan hesaplanır.
-- out_of_order: görevlinin işaretlediği arıza durumu (0 = çalışıyor, 1 = arızalı).
create table machines (
    machine_id   integer primary key,
    laundry_room_id integer not null default 1 references laundry_rooms(laundry_room_id),
    machine_no   integer not null,
    machine_type text    not null check (machine_type in ('washer', 'dryer')),
    out_of_order integer not null default 0 check (out_of_order in (0, 1)),
    unique (laundry_room_id, machine_no, machine_type)   -- 2 nolu washer ile 2 nolu dryer ayrı makineler; her çamaşırhanede numaralar ayrı
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
    laundry_room_id  integer not null default 1 references laundry_rooms(laundry_room_id),
    student_password_hash text not null,
    unique (student_mail),
    unique (student_phone_no)
);


-- Randevular silinmez; iptal ve gelmeme durumları hak takibi ve analiz için saklanır.
-- Tarih/saat formatı: 'YYYY-MM-DD HH:MM:SS', İstanbul yerel saati (bkz. zaman.py)
-- program: çamaşırda 'colored' / 'white', kurutmada NULL.
-- (Çamaşırda programın zorunlu olması makine tipine bağlı; bu kural Python tarafında kontrol edilecek.)
create table appointments (
    appointment_id integer primary key,
    student_id     integer not null references students(student_id),
    machine_id     integer not null references machines(machine_id),
    start_time     text    not null,
    end_time       text    not null,   -- kayıtta kurallar.SURELER ile hesaplanır (kurutma 2 saat, renkli ve beyaz 1 saat)
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

-- Çakışma ve doluluk sorguları (makine + zaman aralığı) için
create index appointments_machine_time on appointments (machine_id, start_time, end_time);


-- Uygulama içi bildirimler (randevu hatırlatması, "çamaşırın bitti", sıradaki yer boşaldı).
-- kind + appointment_id benzersiz: aynı randevu için aynı bildirim iki kez üretilmez.
-- Sıra bildirimlerinde appointment_id NULL olur; NULL değerler benzersizlik kuralına takılmaz.
create table notifications (
    notification_id integer primary key,
    student_id      integer not null references students(student_id),
    appointment_id  integer references appointments(appointment_id),
    kind            text    not null check (kind in ('hatirlatma', 'bitti', 'sira')),
    message         text    not null,
    link            text,
    created_at      text    not null default (datetime('now', 'localtime')),
    read_at         text,
    unique (kind, appointment_id)
);
create index notifications_by_student on notifications (student_id, read_at);


-- Bekleme listesi: dolu bir makine + saat için sıraya giren öğrenciler.
-- O saati kapatan randevu iptal edilince sıradakilere bildirim gider; ilk alan randevuyu alır.
create table waitlist (
    waitlist_id integer primary key,
    student_id  integer not null references students(student_id),
    machine_id  integer not null references machines(machine_id),
    start_time  text    not null,
    created_at  text    not null default (datetime('now', 'localtime')),
    unique (student_id, machine_id, start_time)
);


-- Öğrencilerin arıza bildirimleri. Görevli onaylayınca makine out_of_order = 1 yapılır (görevli paneli ile).
-- photo_path: uploads/ klasöründeki rastgele adlı dosya; fotoğraf isteğe bağlı.
create table fault_reports (
    report_id   integer primary key,
    machine_id  integer not null references machines(machine_id),
    student_id  integer not null references students(student_id),
    description text    not null,
    photo_path  text,
    status      text    not null default 'open' check (status in ('open', 'confirmed', 'rejected')),
    created_at  text    not null default (datetime('now', 'localtime'))
);
-- Bir öğrenci aynı makine için aynı anda yalnızca bir açık bildirim yapabilir
create unique index one_open_report_per_student
    on fault_reports (machine_id, student_id)
    where status = 'open';


-- Kayıp eşya panosu: çamaşırhanede unutulan eşyalar. Her çamaşırhanenin panosu ayrı.
create table lost_items (
    item_id         integer primary key,
    laundry_room_id integer not null references laundry_rooms(laundry_room_id),
    student_id      integer not null references students(student_id),
    machine_id      integer references machines(machine_id),
    description     text    not null,
    created_at      text    not null default (datetime('now', 'localtime')),
    resolved_at     text
);
