USE linkedin_sim;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'profile_photo_url');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN profile_photo_url TEXT NULL', 'SELECT "members.profile_photo_url exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'resume_url');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN resume_url TEXT NULL', 'SELECT "members.resume_url exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'resume_text');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN resume_text MEDIUMTEXT NULL', 'SELECT "members.resume_text exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'current_company');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN current_company VARCHAR(160) NULL', 'SELECT "members.current_company exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'current_title');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN current_title VARCHAR(160) NULL', 'SELECT "members.current_title exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'location_text');
SET @sql = IF(@exists = 1, 'ALTER TABLE members MODIFY COLUMN location_text VARCHAR(255) NULL', 'SELECT "members.location_text missing"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


SET @profile_type = (SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'profile_photo_url' LIMIT 1);
SET @sql = IF(@profile_type IS NOT NULL AND @profile_type <> 'text', 'ALTER TABLE members MODIFY COLUMN profile_photo_url TEXT NULL', 'SELECT "members.profile_photo_url already text"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @resume_type = (SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'resume_url' LIMIT 1);
SET @sql = IF(@resume_type IS NOT NULL AND @resume_type <> 'text', 'ALTER TABLE members MODIFY COLUMN resume_url TEXT NULL', 'SELECT "members.resume_url already text"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
