import sqlite3


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

if __name__ == "__main__":
    durumlar = makine_durumlari("2026-10-07 14:30:00")
    print("Toplam:", len(durumlar))
    print("Dolu:", sum(m["dolu"] for m in durumlar))