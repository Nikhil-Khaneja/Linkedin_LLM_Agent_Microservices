#!/usr/bin/env python3
"""
Bulk-load Kaggle-style CSVs into MySQL (direct INSERTs; same schema as the app — no API / architecture change).

Datasets (download CSVs locally, then point --csv at the file):
  Jobs:  LinkedIn Job 2023  https://www.kaggle.com/datasets/rajatraj0502/linkedin-job-2023
         or LinkedIn Data Jobs https://www.kaggle.com/datasets/joykimaiyo18/linkedin-data-jobs-dataset
  Resumes: Resume Dataset https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset
           or Resume Classification NLP https://www.kaggle.com/datasets/hassnainzaidi/resume-classification-dataset-for-nlp

Primary CSV shapes:
  job_postings.csv (linkedin-job-2023): job_id, company_id, title, description, salary columns,
    formatted_work_type, location, formatted_experience_level, skills_desc, remote_allowed, …
  Resume.csv (snehaanbhawal resume-dataset): ID, Resume_str, Resume_html, Category

Place files under ./data/kaggle/ or ./data/kaggle_download/ (see data/README.md). Example (10k jobs, 500 recruiters, 1k members, 10k applications):
  export MYSQL_HOST=127.0.0.1 MYSQL_USER=root MYSQL_PASSWORD=root MYSQL_DATABASE=linkedin_sim
  python3 scripts/bulk_seed_datasets.py jobs --csv ./data/kaggle/job_postings.csv --recruiters 500 --jobs 10000 --run-id kaggle1 --replace-run
  python3 scripts/bulk_seed_datasets.py members --csv ./data/kaggle_download/Resume/Resume.csv --members 1000 --run-id kaggle1 --replace-run
  python3 scripts/bulk_seed_datasets.py applications --run-id kaggle1 --per-member 10 --replace-run
  python3 scripts/bulk_seed_datasets.py stats
  python3 scripts/bulk_seed_datasets.py stats --run-id kaggle1

Bulk applications are direct INSERTs (no Kafka). Use scripts/seed_full_data.py for a small all-HTTP demo; use applications here for large-scale DB fixtures.

Perf: uses executemany in batches; apply infra/mysql/002_indexes.sql + 006_jobs_fulltext.sql on the DB for search at scale.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import pymysql
except ImportError as e:
    print("Install PyMySQL: pip install pymysql", file=sys.stderr)
    raise SystemExit(1) from e


def connect():
    """Long timeouts help SSH tunnels; avoid huge multi-row INSERTs (see job batch size)."""
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", "root"),
            database=os.environ.get("MYSQL_DATABASE", "linkedin_sim"),
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "60")),
            read_timeout=int(os.environ.get("MYSQL_READ_TIMEOUT", "600")),
            write_timeout=int(os.environ.get("MYSQL_WRITE_TIMEOUT", "600")),
        )
    except pymysql.err.OperationalError as e:
        if e.args and e.args[0] == 2003:
            print(
                f"MySQL unreachable at {host}:{port}. "
                "From your laptop: open an SSH tunnel (-L 3307:127.0.0.1:3306) and set MYSQL_PORT=3307. "
                "On the EC2 box: run ./scripts/bulk_seed_on_ec2_host.sh (see infra/ecs-ec2/README.md).",
                file=sys.stderr,
                flush=True,
            )
        raise


def norm_row(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = str(k).strip().lower().replace(" ", "_").replace("-", "_")
        out[key] = "" if v is None else str(v).strip()
    return out


def pick(row: dict[str, str], *candidates: str, default: str = "") -> str:
    for c in candidates:
        if c in row and row[c]:
            return row[c][:8000] if len(row[c]) > 8000 else row[c]
    return default


def _normalize_company_id_key(s: str) -> str:
    """Match job_postings.company_id to companies.csv (handles '18856871.0' style floats)."""
    t = (s or "").strip()
    if not t:
        return ""
    try:
        x = float(t)
        if abs(x) < 2**53 and x == int(x):
            return str(int(x))
    except (ValueError, OverflowError):
        pass
    return t


def _load_company_names_map(csv_path: str) -> dict[str, str]:
    """linkedin-job-2023 companies.csv: company_id, name, …"""
    p = Path(csv_path)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = norm_row(raw)
            cid = _normalize_company_id_key(row.get("company_id", ""))
            name = (row.get("name") or row.get("company_name") or "").strip()
            if cid and name:
                out[cid] = name[:200]
    return out


def batched(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


_TAG_RE = re.compile(r"<[^>]+>", re.I)


def _strip_html(html: str, limit: int = 60000) -> str:
    if not html:
        return ""
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _name_from_resume_text(resume_plain: str) -> tuple[str, str] | None:
    """Use the first substantive line (often a name or title) for display names."""
    for line in (resume_plain or "").splitlines():
        s = line.strip()
        if len(s) < 3:
            continue
        head = re.split(r"[/|,]+", s, maxsplit=1)[0].strip()
        parts = head.split()
        if len(parts) >= 2 and len(head) <= 120:
            return parts[0][:80], parts[1][:80]
        if len(parts) == 1 and len(parts[0]) <= 40:
            return parts[0][:80], "Member"
    return None


def cmd_jobs(args: argparse.Namespace) -> int:
    run = re.sub(r"[^a-z0-9_]", "_", (args.run_id or "seed").lower())[:24]
    n_rec = max(1, int(args.recruiters))
    n_jobs = max(1, int(args.jobs))

    companies: list[tuple] = []
    recruiters: list[tuple] = []
    for i in range(1, n_rec + 1):
        cid = f"cmp_{run}_{i:04d}"
        rid = f"rec_{run}_{i:04d}"
        companies.append(
            (
                cid,
                f"Bulk Co {run} {i}",
                "Technology",
                "medium",
                json.dumps({"company_id": cid, "company_name": f"Bulk Co {run} {i}", "company_industry": "Technology", "company_size": "medium"}),
            )
        )
        recruiters.append(
            (
                rid,
                cid,
                f"recruiter+{run}+{i}@bulk-seed.local",
                f"Recruiter {i}",
                "",
                "admin",
                json.dumps({"recruiter_id": rid, "company_id": cid, "email": f"recruiter+{run}+{i}@bulk-seed.local", "name": f"Recruiter {i}", "access_level": "admin"}),
            )
        )

    companies_side = (getattr(args, "companies_csv", None) or "").strip()
    if not companies_side:
        cand = Path(args.csv).resolve().parent / "companies.csv"
        if cand.is_file():
            companies_side = str(cand)
    company_by_id = _load_company_names_map(companies_side) if companies_side else {}
    if company_by_id:
        print(f"Company name lookup: {len(company_by_id)} rows from {companies_side}", flush=True)

    rows_out: list[tuple] = []
    with open(args.csv, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for idx, raw in enumerate(reader):
            if len(rows_out) >= n_jobs:
                break
            r = norm_row(raw)
            title = pick(
                r,
                "title",
                "job_title",
                "job_title_name",
                "position",
                "job_position",
                "role",
                "job_role",
                "name",
                default="Untitled role",
            )
            desc = pick(
                r,
                "description",
                "job_description",
                "job_description_text",
                "description_text",
                "job_summary",
                "responsibilities",
                "full_description",
                "job_details",
                "overview",
                "summary",
                default="No description provided.",
            )
            if len(desc) < 20:
                desc = (desc + " ") * 5
            desc = desc[:65000]
            company_name = pick(
                r,
                "company",
                "company_name",
                "employer",
                "employer_name",
                "organization",
                "hiring_organization",
                "company_name_clean",
                default="",
            )
            cid_raw = pick(r, "company_id", default="").strip()
            cid_key = _normalize_company_id_key(cid_raw)
            if not company_name.strip() and cid_key and cid_key in company_by_id:
                company_name = company_by_id[cid_key]
            if not company_name.strip():
                company_name = "Unknown company"
            loc = pick(
                r,
                "location",
                "job_location",
                "location_name",
                "city",
                "job_city",
                "state",
                "country",
                "geo",
                default="",
            )
            sal_raw = pick(r, "salary", "salary_range", "compensation", "pay_range", "salary_estimate", default="")
            smin, smax, scur = _parse_salary(sal_raw)
            # rajatraj0502 / linkedin-job-2023: job_postings.csv uses min_salary, max_salary, currency
            if smin is None and smax is None:
                try:
                    mn = pick(r, "min_salary", default="")
                    mx = pick(r, "max_salary", default="")
                    if mn.strip() or mx.strip():
                        smin = int(float(mn)) if mn.strip() else None
                        smax = int(float(mx)) if mx.strip() else smin
                        scur = (pick(r, "currency", default="") or "USD")[:8]
                except (ValueError, TypeError):
                    pass
            seniority = pick(r, "formatted_experience_level", "seniority_level", "experience_level", default="mid")[:32]
            emp_type = pick(r, "work_type", "formatted_work_type", "employment_type", "application_type", default="full_time")[:32]
            remote_raw = pick(r, "remote_allowed", default="").strip().lower()
            fwt = pick(r, "formatted_work_type", default="").lower()
            work_mode = "remote" if remote_raw in ("1", "true", "yes", "y") or "remote" in fwt else "hybrid"

            rid = f"rec_{run}_{(idx % n_rec) + 1:04d}"
            cid = f"cmp_{run}_{(idx % n_rec) + 1:04d}"
            jid = f"job_{run}_{idx + 1:07d}"
            skills_blob = pick(r, "skills_desc", "skills", default="")[:8000]
            payload = {
                "job_id": jid,
                "company_id": cid,
                "recruiter_id": rid,
                "title": title[:160],
                "description": desc,
                "seniority_level": seniority,
                "employment_type": emp_type,
                "location": loc[:120] if loc else "Remote",
                "work_mode": work_mode,
                "status": "open",
                "version": 1,
                "salary_min": smin,
                "salary_max": smax,
                "salary_currency": scur,
                "company_name": company_name[:160],
                "skills_desc": skills_blob,
                "source_job_id": pick(r, "job_id", default="")[:64],
                "source_company_id": (cid_key or cid_raw or "")[:64],
            }
            rows_out.append(
                (
                    jid,
                    cid,
                    rid,
                    title[:160],
                    desc,
                    seniority,
                    emp_type,
                    (loc[:120] if loc else "Remote"),
                    smin,
                    smax,
                    scur,
                    work_mode,
                    "open",
                    1,
                    json.dumps(payload),
                    "[]",
                    "[]",
                    "[]",
                )
            )

    if not rows_out:
        print("No job rows read from CSV.", file=sys.stderr)
        return 1

    conn = connect()
    try:
        with conn.cursor() as cur:
            if args.replace_run:
                cur.execute("DELETE FROM applications WHERE job_id LIKE %s", (f"job_{run}_%",))
                cur.execute("DELETE FROM jobs WHERE job_id LIKE %s", (f"job_{run}_%",))
                cur.execute("DELETE FROM recruiters WHERE recruiter_id LIKE %s", (f"rec_{run}_%",))
                cur.execute("DELETE FROM companies WHERE company_id LIKE %s", (f"cmp_{run}_%",))
            cur.executemany(
                """INSERT IGNORE INTO companies (company_id, company_name, company_industry, company_size, payload_json)
                   VALUES (%s,%s,%s,%s,%s)""",
                companies,
            )
            cur.executemany(
                """INSERT IGNORE INTO recruiters (recruiter_id, company_id, email, name, phone, access_level, payload_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                recruiters,
            )
            # Large descriptions + JSON per row → keep batches small (2013 / max_allowed_packet over SSH).
            job_batch = max(5, min(int(os.environ.get("BULK_SEED_JOB_BATCH", "30")), 200))
            for chunk in batched(rows_out, job_batch):
                cur.executemany(
                    """INSERT INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level,
                       employment_type, location_text, salary_min, salary_max, salary_currency, work_mode, status, version,
                       payload_json, skills_json, experience_json, education_json)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    chunk,
                )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    print(f"Inserted companies={len(companies)} recruiters={len(recruiters)} jobs={len(rows_out)} (run_id={run})")
    return 0


def _parse_salary(s: str) -> tuple[int | None, int | None, str]:
    if not s:
        return None, None, "USD"
    digits = re.findall(r"\d[\d,]*", s.replace(",", ""))
    if len(digits) >= 2:
        try:
            return int(digits[0]), int(digits[1]), "USD"
        except ValueError:
            return None, None, "USD"
    if len(digits) == 1:
        try:
            v = int(digits[0])
            return v, v, "USD"
        except ValueError:
            pass
    return None, None, "USD"


def cmd_members(args: argparse.Namespace) -> int:
    run = re.sub(r"[^a-z0-9_]", "_", (args.run_id or "seed").lower())[:24]
    n = max(1, int(args.members))

    rows_out: list[tuple] = []
    with open(args.csv, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for idx, raw in enumerate(reader):
            if len(rows_out) >= n:
                break
            r = norm_row(raw)
            resume_text = pick(
                r,
                "resume_str",
                "resume",
                "resume_text",
                "cv_text",
                "cleaned_resume",
                "raw_resume",
                "text",
                "content",
                default="",
            )
            if len(resume_text) < 40:
                resume_text = _strip_html(pick(r, "resume_html", "resume_html_str", default=""))
            category = pick(r, "category", "label", "job_category", "field", "job_title", "class", default="Professional")
            if len(resume_text) < 40:
                resume_text = f"Synthetic profile body for {category}. " * 8
            resume_text = resume_text[:60000]
            headline = (category or "Member")[:218]
            named = _name_from_resume_text(resume_text)
            if named:
                fname, lname = named
            else:
                fname, lname = _split_name(pick(r, "name", "candidate_name", default=f"User{idx+1}"))
            mid = f"mem_{run}_{idx + 1:07d}"
            email = f"member+{run}+{idx+1}@bulk-seed.local"
            src_id = pick(r, "id", "resume_id", "candidate_id", default="")
            payload = {
                "email": email,
                "first_name": fname,
                "last_name": lname,
                "headline": headline,
                "about_summary": resume_text[:5000],
                "skills": [],
                "source_resume_id": src_id,
                "category": category,
            }
            rows_out.append(
                (
                    mid,
                    email,
                    fname[:80],
                    lname[:80],
                    headline[:220],
                    resume_text[:5000],
                    pick(r, "location", "city", default="")[:255] or "United States",
                    1,
                    0,
                    json.dumps(payload),
                    "[]",
                    "[]",
                    "[]",
                    "",
                    "",
                    resume_text,
                    "",
                    headline[:160],
                )
            )

    if not rows_out:
        print("No member rows read from CSV.", file=sys.stderr)
        return 1

    conn = connect()
    try:
        with conn.cursor() as cur:
            if args.replace_run:
                cur.execute("DELETE FROM applications WHERE member_id LIKE %s", (f"mem_{run}_%",))
                cur.execute("DELETE FROM members WHERE member_id LIKE %s", (f"mem_{run}_%",))
            mem_batch = max(10, min(int(os.environ.get("BULK_SEED_MEMBER_BATCH", "50")), 300))
            for chunk in batched(rows_out, mem_batch):
                cur.executemany(
                    """INSERT INTO members (member_id, email, first_name, last_name, headline, about_text, location_text,
                       profile_version, is_deleted, payload_json, skills_json, experience_json, education_json,
                       profile_photo_url, resume_url, resume_text, current_company, current_title)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    chunk,
                )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    print(f"Inserted members={len(rows_out)} (run_id={run})")
    return 0


def cmd_applications(args: argparse.Namespace) -> int:
    """Insert applications for mem_{run}_* members against job_{run}_* jobs (same run_id as bulk jobs/members)."""
    run = re.sub(r"[^a-z0-9_]", "_", (args.run_id or "seed").lower())[:24]
    per = max(1, int(args.per_member))
    cap = int(args.max_applications) if int(args.max_applications) > 0 else 0
    rng = random.Random(int(args.seed))

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT member_id FROM members WHERE member_id LIKE %s ORDER BY member_id",
                (f"mem_{run}_%",),
            )
            member_ids = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT job_id FROM jobs WHERE job_id LIKE %s ORDER BY job_id",
                (f"job_{run}_%",),
            )
            job_ids = [r[0] for r in cur.fetchall()]

        if not member_ids:
            print(f"No members matching mem_{run}_%. Run: members --csv ... --run-id {args.run_id}", file=sys.stderr)
            return 1
        if not job_ids:
            print(f"No jobs matching job_{run}_%. Run: jobs --csv ... --run-id {args.run_id}", file=sys.stderr)
            return 1

        n_pick = min(per, len(job_ids))
        rows: list[tuple] = []
        for mid in member_ids:
            if cap and len(rows) >= cap:
                break
            take = n_pick if not cap else min(n_pick, cap - len(rows))
            if take <= 0:
                break
            picks = rng.sample(job_ids, take)
            for jid in picks:
                app_id = f"app_{uuid.uuid4().hex[:10]}"
                dt = (datetime.now() - timedelta(days=rng.randint(0, 60))).strftime("%Y-%m-%d %H:%M:%S")
                resume_ref = "bulk-seed:resume"
                cover = "Seeded application for integration testing."
                payload = {
                    "application_id": app_id,
                    "job_id": jid,
                    "member_id": mid,
                    "resume_ref": resume_ref,
                    "cover_letter": cover,
                    "status": "submitted",
                    "application_datetime": dt,
                }
                rows.append(
                    (
                        app_id,
                        jid,
                        mid,
                        resume_ref,
                        cover,
                        "submitted",
                        dt,
                        json.dumps(payload),
                    )
                )

        with conn.cursor() as cur:
            if args.replace_run:
                cur.execute("DELETE FROM applications WHERE job_id LIKE %s", (f"job_{run}_%",))
            app_batch = max(25, min(int(os.environ.get("BULK_SEED_APP_BATCH", "150")), 500))
            for chunk in batched(rows, app_batch):
                cur.executemany(
                    """INSERT IGNORE INTO applications
                       (application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    chunk,
                )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    print(
        f"Inserted applications rows={len(rows)} for run_id={run} "
        f"(INSERT IGNORE skips duplicate job_id+member_id pairs)"
    )
    return 0


def _split_name(s: str) -> tuple[str, str]:
    parts = (s or "Bulk User").strip().split()
    if len(parts) == 1:
        return parts[0][:80], "Member"
    return parts[0][:80], " ".join(parts[1:])[:80]


def cmd_stats(args: argparse.Namespace) -> int:
    """Print MySQL row counts (same MYSQL_* env as jobs/members seed)."""
    run_raw = (getattr(args, "run_id", None) or "").strip()
    run = re.sub(r"[^a-z0-9_]", "_", run_raw.lower())[:24] if run_raw else ""

    conn = connect()
    try:

        def one(sql: str, params: tuple | None = None) -> int:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else 0

        jobs = one("SELECT COUNT(*) FROM jobs")
        jobs_open = one("SELECT COUNT(*) FROM jobs WHERE LOWER(COALESCE(status,'')) = 'open'")
        members = one("SELECT COUNT(*) FROM members")
        applications = one("SELECT COUNT(*) FROM applications")
        companies = one("SELECT COUNT(*) FROM companies")
        recruiters = one("SELECT COUNT(*) FROM recruiters")

        print(f"jobs_total={jobs}")
        print(f"jobs_open={jobs_open}")
        print(f"members={members}")
        print(f"applications={applications}")
        print(f"companies={companies}")
        print(f"recruiters={recruiters}")

        if run:
            print(f"jobs_job_{run}_% = {one('SELECT COUNT(*) FROM jobs WHERE job_id LIKE %s', (f'job_{run}_%',))}")
            print(f"members_mem_{run}_% = {one('SELECT COUNT(*) FROM members WHERE member_id LIKE %s', (f'mem_{run}_%',))}")
            print(f"applications_for_those_jobs = {one('SELECT COUNT(*) FROM applications WHERE job_id LIKE %s', (f'job_{run}_%',))}")
    finally:
        conn.close()

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Bulk seed MySQL from Kaggle-style CSVs.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pj = sub.add_parser("jobs", help="Load jobs CSV + synthetic recruiter/company grid")
    pj.add_argument("--csv", required=True)
    pj.add_argument(
        "--companies-csv",
        default="",
        help="Optional companies.csv (linkedin-job-2023). Default: companies.csv next to --csv if present.",
    )
    pj.add_argument("--recruiters", type=int, default=500)
    pj.add_argument("--jobs", type=int, default=10000)
    pj.add_argument("--run-id", default="kaggle", help="Id prefix token (alphanumeric)")
    pj.add_argument("--replace-run", action="store_true", help="Delete prior rows for this run_id then reload")
    pj.set_defaults(func=cmd_jobs)

    pm = sub.add_parser("members", help="Load resume/profile text CSV as member rows")
    pm.add_argument("--csv", required=True)
    pm.add_argument("--members", type=int, default=1000, help="Row cap from CSV (default 1000 for resume-scale demos)")
    pm.add_argument("--run-id", default="kaggle")
    pm.add_argument("--replace-run", action="store_true")
    pm.set_defaults(func=cmd_members)

    pa = sub.add_parser(
        "applications",
        help="Insert applications: bulk members apply to random jobs for the same --run-id (direct SQL, not HTTP)",
    )
    pa.add_argument("--run-id", default="kaggle", help="Must match jobs/members bulk seed --run-id")
    pa.add_argument(
        "--per-member",
        type=int,
        default=10,
        help="How many distinct jobs each member applies to (default 10 → 1000 members × 10 = 10k applications)",
    )
    pa.add_argument(
        "--max-applications",
        type=int,
        default=0,
        help="Cap total rows (0 = no cap). Useful to sample before full N*per-member load.",
    )
    pa.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible job picks")
    pa.add_argument(
        "--replace-run",
        action="store_true",
        help="Delete applications whose job_id belongs to this run before insert",
    )
    pa.set_defaults(func=cmd_applications)

    ps = sub.add_parser(
        "stats",
        help="Print MySQL row counts (jobs, members, applications, …). Uses MYSQL_* env.",
    )
    ps.add_argument(
        "--run-id",
        default="",
        help="If set, also print counts for job_/mem_ ids matching this bulk seed run (e.g. aws1)",
    )
    ps.set_defaults(func=cmd_stats)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
