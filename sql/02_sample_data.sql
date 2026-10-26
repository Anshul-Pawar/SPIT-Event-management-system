USE spit_events;

-- person_id 1 = the root admin (his login is made with: )
-- person_id 5-24 = students (class list). 2-4 are left unused so the student ids stay stable.
INSERT INTO person (person_id, name, email) VALUES
(1, 'Anshul Pawar', 'anshul.pawar25@spit.ac.in');
ALTER TABLE person AUTO_INCREMENT = 5;

INSERT INTO person (name, email) VALUES
('Nair Anikhet Prashanth', '2025300153@spit.ac.in'),
('Nair Ashutosh Subash', '2025300154@spit.ac.in'),
('Nakhat Aadi Premchand', '2025300155@spit.ac.in'),
('Nalawad Ritesh Pandurang', '2025300156@spit.ac.in'),
('Navale Prutha Ganeshnath', '2025300157@spit.ac.in'),
('Nayak Sahil Gurudutt', '2025300158@spit.ac.in'),
('Niwate Shreyash Ravindra', '2025300159@spit.ac.in'),
('Pagariya Neil Chetan', '2025300160@spit.ac.in'),
('Parekh Dron Parekh', '2025300161@spit.ac.in'),
('Pargaonkar Sumedh Dilip', '2025300162@spit.ac.in'),
('Parmar Shrey Yogesh', '2025300163@spit.ac.in'),
('Patankar Manasvi Bhalchandra', '2025300164@spit.ac.in'),
('Patel Krish Himanshu', '2025300165@spit.ac.in'),
('Patel Om Paras', '2025300166@spit.ac.in'),
('Pathak Purva Kalpesh', '2025300167@spit.ac.in'),
('Patil Advait Nilesh', '2025300168@spit.ac.in'),
('Patil Dhruv Yuvraj', '2025300169@spit.ac.in'),
('Patil Harshavardhan Arvind', '2025300170@spit.ac.in'),
('Patil Leesha Yogesh', '2025300171@spit.ac.in'),
('Patil Sanskruti Vijay', '2025300172@spit.ac.in');

-- UID is used as roll_no
INSERT INTO student (person_id, roll_no) VALUES
(5,'2025300153'),
(6,'2025300154'),
(7,'2025300155'),
(8,'2025300156'),
(9,'2025300157'),
(10,'2025300158'),
(11,'2025300159'),
(12,'2025300160'),
(13,'2025300161'),
(14,'2025300162'),
(15,'2025300163'),
(16,'2025300164'),
(17,'2025300165'),
(18,'2025300166'),
(19,'2025300167'),
(20,'2025300168'),
(21,'2025300169'),
(22,'2025300170'),
(23,'2025300171'),
(24,'2025300172');

-- Student clubs (from the SPIT website menu)
INSERT INTO committee (name, email, founded_year) VALUES
('E-Cell',        'ecell@spit.ac.in',    2012),
('SPARK',         'spark@spit.ac.in',    2014),
('IEEE',          'ieee@spit.ac.in',     2010),
('IIC',           'iic@spit.ac.in',      2019),
('ACSES',         'acses@spit.ac.in',    2011),
('NISP',          'nisp@spit.ac.in',     2013),
('IETE',          'iete@spit.ac.in',     2009),
('Rotaract Club', 'rotaract@spit.ac.in', 2008),
('Enactus',       'enactus@spit.ac.in',  2015),
('FACE',          'face@spit.ac.in',     2016);

INSERT INTO committee_member (committee_id, student_id, role, joined_on) VALUES
(1,5,'President','2026-07-10'),(1,6,'Member','2026-07-12'),
(2,7,'Head','2026-07-10'),(2,8,'Member','2026-07-15'),
(3,9,'Chair','2026-07-11'),(3,10,'Secretary','2026-07-11'),
(4,11,'Lead','2026-07-14'),
(5,12,'President','2026-07-09'),(5,13,'Treasurer','2026-07-09'),
(6,14,'Member','2026-07-20'),
(7,15,'Member','2026-07-21'),
(8,16,'President','2026-07-08'),(8,17,'Member','2026-07-13'),
(9,18,'Member','2026-07-22'),
(10,19,'Head','2026-07-10'),(10,20,'Member','2026-07-16'),
(1,7,'Member','2026-08-01');

INSERT INTO category (cat_name) VALUES
('Technical'),
('Workshop'),
('Seminar'),
('Cultural'),
('Social');

INSERT INTO venue (venue_name, capacity, location) VALUES
('SPIT Auditorium',   500,'SPIT Campus, Andheri (W)'),
('Room 103',           80,'SPIT Campus, 1st floor'),
('Room 203',           80,'SPIT Campus, 2nd floor'),
('SPJIMR Auditorium', 400,'SPJIMR Campus, Andheri (W)');

-- Dates are relative to today so every trigger rule (deadline, session after deadline) passes on any day
-- Seeded approvals are recorded against the root admin (person 1).
INSERT INTO event (title, fee, max_seats, reg_deadline, committee_id, cat_id, approved_by, approval_status, approval_remarks) VALUES
('CodeSprint 2026',        100.00,  60, CURDATE() + INTERVAL 5 DAY,  5, 1, 1,    'Approved', 'Approved for lab use'),
('Web Dev Workshop',       150.00,  50, CURDATE() + INTERVAL 10 DAY, 3, 2, 1,    'Approved', NULL),
('Startup Pitch Day',        0.00,  80, CURDATE() + INTERVAL 14 DAY, 1, 3, 1,    'Approved', NULL),
('Innovation Talk',          0.00, 400, CURDATE() + INTERVAL 20 DAY, 4, 3, 1,    'Approved', NULL),
('Cultural Night',          50.00, 400, CURDATE() + INTERVAL 25 DAY, 10,4, NULL, 'Pending',  NULL),
('Blood Donation Drive',     0.00, 100, CURDATE() + INTERVAL 6 DAY,  8, 5, 1,    'Approved', NULL),
('Mini Workshop',            0.00,   2, CURDATE() + INTERVAL 4 DAY,  2, 2, 1,    'Approved', 'Tiny group, used for the full-event test'),
('Quiz Night (closed)',     20.00,  80, CURDATE() - INTERVAL 5 DAY,  6, 1, 1,    'Approved', 'Registration already closed');

INSERT INTO event_session (event_id, session_no, title, session_date, start_time, end_time) VALUES
(1,1,'Round 1: Screening',  CURDATE() + INTERVAL 8 DAY,  '10:00','13:00'),
(1,2,'Round 2: Finals',     CURDATE() + INTERVAL 8 DAY,  '14:00','16:00'),
(2,1,'Full Stack Workshop', CURDATE() + INTERVAL 12 DAY, '09:30','13:30'),
(3,1,'Pitch Day',          CURDATE() + INTERVAL 17 DAY, '14:00','17:00'),
(4,1,'Innovation Talk',    CURDATE() + INTERVAL 23 DAY, '15:00','17:00'),
(5,1,'Cultural Night',     CURDATE() + INTERVAL 28 DAY, '18:00','21:00'),
(6,1,'Donation Drive',     CURDATE() + INTERVAL 9 DAY,  '10:00','16:00'),
(7,1,'Mini Workshop',      CURDATE() + INTERVAL 6 DAY,  '11:00','12:00'),
(8,1,'Quiz Night',         CURDATE() - INTERVAL 2 DAY,  '17:00','19:00');

INSERT INTO venue_booking (event_id, session_no, venue_id, status) VALUES
(1,1,3,'Approved'),(1,2,3,'Approved'),(2,1,2,'Approved'),(3,1,2,'Pending'),
(4,1,4,'Approved'),(5,1,1,'Pending'),(6,1,4,'Approved'),(7,1,3,'Approved'),(8,1,2,'Approved');

INSERT INTO registration (event_id, student_id, status, amount_paid) VALUES
(1,5,'Registered',100.00),
(1,6,'Registered',100.00),
(1,7,'Registered',100.00),
(1,8,'Registered',100.00),
(1,9,'Registered',100.00),
(2,5,'Registered',150.00),
(2,6,'Registered',150.00),
(2,10,'Registered',150.00),
(3,5,'Registered',0.00),
(3,7,'Registered',0.00),
(3,8,'Registered',0.00),
(3,11,'Registered',0.00),
(3,12,'Registered',0.00),
(4,5,'Registered',0.00),
(4,6,'Registered',0.00),
(4,7,'Registered',0.00),
(4,8,'Registered',0.00),
(4,9,'Registered',0.00),
(4,10,'Registered',0.00),
(4,11,'Registered',0.00),
(4,12,'Registered',0.00),
(4,13,'Registered',0.00),
(4,14,'Registered',0.00),
(6,6,'Registered',0.00),
(6,9,'Registered',0.00),
(6,13,'Registered',0.00),
(7,5,'Registered',0.00),
(7,6,'Registered',0.00);
