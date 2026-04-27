-- Job Service Seed Data
-- Owner 4 - LinkedIn Simulation Project
-- Initial sample data for development and testing

USE job_core;

-- ============================================
-- SAMPLE JOBS (20 initial jobs)
-- ============================================
INSERT INTO jobs (job_id, company_id, recruiter_id, title, description, seniority_level, employment_type, location, work_mode, salary_min, salary_max, status) VALUES
('job_001', 'cmp_001', 'rec_001', 'Backend Engineer',
 'We are looking for a skilled Backend Engineer to join our team. You will be responsible for building scalable APIs, working with Kafka-based event systems, and optimizing database performance. Experience with Java, Spring Boot, and distributed systems is required.',
 'mid', 'full_time', 'San Jose, CA', 'hybrid', 130000, 165000, 'open'),

('job_002', 'cmp_001', 'rec_001', 'Frontend Developer',
 'Join our frontend team to build responsive and accessible user interfaces. You will work with React, TypeScript, and modern CSS frameworks to create amazing user experiences.',
 'mid', 'full_time', 'San Jose, CA', 'remote', 120000, 150000, 'open'),

('job_003', 'cmp_002', 'rec_002', 'Data Scientist',
 'We are seeking a Data Scientist to analyze large datasets and build machine learning models. Experience with Python, TensorFlow, and SQL is required. You will work on recommendation systems and predictive analytics.',
 'senior', 'full_time', 'New York, NY', 'onsite', 150000, 200000, 'open'),

('job_004', 'cmp_002', 'rec_002', 'Machine Learning Engineer',
 'Build and deploy ML models at scale. Work with our data science team to productionize algorithms. Experience with MLOps, Kubernetes, and Python is essential.',
 'senior', 'full_time', 'New York, NY', 'hybrid', 160000, 220000, 'open'),

('job_005', 'cmp_003', 'rec_003', 'DevOps Engineer',
 'Manage our cloud infrastructure and CI/CD pipelines. Experience with AWS, Terraform, Docker, and Kubernetes required. You will ensure high availability and security of our systems.',
 'mid', 'full_time', 'Seattle, WA', 'remote', 140000, 180000, 'open'),

('job_006', 'cmp_003', 'rec_003', 'Site Reliability Engineer',
 'Keep our systems running smoothly. Monitor, troubleshoot, and optimize our distributed systems. Strong scripting skills and experience with observability tools required.',
 'senior', 'full_time', 'Seattle, WA', 'hybrid', 155000, 195000, 'open'),

('job_007', 'cmp_004', 'rec_004', 'Product Manager',
 'Lead product strategy and roadmap for our SaaS platform. Work closely with engineering, design, and customers to deliver valuable features. 5+ years of PM experience required.',
 'senior', 'full_time', 'Austin, TX', 'onsite', 140000, 180000, 'open'),

('job_008', 'cmp_004', 'rec_004', 'UX Designer',
 'Design intuitive user experiences for our web and mobile applications. Experience with Figma, user research, and prototyping required. Portfolio demonstrating strong design skills is essential.',
 'mid', 'full_time', 'Austin, TX', 'hybrid', 100000, 140000, 'open'),

('job_009', 'cmp_005', 'rec_005', 'Full Stack Developer',
 'Build features across our entire stack. Experience with Node.js, React, PostgreSQL, and cloud services required. You will work on both customer-facing features and internal tools.',
 'mid', 'full_time', 'Denver, CO', 'remote', 110000, 145000, 'open'),

('job_010', 'cmp_005', 'rec_005', 'QA Engineer',
 'Ensure quality of our software through automated and manual testing. Experience with Selenium, Jest, and CI/CD integration required. Strong attention to detail is essential.',
 'junior', 'full_time', 'Denver, CO', 'hybrid', 80000, 110000, 'open'),

('job_011', 'cmp_006', 'rec_006', 'Software Engineering Intern',
 'Join our internship program and work on real projects. Learn from experienced engineers while contributing to production code. CS degree in progress required.',
 'intern', 'internship', 'San Francisco, CA', 'onsite', 35, 50, 'open'),

('job_012', 'cmp_006', 'rec_006', 'Security Engineer',
 'Protect our systems and customer data. Conduct security audits, implement security controls, and respond to incidents. Experience with penetration testing and security frameworks required.',
 'senior', 'full_time', 'San Francisco, CA', 'hybrid', 170000, 230000, 'open'),

('job_013', 'cmp_007', 'rec_007', 'Mobile Developer - iOS',
 'Build native iOS applications using Swift and SwiftUI. Experience with App Store deployment, Core Data, and RESTful APIs required. Passion for great mobile UX is essential.',
 'mid', 'full_time', 'Los Angeles, CA', 'remote', 125000, 160000, 'open'),

('job_014', 'cmp_007', 'rec_007', 'Mobile Developer - Android',
 'Develop Android applications using Kotlin and Jetpack Compose. Experience with Material Design, Room database, and Google Play deployment required.',
 'mid', 'full_time', 'Los Angeles, CA', 'remote', 125000, 160000, 'open'),

('job_015', 'cmp_008', 'rec_008', 'Database Administrator',
 'Manage and optimize our MySQL and PostgreSQL databases. Experience with replication, backup strategies, and performance tuning required. 24/7 on-call rotation.',
 'senior', 'full_time', 'Chicago, IL', 'onsite', 130000, 170000, 'open'),

('job_016', 'cmp_008', 'rec_008', 'Technical Writer',
 'Create clear and comprehensive technical documentation. Experience with API documentation, user guides, and developer docs required. Strong writing skills essential.',
 'mid', 'contract', 'Chicago, IL', 'remote', 70000, 95000, 'open'),

('job_017', 'cmp_009', 'rec_009', 'Cloud Architect',
 'Design and implement cloud-native architectures on AWS. Experience with microservices, serverless, and multi-region deployments required. AWS certifications preferred.',
 'lead', 'full_time', 'Boston, MA', 'hybrid', 180000, 250000, 'open'),

('job_018', 'cmp_009', 'rec_009', 'Platform Engineer',
 'Build and maintain our internal developer platform. Experience with Kubernetes, service mesh, and developer tooling required. You will improve developer productivity.',
 'senior', 'full_time', 'Boston, MA', 'remote', 150000, 190000, 'open'),

('job_019', 'cmp_010', 'rec_010', 'AI Research Scientist',
 'Conduct research in natural language processing and large language models. PhD in CS, ML, or related field required. Publications in top venues preferred.',
 'senior', 'full_time', 'Palo Alto, CA', 'hybrid', 200000, 300000, 'open'),

('job_020', 'cmp_010', 'rec_010', 'Software Engineer - AI Infrastructure',
 'Build infrastructure to train and serve large ML models. Experience with distributed computing, GPU clusters, and model optimization required.',
 'senior', 'full_time', 'Palo Alto, CA', 'onsite', 180000, 260000, 'open');

-- ============================================
-- JOB SKILLS
-- ============================================
INSERT INTO job_skills (job_id, skill_name, is_required) VALUES
-- Job 001: Backend Engineer
('job_001', 'Java', TRUE),
('job_001', 'Spring Boot', TRUE),
('job_001', 'Kafka', TRUE),
('job_001', 'MySQL', TRUE),
('job_001', 'Redis', FALSE),
('job_001', 'Docker', FALSE),

-- Job 002: Frontend Developer
('job_002', 'React', TRUE),
('job_002', 'TypeScript', TRUE),
('job_002', 'JavaScript', TRUE),
('job_002', 'CSS', TRUE),
('job_002', 'HTML', TRUE),

-- Job 003: Data Scientist
('job_003', 'Python', TRUE),
('job_003', 'TensorFlow', TRUE),
('job_003', 'SQL', TRUE),
('job_003', 'Machine Learning', TRUE),
('job_003', 'Statistics', TRUE),

-- Job 004: ML Engineer
('job_004', 'Python', TRUE),
('job_004', 'Kubernetes', TRUE),
('job_004', 'MLOps', TRUE),
('job_004', 'TensorFlow', FALSE),
('job_004', 'PyTorch', FALSE),

-- Job 005: DevOps Engineer
('job_005', 'AWS', TRUE),
('job_005', 'Terraform', TRUE),
('job_005', 'Docker', TRUE),
('job_005', 'Kubernetes', TRUE),
('job_005', 'Linux', TRUE),

-- Job 006: SRE
('job_006', 'Kubernetes', TRUE),
('job_006', 'Prometheus', TRUE),
('job_006', 'Python', TRUE),
('job_006', 'Linux', TRUE),
('job_006', 'AWS', FALSE),

-- Job 007: Product Manager
('job_007', 'Product Strategy', TRUE),
('job_007', 'Agile', TRUE),
('job_007', 'Data Analysis', TRUE),
('job_007', 'User Research', FALSE),

-- Job 008: UX Designer
('job_008', 'Figma', TRUE),
('job_008', 'User Research', TRUE),
('job_008', 'Prototyping', TRUE),
('job_008', 'UI Design', TRUE),

-- Job 009: Full Stack Developer
('job_009', 'Node.js', TRUE),
('job_009', 'React', TRUE),
('job_009', 'PostgreSQL', TRUE),
('job_009', 'AWS', FALSE),
('job_009', 'TypeScript', FALSE),

-- Job 010: QA Engineer
('job_010', 'Selenium', TRUE),
('job_010', 'Jest', TRUE),
('job_010', 'Python', FALSE),
('job_010', 'CI/CD', TRUE),

-- Job 011: Software Engineering Intern
('job_011', 'Python', FALSE),
('job_011', 'Java', FALSE),
('job_011', 'Data Structures', TRUE),
('job_011', 'Algorithms', TRUE),

-- Job 012: Security Engineer
('job_012', 'Penetration Testing', TRUE),
('job_012', 'Security Frameworks', TRUE),
('job_012', 'Python', TRUE),
('job_012', 'Network Security', TRUE),

-- Job 013: iOS Developer
('job_013', 'Swift', TRUE),
('job_013', 'SwiftUI', TRUE),
('job_013', 'iOS', TRUE),
('job_013', 'Core Data', FALSE),

-- Job 014: Android Developer
('job_014', 'Kotlin', TRUE),
('job_014', 'Jetpack Compose', TRUE),
('job_014', 'Android', TRUE),
('job_014', 'Room', FALSE),

-- Job 015: DBA
('job_015', 'MySQL', TRUE),
('job_015', 'PostgreSQL', TRUE),
('job_015', 'Database Administration', TRUE),
('job_015', 'Performance Tuning', TRUE),

-- Job 016: Technical Writer
('job_016', 'Technical Writing', TRUE),
('job_016', 'API Documentation', TRUE),
('job_016', 'Markdown', TRUE),

-- Job 017: Cloud Architect
('job_017', 'AWS', TRUE),
('job_017', 'Microservices', TRUE),
('job_017', 'Serverless', TRUE),
('job_017', 'Architecture', TRUE),

-- Job 018: Platform Engineer
('job_018', 'Kubernetes', TRUE),
('job_018', 'Go', TRUE),
('job_018', 'Service Mesh', TRUE),
('job_018', 'Platform Engineering', TRUE),

-- Job 019: AI Research Scientist
('job_019', 'Machine Learning', TRUE),
('job_019', 'NLP', TRUE),
('job_019', 'Python', TRUE),
('job_019', 'PyTorch', TRUE),
('job_019', 'Research', TRUE),

-- Job 020: AI Infrastructure
('job_020', 'Distributed Systems', TRUE),
('job_020', 'Python', TRUE),
('job_020', 'CUDA', TRUE),
('job_020', 'Kubernetes', TRUE);

-- ============================================
-- SAMPLE SAVED JOBS
-- ============================================
INSERT INTO saved_jobs (member_id, job_id) VALUES
('mem_001', 'job_001'),
('mem_001', 'job_002'),
('mem_001', 'job_005'),
('mem_002', 'job_003'),
('mem_002', 'job_004'),
('mem_003', 'job_007'),
('mem_003', 'job_008'),
('mem_004', 'job_012'),
('mem_005', 'job_019'),
('mem_005', 'job_020');

-- Update saves_count based on saved_jobs
UPDATE jobs j SET saves_count = (
    SELECT COUNT(*) FROM saved_jobs s WHERE s.job_id = j.job_id
);

-- Add some view counts
UPDATE jobs SET views_count = FLOOR(RAND() * 500 + 50) WHERE status = 'open';

-- Add some applicant counts
UPDATE jobs SET applicants_count = FLOOR(RAND() * 50 + 5) WHERE status = 'open';
