from __future__ import annotations

import re
from dataclasses import dataclass

from services.shared.resume_parser import extract_keywords

COMMON_SKILLS = {
    'python', 'java', 'javascript', 'typescript', 'react', 'node', 'node.js', 'sql', 'mysql', 'mongodb', 'redis', 'kafka',
    'docker', 'kubernetes', 'aws', 'gcp', 'azure', 'spark', 'hadoop', 'airflow', 'tensorflow', 'pytorch', 'machine learning',
    'deep learning', 'nlp', 'llm', 'rag', 'fastapi', 'flask', 'django', 'spring', 'c++', 'c#', 'go', 'golang', 'scala', 'rust',
    'html', 'css', 'git', 'linux', 'tableau', 'power bi', 'excel', 'statistics', 'data analysis', 'data science', 'etl', 'api',
    'rest', 'graphql', 'microservices', 'system design', 'elasticsearch', 'mlflow', 'bert', 'pandas', 'numpy', 'scikit-learn',
    'postgresql', 'oracle', 'firebase', 'supabase', 'terraform', 'ansible', 'jenkins', 'ci/cd', 'testing', 'pytest', 'selenium',
    'communication', 'leadership', 'product management', 'project management', 'salesforce', 'figma', 'ux', 'ui', 'superset'
}


@dataclass(slots=True)
class ParsedResume:
    skills: list[str]
    years_experience: float
    education: str
    certifications: list[str]
    resume_excerpt: str

    def as_dict(self) -> dict:
        return {
            'skills': list(self.skills),
            'years_experience': self.years_experience,
            'education': self.education,
            'certifications': list(self.certifications),
            'resume_excerpt': self.resume_excerpt,
        }


def normalize_skill(value) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def skills_from_value(value) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in ('skill_name', 'name', 'skill', 'label'):
                if item.get(key):
                    out.append(str(item.get(key)).strip())
                    break
        elif isinstance(item, str):
            parts = [p.strip() for p in re.split(r'[,|/;\n]', item) if p.strip()]
            out.extend(parts or [item.strip()])
    deduped: list[str] = []
    seen: set[str] = set()
    for item in out:
        norm = normalize_skill(item)
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(item.strip())
    return deduped


def experience_years_from_entries(experience_entries) -> float:
    total = 0.0
    for entry in experience_entries or []:
        if not isinstance(entry, dict):
            continue
        start = entry.get('start_year') or entry.get('from_year') or entry.get('year_from')
        end = entry.get('end_year') or entry.get('to_year') or entry.get('year_to') or entry.get('end')
        try:
            start_num = int(str(start)[:4]) if start else None
        except Exception:
            start_num = None
        try:
            end_num = int(str(end)[:4]) if end and str(end).lower() not in {'present', 'current'} else None
        except Exception:
            end_num = None
        if start_num:
            end_num = end_num or 2026
            if end_num >= start_num:
                total += min(10.0, float(end_num - start_num + 1))
    return total


def collect_resume_text(application: dict, member: dict) -> str:
    chunks: list[str] = []
    for value in (
        application.get('resume_text'),
        application.get('cover_letter'),
        member.get('resume_text'),
        member.get('headline'),
        member.get('about'),
        member.get('about_summary'),
        member.get('current_title'),
        member.get('current_company'),
    ):
        if value:
            chunks.append(str(value))
    for exp in member.get('experience') or []:
        if isinstance(exp, dict):
            chunks.extend([
                str(exp.get('title') or exp.get('role') or ''),
                str(exp.get('company') or exp.get('company_name') or ''),
                str(exp.get('employment_type') or ''),
                str(exp.get('description') or ''),
            ])
        elif exp:
            chunks.append(str(exp))
    for edu in member.get('education') or []:
        if isinstance(edu, dict):
            chunks.extend([
                str(edu.get('school') or ''),
                str(edu.get('degree') or ''),
                str(edu.get('field_of_study') or ''),
                str(edu.get('description') or ''),
            ])
        elif edu:
            chunks.append(str(edu))
    skills = skills_from_value(application.get('skills')) + skills_from_value(member.get('skills'))
    if skills:
        chunks.append('Skills: ' + ', '.join(skills))
    text = '\n'.join([c for c in chunks if c and str(c).strip()])
    return text[:12000]


def parse_resume(resume_text: str, member: dict, application: dict) -> ParsedResume:
    text = resume_text or ''
    lower = text.lower()
    skills = skills_from_value(application.get('skills')) + skills_from_value(member.get('skills'))
    for skill in COMMON_SKILLS:
        if re.search(rf'(?<!\w){re.escape(skill)}(?!\w)', lower):
            skills.append(skill)
    seen: set[str] = set()
    parsed_skills: list[str] = []
    for skill in skills:
        norm = normalize_skill(skill)
        if norm and norm not in seen:
            seen.add(norm)
            parsed_skills.append(skill)
    years = 0.0
    for match in re.findall(r'(\d{1,2})\s*\+?\s*(?:years|yrs)', lower):
        try:
            years = max(years, float(match))
        except Exception:
            pass
    years = max(years, experience_years_from_entries(member.get('experience')))
    education_values: list[str] = []
    for edu in member.get('education') or []:
        if isinstance(edu, dict):
            education_values.append(' '.join([
                str(edu.get('degree') or ''),
                str(edu.get('field_of_study') or ''),
                str(edu.get('school') or ''),
            ]).strip())
        elif edu:
            education_values.append(str(edu))
    edu_text = ' | '.join([e for e in education_values if e])
    if not edu_text:
        for label in ('phd', 'doctorate', 'master', 'msc', 'ms', 'mba', 'bachelor', 'bs', 'b.e', 'btech', 'associate'):
            if label in lower:
                edu_text = label
                break
    certifications = [
        cert.strip()
        for cert in re.findall(r'(aws certified[^,\n]*|google cloud[^,\n]*|azure[^,\n]*certified|pmp|scrum master)', lower)
    ]
    return ParsedResume(
        skills=parsed_skills[:24],
        years_experience=round(years, 1),
        education=edu_text,
        certifications=certifications[:6],
        resume_excerpt=text[:400],
    )


def seniority_target_years(seniority: str | None) -> tuple[int, int]:
    value = (seniority or '').lower()
    if 'intern' in value:
        return (0, 1)
    if 'entry' in value or 'junior' in value:
        return (0, 2)
    if 'mid' in value or 'associate' in value:
        return (2, 5)
    if 'senior' in value or 'lead' in value or 'staff' in value:
        return (5, 9)
    if 'principal' in value or 'director' in value:
        return (8, 15)
    return (1, 6)


def job_skills(job: dict) -> list[str]:
    explicit = skills_from_value(job.get('skills_required')) + skills_from_value(job.get('skills'))
    text = ' '.join([
        str(job.get('title') or ''),
        str(job.get('description') or job.get('description_text') or ''),
    ]).lower()
    inferred = [skill for skill in COMMON_SKILLS if re.search(rf'(?<!\w){re.escape(skill)}(?!\w)', text)]
    combined = explicit + inferred
    seen: set[str] = set()
    out: list[str] = []
    for item in combined:
        norm = normalize_skill(item)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(item)
    return out
