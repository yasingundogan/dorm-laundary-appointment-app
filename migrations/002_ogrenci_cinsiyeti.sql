-- 002: Öğrencinin cinsiyeti (isteğe bağlı). Yalnızca anonim profil görselini seçmek için kullanılır.
-- NULL = belirtilmemiş: nötr görsel gösterilir. KVKK: zorunlu değildir, öğrenci istediği zaman boşaltabilir.
alter table students add column gender text check (gender in ('male', 'female'));
