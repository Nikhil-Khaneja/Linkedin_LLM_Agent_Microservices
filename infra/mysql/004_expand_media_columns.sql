USE linkedin_sim;

SET @profile_type = (SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'profile_photo_url' LIMIT 1);
SET @sql = IF(@profile_type IS NOT NULL AND @profile_type <> 'text', 'ALTER TABLE members MODIFY COLUMN profile_photo_url TEXT NULL', 'SELECT "members.profile_photo_url already text"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @resume_type = (SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'members' AND column_name = 'resume_url' LIMIT 1);
SET @sql = IF(@resume_type IS NOT NULL AND @resume_type <> 'text', 'ALTER TABLE members MODIFY COLUMN resume_url TEXT NULL', 'SELECT "members.resume_url already text"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @app_resume_type = (SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'applications' AND column_name = 'resume_ref' LIMIT 1);
SET @sql = IF(@app_resume_type IS NOT NULL AND @app_resume_type <> 'text', 'ALTER TABLE applications MODIFY COLUMN resume_ref TEXT NULL', 'SELECT "applications.resume_ref already text"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
