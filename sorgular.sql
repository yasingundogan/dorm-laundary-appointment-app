.headers on
.mode column

--arızalı olmayan çamaşır makineleri
.print
select machine_no from machines where out_of_order = 0 and machine_type = 'washer' order by machine_no;


--Zeynep'in (student_id = 2) aktif randevularını listele. Her satırda başlangıç saati, makinenin numarası ve tipi görünsün.
.print
select start_time , machine_no , machine_type from appointments join machines on appointments.machine_id = machines.machine_id where student_id = 2 and status = 'active';

--'2026-09-30 14:00:00' saatinde boş olan, arızalı olmayan çamaşır makinelerini listele.
.print
select machine_no 
from machines
where out_of_order = 0 
and machine_type = 'washer'
and not exists (
    select 1 
    from appointments
    where appointments.machine_id = machines.machine_id
    and start_time = '2026-09-30 14:00:00'
    and status = 'active'
    
);


--Hiç aktif randevusu olmayan öğrencilerin adlarını listele. 
--hangi öğrenciler için aktif randevu yok
--dış sorgu öğrenci adı students tablosu
--iç sorgu status active mi bakıyor 
--iç sorgu dış satıra students id ile bağlanıyor

.print
select student_name
from students
where not exists (
    select 1
    from appointments
    where appointments.student_id = students.student_id
    and status = 'active'
);

--Zeynep'in 28 Eylül - 4 Ekim haftasında kaç tane çamaşır randevusu var?
--adım 1:zeynepin iptal edilmemiş randevularını say
.print
select count(*) 
from appointments
where student_id = 2 
and status != 'cancelled';

--adım 2:sadece çamaşır makinelerini say
.print
select count(*) 
from appointments 
join machines on appointments.machine_id = machines.machine_id
where student_id = 2
and status != 'cancelled' 
and machine_type = 'washer' ;

--adım 3:sadece o haftayı say
.print
select count(*) 
from appointments 
join machines on appointments.machine_id = machines.machine_id
where student_id = 2 
and status != 'cancelled'
and machine_type = 'washer'
and start_time >= '2026-09-28 00:00:00'
and start_time <  '2026-10-05 00:00:00' ;

--Son dakika iptali yapılmış randevuları; öğrencinin adı, randevu saati ve iptal saatiyle birlikte listele.
.print
select student_name , start_time , cancelled_at 
from appointments
join students on appointments.student_id = students.student_id
where status = 'cancelled' 
and datetime(start_time , '-15 minutes' ) < cancelled_at ;
