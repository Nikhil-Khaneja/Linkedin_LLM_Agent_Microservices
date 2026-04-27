-- Job Service Database Schema
-- Owner 4 - LinkedIn Simulation Project

-- Use the database
USE job_core;

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS saved_jobs;
DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS jobs;

-- ============================================
-- JOBS TABLE
-- Main table for job postings
-- ============================================
CREATE TABLE jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    recruiter_id VARCHAR(50) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    seniority_level ENUM('intern', 'junior', 'mid', 'senior', 'lead') DEFAULT 'mid',
    employment_type ENUM('full_time', 'part_time', 'contract', 'internship') DEFAULT 'full_time',
    location VARCHAR(120) NOT NULL,
    work_mode ENUM('remote', 'hybrid', 'onsite') DEFAULT 'onsite',
    salary_min DECIMAL(12, 2) DEFAULT NULL,
    salary_max DECIMAL(12, 2) DEFAULT NULL,
    salary_currency VARCHAR(3) DEFAULT 'USD',
    posted_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_datetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    closed_datetime DATETIME DEFAULT NULL,
    status ENUM('open', 'closed', 'draft') DEFAULT 'open',
    views_count INT UNSIGNED DEFAULT 0,
    applicants_count INT UNSIGNED DEFAULT 0,
    saves_count INT UNSIGNED DEFAULT 0,
    version INT UNSIGNED DEFAULT 1,

    -- Indexes for search and filtering
    INDEX idx_status_location_type_posted (status, location(50), employment_type, posted_datetime DESC),
    INDEX idx_recruiter_posted (recruiter_id, posted_datetime DESC),
    INDEX idx_company (company_id),
    INDEX idx_posted_datetime (posted_datetime DESC),
    INDEX idx_status (status),
    INDEX idx_seniority (seniority_level),
    INDEX idx_work_mode (work_mode),

    -- Full-text index for keyword search
    FULLTEXT INDEX idx_fulltext_search (title, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- JOB_SKILLS TABLE
-- Skills required for each job
-- ============================================
CREATE TABLE job_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(50) NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key
    CONSTRAINT fk_job_skills_job FOREIGN KEY (job_id)
        REFERENCES jobs(job_id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_job_id (job_id),
    INDEX idx_skill_name (skill_name),

    -- Unique constraint to prevent duplicate skills per job
    UNIQUE KEY unique_job_skill (job_id, skill_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- SAVED_JOBS TABLE
-- Jobs saved by members for later viewing
-- ============================================
CREATE TABLE saved_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id VARCHAR(50) NOT NULL,
    job_id VARCHAR(50) NOT NULL,
    saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key
    CONSTRAINT fk_saved_jobs_job FOREIGN KEY (job_id)
        REFERENCES jobs(job_id) ON DELETE CASCADE,

    -- Unique constraint - member can save a job only once
    UNIQUE KEY unique_member_job (member_id, job_id),

    -- Indexes
    INDEX idx_member_saved (member_id, saved_at DESC),
    INDEX idx_job_id (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- IDEMPOTENCY TABLE
-- Track idempotency keys for retry-safe operations
-- ============================================
CREATE TABLE idempotency_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    endpoint VARCHAR(100) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_data JSON,
    status ENUM('processing', 'completed', 'failed') DEFAULT 'processing',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME DEFAULT (CURRENT_TIMESTAMP + INTERVAL 24 HOUR),

    INDEX idx_key (idempotency_key),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- STORED PROCEDURES
-- ============================================

-- Procedure to increment view count
DELIMITER //
CREATE PROCEDURE increment_job_views(IN p_job_id VARCHAR(50))
BEGIN
    UPDATE jobs SET views_count = views_count + 1 WHERE job_id = p_job_id;
END //
DELIMITER ;

-- Procedure to increment applicants count
DELIMITER //
CREATE PROCEDURE increment_job_applicants(IN p_job_id VARCHAR(50))
BEGIN
    UPDATE jobs SET applicants_count = applicants_count + 1 WHERE job_id = p_job_id;
END //
DELIMITER ;

-- Procedure to increment saves count
DELIMITER //
CREATE PROCEDURE increment_job_saves(IN p_job_id VARCHAR(50))
BEGIN
    UPDATE jobs SET saves_count = saves_count + 1 WHERE job_id = p_job_id;
END //
DELIMITER ;

-- Procedure to decrement saves count
DELIMITER //
CREATE PROCEDURE decrement_job_saves(IN p_job_id VARCHAR(50))
BEGIN
    UPDATE jobs SET saves_count = GREATEST(0, saves_count - 1) WHERE job_id = p_job_id;
END //
DELIMITER ;

-- ============================================
-- EVENTS FOR CLEANUP
-- ============================================

-- Enable event scheduler (run once manually if needed)
-- SET GLOBAL event_scheduler = ON;

-- Event to clean up expired idempotency keys
DELIMITER //
CREATE EVENT IF NOT EXISTS cleanup_expired_idempotency_keys
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    DELETE FROM idempotency_keys WHERE expires_at < NOW();
END //
DELIMITER ;
