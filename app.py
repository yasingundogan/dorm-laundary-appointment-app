"""Uygulama kurulumu: ayarlar, güvenlik (CSRF), her sayfada ortak işler ve Blueprint'lerin kaydı.

Katmanlar:
  zaman.py     tek zaman kaynağı (Europe/Istanbul)
  kurallar.py  saf iş kuralları (süre, çalışma saatleri, hak, doğrulama)
  servis.py    iş akışları (kurallar + veritabanı + kilitli işlem)
  db.py        SQL sorguları
  web/         sayfalar (Blueprint'ler): auth, randevu, profil, bildirim, yurt
"""
import hmac
import os
import secrets

from flask import Flask, abort, request, session

import db
from web import auth, bildirim, profil, randevu, yurt

app = Flask(__name__)
# Ortam değişkeni yoksa her açılışta rastgele anahtar üretilir (sunucu yeniden başlayınca oturumlar kapanır).
# Yayında SECRET_KEY mutlaka sabit ve gizli bir değerle verilmeli.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
# Arıza fotoğrafları: static dışında, rastgele adlarla saklanır (adı tahmin edilip açılamasın)
app.config["UPLOAD_DIR"] = os.environ.get("UPLOAD_DIR", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # istek sınırı; fotoğraf en fazla 5 MB
# Deneme modu (ör. /makineler?demo=washer): yalnızca geliştirmede. Yayında FLASK_DEBUG/DEMO verilmez, kapalı kalır.
app.config["DEMO_ACIK"] = os.environ.get("FLASK_DEBUG") == "1" or os.environ.get("DEMO") == "1"

for blueprint in (auth.bp, randevu.bp, profil.bp, bildirim.bp, yurt.bp):
    app.register_blueprint(blueprint)


# ---- CSRF koruması: her POST formu oturumdaki gizli anahtarı geri göndermek zorunda ----
@app.before_request
def csrf_kontrol():
    if request.method == "POST" and app.config.get("CSRF_ACIK", True):
        beklenen = session.get("csrf")
        if not beklenen or not hmac.compare_digest(beklenen, request.form.get("csrf", "")):
            abort(400, "Form süresi doldu, sayfayı yenileyip tekrar deneyin.")


@app.context_processor
def csrf_alani():
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]
    return {"csrf_token": csrf_token}


# ---- Bildirimler: her sayfada zamanı gelen hatırlatmalar üretilir, üst çubukta okunmamış sayısı gösterilir ----
# shortcut: bildirimler sayfa açılınca üretilir; push/e-posta bildirimine geçince zamanlanmış göreve taşınmalı
@app.before_request
def bildirim_uret():
    if request.method == "GET" and session.get("student_id") and request.endpoint != "static":
        db.bildirimleri_uret(session["student_id"])


@app.context_processor
def bildirim_sayisi():
    if not session.get("student_id"):
        return {}
    return {"okunmamis_bildirim": db.okunmamis_bildirim_sayisi(session["student_id"])}


if __name__ == "__main__":
    # Debug ekranı tarayıcıdan kod çalıştırmaya izin verir; yalnızca geliştirmede FLASK_DEBUG=1 ile açılır
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5001)
