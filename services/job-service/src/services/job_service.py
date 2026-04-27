"""
Job Service - Business logic for job operations
"""
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JobService:
    """Service class for job-related database operations"""

    def __init__(self, db: Session):
        self.db = db

    def generate_job_id(self) -> str:
        """Generate unique job ID"""
        return f"job_{uuid.uuid4().hex[:8]}"

    async def create_job(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job posting"""
        job_id = self.generate_job_id()

        # Insert job
        insert_job_sql = text("""
            INSERT INTO jobs (
                job_id, company_id, recruiter_id, title, description,
                seniority_level, employment_type, location, work_mode,
                salary_min, salary_max, salary_currency, status
            ) VALUES (
                :job_id, :company_id, :recruiter_id, :title, :description,
                :seniority_level, :employment_type, :location, :work_mode,
                :salary_min, :salary_max, :salary_currency, 'open'
            )
        """)

        salary_range = data.get("salary_range") or {}

        self.db.execute(insert_job_sql, {
            "job_id": job_id,
            "company_id": data["company_id"],
            "recruiter_id": data["recruiter_id"],
            "title": data["title"],
            "description": data["description"],
            "seniority_level": data.get("seniority_level", "mid"),
            "employment_type": data.get("employment_type", "full_time"),
            "location": data["location"],
            "work_mode": data.get("work_mode", "onsite"),
            "salary_min": salary_range.get("min"),
            "salary_max": salary_range.get("max"),
            "salary_currency": salary_range.get("currency", "USD")
        })

        # Insert skills
        if data.get("skills_required"):
            insert_skill_sql = text("""
                INSERT INTO job_skills (job_id, skill_name, is_required)
                VALUES (:job_id, :skill_name, TRUE)
            """)
            for skill in data["skills_required"]:
                self.db.execute(insert_skill_sql, {
                    "job_id": job_id,
                    "skill_name": skill.strip()
                })

        self.db.commit()

        return {
            "job_id": job_id,
            "status": "open",
            "recruiter_id": data["recruiter_id"]
        }

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID with skills"""
        # Get job
        job_sql = text("""
            SELECT
                job_id, company_id, recruiter_id, title, description,
                seniority_level, employment_type, location, work_mode,
                salary_min, salary_max, salary_currency,
                posted_datetime, updated_datetime, closed_datetime,
                status, views_count, applicants_count, saves_count, version
            FROM jobs
            WHERE job_id = :job_id
        """)

        result = self.db.execute(job_sql, {"job_id": job_id}).fetchone()

        if not result:
            return None

        # Get skills
        skills_sql = text("""
            SELECT skill_name FROM job_skills WHERE job_id = :job_id
        """)
        skills_result = self.db.execute(skills_sql, {"job_id": job_id}).fetchall()
        skills = [row[0] for row in skills_result]

        job = {
            "job_id": result[0],
            "company_id": result[1],
            "recruiter_id": result[2],
            "title": result[3],
            "description": result[4],
            "seniority_level": result[5],
            "employment_type": result[6],
            "location": result[7],
            "work_mode": result[8],
            "salary_range": {
                "min": float(result[9]) if result[9] else None,
                "max": float(result[10]) if result[10] else None,
                "currency": result[11]
            } if result[9] or result[10] else None,
            "posted_datetime": result[12],
            "updated_datetime": result[13],
            "closed_datetime": result[14],
            "status": result[15],
            "views_count": result[16],
            "applicants_count": result[17],
            "saves_count": result[18],
            "version": result[19],
            "skills_required": skills
        }

        return job

    async def update_job(
        self,
        job_id: str,
        recruiter_id: str,
        updates: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Update job fields"""
        # Check job exists and belongs to recruiter
        check_sql = text("""
            SELECT recruiter_id, status, version FROM jobs WHERE job_id = :job_id
        """)
        result = self.db.execute(check_sql, {"job_id": job_id}).fetchone()

        if not result:
            return False, {"error": "not_found", "message": "Job not found"}

        if result[0] != recruiter_id:
            return False, {"error": "forbidden", "message": "Not authorized to update this job"}

        if result[1] == "closed":
            return False, {"error": "job_closed", "message": "Cannot update closed job"}

        current_version = result[2]

        # Check version if provided
        if expected_version and expected_version != current_version:
            return False, {
                "error": "version_conflict",
                "message": "Job was updated by another action",
                "details": {"expected_version": expected_version, "current_version": current_version}
            }

        # Build update query dynamically
        update_fields = []
        params = {"job_id": job_id, "new_version": current_version + 1}

        field_mapping = {
            "title": "title",
            "description": "description",
            "seniority_level": "seniority_level",
            "employment_type": "employment_type",
            "location": "location",
            "work_mode": "work_mode"
        }

        for key, column in field_mapping.items():
            if key in updates and updates[key] is not None:
                update_fields.append(f"{column} = :{key}")
                params[key] = updates[key]

        # Handle salary range
        if "salary_range" in updates and updates["salary_range"]:
            salary = updates["salary_range"]
            if "min" in salary:
                update_fields.append("salary_min = :salary_min")
                params["salary_min"] = salary.get("min")
            if "max" in salary:
                update_fields.append("salary_max = :salary_max")
                params["salary_max"] = salary.get("max")
            if "currency" in salary:
                update_fields.append("salary_currency = :salary_currency")
                params["salary_currency"] = salary.get("currency", "USD")

        # Always update version
        update_fields.append("version = :new_version")

        if update_fields:
            update_sql = text(f"""
                UPDATE jobs SET {', '.join(update_fields)}
                WHERE job_id = :job_id
            """)
            self.db.execute(update_sql, params)

        # Handle skills update
        if "skills_required" in updates and updates["skills_required"]:
            # Delete existing skills
            self.db.execute(
                text("DELETE FROM job_skills WHERE job_id = :job_id"),
                {"job_id": job_id}
            )
            # Insert new skills
            for skill in updates["skills_required"]:
                self.db.execute(
                    text("INSERT INTO job_skills (job_id, skill_name, is_required) VALUES (:job_id, :skill, TRUE)"),
                    {"job_id": job_id, "skill": skill.strip()}
                )

        self.db.commit()

        return True, {
            "job_id": job_id,
            "updated": True,
            "version": current_version + 1
        }

    async def search_jobs(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        employment_type: Optional[str] = None,
        seniority_level: Optional[str] = None,
        work_mode: Optional[str] = None,
        skills: Optional[List[str]] = None,
        salary_min: Optional[float] = None,
        remote: Optional[bool] = None,
        page: int = 1,
        page_size: int = 10,
        sort: str = "relevance"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search jobs with filters"""
        # Build WHERE conditions
        conditions = ["j.status = 'open'"]
        params = {}

        if keyword:
            conditions.append("MATCH(j.title, j.description) AGAINST(:keyword IN NATURAL LANGUAGE MODE)")
            params["keyword"] = keyword

        if location:
            conditions.append("j.location LIKE :location")
            params["location"] = f"%{location}%"

        if employment_type:
            conditions.append("j.employment_type = :employment_type")
            params["employment_type"] = employment_type

        if seniority_level:
            conditions.append("j.seniority_level = :seniority_level")
            params["seniority_level"] = seniority_level

        if work_mode:
            conditions.append("j.work_mode = :work_mode")
            params["work_mode"] = work_mode

        if remote is True:
            conditions.append("j.work_mode = 'remote'")

        if salary_min:
            conditions.append("(j.salary_max >= :salary_min OR j.salary_max IS NULL)")
            params["salary_min"] = salary_min

        # Build skill filter
        if skills and len(skills) > 0:
            skill_placeholders = []
            for i, skill in enumerate(skills):
                param_name = f"skill_{i}"
                skill_placeholders.append(f":{param_name}")
                params[param_name] = skill
            conditions.append(f"""
                j.job_id IN (
                    SELECT DISTINCT job_id FROM job_skills
                    WHERE skill_name IN ({', '.join(skill_placeholders)})
                )
            """)

        where_clause = " AND ".join(conditions)

        # Build ORDER BY
        order_by = "j.posted_datetime DESC"
        if sort == "oldest":
            order_by = "j.posted_datetime ASC"
        elif sort == "relevance" and keyword:
            order_by = f"MATCH(j.title, j.description) AGAINST(:keyword IN NATURAL LANGUAGE MODE) DESC, j.posted_datetime DESC"

        # Count total
        count_sql = text(f"""
            SELECT COUNT(*) FROM jobs j WHERE {where_clause}
        """)
        total = self.db.execute(count_sql, params).scalar()

        # Fetch page
        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        search_sql = text(f"""
            SELECT
                j.job_id, j.title, j.company_id, j.location, j.employment_type,
                j.work_mode, j.seniority_level, j.posted_datetime, j.status,
                j.views_count, j.applicants_count, j.saves_count
            FROM jobs j
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT :limit OFFSET :offset
        """)

        results = self.db.execute(search_sql, params).fetchall()

        jobs = []
        for row in results:
            jobs.append({
                "job_id": row[0],
                "title": row[1],
                "company_id": row[2],
                "location": row[3],
                "employment_type": row[4],
                "work_mode": row[5],
                "seniority_level": row[6],
                "posted_datetime": row[7],
                "status": row[8],
                "views_count": row[9],
                "applicants_count": row[10],
                "saves_count": row[11]
            })

        return jobs, total

    async def close_job(self, job_id: str, recruiter_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Close a job posting"""
        # Check job exists and belongs to recruiter
        check_sql = text("""
            SELECT recruiter_id, status FROM jobs WHERE job_id = :job_id
        """)
        result = self.db.execute(check_sql, {"job_id": job_id}).fetchone()

        if not result:
            return False, {"error": "not_found", "message": "Job not found"}

        if result[0] != recruiter_id:
            return False, {"error": "forbidden", "message": "Not authorized to close this job"}

        if result[1] == "closed":
            return False, {"error": "already_closed", "message": "Job is already closed"}

        # Close the job
        close_sql = text("""
            UPDATE jobs
            SET status = 'closed', closed_datetime = NOW()
            WHERE job_id = :job_id
        """)
        self.db.execute(close_sql, {"job_id": job_id})
        self.db.commit()

        return True, {
            "job_id": job_id,
            "status": "closed",
            "closed_datetime": datetime.utcnow()
        }

    async def get_jobs_by_recruiter(
        self,
        recruiter_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get jobs owned by a recruiter"""
        conditions = ["recruiter_id = :recruiter_id"]
        params = {"recruiter_id": recruiter_id}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)

        # Count
        count_sql = text(f"SELECT COUNT(*) FROM jobs WHERE {where_clause}")
        total = self.db.execute(count_sql, params).scalar()

        # Fetch
        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        fetch_sql = text(f"""
            SELECT
                job_id, title, company_id, location, employment_type,
                work_mode, seniority_level, posted_datetime, status,
                views_count, applicants_count, saves_count
            FROM jobs
            WHERE {where_clause}
            ORDER BY posted_datetime DESC
            LIMIT :limit OFFSET :offset
        """)

        results = self.db.execute(fetch_sql, params).fetchall()

        jobs = []
        for row in results:
            jobs.append({
                "job_id": row[0],
                "title": row[1],
                "company_id": row[2],
                "location": row[3],
                "employment_type": row[4],
                "work_mode": row[5],
                "seniority_level": row[6],
                "posted_datetime": row[7],
                "status": row[8],
                "views_count": row[9],
                "applicants_count": row[10],
                "saves_count": row[11]
            })

        return jobs, total

    async def save_job(self, job_id: str, member_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Save a job for a member"""
        # Check job exists
        check_sql = text("SELECT status FROM jobs WHERE job_id = :job_id")
        result = self.db.execute(check_sql, {"job_id": job_id}).fetchone()

        if not result:
            return False, {"error": "not_found", "message": "Job not found"}

        # Try to insert (will fail if already saved due to unique constraint)
        try:
            insert_sql = text("""
                INSERT INTO saved_jobs (member_id, job_id) VALUES (:member_id, :job_id)
            """)
            self.db.execute(insert_sql, {"member_id": member_id, "job_id": job_id})

            # Update saves count
            self.db.execute(text("CALL increment_job_saves(:job_id)"), {"job_id": job_id})

            self.db.commit()

            return True, {"saved": True, "saved_at": datetime.utcnow()}

        except Exception as e:
            self.db.rollback()
            if "Duplicate" in str(e):
                return False, {"error": "already_saved", "message": "Job already saved"}
            raise

    async def unsave_job(self, job_id: str, member_id: str) -> bool:
        """Remove saved job"""
        delete_sql = text("""
            DELETE FROM saved_jobs WHERE member_id = :member_id AND job_id = :job_id
        """)
        result = self.db.execute(delete_sql, {"member_id": member_id, "job_id": job_id})

        if result.rowcount > 0:
            self.db.execute(text("CALL decrement_job_saves(:job_id)"), {"job_id": job_id})
            self.db.commit()
            return True

        return False

    async def get_saved_jobs_by_member(
        self,
        member_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get jobs saved by a member"""
        # Count
        count_sql = text("SELECT COUNT(*) FROM saved_jobs WHERE member_id = :member_id")
        total = self.db.execute(count_sql, {"member_id": member_id}).scalar()

        # Fetch
        offset = (page - 1) * page_size

        fetch_sql = text("""
            SELECT
                j.job_id, j.title, j.company_id, j.location, j.employment_type,
                j.work_mode, j.seniority_level, j.posted_datetime, j.status,
                j.views_count, j.applicants_count, j.saves_count,
                s.saved_at
            FROM saved_jobs s
            JOIN jobs j ON s.job_id = j.job_id
            WHERE s.member_id = :member_id
            ORDER BY s.saved_at DESC
            LIMIT :limit OFFSET :offset
        """)

        results = self.db.execute(fetch_sql, {
            "member_id": member_id,
            "limit": page_size,
            "offset": offset
        }).fetchall()

        jobs = []
        for row in results:
            jobs.append({
                "job_id": row[0],
                "title": row[1],
                "company_id": row[2],
                "location": row[3],
                "employment_type": row[4],
                "work_mode": row[5],
                "seniority_level": row[6],
                "posted_datetime": row[7],
                "status": row[8],
                "views_count": row[9],
                "applicants_count": row[10],
                "saves_count": row[11],
                "saved_at": row[12]
            })

        return jobs, total

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status (internal API for Owner 5)"""
        sql = text("""
            SELECT status, closed_datetime FROM jobs WHERE job_id = :job_id
        """)
        result = self.db.execute(sql, {"job_id": job_id}).fetchone()

        if not result:
            return None

        return {
            "job_id": job_id,
            "status": result[0],
            "closed_datetime": result[1]
        }

    async def increment_view_count(self, job_id: str):
        """Increment job view count"""
        self.db.execute(text("CALL increment_job_views(:job_id)"), {"job_id": job_id})
        self.db.commit()
