"""Web katmanı: her dosya bir Blueprint (auth, randevu, profil, bildirim, yurt).
Sayfalar formu okur, servis.py'yi çağırır, sonucu gösterir; iş kuralı içermez."""
from functools import wraps

from flask import current_app, redirect, request, session, url_for

import servis


def giris_gerekli(gorunum):
    """Giriş yapılmamışsa giriş sayfasına yönlendirir."""
    @wraps(gorunum)
    def sarmal(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("auth.giris"))
        return gorunum(*args, **kwargs)
    return sarmal


def durum_penceresi():
    """Ana ekran ve profilin altındaki çamaşır durum penceresi için veri (yoksa None).
    Geliştirmede ?demo=washer|dryer&kalan=SANIYE ile sahte bir çamaşır gösterilir (veritabanına yazılmaz)."""
    student_id = session.get("student_id")
    if not student_id:
        return None
    demo = request.args.get("demo")
    if demo in ("washer", "dryer") and current_app.config.get("DEMO_ACIK"):
        kalan = request.args.get("kalan", default=20, type=int)
        return servis.demo_yikama(student_id, demo, max(0, min(kalan, 7200)))
    return servis.calisan_yikama(student_id)
