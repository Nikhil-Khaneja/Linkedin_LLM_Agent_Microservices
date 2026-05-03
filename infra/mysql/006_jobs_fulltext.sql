USE linkedin_sim;

-- Fast job search: InnoDB FULLTEXT on short text columns (avoid scanning description_text).
SET @db = DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'jobs' AND INDEX_NAME = 'ft_jobs_title_location'
);
SET @sql := IF(
  @exists = 0,
  'CREATE FULLTEXT INDEX ft_jobs_title_location ON jobs (title, location_text)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
