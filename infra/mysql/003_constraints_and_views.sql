USE linkedin_sim;

DROP VIEW IF EXISTS recruiter_job_counts;
CREATE VIEW recruiter_job_counts AS
SELECT recruiter_id, COUNT(*) AS total_jobs
FROM jobs
GROUP BY recruiter_id;

DROP VIEW IF EXISTS member_application_counts;
CREATE VIEW member_application_counts AS
SELECT member_id, COUNT(*) AS total_applications
FROM applications
GROUP BY member_id;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'first_name');
SET @sql = IF(@exists = 0, 'ALTER TABLE users ADD COLUMN first_name VARCHAR(80) NULL', 'SELECT "users.first_name exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'last_name');
SET @sql = IF(@exists = 0, 'ALTER TABLE users ADD COLUMN last_name VARCHAR(80) NULL', 'SELECT "users.last_name exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN payload_json TEXT NULL', 'SELECT "members.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'recruiters' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE recruiters ADD COLUMN payload_json TEXT NULL', 'SELECT "recruiters.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'companies' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE companies ADD COLUMN payload_json TEXT NULL', 'SELECT "companies.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'jobs' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE jobs ADD COLUMN payload_json TEXT NULL', 'SELECT "jobs.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'applications' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE applications ADD COLUMN payload_json TEXT NULL', 'SELECT "applications.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'application_notes' AND column_name = 'payload_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE application_notes ADD COLUMN payload_json TEXT NULL', 'SELECT "application_notes.payload_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'profile_views');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN profile_views INT NOT NULL DEFAULT 0', 'SELECT "members.profile_views exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'connections_count');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN connections_count INT NOT NULL DEFAULT 0', 'SELECT "members.connections_count exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
