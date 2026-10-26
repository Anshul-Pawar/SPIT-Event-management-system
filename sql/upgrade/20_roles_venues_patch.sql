-- UPGRADE ONLY: for a database built from the OLD 01_schema.sql. A fresh build needs only 01 + 02.
-- Run AFTER 10_approver_patch.sql.
-- Use the mysql CLI (the file has DELIMITER blocks).
--
-- 1. Signup: a new account only gives email + password, so a new student row has no year/department
--    yet and its roll_no starts as the part of the email before the @ (can be longer than 15).
-- 2. Venues can be Active / Suspended / Removed (removed = soft delete, booking history stays).
-- 3. Suspending/removing a venue FLAGS its upcoming bookings; the council keeps or cancels each one.
USE spit_events;

-- 1. Student details are optional until the student fills them in -----------------------------
ALTER TABLE student
    MODIFY roll_no VARCHAR(64) NOT NULL,
    MODIFY year    TINYINT NULL CHECK (year BETWEEN 1 AND 4),
    MODIFY dept_id INT NULL;

-- Same views as before, but a student with no department still shows up.
CREATE OR REPLACE VIEW student_details AS
SELECT s.person_id, s.roll_no, p.name, p.email, s.year, s.division, s.dob,
       TIMESTAMPDIFF(YEAR, s.dob, CURDATE()) AS age, d.dept_name
FROM student s
JOIN person p          ON p.person_id = s.person_id
LEFT JOIN department d ON d.dept_id = s.dept_id;

CREATE OR REPLACE VIEW student_registrations AS
SELECT s.roll_no, p.name AS student, d.dept_name, e.title AS event,
       r.reg_date, r.status, r.amount_paid
FROM registration r
JOIN student s         ON s.person_id = r.student_id
JOIN person p          ON p.person_id = s.person_id
LEFT JOIN department d ON d.dept_id   = s.dept_id
JOIN event e           ON e.event_id  = r.event_id;

-- 2. Venue status + 3. booking flag ----------------------------------------------------------------
ALTER TABLE venue
    ADD COLUMN status ENUM('Active','Suspended','Removed') NOT NULL DEFAULT 'Active';

ALTER TABLE venue_booking
    ADD COLUMN flagged TINYINT(1) NOT NULL DEFAULT 0;

DELIMITER $$

-- A suspended or removed venue can't be requested
CREATE TRIGGER trg_booking_venue_active BEFORE INSERT ON venue_booking
FOR EACH ROW
BEGIN
    IF (SELECT status FROM venue WHERE venue_id = NEW.venue_id) <> 'Active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue is not available (suspended or removed)';
    END IF;
END$$

-- ...and a pending request for it can't be approved
CREATE TRIGGER trg_booking_venue_active_update BEFORE UPDATE ON venue_booking
FOR EACH ROW
BEGIN
    IF NEW.status = 'Approved' AND OLD.status <> 'Approved'
       AND (SELECT status FROM venue WHERE venue_id = NEW.venue_id) <> 'Active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue is not available (suspended or removed)';
    END IF;
END$$

-- Venue goes out of service: flag its upcoming Pending/Approved bookings and raise an alert.
-- Venue comes back: nothing left to decide, so clear the flags.
CREATE TRIGGER trg_venue_status_flag AFTER UPDATE ON venue
FOR EACH ROW
BEGIN
    DECLARE v_count INT;
    IF NEW.status <> 'Active' AND OLD.status = 'Active' THEN
        UPDATE venue_booking vb
        JOIN event_session s ON s.event_id = vb.event_id AND s.session_no = vb.session_no
        SET vb.flagged = 1
        WHERE vb.venue_id = NEW.venue_id
          AND vb.status IN ('Pending','Approved')
          AND s.session_date >= CURDATE();
        SET v_count = ROW_COUNT();
        IF v_count > 0 THEN
            CALL sp_raise_alert('VENUE_UNAVAILABLE', 'WARNING',
                 CONCAT(NEW.venue_name, ' is ', LOWER(NEW.status), ': ', v_count,
                        ' upcoming booking(s) need a keep / cancel decision'),
                 'venue', NEW.venue_id);
        END IF;
    ELSEIF NEW.status = 'Active' AND OLD.status <> 'Active' THEN
        UPDATE venue_booking SET flagged = 0 WHERE venue_id = NEW.venue_id AND flagged = 1;
    END IF;
END$$

DELIMITER ;
