from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from services.shared.relational import fetch_one, fetch_all, execute, execute_many
from services.shared.document_store import find_one, find_many, insert_one, replace_one, update_one


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_mysql_datetime() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def normalize_mysql_datetime(value: Any) -> str:
    if value is None or value == '':
        return now_mysql_datetime()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    if 'T' in text:
        text = text.replace('T', ' ')
    if len(text) >= 19:
        return text[:19]
    return now_mysql_datetime()


def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _from_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default




def _load_company_names(company_ids: list[str]) -> dict[str, str]:
    ids = [cid for cid in dict.fromkeys(company_ids) if cid]
    if not ids:
        return {}
    placeholders = ','.join([f":cid_{i}" for i in range(len(ids))])
    params = {f"cid_{i}": cid for i, cid in enumerate(ids)}
    rows = fetch_all(
        f"SELECT company_id, company_name, payload_json FROM companies WHERE company_id IN ({placeholders})",
        params,
    )
    out = {}
    for row in rows:
        payload = _from_json(row.get('payload_json'), {})
        out[row.get('company_id')] = row.get('company_name') or payload.get('company_name') or ''
    return out


def _load_job_application_counts(job_ids: list[str]) -> dict[str, int]:
    ids = [jid for jid in dict.fromkeys(job_ids) if jid]
    if not ids:
        return {}
    placeholders = ','.join([f":jid_{i}" for i in range(len(ids))])
    params = {f"jid_{i}": jid for i, jid in enumerate(ids)}
    rows = fetch_all(
        f"SELECT job_id, COUNT(*) AS applicants_count FROM applications WHERE job_id IN ({placeholders}) GROUP BY job_id",
        params,
    )
    return {row.get('job_id'): int(row.get('applicants_count') or 0) for row in rows}


class IdempotencyRepository:
    def key_name(self, route: str, key: str) -> str:
        return f"{route}:{key}"

    def get(self, route: str, key: str) -> dict[str, Any] | None:
        row = fetch_one(
            "SELECT * FROM idempotency_keys WHERE idempotency_key = :idempotency_key",
            {"idempotency_key": self.key_name(route, key)},
        )
        if not row:
            return None
        row["response_json"] = _from_json(row.get("response_json"), {})
        return row

    def save(self, route: str, key: str, body_hash: str, response_body: dict[str, Any], trace_id: str) -> None:
        execute(
            """
            INSERT INTO idempotency_keys (idempotency_key, route_name, body_hash, response_json, original_trace_id)
            VALUES (:idempotency_key, :route_name, :body_hash, :response_json, :original_trace_id)
            """,
            {
                "idempotency_key": self.key_name(route, key),
                "route_name": route,
                "body_hash": body_hash,
                "response_json": _to_json(response_body),
                "original_trace_id": trace_id,
            },
        )


class AuthRepository:
    def create_user(self, email: str, password_hash: str, subject_type: str, first_name: str | None, last_name: str | None) -> dict[str, Any]:
        user_id = f"usr_{uuid4().hex[:8]}"
        execute(
            "INSERT INTO users (user_id, email, password_hash, subject_type, first_name, last_name) VALUES (:user_id, :email, :password_hash, :subject_type, :first_name, :last_name)",
            {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "subject_type": subject_type,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        return self.get_user_by_email(email) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return fetch_one("SELECT * FROM users WHERE lower(email)=lower(:email)", {"email": email})

    def issue_refresh_token(self, user_id: str) -> str:
        token = f"rft_{uuid4().hex[:12]}"
        execute(
            "INSERT INTO refresh_tokens (refresh_token_id, user_id, token_hash, is_revoked) VALUES (:refresh_token_id, :user_id, :token_hash, 0)",
            {"refresh_token_id": token, "user_id": user_id, "token_hash": token},
        )
        return token

    def get_user_by_refresh_token(self, token: str) -> dict[str, Any] | None:
        return fetch_one(
            """
            SELECT u.* FROM refresh_tokens r
            JOIN users u ON u.user_id = r.user_id
            WHERE r.refresh_token_id = :token AND r.is_revoked = 0
            """,
            {"token": token},
        )

    def revoke_refresh_token(self, token: str) -> None:
        execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE refresh_token_id = :token", {"token": token})


class MemberRepository:
    def create(self, member: dict[str, Any]) -> dict[str, Any]:
        payload_json = _to_json(member)
        execute(
            """
            INSERT INTO members (member_id, email, first_name, last_name, headline, about_text, location_text, profile_version, is_deleted, payload_json)
            VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text, :profile_version, 0, :payload_json)
            """,
            {
                "member_id": member["member_id"],
                "email": member.get("email"),
                "first_name": member.get("first_name"),
                "last_name": member.get("last_name"),
                "headline": member.get("headline"),
                "about_text": member.get("about") or member.get('about_summary'),
                "location_text": _to_json(member.get("location")) if isinstance(member.get("location"), dict) else (member.get("location") or ', '.join([v for v in [member.get('city'), member.get('state')] if v])),
                "profile_version": member.get("profile_version", 1),
                "payload_json": payload_json,
            },
        )
        return self.get(member["member_id"]) or member

    def get(self, member_id: str) -> dict[str, Any] | None:
        row = fetch_one("SELECT * FROM members WHERE member_id = :member_id", {"member_id": member_id})
        if not row or row.get("is_deleted"):
            return None
        payload = _from_json(row.get("payload_json"), {})
        payload.setdefault("member_id", row["member_id"])
        payload.setdefault("profile_version", row.get("profile_version", 1))
        return payload

    def update(self, member_id: str, updates: dict[str, Any], expected_version: int | None = None) -> dict[str, Any] | None:
        current = self.get(member_id)
        if not current:
            return None
        if expected_version and expected_version != current.get("profile_version", 1):
            raise ValueError("version_conflict")
        current.update({k: v for k, v in updates.items() if k not in {"member_id", "expected_version"}})
        current["profile_version"] = current.get("profile_version", 1) + 1
        execute(
            "UPDATE members SET email=:email, first_name=:first_name, last_name=:last_name, headline=:headline, about_text=:about_text, location_text=:location_text, profile_version=:profile_version, payload_json=:payload_json WHERE member_id=:member_id",
            {
                "member_id": member_id,
                "email": current.get("email"),
                "first_name": current.get("first_name"),
                "last_name": current.get("last_name"),
                "headline": current.get("headline"),
                "about_text": current.get("about") or current.get('about_summary'),
                "location_text": _to_json(current.get("location")) if isinstance(current.get("location"), dict) else (current.get("location") or ', '.join([v for v in [current.get('city'), current.get('state')] if v])),
                "profile_version": current["profile_version"],
                "payload_json": _to_json(current),
            },
        )
        return current

    def delete(self, member_id: str) -> bool:
        return bool(execute("UPDATE members SET is_deleted = 1 WHERE member_id = :member_id", {"member_id": member_id}))

    def search(self, *, skill: str = "", location: str = "", keyword: str = "") -> list[dict[str, Any]]:
        rows = fetch_all("SELECT payload_json FROM members WHERE is_deleted = 0")
        items = []
        skill = skill.lower()
        location = location.lower()
        keyword = keyword.lower()
        for row in rows:
            payload = _from_json(row.get("payload_json"), {})
            skills = [str(s).lower() for s in payload.get("skills", [])]
            text = f"{payload.get('first_name','')} {payload.get('last_name','')} {payload.get('headline','')} {payload.get('about','') or payload.get('about_summary','')}".lower()
            loc_raw = payload.get('location') or ', '.join([v for v in [payload.get('city'), payload.get('state')] if v])
            loc = _to_json(loc_raw).lower() if isinstance(loc_raw, dict) else str(loc_raw).lower()
            if skill and skill not in skills:
                continue
            if location and location not in loc:
                continue
            if keyword and keyword not in text:
                continue
            items.append(payload)
        return items


class RecruiterRepository:
    def create_company(self, company: dict[str, Any]) -> dict[str, Any]:
        execute(
            "INSERT INTO companies (company_id, company_name, company_industry, company_size, payload_json) VALUES (:company_id, :company_name, :company_industry, :company_size, :payload_json)",
            {
                "company_id": company["company_id"],
                "company_name": company.get("company_name"),
                "company_industry": company.get("company_industry"),
                "company_size": company.get("company_size"),
                "payload_json": _to_json(company),
            },
        )
        return self.get_company(company["company_id"]) or company

    def update_company(self, company_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        company = self.get_company(company_id)
        if not company:
            return None
        company.update({k: v for k, v in updates.items() if k in {"company_name", "company_industry", "company_size"}})
        execute(
            "UPDATE companies SET company_name=:company_name, company_industry=:company_industry, company_size=:company_size, payload_json=:payload_json WHERE company_id=:company_id",
            {
                "company_id": company_id,
                "company_name": company.get("company_name"),
                "company_industry": company.get("company_industry"),
                "company_size": company.get("company_size"),
                "payload_json": _to_json(company),
            },
        )
        return self.get_company(company_id)

    def create(self, recruiter: dict[str, Any], company: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        self.create_company(company)
        execute(
            "INSERT INTO recruiters (recruiter_id, company_id, email, name, phone, access_level, payload_json) VALUES (:recruiter_id, :company_id, :email, :name, :phone, :access_level, :payload_json)",
            {
                "recruiter_id": recruiter["recruiter_id"],
                "company_id": company["company_id"],
                "email": recruiter.get("email"),
                "name": recruiter.get("name"),
                "phone": recruiter.get("phone"),
                "access_level": recruiter.get("access_level"),
                "payload_json": _to_json({**recruiter, "company_id": company["company_id"]}),
            },
        )
        return self.get_recruiter(recruiter["recruiter_id"]) or recruiter, self.get_company(company["company_id"]) or company

    def get_recruiter(self, recruiter_id: str) -> dict[str, Any] | None:
        row = fetch_one("SELECT payload_json FROM recruiters WHERE recruiter_id = :recruiter_id", {"recruiter_id": recruiter_id})
        return _from_json(row.get("payload_json"), {}) if row else None

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        row = fetch_one("SELECT payload_json FROM companies WHERE company_id = :company_id", {"company_id": company_id})
        return _from_json(row.get("payload_json"), {}) if row else None

    def email_exists(self, email: str) -> bool:
        row = fetch_one("SELECT recruiter_id FROM recruiters WHERE lower(email)=lower(:email)", {"email": email})
        return bool(row)

    def update_recruiter(self, recruiter_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        recruiter = self.get_recruiter(recruiter_id)
        if not recruiter:
            return None
        recruiter.update({k: v for k, v in updates.items() if k in {"name", "phone", "access_level", "email", "company_id", "company_name", "company_industry", "company_size"}})
        execute("UPDATE recruiters SET company_id=:company_id, email=:email, name=:name, phone=:phone, access_level=:access_level, payload_json=:payload_json WHERE recruiter_id=:recruiter_id", {
            "recruiter_id": recruiter_id,
            "company_id": recruiter.get("company_id"),
            "email": recruiter.get("email"),
            "name": recruiter.get("name"),
            "phone": recruiter.get("phone"),
            "access_level": recruiter.get("access_level"),
            "payload_json": _to_json(recruiter),
        })
        if recruiter.get("company_id"):
            company = self.get_company(recruiter["company_id"]) or {"company_id": recruiter["company_id"]}
            company.update({k: recruiter.get(k) for k in ["company_name", "company_industry", "company_size"] if recruiter.get(k) is not None})
            execute("UPDATE companies SET company_name=:company_name, company_industry=:company_industry, company_size=:company_size, payload_json=:payload_json WHERE company_id=:company_id", {
                "company_id": company["company_id"],
                "company_name": company.get("company_name"),
                "company_industry": company.get("company_industry"),
                "company_size": company.get("company_size"),
                "payload_json": _to_json(company),
            })
        return self.get_recruiter(recruiter_id)


class JobRepository:
    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id") or f"job_{uuid4().hex[:8]}"
        full = {**payload, "job_id": job_id, "status": payload.get("status", "open"), "version": payload.get("version", 1)}
        execute(
            """
            INSERT INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level, employment_type, location_text, work_mode, status, version, payload_json)
            VALUES (:job_id, :company_id, :recruiter_id, :title, :description_text, :seniority_level, :employment_type, :location_text, :work_mode, :status, :version, :payload_json)
            """,
            {
                "job_id": full["job_id"],
                "company_id": full.get("company_id"),
                "recruiter_id": full.get("recruiter_id"),
                "title": full.get("title"),
                "description_text": full.get("description"),
                "seniority_level": full.get("seniority_level"),
                "employment_type": full.get("employment_type"),
                "location_text": full.get("location"),
                "work_mode": full.get("work_mode"),
                "status": full.get("status"),
                "version": full.get("version", 1),
                "payload_json": _to_json(full),
            },
        )
        return full

    def find_duplicate_open(self, recruiter_id: str, title: str) -> dict[str, Any] | None:
        row = fetch_one("SELECT payload_json FROM jobs WHERE recruiter_id=:recruiter_id AND title=:title AND status='open'", {"recruiter_id": recruiter_id, "title": title})
        return _from_json(row.get("payload_json"), {}) if row else None

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = fetch_one("SELECT payload_json FROM jobs WHERE job_id=:job_id", {"job_id": job_id})
        return _from_json(row.get("payload_json"), {}) if row else None

    def update(self, job_id: str, updates: dict[str, Any], expected_version: int | None = None) -> dict[str, Any] | None:
        current = self.get(job_id)
        if not current:
            return None
        if expected_version and expected_version != current.get("version", 1):
            raise ValueError("version_conflict")
        if current.get("status") == "closed":
            raise RuntimeError("job_closed")
        current.update({k: v for k, v in updates.items() if k not in {"job_id", "expected_version"}})
        current["version"] = current.get("version", 1) + 1
        execute(
            "UPDATE jobs SET company_id=:company_id, recruiter_id=:recruiter_id, title=:title, description_text=:description_text, seniority_level=:seniority_level, employment_type=:employment_type, location_text=:location_text, work_mode=:work_mode, status=:status, version=:version, payload_json=:payload_json WHERE job_id=:job_id",
            {
                "job_id": job_id,
                "company_id": current.get("company_id"),
                "recruiter_id": current.get("recruiter_id"),
                "title": current.get("title"),
                "description_text": current.get("description"),
                "seniority_level": current.get("seniority_level"),
                "employment_type": current.get("employment_type"),
                "location_text": current.get("location"),
                "work_mode": current.get("work_mode"),
                "status": current.get("status"),
                "version": current["version"],
                "payload_json": _to_json(current),
            },
        )
        return current

    
def search(self) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT job_id, company_id, recruiter_id, title, description_text, seniority_level,
               employment_type, location_text, work_mode, status, version, payload_json, created_at
        FROM jobs
        ORDER BY created_at DESC
        """
    )
    items = []
    for row in rows:
        payload = _from_json(row.get("payload_json"), {})
        item = {
            "job_id": row.get("job_id"),
            "company_id": row.get("company_id"),
            "recruiter_id": row.get("recruiter_id"),
            "title": row.get("title"),
            "description": row.get("description_text"),
            "description_text": row.get("description_text"),
            "seniority_level": row.get("seniority_level"),
            "employment_type": row.get("employment_type"),
            "location": row.get("location_text"),
            "location_text": row.get("location_text"),
            "work_mode": row.get("work_mode"),
            "status": row.get("status"),
            "version": row.get("version"),
            "created_at": row.get("created_at"),
        }
        if isinstance(payload, dict):
            item.update(payload)
        items.append(item)
    return items

    
def list_by_recruiter(self, recruiter_id: str, status: str) -> list[dict[str, Any]]:
    params = {"recruiter_id": recruiter_id}
    sql = """
        SELECT job_id, company_id, recruiter_id, title, description_text, seniority_level,
               employment_type, location_text, work_mode, status, version, payload_json, created_at
        FROM jobs
        WHERE recruiter_id=:recruiter_id
    """
    if status != "all":
        sql += " AND status=:status"
        params["status"] = status
    sql += " ORDER BY created_at DESC"
    rows = fetch_all(sql, params)
    items = []
    for row in rows:
        payload = _from_json(row.get("payload_json"), {})
        item = {
            "job_id": row.get("job_id"),
            "company_id": row.get("company_id"),
            "recruiter_id": row.get("recruiter_id"),
            "title": row.get("title"),
            "description": row.get("description_text"),
            "description_text": row.get("description_text"),
            "seniority_level": row.get("seniority_level"),
            "employment_type": row.get("employment_type"),
            "location": row.get("location_text"),
            "location_text": row.get("location_text"),
            "work_mode": row.get("work_mode"),
            "status": row.get("status"),
            "version": row.get("version"),
            "created_at": row.get("created_at"),
        }
        if isinstance(payload, dict):
            item.update(payload)
        items.append(item)
    return items


class ApplicationRepository:
    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        application_id = payload.get("application_id") or f"app_{uuid4().hex[:8]}"
        full = {**payload, "application_id": application_id, "status": payload.get("status", "submitted"), "application_datetime": normalize_mysql_datetime(payload.get("application_datetime"))}
        execute(
            "INSERT INTO applications (application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json) VALUES (:application_id, :job_id, :member_id, :resume_ref, :cover_letter, :status, :application_datetime, :payload_json)",
            {
                "application_id": full["application_id"],
                "job_id": full.get("job_id"),
                "member_id": full.get("member_id"),
                "resume_ref": full.get("resume_ref"),
                "cover_letter": full.get("cover_letter"),
                "status": full.get("status"),
                "application_datetime": full.get("application_datetime"),
                "payload_json": _to_json(full),
            },
        )
        return full

    
def find_duplicate(self, job_id: str, member_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE job_id=:job_id AND member_id=:member_id
        """,
        {"job_id": job_id, "member_id": member_id},
    )
    if not row:
        return None
    item = {
        "application_id": row.get("application_id"),
        "job_id": row.get("job_id"),
        "member_id": row.get("member_id"),
        "resume_ref": row.get("resume_ref"),
        "cover_letter": row.get("cover_letter"),
        "status": row.get("status"),
        "application_datetime": row.get("application_datetime"),
    }
    payload = _from_json(row.get("payload_json"), {})
    if isinstance(payload, dict):
        item.update(payload)
    return item

    
def get(self, application_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE application_id=:application_id
        """,
        {"application_id": application_id},
    )
    if not row:
        return None
    item = {
        "application_id": row.get("application_id"),
        "job_id": row.get("job_id"),
        "member_id": row.get("member_id"),
        "resume_ref": row.get("resume_ref"),
        "cover_letter": row.get("cover_letter"),
        "status": row.get("status"),
        "application_datetime": row.get("application_datetime"),
    }
    payload = _from_json(row.get("payload_json"), {})
    if isinstance(payload, dict):
        item.update(payload)
    return item

    
def list_by_job(self, job_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE job_id=:job_id ORDER BY application_datetime DESC
        """,
        {"job_id": job_id},
    )
    items = []
    for row in rows:
        item = {
            "application_id": row.get("application_id"),
            "job_id": row.get("job_id"),
            "member_id": row.get("member_id"),
            "resume_ref": row.get("resume_ref"),
            "cover_letter": row.get("cover_letter"),
            "status": row.get("status"),
            "application_datetime": row.get("application_datetime"),
        }
        payload = _from_json(row.get("payload_json"), {})
        if isinstance(payload, dict):
            item.update(payload)
        items.append(item)
    return items

    
def list_by_member(self, member_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE member_id=:member_id ORDER BY application_datetime DESC
        """,
        {"member_id": member_id},
    )
    items = []
    for row in rows:
        item = {
            "application_id": row.get("application_id"),
            "job_id": row.get("job_id"),
            "member_id": row.get("member_id"),
            "resume_ref": row.get("resume_ref"),
            "cover_letter": row.get("cover_letter"),
            "status": row.get("status"),
            "application_datetime": row.get("application_datetime"),
        }
        payload = _from_json(row.get("payload_json"), {})
        if isinstance(payload, dict):
            item.update(payload)
        items.append(item)
    return items

    def update_status(self, application_id: str, new_status: str) -> tuple[dict[str, Any] | None, str | None]:
        current = self.get(application_id)
        if not current:
            return None, None
        old = current.get("status", "submitted")
        current["status"] = new_status
        execute("UPDATE applications SET status=:status, payload_json=:payload_json WHERE application_id=:application_id", {"status": new_status, "payload_json": _to_json(current), "application_id": application_id})
        return current, old

    def add_note(self, note: dict[str, Any]) -> dict[str, Any]:
        note_id = note.get("note_id") or f"note_{uuid4().hex[:8]}"
        full = {**note, "note_id": note_id}
        execute("INSERT INTO application_notes (note_id, application_id, recruiter_id, note_text, visibility, payload_json) VALUES (:note_id, :application_id, :recruiter_id, :note_text, :visibility, :payload_json)", {
            "note_id": note_id,
            "application_id": full.get("application_id"),
            "recruiter_id": full.get("recruiter_id"),
            "note_text": full.get("note_text"),
            "visibility": full.get("visibility", "internal"),
            "payload_json": _to_json(full),
        })
        return full

    def notes_for_application(self, application_id: str) -> list[dict[str, Any]]:
        return [_from_json(row.get("payload_json"), {}) for row in fetch_all("SELECT payload_json FROM application_notes WHERE application_id=:application_id", {"application_id": application_id})]


class MessagingRepository:
    def get_or_create_thread(self, participants: list[str]) -> tuple[dict[str, Any], bool]:
        key = "|".join(sorted(participants))
        existing = find_one("threads", {"participant_key": key})
        if existing:
            return existing, False
        thread = {
            "thread_id": f"thr_{uuid4().hex[:8]}",
            "participant_ids": participants,
            "participant_key": key,
            "latest_message_at": None,
            "latest_message_id": None,
            "created_at": now_iso(),
        }
        insert_one("threads", thread)
        return thread, True

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        return find_one("threads", {"thread_id": thread_id})

    def list_threads_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [t for t in find_many("threads", sort=[("latest_message_at", -1)]) if user_id in t.get("participant_ids", [])]

    def save_thread(self, thread: dict[str, Any]) -> None:
        replace_one("threads", {"thread_id": thread["thread_id"]}, thread, upsert=True)

    def get_message_by_client_id(self, thread_id: str, client_message_id: str) -> dict[str, Any] | None:
        return find_one("messages", {"thread_id": thread_id, "client_message_id": client_message_id})

    def create_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = {**payload, "message_id": payload.get("message_id") or f"msg_{uuid4().hex[:8]}", "sent_at": payload.get("sent_at", now_iso())}
        insert_one("messages", message)
        return message

    def list_messages(self, thread_id: str) -> list[dict[str, Any]]:
        return find_many("messages", {"thread_id": thread_id}, sort=[("sent_at", -1)])

    def create_connection_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = {**payload, "request_id": payload.get("request_id") or f"crq_{uuid4().hex[:8]}", "status": payload.get("status", "pending"), "created_at": now_iso(), "updated_at": now_iso()}
        insert_one("connection_requests", req)
        return req

    def get_connection_request(self, request_id: str) -> dict[str, Any] | None:
        return find_one("connection_requests", {"request_id": request_id})

    def pending_request_exists(self, requester_id: str, receiver_id: str) -> bool:
        pair_key = "|".join(sorted([requester_id, receiver_id]))
        requests = find_many("connection_requests", {"status": "pending"})
        return any("|".join(sorted([r.get("requester_id"), r.get("receiver_id")])) == pair_key for r in requests)

    def save_connection_request(self, request: dict[str, Any]) -> None:
        request["updated_at"] = now_iso()
        replace_one("connection_requests", {"request_id": request["request_id"]}, request, upsert=True)

    def list_pending_requests_for_receiver(self, receiver_id: str) -> list[dict[str, Any]]:
        return find_many("connection_requests", {"receiver_id": receiver_id, "status": "pending"}, sort=[("created_at", -1)])

    def list_pending_requests_for_requester(self, requester_id: str) -> list[dict[str, Any]]:
        return find_many("connection_requests", {"requester_id": requester_id, "status": "pending"}, sort=[("created_at", -1)])

    def connection_exists(self, user_a: str, user_b: str) -> bool:
        return bool(find_one("connections", {"pair_key": "|".join(sorted([user_a, user_b]))}))

    def create_connection(self, requester_id: str, receiver_id: str, source_request_id: str) -> dict[str, Any]:
        pair_key = "|".join(sorted([requester_id, receiver_id]))
        existing = find_one("connections", {"pair_key": pair_key})
        if existing:
            return existing
        connection = {
            "connection_id": f"cnn_{uuid4().hex[:8]}",
            "pair_key": pair_key,
            "user_a": min(requester_id, receiver_id),
            "user_b": max(requester_id, receiver_id),
            "source_request_id": source_request_id,
            "connected_at": now_iso(),
        }
        insert_one("connections", connection)
        return connection

    def list_connections(self, user_id: str) -> list[dict[str, Any]]:
        return [c for c in find_many("connections") if user_id in {c.get("user_a"), c.get("user_b")}]


class AnalyticsRepository:
    def event_exists(self, idempotency_key: str) -> bool:
        return bool(find_one("events", {"idempotency_key": idempotency_key}))

    def insert_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"event_id": f"evt_{uuid4().hex[:8]}", **payload}
        insert_one("events", event)
        return event

    def list_events(self) -> list[dict[str, Any]]:
        return find_many("events", sort=[("timestamp", -1)])

    def insert_benchmark(self, payload: dict[str, Any]) -> dict[str, Any]:
        benchmark = {"benchmark_id": f"bm_{uuid4().hex[:8]}", **payload}
        insert_one("benchmarks", benchmark)
        return benchmark


class AIRepository:
    def _normalize_task(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        if not task:
            return task
        item = dict(task)
        if not isinstance(item.get("input"), dict):
            item["input"] = {}
        if not isinstance(item.get("output"), dict):
            item["output"] = {}
        if not isinstance(item.get("steps"), list):
            item["steps"] = []
        return item

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self._normalize_task({
            "task_id": payload.get("task_id") or f"ait_{uuid4().hex[:8]}",
            "status": payload.get("status", "queued"),
            "current_step": payload.get("current_step", "queued"),
            "approval_state": payload.get("approval_state", "pending"),
            "input": payload.get("input", {}),
            "output": payload.get("output", {}),
            "steps": payload.get("steps", []),
            "created_by": payload.get("created_by"),
            "created_by_role": payload.get("created_by_role"),
            "created_at": payload.get("created_at", now_iso()),
            "updated_at": payload.get("updated_at", now_iso()),
        })
        insert_one("ai_tasks", task)
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._normalize_task(find_one("ai_tasks", {"task_id": task_id}))

    def list_tasks_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [self._normalize_task(item) for item in find_many("ai_tasks", {"created_by": user_id}, sort=[("created_at", -1)])]

    def list_all_tasks(self) -> list[dict[str, Any]]:
        return [self._normalize_task(item) for item in find_many("ai_tasks", {}, sort=[("created_at", -1)])]

    def save_task(self, task: dict[str, Any]) -> None:
        task = self._normalize_task(task)
        task["updated_at"] = now_iso()
        replace_one("ai_tasks", {"task_id": task["task_id"]}, task, upsert=True)

from services.shared.relational import cursor_ctx, _adapt_sql, _params_for_query
from services.shared.document_store import delete_many


def _sql_insert_ignore(query_sqlite: str, query_mysql: str | None = None) -> str:
    """Return the MySQL variant for INSERT IGNORE style statements."""
    return query_mysql or query_sqlite.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO')


def _job_create_with_outbox(self, payload: dict[str, Any], topic: str, event: dict[str, Any]) -> dict[str, Any]:
    job_id = payload.get('job_id') or f"job_{uuid4().hex[:8]}"
    full = {**payload, 'job_id': job_id, 'status': payload.get('status', 'open'), 'version': payload.get('version', 1)}
    event = dict(event)
    event.setdefault('entity', {})['entity_id'] = job_id
    event.setdefault('payload', {})['job_id'] = job_id
    current_key = str(event.get('idempotency_key') or '')
    if not current_key or ':pending' in current_key:
        event['idempotency_key'] = f"{topic}:{job_id}:{event.get('actor_id', '')}"
    outbox_id = f"out_{uuid4().hex[:12]}"
    with cursor_ctx() as cur:
        q1 = """
        INSERT INTO jobs (job_id, company_id, recruiter_id, title, description_text, seniority_level, employment_type, location_text, work_mode, status, version, payload_json)
        VALUES (:job_id, :company_id, :recruiter_id, :title, :description_text, :seniority_level, :employment_type, :location_text, :work_mode, :status, :version, :payload_json)
        """
        params1 = {
            'job_id': full['job_id'], 'company_id': full.get('company_id'), 'recruiter_id': full.get('recruiter_id'), 'title': full.get('title'),
            'description_text': full.get('description'), 'seniority_level': full.get('seniority_level'), 'employment_type': full.get('employment_type'),
            'location_text': full.get('location'), 'work_mode': full.get('work_mode'), 'status': full.get('status'), 'version': full.get('version', 1),
            'payload_json': _to_json(full),
        }
        cur.execute(_adapt_sql(q1), _params_for_query(q1, params1))
        q2 = _sql_insert_ignore(
            """INSERT OR IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
            """INSERT IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
        )
        params2 = {'outbox_id': outbox_id, 'topic': topic, 'event_type': event.get('event_type', topic), 'aggregate_type': 'job', 'aggregate_id': full['job_id'], 'payload_json': _to_json(event), 'trace_id': event.get('trace_id'), 'idempotency_key': event.get('idempotency_key') or f'{topic}:{full["job_id"]}', 'status': 'pending', 'attempts': 0, 'available_at': now_mysql_datetime()}
        cur.execute(_adapt_sql(q2), _params_for_query(q2, params2))
    return full


def _job_update_with_outbox(self, job_id: str, updates: dict[str, Any], topic: str, event: dict[str, Any], expected_version: int | None = None) -> dict[str, Any] | None:
    current = self.get(job_id)
    if not current:
        return None
    if expected_version and expected_version != current.get('version', 1):
        raise ValueError('version_conflict')
    if current.get('status') == 'closed' and updates.get('status') != 'closed':
        raise RuntimeError('job_closed')
    current.update({k: v for k, v in updates.items() if k not in {'job_id', 'expected_version'}})
    current['version'] = current.get('version', 1) + 1
    outbox_id = f"out_{uuid4().hex[:12]}"
    with cursor_ctx() as cur:
        q1 = "UPDATE jobs SET company_id=:company_id, recruiter_id=:recruiter_id, title=:title, description_text=:description_text, seniority_level=:seniority_level, employment_type=:employment_type, location_text=:location_text, work_mode=:work_mode, status=:status, version=:version, payload_json=:payload_json WHERE job_id=:job_id"
        params1 = {'job_id': job_id, 'company_id': current.get('company_id'), 'recruiter_id': current.get('recruiter_id'), 'title': current.get('title'), 'description_text': current.get('description'), 'seniority_level': current.get('seniority_level'), 'employment_type': current.get('employment_type'), 'location_text': current.get('location'), 'work_mode': current.get('work_mode'), 'status': current.get('status'), 'version': current['version'], 'payload_json': _to_json(current)}
        cur.execute(_adapt_sql(q1), _params_for_query(q1, params1))
        q2 = _sql_insert_ignore(
            """INSERT OR IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
            """INSERT IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
        )
        params2 = {'outbox_id': outbox_id, 'topic': topic, 'event_type': event.get('event_type', topic), 'aggregate_type': 'job', 'aggregate_id': current['job_id'], 'payload_json': _to_json(event), 'trace_id': event.get('trace_id'), 'idempotency_key': event.get('idempotency_key') or f'{topic}:{current["job_id"]}:{current["version"]}', 'status': 'pending', 'attempts': 0, 'available_at': now_mysql_datetime()}
        cur.execute(_adapt_sql(q2), _params_for_query(q2, params2))
    return current


def _application_create_with_outbox(self, payload: dict[str, Any], topic: str, event: dict[str, Any]) -> dict[str, Any]:
    application_id = payload.get('application_id') or f"app_{uuid4().hex[:8]}"
    full = {**payload, 'application_id': application_id, 'status': payload.get('status', 'submitted'), 'application_datetime': normalize_mysql_datetime(payload.get('application_datetime'))}
    event = dict(event)
    event.setdefault('entity', {})['entity_id'] = application_id
    event.setdefault('payload', {})['application_id'] = application_id
    outbox_id = f"out_{uuid4().hex[:12]}"
    with cursor_ctx() as cur:
        q1 = 'INSERT INTO applications (application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json) VALUES (:application_id, :job_id, :member_id, :resume_ref, :cover_letter, :status, :application_datetime, :payload_json)'
        params1 = {'application_id': full['application_id'], 'job_id': full.get('job_id'), 'member_id': full.get('member_id'), 'resume_ref': full.get('resume_ref'), 'cover_letter': full.get('cover_letter'), 'status': full.get('status'), 'application_datetime': full.get('application_datetime'), 'payload_json': _to_json(full)}
        cur.execute(_adapt_sql(q1), _params_for_query(q1, params1))
        q2 = _sql_insert_ignore(
            """INSERT OR IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
            """INSERT IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
        )
        params2 = {'outbox_id': outbox_id, 'topic': topic, 'event_type': event.get('event_type', topic), 'aggregate_type': 'application', 'aggregate_id': full['application_id'], 'payload_json': _to_json(event), 'trace_id': event.get('trace_id'), 'idempotency_key': event.get('idempotency_key') or f'{topic}:{full["application_id"]}', 'status': 'pending', 'attempts': 0, 'available_at': now_mysql_datetime()}
        cur.execute(_adapt_sql(q2), _params_for_query(q2, params2))
    return full


def _application_update_status_with_outbox(self, application_id: str, new_status: str, topic: str, event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    current = self.get(application_id)
    if not current:
        return None, None
    old = current.get('status', 'submitted')
    current['status'] = new_status
    outbox_id = f"out_{uuid4().hex[:12]}"
    with cursor_ctx() as cur:
        q1 = 'UPDATE applications SET status=:status, payload_json=:payload_json WHERE application_id=:application_id'
        params1 = {'status': new_status, 'payload_json': _to_json(current), 'application_id': application_id}
        cur.execute(_adapt_sql(q1), _params_for_query(q1, params1))
        q2 = _sql_insert_ignore(
            """INSERT OR IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
            """INSERT IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, available_at) VALUES (:outbox_id,:topic,:event_type,:aggregate_type,:aggregate_id,:payload_json,:trace_id,:idempotency_key,:status,:attempts,:available_at)""",
        )
        params2 = {'outbox_id': outbox_id, 'topic': topic, 'event_type': event.get('event_type', topic), 'aggregate_type': 'application', 'aggregate_id': current['application_id'], 'payload_json': _to_json(event), 'trace_id': event.get('trace_id'), 'idempotency_key': event.get('idempotency_key') or f'{topic}:{current["application_id"]}:{new_status}', 'status': 'pending', 'attempts': 0, 'available_at': now_mysql_datetime()}
        cur.execute(_adapt_sql(q2), _params_for_query(q2, params2))
    return current, old


JobRepository.create_with_outbox = _job_create_with_outbox
JobRepository.update_with_outbox = _job_update_with_outbox
ApplicationRepository.create_with_outbox = _application_create_with_outbox
ApplicationRepository.update_status_with_outbox = _application_update_status_with_outbox


class AnalyticsRollupRepository:
    def clear(self) -> None:
        delete_many('events_rollup', {})

    def _upsert_counter(self, rollup_id: str, fields: dict[str, Any]) -> None:
        existing = find_one('events_rollup', {'rollup_id': rollup_id}) or {'rollup_id': rollup_id}
        existing.update(fields)
        replace_one('events_rollup', {'rollup_id': rollup_id}, existing, upsert=True)

    def apply_event(self, event: dict[str, Any]) -> None:
        event_type = event.get('event_type')
        payload = event.get('payload', {}) or {}
        entity = event.get('entity', {}) or {}
        timestamp = event.get('timestamp', now_iso())
        day = str(timestamp)[:10]
        job_id = payload.get('job_id') or entity.get('entity_id')
        member_id = payload.get('member_id') or event.get('actor_id')
        if event_type in {'application.submitted', 'job.viewed', 'job.saved'} and job_id:
            metric = {'application.submitted': 'applications', 'job.viewed': 'views', 'job.saved': 'saves'}[event_type]
            rollup_id = f'job_metric:{metric}:{job_id}'
            existing = find_one('events_rollup', {'rollup_id': rollup_id}) or {'rollup_id': rollup_id, 'kind': 'job_metric', 'metric': metric, 'job_id': job_id, 'count': 0}
            existing['count'] = int(existing.get('count', 0)) + 1
            replace_one('events_rollup', {'rollup_id': rollup_id}, existing, upsert=True)
        if event_type in {'job.viewed', 'job.saved', 'application.started', 'application.submitted'} and job_id:
            rollup_id = f'funnel:{job_id}'
            existing = find_one('events_rollup', {'rollup_id': rollup_id}) or {'rollup_id': rollup_id, 'kind': 'funnel', 'job_id': job_id, 'viewed': 0, 'saved': 0, 'apply_started': 0, 'submitted': 0}
            mapping = {'job.viewed': 'viewed', 'job.saved': 'saved', 'application.started': 'apply_started', 'application.submitted': 'submitted'}
            key = mapping[event_type]
            existing[key] = int(existing.get(key, 0)) + 1
            replace_one('events_rollup', {'rollup_id': rollup_id}, existing, upsert=True)
        if event_type == 'application.submitted' and job_id:
            city = payload.get('city', 'Unknown')
            state = payload.get('state', 'Unknown')
            for gran, value in [('city', city), ('state', state)]:
                rid = f'geo:{gran}:{job_id}:{value}'
                existing = find_one('events_rollup', {'rollup_id': rid}) or {'rollup_id': rid, 'kind': 'geo', 'granularity': gran, 'job_id': job_id, 'key': value, 'count': 0}
                existing['count'] = int(existing.get('count', 0)) + 1
                replace_one('events_rollup', {'rollup_id': rid}, existing, upsert=True)
        if event_type == 'profile.viewed' and entity.get('entity_id'):
            rid = f'member_views:{entity["entity_id"]}'
            existing = find_one('events_rollup', {'rollup_id': rid}) or {'rollup_id': rid, 'kind': 'member_views', 'member_id': entity['entity_id'], 'daily': {}}
            daily = existing.get('daily', {})
            daily[day] = int(daily.get(day, 0)) + 1
            existing['daily'] = daily
            replace_one('events_rollup', {'rollup_id': rid}, existing, upsert=True)
        if event_type in {'application.status.updated', 'application.submitted'} and member_id:
            rid = f'member_status:{member_id}'
            existing = find_one('events_rollup', {'rollup_id': rid}) or {'rollup_id': rid, 'kind': 'member_status', 'member_id': member_id, 'statuses': {}}
            statuses = existing.get('statuses', {})
            status = payload.get('status', 'submitted')
            statuses[status] = int(statuses.get(status, 0)) + 1
            existing['statuses'] = statuses
            replace_one('events_rollup', {'rollup_id': rid}, existing, upsert=True)

    def top_jobs(self, metric: str, limit: int) -> list[dict[str, Any]]:
        rows = [r for r in find_many('events_rollup', {'kind': 'job_metric'}) if r.get('metric') == metric]
        rows.sort(key=lambda r: int(r.get('count', 0)), reverse=True)
        return rows[:limit]

    def funnel(self, job_id: str) -> dict[str, Any]:
        return find_one('events_rollup', {'rollup_id': f'funnel:{job_id}'}) or {'viewed': 0, 'saved': 0, 'apply_started': 0, 'submitted': 0}

    def geo(self, job_id: str, granularity: str) -> list[dict[str, Any]]:
        rows = [r for r in find_many('events_rollup', {'kind': 'geo'}) if r.get('job_id') == job_id and r.get('granularity') == granularity]
        rows.sort(key=lambda r: int(r.get('count', 0)), reverse=True)
        return rows

    def member_dashboard(self, member_id: str) -> dict[str, Any]:
        views = find_one('events_rollup', {'rollup_id': f'member_views:{member_id}'}) or {'daily': {}}
        statuses = find_one('events_rollup', {'rollup_id': f'member_status:{member_id}'}) or {'statuses': {}}
        return {'member_id': member_id, 'profile_views': [{'date': d, 'count': c} for d, c in sorted(views.get('daily', {}).items())], 'application_status_breakdown': statuses.get('statuses', {})}


# --- patched bindings for MySQL-only runtime stability ---
def _jobrepo_search_impl(self):
    rows = fetch_all(
        """
        SELECT job_id, company_id, recruiter_id, title, description_text, seniority_level,
               employment_type, location_text, work_mode, status, version, payload_json, created_at
        FROM jobs
        ORDER BY created_at DESC
        """
    )
    company_names = _load_company_names([row.get('company_id') for row in rows])
    applicant_counts = _load_job_application_counts([row.get('job_id') for row in rows])
    items = []
    for row in rows:
        payload = _from_json(row.get('payload_json'), {})
        item = {
            'job_id': row.get('job_id'),
            'company_id': row.get('company_id'),
            'recruiter_id': row.get('recruiter_id'),
            'title': row.get('title'),
            'description': row.get('description_text'),
            'description_text': row.get('description_text'),
            'seniority_level': row.get('seniority_level'),
            'employment_type': row.get('employment_type'),
            'location': row.get('location_text'),
            'location_text': row.get('location_text'),
            'work_mode': row.get('work_mode'),
            'status': row.get('status'),
            'version': row.get('version'),
            'created_at': row.get('created_at'),
            'posted_at': row.get('created_at'),
            'company_name': company_names.get(row.get('company_id'), ''),
            'applicants_count': applicant_counts.get(row.get('job_id'), 0),
        }
        if isinstance(payload, dict):
            item.update(payload)
        item['company_name'] = item.get('company_name') or company_names.get(row.get('company_id'), '')
        item['applicants_count'] = applicant_counts.get(row.get('job_id'), item.get('applicants_count', 0))
        items.append(item)
    return items


def _jobrepo_list_by_recruiter_impl(self, recruiter_id: str, status: str):
    params = {'recruiter_id': recruiter_id}
    sql = """
        SELECT job_id, company_id, recruiter_id, title, description_text, seniority_level,
               employment_type, location_text, work_mode, status, version, payload_json, created_at
        FROM jobs
        WHERE recruiter_id=:recruiter_id
    """
    if status != 'all':
        sql += ' AND status=:status'
        params['status'] = status
    sql += ' ORDER BY created_at DESC'
    rows = fetch_all(sql, params)
    company_names = _load_company_names([row.get('company_id') for row in rows])
    applicant_counts = _load_job_application_counts([row.get('job_id') for row in rows])
    items = []
    for row in rows:
        payload = _from_json(row.get('payload_json'), {})
        item = {
            'job_id': row.get('job_id'),
            'company_id': row.get('company_id'),
            'recruiter_id': row.get('recruiter_id'),
            'title': row.get('title'),
            'description': row.get('description_text'),
            'description_text': row.get('description_text'),
            'seniority_level': row.get('seniority_level'),
            'employment_type': row.get('employment_type'),
            'location': row.get('location_text'),
            'location_text': row.get('location_text'),
            'work_mode': row.get('work_mode'),
            'status': row.get('status'),
            'version': row.get('version'),
            'created_at': row.get('created_at'),
            'posted_at': row.get('created_at'),
            'company_name': company_names.get(row.get('company_id'), ''),
            'applicants_count': applicant_counts.get(row.get('job_id'), 0),
        }
        if isinstance(payload, dict):
            item.update(payload)
        item['company_name'] = item.get('company_name') or company_names.get(row.get('company_id'), '')
        item['applicants_count'] = applicant_counts.get(row.get('job_id'), item.get('applicants_count', 0))
        items.append(item)
    return items


def _apprepo_find_duplicate_impl(self, job_id: str, member_id: str):
    row = fetch_one(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE job_id=:job_id AND member_id=:member_id
        """,
        {"job_id": job_id, "member_id": member_id},
    )
    if not row:
        return None
    item = {
        "application_id": row.get("application_id"),
        "job_id": row.get("job_id"),
        "member_id": row.get("member_id"),
        "resume_ref": row.get("resume_ref"),
        "cover_letter": row.get("cover_letter"),
        "status": row.get("status"),
        "application_datetime": row.get("application_datetime"),
    }
    payload = _from_json(row.get("payload_json"), {})
    if isinstance(payload, dict):
        item.update(payload)
    return item


def _apprepo_get_impl(self, application_id: str):
    row = fetch_one(
        """
        SELECT application_id, job_id, member_id, resume_ref, cover_letter, status, application_datetime, payload_json
        FROM applications WHERE application_id=:application_id
        """,
        {"application_id": application_id},
    )
    if not row:
        return None
    item = {
        "application_id": row.get("application_id"),
        "job_id": row.get("job_id"),
        "member_id": row.get("member_id"),
        "resume_ref": row.get("resume_ref"),
        "cover_letter": row.get("cover_letter"),
        "status": row.get("status"),
        "application_datetime": row.get("application_datetime"),
    }
    payload = _from_json(row.get("payload_json"), {})
    if isinstance(payload, dict):
        item.update(payload)
    return item


def _apprepo_list_by_job_impl(self, job_id: str):
    rows = fetch_all(
        """
        SELECT a.application_id, a.job_id, a.member_id, a.resume_ref, a.cover_letter, a.status,
               a.application_datetime, a.payload_json,
               m.first_name, m.last_name, m.headline, m.payload_json AS member_payload_json
        FROM applications a
        LEFT JOIN members m ON m.member_id = a.member_id
        WHERE a.job_id=:job_id
        ORDER BY a.application_datetime DESC
        """,
        {'job_id': job_id},
    )
    items = []
    for row in rows:
        item = {
            'application_id': row.get('application_id'),
            'job_id': row.get('job_id'),
            'member_id': row.get('member_id'),
            'resume_ref': row.get('resume_ref'),
            'cover_letter': row.get('cover_letter'),
            'status': row.get('status') or 'submitted',
            'application_datetime': row.get('application_datetime'),
            'first_name': row.get('first_name'),
            'last_name': row.get('last_name'),
            'headline': row.get('headline'),
        }
        payload = _from_json(row.get('payload_json'), {})
        if isinstance(payload, dict):
            item.update(payload)
        member_payload = _from_json(row.get('member_payload_json'), {})
        if isinstance(member_payload, dict):
            item['profile_photo_url'] = member_payload.get('profile_photo_url')
            item['resume_url'] = member_payload.get('resume_url')
            item['city'] = item.get('city') or member_payload.get('city')
            item['state'] = item.get('state') or member_payload.get('state')
        items.append(item)
    return items


def _apprepo_list_by_member_impl(self, member_id: str):
    rows = fetch_all(
        """
        SELECT a.application_id, a.job_id, a.member_id, a.resume_ref, a.cover_letter, a.status,
               a.application_datetime, a.payload_json,
               j.title, j.company_id, j.payload_json AS job_payload_json
        FROM applications a
        LEFT JOIN jobs j ON j.job_id = a.job_id
        WHERE a.member_id=:member_id
        ORDER BY a.application_datetime DESC
        """,
        {'member_id': member_id},
    )
    company_names = _load_company_names([row.get('company_id') for row in rows])
    items = []
    for row in rows:
        item = {
            'application_id': row.get('application_id'),
            'job_id': row.get('job_id'),
            'member_id': row.get('member_id'),
            'resume_ref': row.get('resume_ref'),
            'cover_letter': row.get('cover_letter'),
            'status': row.get('status') or 'submitted',
            'application_datetime': row.get('application_datetime'),
            'title': row.get('title') or row.get('job_id'),
            'company_name': company_names.get(row.get('company_id'), ''),
        }
        payload = _from_json(row.get('payload_json'), {})
        if isinstance(payload, dict):
            item.update(payload)
        job_payload = _from_json(row.get('job_payload_json'), {})
        if isinstance(job_payload, dict):
            item['title'] = item.get('title') or job_payload.get('title') or row.get('job_id')
            item['company_name'] = item.get('company_name') or job_payload.get('company_name') or company_names.get(row.get('company_id'), '')
            item['city'] = job_payload.get('city')
            item['state'] = job_payload.get('state')
            item['work_mode'] = job_payload.get('work_mode')
            item['employment_type'] = job_payload.get('employment_type')
        items.append(item)
    return items


def _apprepo_update_status_impl(self, application_id: str, new_status: str):
    current = self.get(application_id)
    if not current:
        return None, None
    old = current.get("status", "submitted")
    current["status"] = new_status
    execute(
        "UPDATE applications SET status=:status, payload_json=:payload_json WHERE application_id=:application_id",
        {"status": new_status, "payload_json": _to_json(current), "application_id": application_id},
    )
    return current, old


def _apprepo_notes_impl(self, application_id: str):
    return [_from_json(row.get("payload_json"), {}) for row in fetch_all("SELECT payload_json FROM application_notes WHERE application_id=:application_id", {"application_id": application_id})]


def _apprepo_add_note_impl(self, note: dict[str, Any]):
    note_id = note.get("note_id") or f"note_{uuid4().hex[:8]}"
    full = {**note, "note_id": note_id}
    execute(
        "INSERT INTO application_notes (note_id, application_id, recruiter_id, note_text, visibility, payload_json) VALUES (:note_id, :application_id, :recruiter_id, :note_text, :visibility, :payload_json)",
        {
            "note_id": note_id,
            "application_id": full.get("application_id"),
            "recruiter_id": full.get("recruiter_id"),
            "note_text": full.get("note_text"),
            "visibility": full.get("visibility", "internal"),
            "payload_json": _to_json(full),
        },
    )
    return full


def _member_search_impl(self, *, skill: str = "", location: str = "", keyword: str = ""):
    rows = fetch_all(
        """
        SELECT member_id, email, first_name, last_name, headline, about_text, location_text, payload_json
        FROM members WHERE is_deleted = 0
        ORDER BY first_name, last_name
        """
    )
    items = []
    skill = skill.lower()
    location = location.lower()
    keyword = keyword.lower()
    for row in rows:
        payload = _from_json(row.get("payload_json"), {})
        item = {
            "member_id": row.get("member_id"),
            "email": row.get("email"),
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "headline": row.get("headline"),
            "about_summary": row.get("about_text"),
            "location": row.get("location_text"),
        }
        if isinstance(payload, dict):
            item.update(payload)
        skills = [str(s).lower() for s in item.get("skills", [])]
        text = " ".join([str(item.get("first_name", "")), str(item.get("last_name", "")), str(item.get("headline", "")), str(item.get("about_summary", ""))]).lower()
        loc = str(item.get("location") or ", ".join([v for v in [item.get("city"), item.get("state")] if v])).lower()
        if skill and skill not in skills:
            continue
        if location and location not in loc:
            continue
        if keyword and keyword not in text and keyword not in str(item.get("email", "")).lower():
            continue
        items.append(item)
    return items


def _recruiter_get_impl(self, recruiter_id: str):
    row = fetch_one(
        "SELECT recruiter_id, company_id, email, name, phone, access_level, payload_json FROM recruiters WHERE recruiter_id = :recruiter_id",
        {"recruiter_id": recruiter_id},
    )
    if not row:
        return None
    payload = _from_json(row.get("payload_json"), {})
    item = {
        "recruiter_id": row.get("recruiter_id"),
        "company_id": row.get("company_id"),
        "email": row.get("email"),
        "name": row.get("name"),
        "phone": row.get("phone"),
        "access_level": row.get("access_level"),
    }
    if isinstance(payload, dict):
        item.update(payload)
    return item


def _recruiter_company_impl(self, company_id: str):
    row = fetch_one(
        "SELECT company_id, company_name, company_industry, company_size, payload_json FROM companies WHERE company_id = :company_id",
        {"company_id": company_id},
    )
    if not row:
        return None
    payload = _from_json(row.get("payload_json"), {})
    item = {
        "company_id": row.get("company_id"),
        "company_name": row.get("company_name"),
        "company_industry": row.get("company_industry"),
        "company_size": row.get("company_size"),
    }
    if isinstance(payload, dict):
        item.update(payload)
    return item


JobRepository.search = _jobrepo_search_impl
JobRepository.list_by_recruiter = _jobrepo_list_by_recruiter_impl
ApplicationRepository.find_duplicate = _apprepo_find_duplicate_impl
ApplicationRepository.get = _apprepo_get_impl
ApplicationRepository.list_by_job = _apprepo_list_by_job_impl
ApplicationRepository.list_by_member = _apprepo_list_by_member_impl
ApplicationRepository.update_status = _apprepo_update_status_impl
ApplicationRepository.add_note = _apprepo_add_note_impl
ApplicationRepository.notes_for_application = _apprepo_notes_impl
MemberRepository.search = _member_search_impl
RecruiterRepository.get_recruiter = _recruiter_get_impl
RecruiterRepository.get_company = _recruiter_company_impl

ApplicationRepository.find_by_job_and_member = _apprepo_find_duplicate_impl


def _member_create_v2(self, member: dict[str, Any]) -> dict[str, Any]:
    payload = dict(member)
    experience = payload.get('experience') or []
    current_company = payload.get('current_company') or ''
    current_title = payload.get('current_title') or ''
    if not current_company or not current_title:
        entries = [e for e in experience if isinstance(e, dict)]
        if entries:
            top = entries[0]
            current_company = current_company or top.get('company') or top.get('company_name') or ''
            current_title = current_title or top.get('title') or top.get('role') or ''
    execute(
        """
        INSERT INTO members (member_id, email, first_name, last_name, headline, about_text, location_text, profile_version, is_deleted, payload_json, skills_json, experience_json, education_json, profile_photo_url, resume_url, resume_text, current_company, current_title)
        VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text, :profile_version, 0, :payload_json, :skills_json, :experience_json, :education_json, :profile_photo_url, :resume_url, :resume_text, :current_company, :current_title)
        """,
        {
            'member_id': payload['member_id'],
            'email': payload.get('email'),
            'first_name': payload.get('first_name'),
            'last_name': payload.get('last_name'),
            'headline': payload.get('headline'),
            'about_text': payload.get('about') or payload.get('about_summary'),
            'location_text': _to_json(payload.get('location')) if isinstance(payload.get('location'), dict) else (payload.get('location') or ', '.join([v for v in [payload.get('city'), payload.get('state')] if v])),
            'profile_version': payload.get('profile_version', 1),
            'payload_json': _to_json(payload),
            'skills_json': _to_json(payload.get('skills') or []),
            'experience_json': _to_json(payload.get('experience') or []),
            'education_json': _to_json(payload.get('education') or []),
            'profile_photo_url': payload.get('profile_photo_url') or '',
            'resume_url': payload.get('resume_url') or '',
            'resume_text': payload.get('resume_text') or '',
            'current_company': current_company,
            'current_title': current_title,
        },
    )
    return self.get(payload['member_id']) or payload



def _member_get_v2(self, member_id: str) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM members WHERE member_id = :member_id", {'member_id': member_id})
    if not row or row.get('is_deleted'):
        return None
    payload = _from_json(row.get('payload_json'), {})
    payload.setdefault('member_id', row.get('member_id'))
    payload.setdefault('email', row.get('email'))
    payload.setdefault('first_name', row.get('first_name'))
    payload.setdefault('last_name', row.get('last_name'))
    payload.setdefault('headline', row.get('headline'))
    payload.setdefault('about_summary', row.get('about_text'))
    payload.setdefault('location', row.get('location_text'))
    payload.setdefault('skills', _from_json(row.get('skills_json'), payload.get('skills', [])))
    payload.setdefault('experience', _from_json(row.get('experience_json'), payload.get('experience', [])))
    payload.setdefault('education', _from_json(row.get('education_json'), payload.get('education', [])))
    payload.setdefault('profile_photo_url', row.get('profile_photo_url'))
    payload.setdefault('resume_url', row.get('resume_url'))
    payload.setdefault('resume_text', row.get('resume_text'))
    payload.setdefault('current_company', row.get('current_company'))
    payload.setdefault('current_title', row.get('current_title'))
    payload.setdefault('connections_count', row.get('connections_count', 0))
    payload.setdefault('profile_views', row.get('profile_views', 0))
    payload.setdefault('profile_version', row.get('profile_version', 1))
    return payload



def _member_update_v2(self, member_id: str, updates: dict[str, Any], expected_version: int | None = None) -> dict[str, Any] | None:
    current = self.get(member_id)
    if not current:
        return None
    if expected_version and expected_version != current.get('profile_version', 1):
        raise ValueError('version_conflict')
    current.update({k: v for k, v in updates.items() if k not in {'member_id', 'expected_version'}})
    current['profile_version'] = current.get('profile_version', 1) + 1
    experience = current.get('experience') or []
    current_company = current.get('current_company') or ''
    current_title = current.get('current_title') or ''
    entries = [e for e in experience if isinstance(e, dict)]
    if entries:
        current_company = current_company or entries[0].get('company') or entries[0].get('company_name') or ''
        current_title = current_title or entries[0].get('title') or entries[0].get('role') or ''
    current['current_company'] = current_company
    current['current_title'] = current_title
    execute(
        "UPDATE members SET email=:email, first_name=:first_name, last_name=:last_name, headline=:headline, about_text=:about_text, location_text=:location_text, profile_version=:profile_version, payload_json=:payload_json, skills_json=:skills_json, experience_json=:experience_json, education_json=:education_json, profile_photo_url=:profile_photo_url, resume_url=:resume_url, resume_text=:resume_text, current_company=:current_company, current_title=:current_title WHERE member_id=:member_id",
        {
            'member_id': member_id,
            'email': current.get('email'),
            'first_name': current.get('first_name'),
            'last_name': current.get('last_name'),
            'headline': current.get('headline'),
            'about_text': current.get('about') or current.get('about_summary'),
            'location_text': _to_json(current.get('location')) if isinstance(current.get('location'), dict) else (current.get('location') or ', '.join([v for v in [current.get('city'), current.get('state')] if v])),
            'profile_version': current['profile_version'],
            'payload_json': _to_json(current),
            'skills_json': _to_json(current.get('skills') or []),
            'experience_json': _to_json(current.get('experience') or []),
            'education_json': _to_json(current.get('education') or []),
            'profile_photo_url': current.get('profile_photo_url') or '',
            'resume_url': current.get('resume_url') or '',
            'resume_text': current.get('resume_text') or '',
            'current_company': current_company,
            'current_title': current_title,
        },
    )
    return current


MemberRepository.create = _member_create_v2
MemberRepository.get = _member_get_v2
MemberRepository.update = _member_update_v2


def _jobrepo_save_job_for_member(self, job_id: str, member_id: str) -> bool:
    existing = fetch_one(
        "SELECT save_id FROM saved_jobs WHERE job_id=:job_id AND member_id=:member_id",
        {'job_id': job_id, 'member_id': member_id},
    )
    if existing:
        return False
    record = {
        'save_id': f"sav_{uuid4().hex[:10]}",
        'job_id': job_id,
        'member_id': member_id,
        'created_at': now_mysql_datetime(),
        'payload_json': _to_json({'job_id': job_id, 'member_id': member_id, 'saved_at': now_iso()}),
    }
    execute(
        "INSERT INTO saved_jobs (save_id, job_id, member_id, created_at, payload_json) VALUES (:save_id, :job_id, :member_id, :created_at, :payload_json)",
        record,
    )
    return True


def _jobrepo_unsave_job_for_member(self, job_id: str, member_id: str) -> bool:
    count = execute(
        "DELETE FROM saved_jobs WHERE job_id=:job_id AND member_id=:member_id",
        {'job_id': job_id, 'member_id': member_id},
    )
    return bool(count)


def _jobrepo_is_saved_by_member(self, job_id: str, member_id: str) -> bool:
    return bool(fetch_one(
        "SELECT save_id FROM saved_jobs WHERE job_id=:job_id AND member_id=:member_id",
        {'job_id': job_id, 'member_id': member_id},
    ))


def _jobrepo_saved_job_ids_for_member(self, member_id: str) -> list[str]:
    rows = fetch_all("SELECT job_id FROM saved_jobs WHERE member_id=:member_id", {'member_id': member_id})
    return [row.get('job_id') for row in rows if row.get('job_id')]


def _jobrepo_list_saved_jobs_for_member(self, member_id: str):
    rows = fetch_all(
        """
        SELECT sj.job_id, sj.created_at AS saved_at, j.payload_json AS job_payload_json
        FROM saved_jobs sj
        JOIN jobs j ON j.job_id = sj.job_id
        WHERE sj.member_id=:member_id
        ORDER BY sj.created_at DESC
        """,
        {'member_id': member_id},
    )
    items = []
    for row in rows:
        payload = _from_json(row.get('job_payload_json'), {})
        if not isinstance(payload, dict):
            payload = {}
        payload['job_id'] = payload.get('job_id') or row.get('job_id')
        payload['saved_at'] = str(row.get('saved_at'))
        payload['is_saved'] = True
        items.append(payload)
    return items


JobRepository.save_job_for_member = _jobrepo_save_job_for_member
JobRepository.unsave_job_for_member = _jobrepo_unsave_job_for_member
JobRepository.is_saved_by_member = _jobrepo_is_saved_by_member
JobRepository.saved_job_ids_for_member = _jobrepo_saved_job_ids_for_member
JobRepository.list_saved_jobs_for_member = _jobrepo_list_saved_jobs_for_member


def _analyticsrepo_list_benchmarks(self, limit: int = 20) -> list[dict[str, Any]]:
    items = find_many('benchmarks', sort=[('timestamp', -1), ('benchmark_id', -1)])
    out = []
    for item in items[:limit]:
        row = dict(item)
        row.setdefault('variant', row.get('scenario') or row.get('name'))
        out.append(row)
    return out


AnalyticsRepository.list_benchmarks = _analyticsrepo_list_benchmarks
