DROP DATABASE IF EXISTS spit_events;
CREATE DATABASE spit_events;
USE spit_events;

-- Supertype of the ISA (student is the only subtype now). Committee and admin accounts are just a person.
CREATE TABLE person (
    person_id  INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(80)  NOT NULL,
    email      VARCHAR(100) NOT NULL UNIQUE
);

-- Subtype of Person (ISA). PK is also the FK to the supertype.
-- Signup gives only an email, so roll_no is the part of the email before the @.
CREATE TABLE student (
    person_id  INT PRIMARY KEY,
    roll_no    VARCHAR(64) NOT NULL UNIQUE,
    FOREIGN KEY (person_id) REFERENCES person(person_id) ON DELETE CASCADE
);

-- A committee posts events through its own login account (app_user, role 'committee').
-- The faculty coordinator is just contact details, not a person in the system.
CREATE TABLE committee (
    committee_id       INT AUTO_INCREMENT PRIMARY KEY,
    name               VARCHAR(80)  NOT NULL UNIQUE,
    email              VARCHAR(100) NOT NULL UNIQUE,
    founded_year       YEAR,
    coordinator_name   VARCHAR(80)  NULL,
    coordinator_email  VARCHAR(100) NULL
);

-- member of (Student M : N Committee) with attributes role, joined_on
CREATE TABLE committee_member (
    committee_id  INT NOT NULL,
    student_id    INT NOT NULL,
    role          VARCHAR(40) NOT NULL DEFAULT 'Member',
    joined_on     DATE,
    PRIMARY KEY (committee_id, student_id),
    FOREIGN KEY (committee_id) REFERENCES committee(committee_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)   REFERENCES student(person_id)      ON DELETE CASCADE
);

CREATE TABLE category (
    cat_id       INT AUTO_INCREMENT PRIMARY KEY,
    cat_name     VARCHAR(40) NOT NULL UNIQUE
);

-- organizes (Committee 1 : N Event, total on Event)  -> committee_id NOT NULL
-- in category (Category 1 : N Event)                 -> cat_id FK
-- approves (Person 1 : N Event) with status, remarks -> folded into Event
--   (the approver is a council member or admin, so approved_by points at person)
CREATE TABLE event (
    event_id          INT AUTO_INCREMENT PRIMARY KEY,
    title             VARCHAR(120) NOT NULL,
    fee               DECIMAL(8,2) NOT NULL DEFAULT 0 CHECK (fee >= 0),
    max_seats         INT NOT NULL CHECK (max_seats > 0),
    reg_deadline      DATE NOT NULL,
    committee_id      INT NOT NULL,
    cat_id            INT NOT NULL,
    approved_by       INT NULL,
    approval_status   ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
    approval_remarks  VARCHAR(200),
    FOREIGN KEY (committee_id) REFERENCES committee(committee_id),
    FOREIGN KEY (cat_id)       REFERENCES category(cat_id),
    FOREIGN KEY (approved_by)  REFERENCES person(person_id)
);

-- Weak entity: identified by (event_id, session_no)
CREATE TABLE event_session (
    event_id      INT NOT NULL,
    session_no    TINYINT NOT NULL,
    title         VARCHAR(100) NOT NULL,
    session_date  DATE NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    PRIMARY KEY (event_id, session_no),
    CHECK (end_time > start_time),
    FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE
);

CREATE TABLE venue (
    venue_id    INT AUTO_INCREMENT PRIMARY KEY,
    venue_name  VARCHAR(80) NOT NULL UNIQUE,
    capacity    INT NOT NULL CHECK (capacity > 0),
    location    VARCHAR(80),
    -- Removed = soft delete (booking history stays). Only Active venues can be booked.
    status      ENUM('Active','Suspended','Removed') NOT NULL DEFAULT 'Active'
);

-- books (Session M : N Venue). Date and time come from event_session,
-- so they are NOT repeated here (avoids redundancy, keeps 3NF).
CREATE TABLE venue_booking (
    event_id    INT NOT NULL,
    session_no  TINYINT NOT NULL,
    venue_id    INT NOT NULL,
    status      ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
    -- Set when the venue is suspended/removed after booking; the council keeps or cancels it.
    flagged     TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (event_id, session_no, venue_id),
    FOREIGN KEY (event_id, session_no) REFERENCES event_session(event_id, session_no) ON DELETE CASCADE,
    FOREIGN KEY (venue_id) REFERENCES venue(venue_id)
);

-- registers (Student M : N Event) with reg_date, status, amount_paid
CREATE TABLE registration (
    event_id     INT NOT NULL,
    student_id   INT NOT NULL,
    reg_date     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       ENUM('Registered','Cancelled') NOT NULL DEFAULT 'Registered',
    amount_paid  DECIMAL(8,2) NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
    PRIMARY KEY (event_id, student_id),
    FOREIGN KEY (event_id)   REFERENCES event(event_id)      ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES student(person_id)   ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 3. TRIGGERS: venue clash prevention
-- ---------------------------------------------------------------------
DELIMITER $$

CREATE TRIGGER trg_venue_clash BEFORE INSERT ON venue_booking
FOR EACH ROW
BEGIN
    IF NEW.status = 'Approved' AND EXISTS (
        SELECT 1
        FROM venue_booking vb
        JOIN event_session old_s ON old_s.event_id = vb.event_id AND old_s.session_no = vb.session_no
        JOIN event_session new_s ON new_s.event_id = NEW.event_id AND new_s.session_no = NEW.session_no
        WHERE vb.venue_id = NEW.venue_id
          AND vb.status = 'Approved'
          AND old_s.session_date = new_s.session_date
          AND old_s.start_time < new_s.end_time
          AND old_s.end_time   > new_s.start_time
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue already booked for this time slot';
    END IF;
END$$

DELIMITER ;

-- Every insert / update / delete on the important tables, with before/after data
CREATE TABLE IF NOT EXISTS activity_log (
    log_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name   VARCHAR(40) NOT NULL,
    action_type  ENUM('INSERT','UPDATE','DELETE') NOT NULL,
    record_key   VARCHAR(60) NOT NULL,
    old_data     JSON NULL,
    new_data     JSON NULL,
    changed_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_time  (changed_at),
    INDEX idx_log_table (table_name, action_type)
);

-- Alerts for the backend / admin panel (full events, low stock, pending approvals ...)
CREATE TABLE IF NOT EXISTS system_alert (
    alert_id      INT AUTO_INCREMENT PRIMARY KEY,
    alert_type    VARCHAR(40) NOT NULL,
    severity      ENUM('INFO','WARNING','CRITICAL') NOT NULL DEFAULT 'INFO',
    message       VARCHAR(255) NOT NULL,
    ref_table     VARCHAR(40),
    ref_id        VARCHAR(60),
    is_resolved   TINYINT(1) NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at   DATETIME NULL,
    INDEX idx_alert_open (is_resolved, severity)
);

-- One row per day, filled by a scheduled job (for trend graphs)
CREATE TABLE IF NOT EXISTS daily_stats (
    stat_date              DATE PRIMARY KEY,
    total_students         INT,
    total_events           INT,
    approved_events        INT,
    active_registrations   INT,
    cancelled_registrations INT,
    registration_income    DECIMAL(12,2),
    pending_approvals      INT,
    recorded_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 2. Every event with committee, category and live seat count
CREATE OR REPLACE VIEW event_overview AS
SELECT e.event_id, e.title, c.name AS committee, cat.cat_name AS category,
       e.fee, e.max_seats,
       COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) AS seats_taken,
       e.max_seats - COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) AS seats_left,
       e.reg_deadline, e.approval_status
FROM event e
JOIN committee c    ON c.committee_id = e.committee_id
JOIN category cat   ON cat.cat_id = e.cat_id
LEFT JOIN registration r ON r.event_id = e.event_id
GROUP BY e.event_id, e.title, c.name, cat.cat_name, e.fee, e.max_seats,
         e.reg_deadline, e.approval_status;

-- 3. Full schedule: event, session, date, time, venue, booking status
CREATE OR REPLACE VIEW event_schedule AS
SELECT e.title AS event, s.session_no, s.title AS session_title,
       s.session_date, s.start_time, s.end_time,
       v.venue_name, vb.status AS booking_status
FROM event e
JOIN event_session s        ON s.event_id = e.event_id
LEFT JOIN venue_booking vb  ON vb.event_id = s.event_id AND vb.session_no = s.session_no
LEFT JOIN venue v           ON v.venue_id = vb.venue_id
ORDER BY s.session_date, s.start_time;

-- 4. Committee summary: contact, coordinator, member count, event count
CREATE OR REPLACE VIEW committee_summary AS
SELECT c.committee_id, c.name AS committee, c.email, c.founded_year,
       c.coordinator_name, c.coordinator_email,
       (SELECT COUNT(*) FROM committee_member cm WHERE cm.committee_id = c.committee_id) AS members,
       (SELECT COUNT(*) FROM event e WHERE e.committee_id = c.committee_id) AS events_organized
FROM committee c;

-- 5. Which student registered for which event
CREATE OR REPLACE VIEW student_registrations AS
SELECT s.roll_no, p.name AS student, e.title AS event,
       r.reg_date, r.status, r.amount_paid
FROM registration r
JOIN student s ON s.person_id = r.student_id
JOIN person p  ON p.person_id = s.person_id
JOIN event e   ON e.event_id  = r.event_id;

-- 7. Money per event: what registrations brought in (no payment gateway yet, so this stays 0)
CREATE OR REPLACE VIEW event_finance AS
SELECT e.event_id, e.title,
       (SELECT COALESCE(SUM(r.amount_paid), 0) FROM registration r
         WHERE r.event_id = e.event_id AND r.status <> 'Cancelled') AS registration_income
FROM event e;

-- Activity in the last 24 hours, newest first
CREATE OR REPLACE VIEW v_recent_activity AS
SELECT log_id, changed_at, table_name, action_type, record_key, old_data, new_data
FROM activity_log
WHERE changed_at >= NOW() - INTERVAL 1 DAY
ORDER BY changed_at DESC, log_id DESC;

-- Alerts that still need attention, worst first
CREATE OR REPLACE VIEW v_open_alerts AS
SELECT alert_id, severity, alert_type, message, ref_table, ref_id, created_at
FROM system_alert
WHERE is_resolved = 0
ORDER BY FIELD(severity, 'CRITICAL', 'WARNING', 'INFO'), created_at DESC;

-- Fill percentage of every approved event
CREATE OR REPLACE VIEW v_event_fill_rate AS
SELECT e.event_id, e.title, e.max_seats,
       COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) AS seats_taken,
       ROUND(100 * COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) / e.max_seats, 1) AS fill_percent,
       CASE
           WHEN COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) >= e.max_seats THEN 'FULL'
           WHEN COUNT(CASE WHEN r.status <> 'Cancelled' THEN 1 END) >= 0.9 * e.max_seats THEN 'ALMOST FULL'
           ELSE 'OPEN'
       END AS fill_status
FROM event e
LEFT JOIN registration r ON r.event_id = e.event_id
WHERE e.approval_status = 'Approved'
GROUP BY e.event_id, e.title, e.max_seats;

-- Registrations and money per day
CREATE OR REPLACE VIEW v_registration_trend AS
SELECT DATE(reg_date) AS reg_day, COUNT(*) AS registrations,
       SUM(status = 'Cancelled') AS cancelled, SUM(amount_paid) AS amount_collected
FROM registration
GROUP BY DATE(reg_date)
ORDER BY reg_day DESC;

-- Row count of every table (quick database health check)
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

-- Last 30 daily snapshots (for graphs)
CREATE OR REPLACE VIEW v_daily_stats_recent AS
SELECT * FROM daily_stats ORDER BY stat_date DESC LIMIT 30;

-- ---------------------------------------------------------------------
-- PART 7 : VIEW FOR THE FRONTEND (public event listing)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_public_events AS
SELECT e.event_id, e.title, c.name AS committee, cat.cat_name AS category, e.fee, e.reg_deadline,
       (SELECT MIN(s.session_date) FROM event_session s WHERE s.event_id = e.event_id) AS event_date,
       (SELECT GROUP_CONCAT(DISTINCT v.venue_name SEPARATOR ', ')
          FROM venue_booking vb JOIN venue v ON v.venue_id = vb.venue_id
         WHERE vb.event_id = e.event_id AND vb.status = 'Approved') AS venues,
       e.max_seats - (SELECT COUNT(*) FROM registration r
                       WHERE r.event_id = e.event_id AND r.status <> 'Cancelled') AS seats_left
FROM event e
JOIN committee c  ON c.committee_id = e.committee_id
JOIN category cat ON cat.cat_id = e.cat_id
WHERE e.approval_status = 'Approved' AND e.reg_deadline >= CURDATE()
ORDER BY event_date;

DELIMITER $$

-- Registration rules -------------------------------------------------

-- Students can register only for approved events
CREATE TRIGGER trg_reg_event_approved BEFORE INSERT ON registration
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(10);
    SELECT approval_status INTO v_status FROM event WHERE event_id = NEW.event_id;
    IF v_status <> 'Approved' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event is not approved yet';
    END IF;
END$$

-- No registration after the deadline
CREATE TRIGGER trg_reg_deadline BEFORE INSERT ON registration
FOR EACH ROW
BEGIN
    DECLARE v_deadline DATE;
    SELECT reg_deadline INTO v_deadline FROM event WHERE event_id = NEW.event_id;
    IF CURDATE() > v_deadline THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Registration deadline has passed';
    END IF;
END$$

-- No registration once all seats are taken
CREATE TRIGGER trg_reg_seat_limit BEFORE INSERT ON registration
FOR EACH ROW
BEGIN
    DECLARE v_seats INT;
    DECLARE v_taken INT;
    SELECT max_seats INTO v_seats FROM event WHERE event_id = NEW.event_id;
    SELECT COUNT(*) INTO v_taken FROM registration
     WHERE event_id = NEW.event_id AND status <> 'Cancelled';
    IF v_taken >= v_seats THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event is full';
    END IF;
END$$

-- Amount paid cannot be more than the event fee
CREATE TRIGGER trg_reg_amount_check BEFORE INSERT ON registration
FOR EACH ROW
BEGIN
    DECLARE v_fee DECIMAL(8,2);
    SELECT fee INTO v_fee FROM event WHERE event_id = NEW.event_id;
    IF NEW.amount_paid > v_fee THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Amount paid is more than the event fee';
    END IF;
END$$

-- Venue booking rules ------------------------------------------------

-- Venue must be big enough for the event
CREATE TRIGGER trg_booking_capacity BEFORE INSERT ON venue_booking
FOR EACH ROW
BEGIN
    DECLARE v_seats INT;
    DECLARE v_cap INT;
    SELECT max_seats INTO v_seats FROM event WHERE event_id = NEW.event_id;
    SELECT capacity  INTO v_cap   FROM venue WHERE venue_id = NEW.venue_id;
    IF v_seats > v_cap THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue capacity is less than event seats';
    END IF;
END$$

-- A booking can be Approved only if the event itself is approved
CREATE TRIGGER trg_booking_event_approved BEFORE INSERT ON venue_booking
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(10);
    SELECT approval_status INTO v_status FROM event WHERE event_id = NEW.event_id;
    IF NEW.status = 'Approved' AND v_status <> 'Approved' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot approve booking for an unapproved event';
    END IF;
END$$

-- Clash check also when a Pending booking is changed to Approved
CREATE TRIGGER trg_booking_clash_update BEFORE UPDATE ON venue_booking
FOR EACH ROW
BEGIN
    IF NEW.status = 'Approved' AND OLD.status <> 'Approved' AND EXISTS (
        SELECT 1
        FROM venue_booking vb
        JOIN event_session old_s ON old_s.event_id = vb.event_id AND old_s.session_no = vb.session_no
        JOIN event_session new_s ON new_s.event_id = NEW.event_id AND new_s.session_no = NEW.session_no
        WHERE vb.venue_id = NEW.venue_id
          AND vb.status = 'Approved'
          AND NOT (vb.event_id = NEW.event_id AND vb.session_no = NEW.session_no)
          AND old_s.session_date = new_s.session_date
          AND old_s.start_time < new_s.end_time
          AND old_s.end_time   > new_s.start_time
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue already booked for this time slot';
    END IF;
END$$

-- Event and session rules ---------------------------------

-- A session cannot be held before the registration deadline
CREATE TRIGGER trg_session_after_deadline BEFORE INSERT ON event_session
FOR EACH ROW
BEGIN
    DECLARE v_deadline DATE;
    SELECT reg_deadline INTO v_deadline FROM event WHERE event_id = NEW.event_id;
    IF NEW.session_date < v_deadline THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Session date is before the registration deadline';
    END IF;
END$$

-- An event can be marked Approved only if someone (council / admin) is recorded as the approver
CREATE TRIGGER trg_event_needs_approver BEFORE UPDATE ON event
FOR EACH ROW
BEGIN
    IF NEW.approval_status = 'Approved' AND NEW.approved_by IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Set approved_by before approving the event';
    END IF;
END$$

DELIMITER ;

DELIMITER $$

-- Raise an alert unless the same alert is already open
CREATE PROCEDURE sp_raise_alert(IN p_type VARCHAR(40), IN p_severity VARCHAR(10),
                                IN p_msg VARCHAR(255), IN p_table VARCHAR(40), IN p_ref VARCHAR(60))
BEGIN
    IF NOT EXISTS (SELECT 1 FROM system_alert
                    WHERE alert_type = p_type AND ref_table = p_table
                      AND ref_id = p_ref AND is_resolved = 0) THEN
        INSERT INTO system_alert (alert_type, severity, message, ref_table, ref_id)
        VALUES (p_type, p_severity, p_msg, p_table, p_ref);
    END IF;
END$$

CREATE PROCEDURE sp_resolve_alert(IN p_alert_id INT)
BEGIN
    UPDATE system_alert SET is_resolved = 1, resolved_at = NOW() WHERE alert_id = p_alert_id;
END$$

-- Save today's numbers (safe to run many times a day)
CREATE PROCEDURE sp_daily_snapshot()
BEGIN
    INSERT INTO daily_stats (stat_date, total_students, total_events, approved_events,
                             active_registrations, cancelled_registrations,
                             registration_income, pending_approvals)
    SELECT CURDATE(),
           (SELECT COUNT(*) FROM student),
           (SELECT COUNT(*) FROM event),
           (SELECT COUNT(*) FROM event WHERE approval_status = 'Approved'),
           (SELECT COUNT(*) FROM registration WHERE status <> 'Cancelled'),
           (SELECT COUNT(*) FROM registration WHERE status = 'Cancelled'),
           (SELECT COALESCE(SUM(amount_paid), 0) FROM registration WHERE status <> 'Cancelled'),
           (SELECT COUNT(*) FROM event WHERE approval_status = 'Pending')
           + (SELECT COUNT(*) FROM venue_booking WHERE status = 'Pending')
    ON DUPLICATE KEY UPDATE
        total_students = VALUES(total_students), total_events = VALUES(total_events),
        approved_events = VALUES(approved_events),
        active_registrations = VALUES(active_registrations),
        cancelled_registrations = VALUES(cancelled_registrations),
        registration_income = VALUES(registration_income),
        pending_approvals = VALUES(pending_approvals), recorded_at = NOW();
END$$

-- Alert for events whose registration closes tomorrow
CREATE PROCEDURE sp_deadline_alerts()
BEGIN
    INSERT INTO system_alert (alert_type, severity, message, ref_table, ref_id)
    SELECT 'DEADLINE_TOMORROW', 'INFO',
           CONCAT('Registration for "', e.title, '" closes on ', e.reg_deadline),
           'event', e.event_id
    FROM event e
    WHERE e.approval_status = 'Approved'
      AND e.reg_deadline = CURDATE() + INTERVAL 1 DAY
      AND NOT EXISTS (SELECT 1 FROM system_alert a
                       WHERE a.alert_type = 'DEADLINE_TOMORROW' AND a.ref_table = 'event'
                         AND a.ref_id = e.event_id AND a.is_resolved = 0);
END$$

-- Keep the log tables small: delete logs older than 90 days
CREATE PROCEDURE sp_purge_old_logs()
BEGIN
    DELETE FROM activity_log WHERE changed_at < NOW() - INTERVAL 90 DAY;
    DELETE FROM system_alert WHERE is_resolved = 1 AND resolved_at < NOW() - INTERVAL 90 DAY;
END$$

-- ---------------------------------------------------------------------
-- PART 3 : ACTIVITY LOG TRIGGERS (continuous logs)
-- ---------------------------------------------------------------------

-- event
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

-- registration
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

-- venue_booking
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

-- committee_member
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

-- ---------------------------------------------------------------------
-- PART 4 : ALERT TRIGGERS
-- ---------------------------------------------------------------------

-- Event nearly full (90%) or full
CREATE TRIGGER trg_alert_event_fill AFTER INSERT ON registration
FOR EACH ROW
BEGIN
    DECLARE v_seats INT;
    DECLARE v_taken INT;
    DECLARE v_title VARCHAR(120);
    SELECT max_seats, title INTO v_seats, v_title FROM event WHERE event_id = NEW.event_id;
    SELECT COUNT(*) INTO v_taken FROM registration
     WHERE event_id = NEW.event_id AND status <> 'Cancelled';
    IF v_taken >= v_seats THEN
        CALL sp_raise_alert('EVENT_FULL', 'CRITICAL',
             CONCAT(v_title, ' is full (', v_taken, '/', v_seats, ')'), 'event', NEW.event_id);
    ELSEIF v_taken >= 0.9 * v_seats THEN
        CALL sp_raise_alert('EVENT_NEARLY_FULL', 'WARNING',
             CONCAT(v_title, ' is almost full (', v_taken, '/', v_seats, ')'), 'event', NEW.event_id);
    END IF;
END$$

-- Many cancellations for one event
CREATE TRIGGER trg_alert_cancellations AFTER UPDATE ON registration
FOR EACH ROW
BEGIN
    DECLARE v_cancelled INT;
    DECLARE v_title VARCHAR(120);
    IF OLD.status <> 'Cancelled' AND NEW.status = 'Cancelled' THEN
        SELECT COUNT(*) INTO v_cancelled FROM registration
         WHERE event_id = NEW.event_id AND status = 'Cancelled';
        IF v_cancelled >= 3 THEN
            SELECT title INTO v_title FROM event WHERE event_id = NEW.event_id;
            CALL sp_raise_alert('HIGH_CANCELLATIONS', 'WARNING',
                 CONCAT(v_title, ' has ', v_cancelled, ' cancellations'), 'event', NEW.event_id);
        END IF;
    END IF;
END$$

-- New event / booking waiting for council / admin approval
CREATE TRIGGER trg_alert_event_pending AFTER INSERT ON event
FOR EACH ROW
BEGIN
    IF NEW.approval_status = 'Pending' THEN
        CALL sp_raise_alert('EVENT_PENDING', 'INFO',
             CONCAT('Event "', NEW.title, '" is waiting for approval'), 'event', NEW.event_id);
    END IF;
END$$

CREATE TRIGGER trg_alert_booking_pending AFTER INSERT ON venue_booking
FOR EACH ROW
BEGIN
    IF NEW.status = 'Pending' THEN
        CALL sp_raise_alert('BOOKING_PENDING', 'INFO',
             CONCAT('Venue booking for event ', NEW.event_id, ' session ', NEW.session_no,
                    ' is waiting for approval'),
             'venue_booking', CONCAT(NEW.event_id, '-', NEW.session_no, '-', NEW.venue_id));
    END IF;
END$$

-- ---------------------------------------------------------------------

-- ---------------------------------------------------------------------
CREATE EVENT IF NOT EXISTS ev_daily_snapshot
    ON SCHEDULE EVERY 1 DAY STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 1 MINUTE)
    DO CALL sp_daily_snapshot()$$

CREATE EVENT IF NOT EXISTS ev_deadline_alerts
    ON SCHEDULE EVERY 1 DAY STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 8 HOUR)
    DO CALL sp_deadline_alerts()$$

CREATE EVENT IF NOT EXISTS ev_purge_old_logs
    ON SCHEDULE EVERY 1 WEEK STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 3 HOUR)
    DO CALL sp_purge_old_logs()$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- VENUE AVAILABILITY: suspended / removed venues
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- A booking can't be APPROVED while its event isn't approved. The insert-time version above only
-- catches bookings inserted as Approved; the app inserts Pending and approves later with an UPDATE.
-- ---------------------------------------------------------------------
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
