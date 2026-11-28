import os
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

import zaman

# Randevunun bitişi (end_time) kayıt anında kurallar.SURELER ile hesaplanıp yazılır; sorgular süre kuralını bilmez.
# "Şimdi" her zaman zaman.simdi()'den gelir; SQL'de datetime('now') kullanılmaz (sunucunun saat dilimine bağlı olurdu).

# Testler DB_PATH ile geçici bir veritabanı kullanır
DB_PATH = os.environ.get("DB_PATH", "camasirhane.db")


def baglanti_al():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _baglanti(conn=None):
    """Verilen bağlantıyı kullanır (işlem içindeyken); yoksa yeni açıp sonunda kapatır."""
    if conn is not None:
        yield conn
        return
    conn = baglanti_al()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def islem():
    """Yazma kilitli işlem: içindeki kontroller ve kayıt, başka bir istek araya girmeden yapılır.
    BEGIN IMMEDIATE ile aynı anda yalnızca bir istek randevu yazabilir; diğeri sırasını bekler."""
    conn = baglanti_al()
    conn.isolation_level = None  # BEGIN/COMMIT'i biz yönetiyoruz
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()


def gecmis_randevulari_tamamla():
    """Süresi dolmuş aktif randevuları 'completed' yapar. Gelmeme (no_show) görevli tarafından işaretlenir."""
    conn = baglanti_al()
    try:
        conn.execute(f"""
            update appointments
            set status = 'completed'
            where appointment_id in (
                select a.appointment_id from appointments a join machines m on m.machine_id = a.machine_id
                where a.status = 'active' and a.end_time <= ?)
        """, (zaman.simdi_metin(),))
        conn.commit()
    finally:
        conn.close()

def makine_durumlari(zaman, laundry_room_id=None):
    """Makinelerin verilen andaki durumu. laundry_room_id verilirse yalnızca o çamaşırhane."""
    conn = baglanti_al()
    makineler = conn.execute(f"""
        select m.machine_id, m.machine_no, m.machine_type, m.out_of_order,
               exists (
                   select 1
                   from appointments a
                   where a.machine_id = m.machine_id
                     and a.status = 'active'
                     and a.start_time <= ?                    -- başlangıç ≤ zaman
                     and a.end_time > ?                    -- bitiş > zaman
               ) as dolu
        from machines m
        where ? is null or m.laundry_room_id = ?
        order by m.machine_no
    """, (zaman, zaman, laundry_room_id, laundry_room_id)).fetchall()
    conn.close()
    return makineler

def ogrenci_ekle(ad, soyad, telefon, email, oda, sifre, laundry_room_id=1):
    sifre_hash = generate_password_hash(sifre) 
    conn = baglanti_al()
    try:
        cursor = conn.execute(
            "insert into students (student_name , student_surname , student_phone_no , student_mail , room_no , student_password_hash, laundry_room_id) values (?,?,?,?,?,?,?)",
            (ad, soyad, telefon, email, oda, sifre_hash, laundry_room_id)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def ogrenci_dogrula(email, sifre):
    conn = baglanti_al()
    ogrenci = conn.execute(
        "select * from students where lower(student_mail) = ?",  # eski karışık harfli kayıtlar da bulunsun
        (email, )
    ).fetchone()
    conn.close()

    if ogrenci is None:
        return None

    if check_password_hash(ogrenci["student_password_hash"] , sifre ):
        return ogrenci
    return None
    

def haftalik_camasir_sayisi(student_id, zaman, conn=None):
    with _baglanti(conn) as conn:
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

def makine_musait_mi(machine_id, baslangic, bitis, conn=None):
    with _baglanti(conn) as conn:
        cakisan = conn.execute(f"""
            select count(*)
            from appointments a
            where a.machine_id = ?
              and a.status = 'active'
              and a.start_time < ?
              and a.end_time > ?
        """, (machine_id, bitis, baslangic)).fetchone()[0]
        return cakisan == 0

def ogrenci_musait_mi(student_id, baslangic, bitis, conn=None):
    with _baglanti(conn) as conn:
        cakisan = conn.execute(f"""
            select count(*)
            from appointments a
            where a.student_id = ?
              and a.status = 'active'
              and a.start_time < ?
              and a.end_time > ?
        """, (student_id, bitis, baslangic)).fetchone()[0]
        return cakisan == 0


def makine_getir(machine_id):
    conn = baglanti_al()
    makine = conn.execute(
        "select * from machines where machine_id = ?",
        (machine_id, )
    ).fetchone()
    conn.close()
    return makine

def ogrenci_getir(student_id):
    conn = baglanti_al()
    try:
        return conn.execute(
            "select s.student_name, s.student_surname, s.student_mail, s.student_phone_no, s.room_no, s.laundry_room_id,"
            " l.dorm_name, l.block_name"
            " from students s join laundry_rooms l on l.laundry_room_id = s.laundry_room_id where s.student_id = ?",
            (student_id,)
        ).fetchone()
    finally:
        conn.close()


def ogrenci_randevulari(student_id):
    conn = baglanti_al()
    try:
        return conn.execute(f"""
            select a.appointment_id, a.start_time, a.end_time, a.program, a.status, a.cancelled_at,
                   a.cancelled_at > datetime(a.start_time, '-15 minutes') as son_dakika,  -- başlangıca 15 dk kala ya da sonra iptal
                   m.machine_no, m.machine_type
            from appointments a
            join machines m on a.machine_id = m.machine_id
            where a.student_id = ?
            order by a.start_time desc
        """, (student_id,)).fetchall()
    finally:
        conn.close()


def randevu_ekle(student_id, machine_id, start_time, end_time, program, conn=None):
    """conn verilirse (islem içinde) commit'i islem yapar. end_time: kurallar.bitis_saati ile hesaplanır."""
    kendi_baglantim = conn is None
    with _baglanti(conn) as conn:
        cursor = conn.execute(
            "insert into appointments (student_id, machine_id, start_time, end_time, program, created_at)"
            " values (?,?,?,?,?,?)",
            (student_id, machine_id, start_time, end_time, program, zaman.simdi_metin())
        )
        if kendi_baglantim:
            conn.commit()
        return cursor.lastrowid


# Makine adı SQL içinde birkaç yerde gerekiyor
_MAKINE_ADI = "(case m.machine_type when 'dryer' then 'Kurutma' else 'Çamaşır' end) || ' makinesi ' || m.machine_no"


def randevu_getir(appointment_id, conn=None):
    with _baglanti(conn) as conn:
        return conn.execute(f"""
            select a.*, m.machine_type, m.machine_no
            from appointments a join machines m on a.machine_id = m.machine_id
            where a.appointment_id = ?
        """, (appointment_id,)).fetchone()


def calisan_randevu(student_id, simdi, en_erken_bitis):
    """Başlamış ve bitişi en_erken_bitis'ten sonra olan en son randevu (çalışan ya da az önce biten)."""
    with _baglanti() as conn:
        return conn.execute("""
            select a.appointment_id, a.start_time, a.end_time, a.program, m.machine_no, m.machine_type
            from appointments a join machines m on a.machine_id = m.machine_id
            where a.student_id = ? and a.status in ('active', 'completed')
              and a.start_time <= ? and a.end_time > ?
            order by a.start_time desc limit 1
        """, (student_id, simdi, en_erken_bitis)).fetchone()


def randevu_iptal(appointment_id, conn):
    conn.execute(
        "update appointments set status = 'cancelled', cancelled_at = ? where appointment_id = ?",
        (zaman.simdi_metin(), appointment_id)
    )


def ogrenci_guncelle(student_id, ad, soyad, telefon, oda, laundry_room_id):
    conn = baglanti_al()
    try:
        conn.execute(
            "update students set student_name = ?, student_surname = ?, student_phone_no = ?, room_no = ?, laundry_room_id = ?"
            " where student_id = ?",
            (ad, soyad, telefon, oda, laundry_room_id, student_id)
        )
        conn.commit()
    finally:
        conn.close()


# ---- Çamaşırhaneler (yurt / blok) ----

def makineler(laundry_room_id):
    with _baglanti() as conn:
        return conn.execute(
            "select * from machines where laundry_room_id = ? order by machine_type desc, machine_no", (laundry_room_id,)
        ).fetchall()


def camasirhaneler():
    with _baglanti() as conn:
        return conn.execute("select * from laundry_rooms order by dorm_name, block_name").fetchall()


def gun_dolulugu(laundry_room_id, gun):
    """O gün (YYYY-MM-DD) çamaşırhanedeki aktif randevular: zaman şeridi için. Bitişi ertesi güne taşan olmaz."""
    with _baglanti() as conn:
        return conn.execute(f"""
            select a.machine_id, a.student_id, a.start_time, a.end_time
            from appointments a join machines m on a.machine_id = m.machine_id
            where m.laundry_room_id = ? and a.status = 'active' and date(a.start_time) = ?
        """, (laundry_room_id, gun)).fetchall()


# ---- Arıza bildirimleri ----

def ariza_bildir(machine_id, student_id, description, photo_path):
    """Aynı öğrenci aynı makine için ikinci açık bildirimi yaparsa sqlite3.IntegrityError."""
    conn = baglanti_al()
    try:
        conn.execute(
            "insert into fault_reports (machine_id, student_id, description, photo_path, created_at) values (?, ?, ?, ?, ?)",
            (machine_id, student_id, description, photo_path, zaman.simdi_metin())
        )
        conn.commit()
    finally:
        conn.close()


def acik_ariza_sayilari(laundry_room_id):
    """{machine_id: açık bildirim sayısı}: makine kartında "arıza bildirildi" göstermek için."""
    with _baglanti() as conn:
        return dict(conn.execute("""
            select f.machine_id, count(*) from fault_reports f join machines m on m.machine_id = f.machine_id
            where f.status = 'open' and m.laundry_room_id = ?
            group by f.machine_id
        """, (laundry_room_id,)).fetchall())


# ---- Kayıp eşya panosu ----

def kayip_esyalar(laundry_room_id):
    with _baglanti() as conn:
        return conn.execute(f"""
            select k.*, s.student_name,
                   case when m.machine_id is null then null else {_MAKINE_ADI} end as makine
            from lost_items k
            join students s on s.student_id = k.student_id
            left join machines m on m.machine_id = k.machine_id
            where k.laundry_room_id = ? and k.resolved_at is null
            order by k.created_at desc, k.item_id desc
        """, (laundry_room_id,)).fetchall()


def kayip_esya_ekle(laundry_room_id, student_id, machine_id, description):
    conn = baglanti_al()
    try:
        conn.execute(
            "insert into lost_items (laundry_room_id, student_id, machine_id, description, created_at) values (?, ?, ?, ?, ?)",
            (laundry_room_id, student_id, machine_id, description, zaman.simdi_metin())
        )
        conn.commit()
    finally:
        conn.close()


def kayip_esya_kapat(item_id, student_id):
    """Yalnızca ilanı veren kapatabilir. Kapatıldıysa True."""
    conn = baglanti_al()
    try:
        cur = conn.execute(
            "update lost_items set resolved_at = ?"
            " where item_id = ? and student_id = ? and resolved_at is null",
            (zaman.simdi_metin(), item_id, student_id)
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


# ---- Bildirimler ----

def bildirim_ekle(student_id, kind, message, link=None, conn=None):
    with _baglanti(conn) as c:
        c.execute(
            "insert into notifications (student_id, kind, message, link, created_at) values (?, ?, ?, ?, ?)",
            (student_id, kind, message, link, zaman.simdi_metin())
        )
        if conn is None:
            c.commit()


def bildirimleri_uret(student_id):
    """Zamanı gelen hatırlatmaları üretir. (kind, appointment_id) benzersiz olduğu için her biri bir kez oluşur:
    - hatirlatma: randevu 30 dakika içinde başlıyor
    - bitti: randevu son 24 saatte bitti, çamaşır makinede bekliyor"""
    simdi = zaman.simdi()
    an, yarim_saat_sonra, dun = (zaman.metin(t) for t in (simdi, simdi + timedelta(minutes=30), simdi - timedelta(days=1)))
    conn = baglanti_al()
    try:
        conn.execute(f"""
            insert or ignore into notifications (student_id, appointment_id, kind, message, link, created_at)
            select a.student_id, a.appointment_id, 'hatirlatma',
                   {_MAKINE_ADI} || ': randevun 30 dakika içinde başlıyor (saat ' || strftime('%H:%M', a.start_time) || ').',
                   '/profil', ?
            from appointments a join machines m on a.machine_id = m.machine_id
            where a.student_id = ? and a.status = 'active'
              and a.start_time > ? and a.start_time <= ?
        """, (an, student_id, an, yarim_saat_sonra))
        conn.execute(f"""
            insert or ignore into notifications (student_id, appointment_id, kind, message, link, created_at)
            select a.student_id, a.appointment_id, 'bitti',
                   {_MAKINE_ADI} || ': çamaşırın hazır, lütfen makineden al.',
                   '/profil', ?
            from appointments a join machines m on a.machine_id = m.machine_id
            where a.student_id = ? and a.status in ('active', 'completed')
              and a.end_time <= ? and a.end_time > ?
        """, (an, student_id, an, dun))
        conn.commit()
    finally:
        conn.close()


def okunmamis_bildirim_sayisi(student_id):
    with _baglanti() as conn:
        return conn.execute(
            "select count(*) from notifications where student_id = ? and read_at is null", (student_id,)
        ).fetchone()[0]


def bildirimler(student_id, limit=50):
    with _baglanti() as conn:
        return conn.execute(
            "select * from notifications where student_id = ? order by created_at desc, notification_id desc limit ?",
            (student_id, limit)
        ).fetchall()


def bildirimleri_okundu_yap(student_id):
    conn = baglanti_al()
    try:
        conn.execute(
            "update notifications set read_at = ? where student_id = ? and read_at is null",
            (zaman.simdi_metin(), student_id)
        )
        conn.commit()
    finally:
        conn.close()


# ---- Bekleme listesi ----

def siraya_gir(student_id, machine_id, start_time):
    conn = baglanti_al()
    try:
        conn.execute(
            "insert or ignore into waitlist (student_id, machine_id, start_time, created_at) values (?, ?, ?, ?)",
            (student_id, machine_id, start_time, zaman.simdi_metin())
        )
        conn.commit()
    finally:
        conn.close()


def siradan_cik(student_id, machine_id, start_time):
    conn = baglanti_al()
    try:
        conn.execute(
            "delete from waitlist where student_id = ? and machine_id = ? and start_time = ?",
            (student_id, machine_id, start_time)
        )
        conn.commit()
    finally:
        conn.close()


def siradaki_makineler(student_id, start_time):
    """Öğrencinin bu saatte sırada beklediği makinelerin id'leri."""
    with _baglanti() as conn:
        return {r[0] for r in conn.execute(
            "select machine_id from waitlist where student_id = ? and start_time = ?", (student_id, start_time)
        )}


def sirayi_bilgilendir(appointment_id, conn):
    """İptal edilen randevunun kapattığı saatleri bekleyenlere bildirim gönderir ve onları sıradan çıkarır.
    Kurutma 2 saat sürdüğü için 14:00 randevusu 14:00 ve 15:00 başlangıçlarını kapatır; ikisinin sırası da bilgilendirilir."""
    bekleyenler = conn.execute(f"""
        select w.waitlist_id, w.student_id, w.start_time, {_MAKINE_ADI} as makine
        from waitlist w
        join appointments a on a.appointment_id = ?
        join machines m on m.machine_id = a.machine_id
        where w.machine_id = a.machine_id
          and w.start_time >= a.start_time and w.start_time < a.end_time
          and w.start_time > ?
          and w.student_id != a.student_id
    """, (appointment_id, zaman.simdi_metin())).fetchall()
    for b in bekleyenler:
        saat = f"{b['start_time'][8:10]}.{b['start_time'][5:7]} {b['start_time'][11:16]}"
        bildirim_ekle(
            b["student_id"], "sira",
            f"{b['makine']}: sırada beklediğin {saat} boşaldı. İlk alan randevuyu alır.",
            f"/makineler?zaman={b['start_time'].replace(' ', '+')}",
            conn,
        )
        conn.execute("delete from waitlist where waitlist_id = ?", (b["waitlist_id"],))
    return len(bekleyenler)
