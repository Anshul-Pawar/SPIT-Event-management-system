-- ========== A. Rules that must REJECT the statement (each should raise the shown message) ==========
-- A1 Event not approved
INSERT INTO registration (event_id, student_id) VALUES (5, 5);
-- EXPECT: Event is not approved yet
-- A2 Registration deadline passed
INSERT INTO registration (event_id, student_id) VALUES (8, 5);
-- EXPECT: Registration deadline has passed
-- A3 Event full (Mini Workshop has 2 seats, both taken)
INSERT INTO registration (event_id, student_id) VALUES (7, 7);
-- EXPECT: Event is full
-- A4 Paying more than the fee
INSERT INTO registration (event_id, student_id, amount_paid) VALUES (1, 10, 500);
-- EXPECT: Amount paid is more than the event fee
-- A5 Venue too small (event 4 has 400 seats, Room 103 holds 80)
INSERT INTO venue_booking (event_id, session_no, venue_id, status) VALUES (4, 1, 2, 'Pending');
-- EXPECT: Venue capacity is less than event seats
-- A6 Approve a booking for an unapproved event
INSERT INTO venue_booking (event_id, session_no, venue_id, status) VALUES (5, 1, 4, 'Approved');
-- EXPECT: Cannot approve booking for an unapproved event
-- A7 Venue clash (Room 203 already booked for CodeSprint round 1)
INSERT INTO event_session (event_id, session_no, title, session_date, start_time, end_time)
VALUES (7, 2, 'Clash test', CURDATE() + INTERVAL 8 DAY, '11:00', '12:00');
INSERT INTO venue_booking (event_id, session_no, venue_id, status) VALUES (7, 2, 3, 'Approved');
-- EXPECT: Venue already booked for this time slot
DELETE FROM event_session WHERE event_id = 7 AND session_no = 2;   -- clean up the helper session
-- A8 Requesting a suspended venue (needs 20_roles_venues_patch.sql)
UPDATE venue SET status = 'Suspended' WHERE venue_id = 1;
INSERT INTO venue_booking (event_id, session_no, venue_id, status) VALUES (5, 1, 1, 'Pending');
-- EXPECT: Venue is not available (suspended or removed)
UPDATE venue SET status = 'Active' WHERE venue_id = 1;              -- back in service (clears any flags)
-- A8 Session before registration deadline
INSERT INTO event_session (event_id, session_no, title, session_date, start_time, end_time)
VALUES (2, 2, 'Too early', CURDATE() + INTERVAL 1 DAY, '10:00', '11:00');
-- EXPECT: Session date is before the registration deadline
-- A9 Approving a PENDING booking while its event is still Pending (the update-time check)
UPDATE venue_booking SET status = 'Approved' WHERE event_id = 5 AND session_no = 1 AND venue_id = 1;
-- EXPECT: Cannot approve booking for an unapproved event
-- A10 Approving an event without an approver
UPDATE event SET approval_status = 'Approved' WHERE event_id = 5;
-- EXPECT: Set approved_by before approving the event

-- ========== B. Actions that must SUCCEED and write logs / alerts ==========
UPDATE registration SET status = 'Cancelled' WHERE event_id = 1 AND student_id = 9;
UPDATE event SET approved_by = 1, approval_status = 'Approved' WHERE event_id = 5;
UPDATE venue_booking SET status = 'Approved' WHERE event_id = 5 AND session_no = 1 AND venue_id = 1;
CALL sp_daily_snapshot();
CALL sp_deadline_alerts();

-- ========== C. Check the results ==========
SELECT * FROM v_open_alerts;              -- EXPECT: EVENT_FULL (Mini Workshop). No EVENT_PENDING / BOOKING_PENDING for event 5: both were decided in section B
SELECT * FROM v_event_fill_rate;          -- EXPECT: Mini Workshop = FULL (100%)
SELECT * FROM v_recent_activity LIMIT 20; -- EXPECT: rows for the updates in section B
SELECT * FROM event_overview;
SELECT * FROM event_schedule;
SELECT * FROM committee_summary;
SELECT * FROM event_finance;
SELECT * FROM v_public_events;
SELECT * FROM v_db_health;
SELECT * FROM daily_stats;
SELECT * FROM student_registrations LIMIT 5;
