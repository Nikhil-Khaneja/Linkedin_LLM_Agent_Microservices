USE linkedin_sim;

CREATE TABLE IF NOT EXISTS saved_jobs (
  save_id VARCHAR(32) PRIMARY KEY,
  job_id VARCHAR(32) NOT NULL,
  member_id VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  payload_json TEXT NULL,
  UNIQUE KEY uq_saved_job_member (job_id, member_id),
  INDEX idx_saved_member_created (member_id, created_at),
  INDEX idx_saved_job_created (job_id, created_at)
);
