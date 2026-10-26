-- Clean-up patch. Run ONCE on a database built from the previous schema (v3), to remove what nothing used.
-- It keeps all your data and your login accounts (a fresh 01_schema.sql would wipe app_user).
--
--   mysql -u root -p < sql/upgrade/40_cleanup_patch.sql
--
-- Removes: 6 unused views; resource / event_resource / sponsor / event_sponsor; person_phone;
--          state / city / department and person.street, person.city_id, student.year / division / dob / dept_id;
--          category.description; the 'Attended' registration status; activity_log.db_user.
-- Adds:    a check that a venue booking can't be approved while its event isn't, and triggers that close
--          the "waiting for approval" alerts once the event / booking is decided.
-- Note:    student.year, division, dob and dept_id are DELETED with their data. Nothing in the app filled them.
USE spit_events;

-- 1. views nothing reads
DROP VIEW IF EXISTS student_details, department_summary, venue_utilization,
                    v_activity_summary, v_cancellation_report, pending_approvals;

-- 2. resources and sponsors (the app never wrote to them)
DROP TRIGGER IF EXISTS trg_resource_stock;
DROP TRIGGER IF EXISTS trg_alert_low_stock;
DROP TABLE IF EXISTS event_sponsor, event_resource, sponsor, resource;
DROP TABLE IF EXISTS person_phone;
DELETE FROM system_alert WHERE alert_type = 'LOW_STOCK';

-- 3. location + department + student details
DELIMITER $$
CREATE PROCEDURE tmp_drop_fk_on(IN t VARCHAR(64), IN c VARCHAR(64))
BEGIN
    DECLARE fk VARCHAR(64);
    SELECT constraint_name INTO fk FROM information_schema.key_column_usage
     WHERE table_schema = DATABASE() AND table_name = t AND column_name = c
       AND referenced_table_name IS NOT NULL LIMIT 1;
    IF fk IS NOT NULL THEN
        SET @s = CONCAT('ALTER TABLE `', t, '` DROP FOREIGN KEY `', fk, '`');
        PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;
    END IF;
END$$
DELIMITER ;
CALL tmp_drop_fk_on('student', 'dept_id');
CALL tmp_drop_fk_on('person', 'city_id');
DROP PROCEDURE tmp_drop_fk_on;

ALTER TABLE student DROP COLUMN year, DROP COLUMN division, DROP COLUMN dob, DROP COLUMN dept_id;
ALTER TABLE person  DROP COLUMN street, DROP COLUMN city_id;
DROP TABLE IF EXISTS department;
DROP TABLE IF EXISTS city;
DROP TABLE IF EXISTS state;

-- 4. category.description, and the 'Attended' status (nothing ever set it; any such rows become Registered)
ALTER TABLE category DROP COLUMN description;
UPDATE registration SET status = 'Registered' WHERE status = 'Attended';
ALTER TABLE registration MODIFY status ENUM('Registered','Cancelled') NOT NULL DEFAULT 'Registered';

-- 5. activity_log.db_user: the 11 log triggers fill it, so drop them, drop the column, put them back
DROP TRIGGER IF EXISTS trg_log_event_insert;
DROP TRIGGER IF EXISTS trg_log_event_update;
DROP TRIGGER IF EXISTS trg_log_event_delete;
DROP TRIGGER IF EXISTS trg_log_reg_insert;
DROP TRIGGER IF EXISTS trg_log_reg_update;
DROP TRIGGER IF EXISTS trg_log_reg_delete;
DROP TRIGGER IF EXISTS trg_log_booking_insert;
DROP TRIGGER IF EXISTS trg_log_booking_update;
DROP TRIGGER IF EXISTS trg_log_booking_delete;
DROP TRIGGER IF EXISTS trg_log_member_insert;
DROP TRIGGER IF EXISTS trg_log_member_delete;
ALTER TABLE activity_log DROP COLUMN db_user;
DELIMITER $$
CREATE TRIGGER trg_log_event_insert AFTER INSERT ON event
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, new_data)
    VALUES ('event', 'INSERT', NEW.event_id,
            JSON_OBJECT('title', NEW.title, 'fee', NEW.fee, 'max_seats', NEW.max_seats,
                        'committee_id', NEW.committee_id, 'approval_status', NEW.approval_status));
END$$

CREATE TRIGGER trg_log_event_update AFTER UPDATE ON event
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data, new_data)
    VALUES ('event', 'UPDATE', NEW.event_id,
            JSON_OBJECT('title', OLD.title, 'fee', OLD.fee, 'max_seats', OLD.max_seats,
                        'approval_status', OLD.approval_status, 'approved_by', OLD.approved_by),
            JSON_OBJECT('title', NEW.title, 'fee', NEW.fee, 'max_seats', NEW.max_seats,
                        'approval_status', NEW.approval_status, 'approved_by', NEW.approved_by));
END$$

CREATE TRIGGER trg_log_event_delete AFTER DELETE ON event
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data)
    VALUES ('event', 'DELETE', OLD.event_id,
            JSON_OBJECT('title', OLD.title, 'fee', OLD.fee, 'committee_id', OLD.committee_id));
END$$

CREATE TRIGGER trg_log_reg_insert AFTER INSERT ON registration
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, new_data)
    VALUES ('registration', 'INSERT', CONCAT(NEW.event_id, '-', NEW.student_id),
            JSON_OBJECT('status', NEW.status, 'amount_paid', NEW.amount_paid));
END$$

CREATE TRIGGER trg_log_reg_update AFTER UPDATE ON registration
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data, new_data)
    VALUES ('registration', 'UPDATE', CONCAT(NEW.event_id, '-', NEW.student_id),
            JSON_OBJECT('status', OLD.status, 'amount_paid', OLD.amount_paid),
            JSON_OBJECT('status', NEW.status, 'amount_paid', NEW.amount_paid));
END$$

CREATE TRIGGER trg_log_reg_delete AFTER DELETE ON registration
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data)
    VALUES ('registration', 'DELETE', CONCAT(OLD.event_id, '-', OLD.student_id),
            JSON_OBJECT('status', OLD.status, 'amount_paid', OLD.amount_paid));
END$$

CREATE TRIGGER trg_log_booking_insert AFTER INSERT ON venue_booking
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, new_data)
    VALUES ('venue_booking', 'INSERT', CONCAT(NEW.event_id, '-', NEW.session_no, '-', NEW.venue_id),
            JSON_OBJECT('status', NEW.status));
END$$

CREATE TRIGGER trg_log_booking_update AFTER UPDATE ON venue_booking
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data, new_data)
    VALUES ('venue_booking', 'UPDATE', CONCAT(NEW.event_id, '-', NEW.session_no, '-', NEW.venue_id),
            JSON_OBJECT('status', OLD.status), JSON_OBJECT('status', NEW.status));
END$$

CREATE TRIGGER trg_log_booking_delete AFTER DELETE ON venue_booking
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data)
    VALUES ('venue_booking', 'DELETE', CONCAT(OLD.event_id, '-', OLD.session_no, '-', OLD.venue_id),
            JSON_OBJECT('status', OLD.status));
END$$

CREATE TRIGGER trg_log_member_insert AFTER INSERT ON committee_member
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, new_data)
    VALUES ('committee_member', 'INSERT', CONCAT(NEW.committee_id, '-', NEW.student_id),
            JSON_OBJECT('role', NEW.role));
END$$

CREATE TRIGGER trg_log_member_delete AFTER DELETE ON committee_member
FOR EACH ROW
BEGIN
    INSERT INTO activity_log (table_name, action_type, record_key, old_data)
    VALUES ('committee_member', 'DELETE', CONCAT(OLD.committee_id, '-', OLD.student_id),
            JSON_OBJECT('role', OLD.role));
END$$
DELIMITER ;

-- 6. views that changed
CREATE OR REPLACE VIEW v_recent_activity AS
SELECT log_id, changed_at, table_name, action_type, record_key, old_data, new_data
FROM activity_log
WHERE changed_at >= NOW() - INTERVAL 1 DAY
ORDER BY changed_at DESC, log_id DESC;

CREATE OR REPLACE VIEW student_registrations AS
SELECT s.roll_no, p.name AS student, e.title AS event,
       r.reg_date, r.status, r.amount_paid
FROM registration r
JOIN student s ON s.person_id = r.student_id
JOIN person p  ON p.person_id = s.person_id
JOIN event e   ON e.event_id  = r.event_id;

CREATE OR REPLACE VIEW event_finance AS
SELECT e.event_id, e.title,
       (SELECT COALESCE(SUM(r.amount_paid), 0) FROM registration r
         WHERE r.event_id = e.event_id AND r.status <> 'Cancelled') AS registration_income
FROM event e;

CREATE OR REPLACE VIEW v_db_health AS
SELECT 'person' AS table_name, COUNT(*) AS row_count FROM person
UNION ALL SELECT 'student', COUNT(*) FROM student
UNION ALL SELECT 'committee', COUNT(*) FROM committee
UNION ALL SELECT 'committee_member', COUNT(*) FROM committee_member
UNION ALL SELECT 'category', COUNT(*) FROM category
UNION ALL SELECT 'event', COUNT(*) FROM event
UNION ALL SELECT 'event_session', COUNT(*) FROM event_session
UNION ALL SELECT 'venue', COUNT(*) FROM venue
UNION ALL SELECT 'venue_booking', COUNT(*) FROM venue_booking
UNION ALL SELECT 'registration', COUNT(*) FROM registration
UNION ALL SELECT 'activity_log', COUNT(*) FROM activity_log
UNION ALL SELECT 'system_alert', COUNT(*) FROM system_alert
UNION ALL SELECT 'daily_stats', COUNT(*) FROM daily_stats;

-- 7. new triggers
DELIMITER $$
CREATE TRIGGER trg_booking_event_approved_update BEFORE UPDATE ON venue_booking
FOR EACH ROW
BEGIN
    IF NEW.status = 'Approved' AND OLD.status <> 'Approved'
       AND (SELECT approval_status FROM event WHERE event_id = NEW.event_id) <> 'Approved' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot approve booking for an unapproved event';
    END IF;
END$$

-- "Waiting for approval" alerts close themselves once the event / booking is decided
CREATE TRIGGER trg_alert_event_decided AFTER UPDATE ON event
FOR EACH ROW
BEGIN
    IF OLD.approval_status = 'Pending' AND NEW.approval_status <> 'Pending' THEN
        UPDATE system_alert SET is_resolved = 1, resolved_at = NOW()
         WHERE alert_type = 'EVENT_PENDING' AND ref_table = 'event'
           AND ref_id = CAST(NEW.event_id AS CHAR) AND is_resolved = 0;
    END IF;
END$$

CREATE TRIGGER trg_alert_booking_decided AFTER UPDATE ON venue_booking
FOR EACH ROW
BEGIN
    IF OLD.status = 'Pending' AND NEW.status <> 'Pending' THEN
        UPDATE system_alert SET is_resolved = 1, resolved_at = NOW()
         WHERE alert_type = 'BOOKING_PENDING' AND ref_table = 'venue_booking'
           AND ref_id = CONCAT(NEW.event_id, '-', NEW.session_no, '-', NEW.venue_id) AND is_resolved = 0;
    END IF;
END$$
DELIMITER ;
