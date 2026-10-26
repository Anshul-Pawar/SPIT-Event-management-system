-- UPGRADE ONLY: for a database built from the OLD 01_schema.sql. A fresh build needs only 01 + 02.
-- Run LAST, after 10 + 20, `python manage.py migrate` and
--   python manage.py create_app_user --email anshul.pawar25@spit.ac.in
-- (events approved by faculty are handed to that root admin, so he must exist first).
-- Use the mysql CLI (the file has DELIMITER blocks).
--
-- Removes faculty completely: the faculty table, every faculty person (and their logins), department.hod_id,
-- the student/faculty triggers and the faculty_details view. A committee's coordinator becomes plain
-- contact details on the committee row (empty until council / admin fill them in).
USE spit_events;

DELIMITER $$
DROP PROCEDURE IF EXISTS tmp_drop_faculty$$
CREATE PROCEDURE tmp_drop_faculty()
BEGIN
    DECLARE v_root INT;
    DECLARE v_fk VARCHAR(64);

    SELECT person_id INTO v_root FROM person WHERE email = 'anshul.pawar25@spit.ac.in';
    IF v_root IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Create the root admin first: manage.py create_app_user --email anshul.pawar25@spit.ac.in';
    END IF;

    -- 1. Nothing may point at a faculty person any more
    UPDATE event SET approved_by = v_root
     WHERE approved_by IN (SELECT person_id FROM faculty);
    DELETE t FROM authtoken_token t JOIN app_user u ON u.id = t.user_id
     WHERE u.person_id IN (SELECT person_id FROM faculty);
    DELETE FROM app_user WHERE person_id IN (SELECT person_id FROM faculty);

    -- 2. committee.faculty_id -> coordinator contact details (MySQL auto-named this FK, so look it up)
    SELECT CONSTRAINT_NAME INTO v_fk FROM information_schema.KEY_COLUMN_USAGE
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'committee'
       AND COLUMN_NAME = 'faculty_id' AND REFERENCED_TABLE_NAME IS NOT NULL LIMIT 1;
    SET @sql = CONCAT('ALTER TABLE committee DROP FOREIGN KEY ', v_fk);
    PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

    -- 3. Faculty persons go with the table (phones cascade)
    CREATE TEMPORARY TABLE tmp_faculty_ids AS SELECT person_id FROM faculty;
END$$
DELIMITER ;

CALL tmp_drop_faculty();
DROP PROCEDURE tmp_drop_faculty;

ALTER TABLE committee
    DROP COLUMN faculty_id,
    ADD COLUMN coordinator_name  VARCHAR(80)  NULL,
    ADD COLUMN coordinator_email VARCHAR(100) NULL;

ALTER TABLE department DROP FOREIGN KEY fk_department_hod;
ALTER TABLE department DROP COLUMN hod_id;

DROP TRIGGER IF EXISTS trg_student_not_faculty;
DROP TRIGGER IF EXISTS trg_faculty_not_student;
DROP VIEW IF EXISTS faculty_details;
DROP TABLE faculty;
DELETE FROM person WHERE person_id IN (SELECT person_id FROM tmp_faculty_ids);
DROP TEMPORARY TABLE tmp_faculty_ids;

-- Views that read faculty, rebuilt to match 01_schema.sql
CREATE OR REPLACE VIEW committee_summary AS
SELECT c.committee_id, c.name AS committee, c.email, c.founded_year,
       c.coordinator_name, c.coordinator_email,
       (SELECT COUNT(*) FROM committee_member cm WHERE cm.committee_id = c.committee_id) AS members,
       (SELECT COUNT(*) FROM event e WHERE e.committee_id = c.committee_id) AS events_organized
FROM committee c;

CREATE OR REPLACE VIEW department_summary AS
SELECT d.dept_id, d.dept_name,
       (SELECT COUNT(*) FROM student s WHERE s.dept_id = d.dept_id) AS students
FROM department d;

CREATE OR REPLACE VIEW v_db_health AS
SELECT 'department' AS table_name, COUNT(*) AS row_count FROM department
UNION ALL SELECT 'state', COUNT(*) FROM state
UNION ALL SELECT 'city', COUNT(*) FROM city
UNION ALL SELECT 'person', COUNT(*) FROM person
UNION ALL SELECT 'person_phone', COUNT(*) FROM person_phone
UNION ALL SELECT 'student', COUNT(*) FROM student
UNION ALL SELECT 'committee', COUNT(*) FROM committee
UNION ALL SELECT 'committee_member', COUNT(*) FROM committee_member
UNION ALL SELECT 'category', COUNT(*) FROM category
UNION ALL SELECT 'event', COUNT(*) FROM event
UNION ALL SELECT 'event_session', COUNT(*) FROM event_session
UNION ALL SELECT 'venue', COUNT(*) FROM venue
UNION ALL SELECT 'venue_booking', COUNT(*) FROM venue_booking
UNION ALL SELECT 'registration', COUNT(*) FROM registration
UNION ALL SELECT 'resource', COUNT(*) FROM resource
UNION ALL SELECT 'event_resource', COUNT(*) FROM event_resource
UNION ALL SELECT 'sponsor', COUNT(*) FROM sponsor
UNION ALL SELECT 'event_sponsor', COUNT(*) FROM event_sponsor
UNION ALL SELECT 'activity_log', COUNT(*) FROM activity_log
UNION ALL SELECT 'system_alert', COUNT(*) FROM system_alert
UNION ALL SELECT 'daily_stats', COUNT(*) FROM daily_stats;
