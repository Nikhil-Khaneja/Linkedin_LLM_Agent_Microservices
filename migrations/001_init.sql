-- ============================================================
-- Owner 5 — Application Service
-- migrations/001_init.sql
-- Database: application_core
-- ============================================================

CREATE DATABASE IF NOT EXISTS application_core;
USE application_core;

-- ── applications ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    application_id  VARCHAR(50)  NOT NULL,
    job_id          VARCHAR(50)  NOT NULL,
    member_id       VARCHAR(50)  NOT NULL,
    recruiter_id    VARCHAR(50)  DEFAULT NULL,
    resume_ref      TEXT         DEFAULT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'submitted',
    idempotency_key VARCHAR(100) NOT NULL,
    trace_id        VARCHAR(100) DEFAULT NULL,
    submitted_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (application_id),
    UNIQUE KEY uq_job_member   (job_id, member_id),
    UNIQUE KEY uq_idem_key     (idempotency_key),
    INDEX idx_job_id            (job_id),
    INDEX idx_member_id         (member_id),
    INDEX idx_status            (status),
    INDEX idx_submitted_at      (submitted_at)
);

-- ── application_answers ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS application_answers (
    answer_id      VARCHAR(50)  NOT NULL,
    application_id VARCHAR(50)  NOT NULL,
    question_key   VARCHAR(100) DEFAULT NULL,
    answer_text    TEXT         DEFAULT NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (answer_id),
    INDEX idx_app_answers (application_id),
    CONSTRAINT fk_answers_application
        FOREIGN KEY (application_id)
        REFERENCES applications(application_id)
        ON DELETE CASCADE
);

-- ── recruiter_notes ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recruiter_notes (
    note_id        VARCHAR(50)  NOT NULL,
    application_id VARCHAR(50)  NOT NULL,
    recruiter_id   VARCHAR(50)  NOT NULL,
    note_text      TEXT         NOT NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (note_id),
    INDEX idx_notes_application (application_id),
    CONSTRAINT fk_notes_application
        FOREIGN KEY (application_id)
        REFERENCES applications(application_id)
        ON DELETE CASCADE
);

-- ── job_status_projection ─────────────────────────────────────
-- Populated by consuming Owner 4 Kafka events (job.created/updated/closed).
-- Lets Owner 5 check open/closed without a live HTTP call to Owner 4.
CREATE TABLE IF NOT EXISTS job_status_projection (
    job_id       VARCHAR(50) NOT NULL,
    recruiter_id VARCHAR(50) DEFAULT NULL,
    status       VARCHAR(30) NOT NULL,
    updated_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (job_id),
    INDEX idx_job_status (status)
);

-- ── consumed_kafka_events ─────────────────────────────────────
-- Prevents duplicate DB writes when Kafka replays events.
CREATE TABLE IF NOT EXISTS consumed_kafka_events (
    event_id    VARCHAR(100) NOT NULL,
    event_type  VARCHAR(100) DEFAULT NULL,
    consumed_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (event_id)
);
