-- UPGRADE ONLY: for a database built from the OLD 01_schema.sql. A fresh build needs only 01 + 02.
-- Run AFTER 01_schema.sql (and before 02_sample_data.sql is fine too).
--
-- Why: event.approved_by pointed at faculty(person_id), so only faculty could approve.
-- We want faculty AND student-council members to have equal approval authority, so the column
-- must be able to hold any person. Nothing else changes: the trigger only checks approved_by
-- IS NOT NULL, and no view joins on approved_by.
--
-- MySQL auto-names the FKs event_ibfk_1..3 in declaration order; approved_by is the third.
-- If the DROP fails, run  SHOW CREATE TABLE event;  and use the name it shows.
USE spit_events;

ALTER TABLE event DROP FOREIGN KEY event_ibfk_3;
ALTER TABLE event
    ADD CONSTRAINT fk_event_approved_by FOREIGN KEY (approved_by) REFERENCES person(person_id);
