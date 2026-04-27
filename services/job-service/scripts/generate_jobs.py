"""
Benchmark Data Generator - Scenario A
Generates 10,000 jobs + skills for load testing (Base vs Base+Redis).

Usage:
    python scripts/generate_jobs.py
    python scripts/generate_jobs.py --count 10000 --host 127.0.0.1 --port 3307
"""

import argparse
import random
import string
import time
import mysql.connector
from datetime import datetime, timedelta

# ── Seed data pools ──────────────────────────────────────────────────────────

JOB_TITLES = [
    "Backend Engineer", "Frontend Developer", "Full Stack Developer",
    "Data Scientist", "Machine Learning Engineer", "DevOps Engineer",
    "Site Reliability Engineer", "Cloud Architect", "Platform Engineer",
    "Security Engineer", "Mobile Developer - iOS", "Mobile Developer - Android",
    "QA Engineer", "Database Administrator", "Software Engineering Intern",
    "Product Manager", "UX Designer", "Technical Writer",
    "AI Research Scientist", "AI Infrastructure Engineer",
    "Software Engineer", "Senior Software Engineer", "Staff Engineer",
    "Principal Engineer", "Data Engineer", "Analytics Engineer",
    "Embedded Systems Engineer", "Network Engineer", "Systems Architect",
    "Engineering Manager", "Technical Lead", "Blockchain Developer",
    "Game Developer", "AR/VR Engineer", "Compiler Engineer",
]

COMPANIES = [f"cmp_{str(i).zfill(3)}" for i in range(1, 101)]   # cmp_001 .. cmp_100
RECRUITERS = [f"rec_{str(i).zfill(3)}" for i in range(1, 51)]   # rec_001 .. rec_050

LOCATIONS = [
    "San Jose, CA", "San Francisco, CA", "New York, NY", "Seattle, WA",
    "Austin, TX", "Denver, CO", "Boston, MA", "Los Angeles, CA",
    "Chicago, IL", "Palo Alto, CA", "Portland, OR", "Atlanta, GA",
    "Dallas, TX", "Miami, FL", "Phoenix, AZ", "Minneapolis, MN",
    "Remote", "Remote", "Remote",   # extra weight for remote
]

SENIORITY_LEVELS = ["intern", "junior", "mid", "mid", "senior", "senior", "lead"]
EMPLOYMENT_TYPES = ["full_time", "full_time", "full_time", "part_time", "contract", "internship"]
WORK_MODES = ["remote", "hybrid", "hybrid", "onsite"]

SKILLS_POOL = [
    "Python", "Java", "Go", "TypeScript", "JavaScript", "Kotlin", "Swift",
    "C++", "Rust", "Scala", "Ruby", "PHP",
    "React", "Vue.js", "Angular", "Node.js", "Django", "FastAPI", "Spring Boot",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "DynamoDB",
    "Kafka", "RabbitMQ", "gRPC", "REST API",
    "AWS", "GCP", "Azure", "Terraform", "Kubernetes", "Docker", "Helm",
    "Machine Learning", "TensorFlow", "PyTorch", "Scikit-learn", "MLOps",
    "Data Structures", "Algorithms", "System Design", "Distributed Systems",
    "CI/CD", "Linux", "Bash", "Git", "Prometheus", "Grafana",
    "Figma", "User Research", "Product Strategy", "Agile", "Scrum",
    "Security", "Penetration Testing", "NLP", "Computer Vision",
]

DESCRIPTION_TEMPLATES = [
    "We are looking for a talented {title} to join our growing team. "
    "You will be responsible for building scalable systems and collaborating with cross-functional teams. "
    "Experience with {skill1}, {skill2}, and distributed systems is required. "
    "Join us to work on cutting-edge technology and make an impact.",

    "Join our engineering team as a {title}. "
    "You will design, build, and maintain high-performance services. "
    "Strong proficiency in {skill1} and {skill2} is essential. "
    "We offer competitive compensation, flexible work arrangements, and great benefits.",

    "We are seeking an experienced {title} to help scale our platform. "
    "In this role you will architect solutions, mentor junior engineers, and drive technical decisions. "
    "Expertise in {skill1}, {skill2}, and cloud infrastructure is required. "
    "Excellent communication and problem-solving skills are a must.",

    "Our team is hiring a {title} to work on our core product. "
    "Day-to-day responsibilities include designing features, writing clean code, and participating in code reviews. "
    "Proficiency with {skill1} and {skill2} is expected. "
    "We value curiosity, ownership, and continuous learning.",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def rand_job_id(index: int) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"job_{index:05d}_{suffix}"


def rand_salary(seniority: str):
    base = {
        "intern":  (30000,  60000),
        "junior":  (70000, 110000),
        "mid":    (100000, 150000),
        "senior": (140000, 200000),
        "lead":   (180000, 260000),
    }[seniority]
    lo = random.randint(base[0], base[1] - 20000)
    hi = lo + random.randint(20000, 60000)
    return lo, hi


def rand_posted_datetime() -> datetime:
    # Spread posts over the last 90 days
    days_ago = random.randint(0, 90)
    return datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))


def rand_description(title: str, skills: list) -> str:
    template = random.choice(DESCRIPTION_TEMPLATES)
    s1 = skills[0] if skills else "Python"
    s2 = skills[1] if len(skills) > 1 else "MySQL"
    return template.format(title=title, skill1=s1, skill2=s2)


# ── Main generator ────────────────────────────────────────────────────────────

def generate(count: int, host: str, port: int, user: str, password: str, database: str):
    conn = mysql.connector.connect(
        host=host, port=port, user=user, password=password, database=database
    )
    cursor = conn.cursor()

    print(f"Connected to MySQL at {host}:{port}/{database}")
    print(f"Generating {count:,} jobs ...")

    # Check how many non-seed jobs already exist (seed uses job_001..job_020)
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE job_id NOT LIKE 'job_0%'")
    existing = cursor.fetchone()[0]
    if existing >= 10000:
        print(f"  {existing:,} generated jobs already present — skipping.")
        cursor.close()
        conn.close()
        return

    BATCH = 500
    jobs_batch = []
    skills_batch = []
    start_index = 1001   # leave room for seed jobs (001-020)

    t0 = time.time()

    for i in range(count):
        idx = start_index + i
        job_id = rand_job_id(idx)
        title = random.choice(JOB_TITLES)
        seniority = random.choice(SENIORITY_LEVELS)
        emp_type = random.choice(EMPLOYMENT_TYPES)
        location = random.choice(LOCATIONS)
        work_mode = random.choice(WORK_MODES)
        company_id = random.choice(COMPANIES)
        recruiter_id = random.choice(RECRUITERS)
        sal_min, sal_max = rand_salary(seniority)
        posted_dt = rand_posted_datetime()
        views = random.randint(0, 800)
        applicants = random.randint(0, 60)
        saves = random.randint(0, 30)

        num_skills = random.randint(2, 6)
        skills = random.sample(SKILLS_POOL, num_skills)
        description = rand_description(title, skills)

        jobs_batch.append((
            job_id, company_id, recruiter_id, title, description,
            seniority, emp_type, location, work_mode,
            sal_min, sal_max, "USD",
            posted_dt, "open",
            views, applicants, saves,
        ))

        for skill in skills:
            skills_batch.append((job_id, skill, random.choice([True, True, False])))

        if len(jobs_batch) >= BATCH:
            _flush_jobs(cursor, jobs_batch)
            _flush_skills(cursor, skills_batch)
            conn.commit()
            jobs_batch.clear()
            skills_batch.clear()
            elapsed = time.time() - t0
            done = i + 1
            print(f"  {done:,}/{count:,} inserted  ({elapsed:.1f}s)")

    # Final partial batch
    if jobs_batch:
        _flush_jobs(cursor, jobs_batch)
        _flush_skills(cursor, skills_batch)
        conn.commit()

    elapsed = time.time() - t0
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total = cursor.fetchone()[0]
    print(f"\nDone! {count:,} jobs inserted in {elapsed:.1f}s")
    print(f"Total jobs in DB: {total:,}")

    cursor.close()
    conn.close()


def _flush_jobs(cursor, batch):
    cursor.executemany(
        """INSERT IGNORE INTO jobs
           (job_id, company_id, recruiter_id, title, description,
            seniority_level, employment_type, location, work_mode,
            salary_min, salary_max, salary_currency,
            posted_datetime, status,
            views_count, applicants_count, saves_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        batch,
    )


def _flush_skills(cursor, batch):
    cursor.executemany(
        """INSERT IGNORE INTO job_skills (job_id, skill_name, is_required)
           VALUES (%s, %s, %s)""",
        batch,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate benchmark job data")
    parser.add_argument("--count",    type=int, default=10000, help="Number of jobs to generate (default: 10000)")
    parser.add_argument("--host",     default="127.0.0.1",     help="MySQL host (default: 127.0.0.1)")
    parser.add_argument("--port",     type=int, default=3307,  help="MySQL host port (default: 3307 — mapped in docker-compose)")
    parser.add_argument("--user",     default="root",           help="MySQL user")
    parser.add_argument("--password", default="password",       help="MySQL password")
    parser.add_argument("--database", default="job_core",       help="MySQL database")
    args = parser.parse_args()

    generate(
        count=args.count,
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
