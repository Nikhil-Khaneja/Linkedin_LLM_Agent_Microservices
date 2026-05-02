#!/usr/bin/env python3
"""Seed scale-test data directly into MySQL.

Defaults to 10,000 members, recruiters/companies, and jobs so the project can
show a real scale pipeline without paying the HTTP/API cost for every row.
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

backend_root = str((Path(__file__).resolve().parents[1] / 'backend'))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from services.shared.relational import execute, execute_many  # noqa: E402


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def seed_companies_and_recruiters(count: int, chunk: int) -> None:
    companies = []
    recruiters = []
    users = []
    for i in range(1, count + 1):
        cid = f'cmp_seed_{i:05d}'
        rid = f'rec_seed_{i:05d}'
        companies.append({
            'company_id': cid,
            'company_name': f'Seed Company {i}',
            'company_industry': 'Software',
            'company_size': '1000+',
            'payload_json': json.dumps({'company_id': cid, 'company_name': f'Seed Company {i}'}),
        })
        recruiters.append({
            'recruiter_id': rid,
            'company_id': cid,
            'email': f'recruiter{i}@seed.example.com',
            'name': f'Recruiter {i}',
            'phone': None,
            'access_level': 'admin',
            'payload_json': json.dumps({'recruiter_id': rid, 'company_id': cid}),
        })
        users.append({
            'user_id': rid,
            'email': f'recruiter{i}@seed.example.com',
            'password_hash': 'seeded',
            'subject_type': 'recruiter',
            'first_name': 'Recruiter',
            'last_name': str(i),
            'payload_json': json.dumps({'user_id': rid, 'user_type': 'recruiter'}),
        })
    execute_many("""
        INSERT IGNORE INTO companies (company_id, company_name, company_industry, company_size, payload_json)
        VALUES (:company_id, :company_name, :company_industry, :company_size, :payload_json)
    """, companies)
    execute_many("""
        INSERT IGNORE INTO recruiters (recruiter_id, company_id, email, name, phone, access_level, payload_json)
        VALUES (:recruiter_id, :company_id, :email, :name, :phone, :access_level, :payload_json)
    """, recruiters)
    execute_many("""
        INSERT IGNORE INTO users (user_id, email, password_hash, subject_type, first_name, last_name, payload_json)
        VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name, :payload_json)
    """, users)


def seed_members(count: int, chunk: int) -> None:
    rows = []
    users = []
    for i in range(1, count + 1):
        mid = f'mem_seed_{i:05d}'
        skills = ['Python', 'SQL', 'Kafka', 'FastAPI'] if i % 2 else ['Java', 'MySQL', 'Redis', 'React']
        payload = {
            'member_id': mid,
            'email': f'member{i}@seed.example.com',
            'first_name': f'Member{i}',
            'last_name': 'Seed',
            'headline': 'Software Engineer',
            'location': 'San Jose, CA',
            'skills': skills,
        }
        rows.append({
            'member_id': mid,
            'email': payload['email'],
            'first_name': payload['first_name'],
            'last_name': payload['last_name'],
            'headline': payload['headline'],
            'about_text': 'Scale seed profile',
            'location_text': payload['location'],
            'profile_version': 1,
            'payload_json': json.dumps(payload),
            'skills_json': json.dumps(skills),
            'experience_json': json.dumps([]),
            'education_json': json.dumps([]),
        })
        users.append({
            'user_id': mid,
            'email': payload['email'],
            'password_hash': 'seeded',
            'subject_type': 'member',
            'first_name': payload['first_name'],
            'last_name': payload['last_name'],
            'payload_json': json.dumps({'user_id': mid, 'user_type': 'member'}),
        })
    for part in chunked(rows, chunk):
        execute_many("""
            INSERT IGNORE INTO members (member_id, email, first_name, last_name, headline, about_text, location_text, profile_version, payload_json, skills_json, experience_json, education_json)
            VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text, :profile_version, :payload_json, :skills_json, :experience_json, :education_json)
        """, part)
    for part in chunked(users, chunk):
        execute_many("""
            INSERT IGNORE INTO users (user_id, email, password_hash, subject_type, first_name, last_name, payload_json)
            VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name, :payload_json)
        """, part)


def seed_jobs(count: int, recruiter_count: int, chunk: int) -> None:
    rows = []
    for i in range(1, count + 1):
        recruiter_num = ((i - 1) % recruiter_count) + 1
        recruiter_id = f'rec_seed_{recruiter_num:05d}'
        company_id = f'cmp_seed_{recruiter_num:05d}'
        job_id = f'job_seed_{i:05d}'
        title = f'Seed Software Engineer {i}'
        payload = {
            'job_id': job_id,
            'company_id': company_id,
            'recruiter_id': recruiter_id,
            'title': title,
            'description': 'Scale seed job with Kafka, MySQL, MongoDB, and FastAPI.',
            'location': 'San Jose, CA',
            'employment_type': 'full_time',
            'work_mode': 'hybrid',
            'seniority_level': 'mid',
            'skills_required': ['Python', 'Kafka', 'MySQL'],
            'status': 'open',
        }
        rows.append({
            'job_id': job_id,
            'company_id': company_id,
            'recruiter_id': recruiter_id,
            'title': title,
            'description_text': payload['description'],
            'seniority_level': 'mid',
            'employment_type': 'full_time',
            'location_text': 'San Jose, CA',
            'work_mode': 'hybrid',
            'status': 'open',
            'version': 1,
            'payload_json': json.dumps(payload),
        })
    for part in chunked(rows, chunk):
        execute_many("""
            INSERT IGNORE INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level, employment_type, location_text, work_mode, status, version, payload_json)
            VALUES (:job_id, :company_id, :recruiter_id, :title, :description_text, :seniority_level, :employment_type, :location_text, :work_mode, :status, :version, :payload_json)
        """, part)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--members', type=int, default=10000)
    parser.add_argument('--recruiters', type=int, default=10000)
    parser.add_argument('--jobs', type=int, default=10000)
    parser.add_argument('--chunk-size', type=int, default=500)
    args = parser.parse_args()

    execute('CREATE DATABASE IF NOT EXISTS linkedin_sim')
    seed_companies_and_recruiters(args.recruiters, args.chunk_size)
    seed_members(args.members, args.chunk_size)
    seed_jobs(args.jobs, args.recruiters, args.chunk_size)
    print(f'Seed complete: {args.members} members, {args.recruiters} recruiters/companies, {args.jobs} jobs.')


if __name__ == '__main__':
    main()
