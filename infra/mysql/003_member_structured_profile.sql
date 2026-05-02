USE linkedin_sim;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'skills_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN skills_json JSON NULL AFTER payload_json', 'SELECT "members.skills_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'experience_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN experience_json JSON NULL AFTER skills_json', 'SELECT "members.experience_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'education_json');
SET @sql = IF(@exists = 0, 'ALTER TABLE members ADD COLUMN education_json JSON NULL AFTER experience_json', 'SELECT "members.education_json exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
