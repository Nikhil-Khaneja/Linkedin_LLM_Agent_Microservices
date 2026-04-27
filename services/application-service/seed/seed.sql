-- ============================================================
-- Owner 5 — Application Service
-- seed/seed.sql
-- Seed data for standalone demo mode.
-- Allows testing without Owner 4 running.
-- ============================================================

USE application_core;

-- ── Seed job_status_projection ────────────────────────────────
-- job_3301 = open  → applications allowed
-- job_3302 = closed → applications blocked (returns HTTP 400)
-- job_3303 = open  → extra open job for testing
INSERT INTO job_status_projection (job_id, recruiter_id, status)
VALUES
    ('job_3301', 'rec_120', 'open'),
    ('job_3302', 'rec_120', 'closed'),
    ('job_3303', 'rec_121', 'open')
ON DUPLICATE KEY UPDATE
    recruiter_id = VALUES(recruiter_id),
    status       = VALUES(status);

-- ── Seed sample applications ──────────────────────────────────
INSERT INTO applications
    (application_id, job_id, member_id, recruiter_id, resume_ref, status, idempotency_key, trace_id)
VALUES
    ('app_seed001', 'job_3301', 'mem_501', 'rec_120',
     's3://bucket/resume-501.pdf', 'submitted',
     'seed-mem501-job3301', 'trc_seed001'),
    ('app_seed002', 'job_3301', 'mem_502', 'rec_120',
     's3://bucket/resume-502.pdf', 'under_review',
     'seed-mem502-job3301', 'trc_seed002'),
    ('app_seed003', 'job_3303', 'mem_501', 'rec_121',
     's3://bucket/resume-501.pdf', 'interview',
     'seed-mem501-job3303', 'trc_seed003')
ON DUPLICATE KEY UPDATE status = VALUES(status);

-- ── Seed recruiter notes ──────────────────────────────────────
INSERT INTO recruiter_notes (note_id, application_id, recruiter_id, note_text)
VALUES
    ('note_seed001', 'app_seed001', 'rec_120',
     'Candidate has strong Python and SQL background. Schedule phone screen.'),
    ('note_seed002', 'app_seed002', 'rec_120',
     'Good communication skills observed in cover letter. Move to under_review.')
ON DUPLICATE KEY UPDATE note_text = VALUES(note_text);
