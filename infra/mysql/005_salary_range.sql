USE linkedin_sim;

-- Idempotent: safe if apply_mysql_schema.sh runs multiple times.
SET @db = DATABASE();

SET @cnt := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'jobs' AND COLUMN_NAME = 'salary_min');
SET @sql := IF(@cnt = 0, 'ALTER TABLE jobs ADD COLUMN salary_min INT NULL AFTER location_text', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @cnt := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'jobs' AND COLUMN_NAME = 'salary_max');
SET @sql := IF(@cnt = 0, 'ALTER TABLE jobs ADD COLUMN salary_max INT NULL AFTER salary_min', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @cnt := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'jobs' AND COLUMN_NAME = 'salary_currency');
SET @sql := IF(@cnt = 0, 'ALTER TABLE jobs ADD COLUMN salary_currency VARCHAR(8) NULL DEFAULT ''USD'' AFTER salary_max', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
