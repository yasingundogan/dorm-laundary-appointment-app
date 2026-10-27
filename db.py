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

if __name__ == "__main__":
    for m in tum_makineler():
        print(m["machine_no"], m["machine_type"], m["out_of_order"])