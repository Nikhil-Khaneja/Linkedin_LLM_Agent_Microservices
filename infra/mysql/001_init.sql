CREATE DATABASE IF NOT EXISTS linkedin_sim;
USE linkedin_sim;

CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(32) PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  subject_type VARCHAR(32) NOT NULL,
  first_name VARCHAR(80) NULL,
  last_name VARCHAR(80) NULL,
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  refresh_token_id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(32) NOT NULL,
  token_hash VARCHAR(255) NOT NULL,
  is_revoked BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NULL,
  INDEX idx_refresh_user (user_id)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  idempotency_key VARCHAR(128) PRIMARY KEY,
  route_name VARCHAR(128) NOT NULL,
  body_hash VARCHAR(255) NOT NULL,
  response_json JSON NULL,
  original_trace_id VARCHAR(64) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
  member_id VARCHAR(32) PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  first_name VARCHAR(80),
  last_name VARCHAR(80),
  headline VARCHAR(220),
  about_text TEXT,
  location_text VARCHAR(255),
  profile_version INT DEFAULT 1,
  is_deleted BOOLEAN DEFAULT FALSE,
  profile_views INT NOT NULL DEFAULT 0,
  connections_count INT NOT NULL DEFAULT 0,
  profile_photo_url TEXT NULL,
  resume_url TEXT NULL,
  resume_text MEDIUMTEXT NULL,
  current_company VARCHAR(160) NULL,
  current_title VARCHAR(160) NULL,
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recruiters (
  recruiter_id VARCHAR(32) PRIMARY KEY,
  company_id VARCHAR(32) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(120),
  phone VARCHAR(24),
  access_level VARCHAR(32),
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
  company_id VARCHAR(32) PRIMARY KEY,
  company_name VARCHAR(160) NOT NULL,
  company_industry VARCHAR(80),
  company_size VARCHAR(32),
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
  job_id VARCHAR(32) PRIMARY KEY,
  company_id VARCHAR(32) NOT NULL,
  recruiter_id VARCHAR(32) NOT NULL,
  title VARCHAR(160) NOT NULL,
  description_text TEXT NOT NULL,
  seniority_level VARCHAR(32),
  employment_type VARCHAR(32),
  location_text VARCHAR(120),
  work_mode VARCHAR(32),
  status VARCHAR(32) DEFAULT 'open',
  version INT DEFAULT 1,
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
  application_id VARCHAR(32) PRIMARY KEY,
  job_id VARCHAR(32) NOT NULL,
  member_id VARCHAR(32) NOT NULL,
  resume_ref TEXT,
  cover_letter TEXT,
  status VARCHAR(32) DEFAULT 'submitted',
  application_datetime DATETIME,
  payload_json TEXT NULL,
  UNIQUE KEY uq_job_member (job_id, member_id)
);


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

CREATE TABLE IF NOT EXISTS application_notes (
  note_id VARCHAR(32) PRIMARY KEY,
  application_id VARCHAR(32) NOT NULL,
  recruiter_id VARCHAR(32) NOT NULL,
  note_text TEXT NOT NULL,
  visibility VARCHAR(32) DEFAULT 'internal',
  payload_json TEXT NULL,
  skills_json JSON NULL,
  experience_json JSON NULL,
  education_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_notes_application (application_id)
);


CREATE TABLE IF NOT EXISTS outbox_events (
  outbox_id VARCHAR(64) PRIMARY KEY,
  topic VARCHAR(128) NOT NULL,
  event_type VARCHAR(128) NOT NULL,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id VARCHAR(64) NOT NULL,
  payload_json JSON NOT NULL,
  trace_id VARCHAR(64) NULL,
  idempotency_key VARCHAR(255) NOT NULL UNIQUE,
  status VARCHAR(32) DEFAULT 'pending',
  attempts INT DEFAULT 0,
  error_message TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  published_at TIMESTAMP NULL,
  available_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_outbox_status_available (status, available_at)
);
