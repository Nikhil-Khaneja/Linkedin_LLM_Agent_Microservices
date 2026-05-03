#!/usr/bin/env python3
"""Load Kaggle-style job and resume CSV exports into linkedin_sim (MySQL).

After downloading datasets (e.g. `kaggle datasets download rajatraj0502/linkedin-job-2023`
and `kaggle datasets download snehaanbhawal/resume-dataset`) and unzipping, run:

  python3 scripts/load_kaggle_datasets.py \\
    --jobs-csv /path/to/jobs.csv \\
    --resumes-csv /path/to/resumes.csv \\
    --max-jobs 10000 --max-members 5000

Without CSV files (synthetic bulk for dashboards / perf):

  python3 scripts/load_kaggle_datasets.py --synthetic --max-jobs 10000 --max-members 5000

After real Kaggle résumés (~2.5k rows), pad to 5k+ **unique** members (synthetic `mem_syn_*`, unique emails):

  python3 scripts/load_kaggle_datasets.py --synthetic-members-extra 3000 --chunk-size 400

Combine with CSV paths in one run (CSV first, then top-up):

  python3 scripts/load_kaggle_datasets.py --resumes-csv .../Resume.csv --max-members 50000 \\
    --synthetic-members-extra 2600 --chunk-size 400

Uses the same MYSQL_* environment variables as seed_perf_data.py.
Apply schema first (includes infra/mysql/005_salary_range.sql for salary columns on jobs).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import uuid
from pathlib import Path

backend_root = str((Path(__file__).resolve().parents[1] / "backend"))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from services.shared.relational import execute, execute_many  # noqa: E402
from services.shared.auth import password_hash  # noqa: E402


BULK_COMPANY_ID = "cmp_kaggle_import"
BULK_RECRUITER_ID = "rec_kaggle_import"
# Dev login for the bulk-import recruiter (JWT sub must match BULK_RECRUITER_ID — see auth_service._domain_subject_for).
# Use a domain accepted by Pydantic EmailStr on /auth/login (not .invalid).
BULK_IMPORT_EMAIL = "bulk-kaggle-recruiter@example.com"
BULK_IMPORT_LOGIN_PASSWORD = "KaggleImport#2026"


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _pick_col(row: dict[str, str], candidates: list[str]) -> str | None:
    keys = {_norm_key(k): k for k in row.keys()}
    for c in candidates:
        nk = _norm_key(c)
        if nk in keys:
            return keys[nk]
    for want in candidates:
        w = _norm_key(want)
        for nk, orig in keys.items():
            if w in nk or nk in w:
                return orig
    return None


def _read_csv_rows(path: Path, max_rows: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append({k: (v or "").strip() if isinstance(v, str) else "" for k, v in row.items()})
    return rows


def ensure_bulk_recruiter() -> None:
    execute(
        """
        INSERT IGNORE INTO companies (company_id, company_name, company_industry, company_size, payload_json)
        VALUES (:company_id, :company_name, :company_industry, :company_size, :payload_json)
        """,
        {
            "company_id": BULK_COMPANY_ID,
            "company_name": "Kaggle Import Co",
            "company_industry": "Imported",
            "company_size": "large",
            "payload_json": json.dumps({"company_id": BULK_COMPANY_ID}),
        },
    )
    execute(
        """
        INSERT IGNORE INTO recruiters (recruiter_id, company_id, email, name, phone, access_level, payload_json)
        VALUES (:recruiter_id, :company_id, :email, :name, :phone, :access_level, :payload_json)
        """,
        {
            "recruiter_id": BULK_RECRUITER_ID,
            "company_id": BULK_COMPANY_ID,
            "email": BULK_IMPORT_EMAIL,
            "name": "Kaggle Import",
            "phone": None,
            "access_level": "admin",
            "payload_json": json.dumps({"recruiter_id": BULK_RECRUITER_ID, "company_id": BULK_COMPANY_ID}),
        },
    )
    execute(
        """
        INSERT IGNORE INTO users (user_id, email, password_hash, subject_type, first_name, last_name, payload_json)
        VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name, :payload_json)
        """,
        {
            "user_id": BULK_RECRUITER_ID,
            "email": BULK_IMPORT_EMAIL,
            "password_hash": password_hash(BULK_IMPORT_LOGIN_PASSWORD),
            "subject_type": "recruiter",
            "first_name": "Kaggle",
            "last_name": "Import",
            "payload_json": json.dumps({"user_type": "recruiter"}),
        },
    )
    execute(
        "UPDATE users SET email=:em, password_hash=:ph WHERE user_id=:uid",
        {"em": BULK_IMPORT_EMAIL, "ph": password_hash(BULK_IMPORT_LOGIN_PASSWORD), "uid": BULK_RECRUITER_ID},
    )
    execute(
        "UPDATE recruiters SET email=:em WHERE recruiter_id=:rid",
        {"em": BULK_IMPORT_EMAIL, "rid": BULK_RECRUITER_ID},
    )


def synthetic_salary(seniority: str) -> tuple[int | None, int | None]:
    base = {"internship": 40000, "entry": 65000, "associate": 80000, "mid": 100000, "senior": 140000, "director": 180000, "executive": 220000}.get(
        (seniority or "mid").lower(), 90000
    )
    lo = int(base * random.uniform(0.85, 1.0))
    hi = int(base * random.uniform(1.05, 1.45))
    return lo, hi


def load_synthetic_jobs(max_jobs: int, chunk: int) -> int:
    """Seed jobs without a CSV (local demo / CI). Same columns as Kaggle import."""
    work_modes = ["remote", "hybrid", "onsite"]
    out: list[dict] = []
    for i in range(max_jobs):
        sen = random.choice(["internship", "entry", "associate", "mid", "senior", "director"])
        title = f"Synthetic role {i + 1}: {random.choice(['Engineer', 'Analyst', 'Designer', 'Manager'])}"
        desc = (
            f"Auto-generated description for benchmarking and dashboard tests. "
            f"Stack: Python, SQL, cloud. Req id {i}."
        )[:4000]
        location = random.choice(["San Jose, CA", "Remote", "New York, NY", "Austin, TX"])
        job_id = f"job_syn_{uuid.uuid4().hex[:10]}"
        smin, smax = synthetic_salary(sen)
        wm = random.choices(work_modes, weights=[3, 4, 3])[0]
        payload = {
            "job_id": job_id,
            "company_id": BULK_COMPANY_ID,
            "recruiter_id": BULK_RECRUITER_ID,
            "title": title,
            "description": desc,
            "location": location,
            "employment_type": "full_time",
            "seniority_level": sen,
            "work_mode": wm,
            "company_name": f"Synthetic Co {i % 50}",
            "company_industry": "Software",
            "skills_required": ["Python", "SQL", "Communication"],
            "status": "open",
            "salary_min": smin,
            "salary_max": smax,
            "salary_currency": "USD",
        }
        out.append(
            {
                "job_id": job_id,
                "company_id": BULK_COMPANY_ID,
                "recruiter_id": BULK_RECRUITER_ID,
                "title": title[:160],
                "description_text": desc,
                "seniority_level": sen,
                "employment_type": "full_time",
                "location_text": location,
                "salary_min": smin,
                "salary_max": smax,
                "salary_currency": "USD",
                "work_mode": wm,
                "status": "open",
                "version": 1,
                "payload_json": json.dumps(payload),
            }
        )
    for part in (out[i : i + chunk] for i in range(0, len(out), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level,
                employment_type, location_text, salary_min, salary_max, salary_currency, work_mode, status, version, payload_json)
            VALUES (:job_id, :company_id, :recruiter_id, :title, :description_text, :seniority_level, :employment_type,
                :location_text, :salary_min, :salary_max, :salary_currency, :work_mode, :status, :version, :payload_json)
            """,
            part,
        )
    return len(out)


def load_synthetic_members(max_members: int, chunk: int) -> int:
    """Seed members with resume_text without a CSV."""
    out: list[dict] = []
    users: list[dict] = []
    for i in range(max_members):
        text = (
            f"Experienced professional with background in software and data. "
            f"Skills: Python, JavaScript, SQL, leadership. Project {i}. "
            f"Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 8
        )[:12000]
        cat = random.choice(["Engineering", "Data", "Product", "Design"])
        mid = f"mem_syn_{uuid.uuid4().hex[:10]}"
        email = f"synthetic_member_{i}_{uuid.uuid4().hex[:6]}@example.invalid"
        skills = ["Python", "SQL", "Communication"] if i % 2 else ["Java", "Leadership", "Excel"]
        payload = {
            "member_id": mid,
            "email": email,
            "first_name": "Synthetic",
            "last_name": str(i + 1),
            "headline": f"{cat} — bench profile",
            "location": "United States",
            "skills": skills,
        }
        out.append(
            {
                "member_id": mid,
                "email": email,
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "headline": payload["headline"][:220],
                "about_text": text[:5000],
                "location_text": payload["location"],
                "profile_version": 1,
                "payload_json": json.dumps(payload),
                "skills_json": json.dumps(skills),
                "experience_json": json.dumps([]),
                "education_json": json.dumps([]),
                "resume_text": text,
            }
        )
        users.append(
            {
                "user_id": mid,
                "email": email,
                "password_hash": "imported",
                "subject_type": "member",
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "payload_json": json.dumps({"user_type": "member"}),
            }
        )
    for part in (out[i : i + chunk] for i in range(0, len(out), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO members (member_id, email, first_name, last_name, headline, about_text, location_text,
                profile_version, payload_json, skills_json, experience_json, education_json, resume_text)
            VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text,
                :profile_version, :payload_json, :skills_json, :experience_json, :education_json, :resume_text)
            """,
            part,
        )
    for part in (users[i : i + chunk] for i in range(0, len(users), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO users (user_id, email, password_hash, subject_type, first_name, last_name, payload_json)
            VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name, :payload_json)
            """,
            part,
        )
    return len(out)


def _company_name_lookup(jobs_csv: Path) -> dict[str, str]:
    """linkedin-job-2023 ships `companies.csv` beside `job_postings.csv`."""
    p = jobs_csv.parent / "companies.csv"
    if not p.exists():
        return {}
    rows = _read_csv_rows(p, 500_000)
    if not rows:
        return {}
    sample = rows[0]
    cid = _pick_col(sample, ["company_id", "id"])
    cname = _pick_col(sample, ["name", "company_name"])
    if not cid or not cname:
        return {}
    out: dict[str, str] = {}
    for r in rows:
        k = (r.get(cid or "") or "").strip()
        v = (r.get(cname or "") or "").strip()
        if k and v:
            out[k] = v
    return out


def load_jobs(path: Path, max_jobs: int, chunk: int) -> int:
    rows_raw = _read_csv_rows(path, max_jobs)
    if not rows_raw:
        return 0
    sample = rows_raw[0]
    c_title = _pick_col(sample, ["title", "job_title", "position", "name"])
    c_desc = _pick_col(sample, ["description", "job_description", "desc", "summary"])
    c_company = _pick_col(sample, ["company", "company_name", "employer", "organization"])
    c_company_id = _pick_col(sample, ["company_id"])
    c_location = _pick_col(sample, ["location", "job_location", "city", "place"])
    c_emp = _pick_col(sample, ["employment_type", "job_type", "type", "formatted_work_type", "work_type"])
    c_sen = _pick_col(sample, ["seniority_level", "seniority", "level", "experience", "formatted_experience_level"])
    c_ind = _pick_col(sample, ["industry", "company_industry", "sector"])
    c_smin = _pick_col(sample, ["min_salary"])
    c_smax = _pick_col(sample, ["max_salary"])
    if not c_title or not c_desc:
        raise SystemExit(f"Could not detect title/description columns in {path}. Headers: {list(sample.keys())[:30]}")

    company_by_id = _company_name_lookup(path)
    work_modes = ["remote", "hybrid", "onsite"]
    out: list[dict] = []
    for r in rows_raw:
        title = (r.get(c_title or "") or "Imported role")[:160]
        desc = (r.get(c_desc or "") or title)[:8000]
        company = (r.get(c_company or "") if c_company else "").strip()
        if not company and c_company_id:
            company = company_by_id.get((r.get(c_company_id) or "").strip(), "") or "Unknown company"
        if not company:
            company = "Unknown company"
        location = (r.get(c_location or "") if c_location else "")[:120] or "Remote"
        emp = (r.get(c_emp or "") if c_emp else "full_time").lower().replace(" ", "_")[:32] or "full_time"
        sen = (r.get(c_sen or "") if c_sen else "mid").lower()[:32] or "mid"
        industry = (r.get(c_ind or "") if c_ind else "")[:80] or "General"
        job_id = f"job_kg_{uuid.uuid4().hex[:10]}"
        smin, smax = synthetic_salary(sen)
        if c_smin and c_smax:
            try:
                lo = int(float((r.get(c_smin) or "").replace(",", "") or 0))
                hi = int(float((r.get(c_smax) or "").replace(",", "") or 0))
                if lo > 0 and hi >= lo:
                    smin, smax = lo, hi
            except (TypeError, ValueError):
                pass
        wm = random.choices(work_modes, weights=[3, 4, 3])[0]
        payload = {
            "job_id": job_id,
            "company_id": BULK_COMPANY_ID,
            "recruiter_id": BULK_RECRUITER_ID,
            "title": title,
            "description": desc,
            "location": location,
            "employment_type": emp if emp in {"full_time", "part_time", "contract", "internship"} else "full_time",
            "seniority_level": sen if len(sen) < 33 else "mid",
            "work_mode": wm,
            "company_name": company[:160],
            "company_industry": industry,
            "skills_required": [],
            "status": "open",
            "salary_min": smin,
            "salary_max": smax,
            "salary_currency": "USD",
        }
        out.append(
            {
                "job_id": job_id,
                "company_id": BULK_COMPANY_ID,
                "recruiter_id": BULK_RECRUITER_ID,
                "title": title,
                "description_text": desc,
                "seniority_level": payload["seniority_level"],
                "employment_type": payload["employment_type"],
                "location_text": location,
                "salary_min": smin,
                "salary_max": smax,
                "salary_currency": "USD",
                "work_mode": wm,
                "status": "open",
                "version": 1,
                "payload_json": json.dumps(payload),
            }
        )

    for part in (out[i : i + chunk] for i in range(0, len(out), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level,
                employment_type, location_text, salary_min, salary_max, salary_currency, work_mode, status, version, payload_json)
            VALUES (:job_id, :company_id, :recruiter_id, :title, :description_text, :seniority_level, :employment_type,
                :location_text, :salary_min, :salary_max, :salary_currency, :work_mode, :status, :version, :payload_json)
            """,
            part,
        )
    return len(out)


def load_resumes(path: Path, max_members: int, chunk: int) -> int:
    rows_raw = _read_csv_rows(path, max_members)
    if not rows_raw:
        return 0
    sample = rows_raw[0]
    c_resume = _pick_col(sample, ["resume_str", "resume_text", "Resume", "cv", "text", "content"])
    c_cat = _pick_col(sample, ["category", "job_category", "label", "role"])
    if not c_resume:
        raise SystemExit(f"Could not detect resume text column in {path}. Headers: {list(sample.keys())[:30]}")

    out: list[dict] = []
    users: list[dict] = []
    for i, r in enumerate(rows_raw):
        text = (r.get(c_resume or "") or "")[:60000]
        if len(text) < 40:
            continue
        cat = (r.get(c_cat or "") if c_cat else "")[:160] or "Professional"
        mid = f"mem_kg_{uuid.uuid4().hex[:10]}"
        email = f"kaggle_member_{i}_{uuid.uuid4().hex[:6]}@example.invalid"
        skills = ["Python", "SQL", "Communication", "Analysis"] if i % 2 else ["Java", "Leadership", "Excel"]
        payload = {
            "member_id": mid,
            "email": email,
            "first_name": "Imported",
            "last_name": str(i + 1),
            "headline": f"{cat} — imported profile",
            "location": "United States",
            "skills": skills,
        }
        out.append(
            {
                "member_id": mid,
                "email": email,
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "headline": payload["headline"][:220],
                "about_text": text[:5000],
                "location_text": payload["location"],
                "profile_version": 1,
                "payload_json": json.dumps(payload),
                "skills_json": json.dumps(skills),
                "experience_json": json.dumps([]),
                "education_json": json.dumps([]),
                "resume_text": text,
            }
        )
        users.append(
            {
                "user_id": mid,
                "email": email,
                "password_hash": "imported",
                "subject_type": "member",
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "payload_json": json.dumps({"user_type": "member"}),
            }
        )

    for part in (out[i : i + chunk] for i in range(0, len(out), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO members (member_id, email, first_name, last_name, headline, about_text, location_text,
                profile_version, payload_json, skills_json, experience_json, education_json, resume_text)
            VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text,
                :profile_version, :payload_json, :skills_json, :experience_json, :education_json, :resume_text)
            """,
            part,
        )
    for part in (users[i : i + chunk] for i in range(0, len(users), chunk)):
        execute_many(
            """
            INSERT IGNORE INTO users (user_id, email, password_hash, subject_type, first_name, last_name, payload_json)
            VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name, :payload_json)
            """,
            part,
        )
    return len(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Kaggle CSV exports into MySQL.")
    parser.add_argument("--jobs-csv", type=Path, help="Path to jobs CSV")
    parser.add_argument("--resumes-csv", type=Path, help="Path to resumes CSV")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Generate synthetic jobs/members in bulk (no CSV). Uses --max-jobs and --max-members.",
    )
    parser.add_argument("--max-jobs", type=int, default=10_000)
    parser.add_argument("--max-members", type=int, default=5_000)
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument(
        "--synthetic-members-extra",
        type=int,
        default=0,
        help="After CSV import (or alone), insert this many synthetic members (mem_syn_*). Use to reach 5k+ when Kaggle Resume.csv has fewer valid rows.",
    )
    args = parser.parse_args()

    if not args.synthetic and not args.jobs_csv and not args.resumes_csv and args.synthetic_members_extra <= 0:
        parser.error("Provide --synthetic and/or --jobs-csv / --resumes-csv and/or --synthetic-members-extra N")
    if args.synthetic and (args.jobs_csv or args.resumes_csv or args.synthetic_members_extra > 0):
        parser.error("Use --synthetic alone, or CSV paths / --synthetic-members-extra — not --synthetic with CSV or extra.")

    execute("CREATE DATABASE IF NOT EXISTS linkedin_sim")
    ensure_bulk_recruiter()
    if args.synthetic:
        n_jobs = load_synthetic_jobs(args.max_jobs, args.chunk_size)
        n_mem = load_synthetic_members(args.max_members, args.chunk_size)
    else:
        n_jobs = load_jobs(args.jobs_csv, args.max_jobs, args.chunk_size) if args.jobs_csv else 0
        n_mem = load_resumes(args.resumes_csv, args.max_members, args.chunk_size) if args.resumes_csv else 0
        if args.synthetic_members_extra > 0:
            n_mem += load_synthetic_members(args.synthetic_members_extra, args.chunk_size)
    print(f"Import complete: {n_jobs} jobs, {n_mem} members (INSERT IGNORE — skips duplicates).")


if __name__ == "__main__":
    main()
