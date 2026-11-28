-- 003: 002'de eklenen cinsiyet sütunu kaldırılır. Profil görseli herkes için tek bir anonim siluet oldu;
-- kullanılmayan kişisel veri tutulmaz (KVKK: veri en aza indirme). Sütundaki mevcut değerler de silinir.
alter table students drop column gender;
