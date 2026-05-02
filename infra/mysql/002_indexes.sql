USE linkedin_sim;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'users' AND index_name = 'idx_users_email');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_users_email ON users (email)', 'SELECT "idx_users_email exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'members' AND index_name = 'idx_members_email');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_members_email ON members (email)', 'SELECT "idx_members_email exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'members' AND index_name = 'idx_members_location');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_members_location ON members (location_text)', 'SELECT "idx_members_location exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'recruiters' AND index_name = 'idx_recruiters_company');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_recruiters_company ON recruiters (company_id)', 'SELECT "idx_recruiters_company exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'jobs' AND index_name = 'idx_jobs_recruiter');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_jobs_recruiter ON jobs (recruiter_id)', 'SELECT "idx_jobs_recruiter exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'jobs' AND index_name = 'idx_jobs_company');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_jobs_company ON jobs (company_id)', 'SELECT "idx_jobs_company exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'jobs' AND index_name = 'idx_jobs_status');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_jobs_status ON jobs (status)', 'SELECT "idx_jobs_status exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'jobs' AND index_name = 'idx_jobs_location');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_jobs_location ON jobs (location_text)', 'SELECT "idx_jobs_location exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'jobs' AND index_name = 'idx_jobs_created_at');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_jobs_created_at ON jobs (created_at)', 'SELECT "idx_jobs_created_at exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'applications' AND index_name = 'idx_applications_member');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_applications_member ON applications (member_id)', 'SELECT "idx_applications_member exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'applications' AND index_name = 'idx_applications_job');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_applications_job ON applications (job_id)', 'SELECT "idx_applications_job exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'applications' AND index_name = 'idx_applications_status');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_applications_status ON applications (status)', 'SELECT "idx_applications_status exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'idempotency_keys' AND index_name = 'idx_idempotency_route');
SET @sql = IF(@exists = 0, 'CREATE INDEX idx_idempotency_route ON idempotency_keys (route_name)', 'SELECT "idx_idempotency_route exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
