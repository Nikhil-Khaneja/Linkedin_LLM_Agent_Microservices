"""
Hiring Assistant Supervisor Agent
Orchestrates: ResumeParser -> JobMatcher -> OutreachDraftGenerator
"""
import asyncio
import httpx
import json
import re
import os
from datetime import datetime
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, db, redis, kafka):
        self.db = db
        self.redis = redis
        self.kafka = kafka

    async def run_task(self, task_id: str, broadcast: Callable):
        task = await self.db.agent_tasks.find_one({"task_id": task_id})
        if not task:
            return
        try:
            await self._update_task(task_id, {"status": "running", "current_step": "starting"})
            await broadcast(task_id, {"type": "step", "step": "starting", "task_id": task_id})

            task_type = task["task_type"]
            if task_type in ("full_pipeline", "shortlist", "shortlist_and_outreach"):
                await self._run_full_pipeline(task_id, task, broadcast)
            elif task_type == "resume_parse":
                await self._run_resume_parse(task_id, task, broadcast)
            elif task_type == "match_score":
                await self._run_match_score(task_id, task, broadcast)

        except Exception as e:
            logger.error(f"[orchestrator] Task {task_id} failed: {e}")
            await self._update_task(task_id, {"status": "failed", "error_message": str(e)})
            await broadcast(task_id, {"type": "error", "task_id": task_id, "message": str(e)})

    async def _run_full_pipeline(self, task_id: str, task: dict, broadcast: Callable):
        job_id = task["job_id"]
        steps = []

        # Step 1: Fetch job details
        await self._update_task(task_id, {"current_step": "fetching_job"})
        await broadcast(task_id, {"type": "step", "step": "fetching_job", "task_id": task_id})
        auth_header = task.get("auth_token")
        job = await self._fetch_job(job_id, auth_header=auth_header)
        steps.append({"step": "fetch_job", "status": "done", "ts": datetime.utcnow().isoformat()})

        # Step 2: Fetch candidates
        await self._update_task(task_id, {"current_step": "fetching_candidates"})
        await broadcast(task_id, {"type": "step", "step": "fetching_candidates", "task_id": task_id})
        candidates = await self._fetch_candidates(job_id, auth_header=auth_header)
        steps.append({"step": "fetch_candidates", "status": "done", "count": len(candidates), "ts": datetime.utcnow().isoformat()})

        # Step 3: Resume Parser Skill
        await self._update_task(task_id, {"current_step": "parsing_resumes"})
        await broadcast(task_id, {"type": "step", "step": "parsing_resumes", "count": len(candidates), "task_id": task_id})
        parsed_candidates = []
        for c in candidates[:50]:
            parsed = await self._parse_resume_skill(c.get("resume_text", ""))
            parsed_candidates.append({**c, "parsed": parsed})
        steps.append({"step": "parse_resumes", "status": "done", "ts": datetime.utcnow().isoformat()})

        # Step 4: Job-Candidate Matching Skill
        await self._update_task(task_id, {"current_step": "matching_candidates"})
        await broadcast(task_id, {"type": "step", "step": "matching_candidates", "task_id": task_id})
        scored = await self._match_skill(job, parsed_candidates)
        top_k = sorted(scored, key=lambda x: x["match_score"], reverse=True)[:10]
        steps.append({"step": "match_candidates", "status": "done", "ts": datetime.utcnow().isoformat()})

        # Step 5: Outreach Draft Generator
        await self._update_task(task_id, {"current_step": "drafting_outreach"})
        await broadcast(task_id, {"type": "step", "step": "drafting_outreach", "task_id": task_id})
        outreach_drafts = []
        for candidate in top_k[:3]:
            draft = await self._generate_outreach(job, candidate)
            outreach_drafts.append({"candidate_id": candidate.get("member_id"), "draft": draft})
        steps.append({"step": "generate_outreach", "status": "done", "ts": datetime.utcnow().isoformat()})

        top_skills_overlap = self._compute_skills_overlap(job.get("skills", []), top_k)

        output = {
            "shortlist": top_k,
            "outreach_drafts": outreach_drafts,
            "total_candidates": len(candidates),
            "evaluated": len(parsed_candidates),
            "metrics": {
                "avg_match_score": round(sum(c["match_score"] for c in top_k) / max(len(top_k), 1), 3),
                "top_skills_overlap_pct": top_skills_overlap,
                "shortlist_size": len(top_k),
            }
        }

        await self._update_task(task_id, {
            "status": "waiting_approval",
            "current_step": "waiting_approval",
            "steps": steps,
            "output": output,
        })
        await broadcast(task_id, {
            "type": "waiting_approval",
            "task_id": task_id,
            "output_summary": {"shortlist_size": len(top_k), "metrics": output["metrics"]}
        })

        await self.kafka.send_and_wait("ai.results", json.dumps({
            "event_type": "ai.completed",
            "trace_id": task.get("trace_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": task.get("recruiter_id"),
            "entity": {"entity_type": "ai_task", "entity_id": task_id},
            "payload": {"task_id": task_id, "status": "waiting_approval", "shortlist_size": len(top_k)},
            "idempotency_key": task_id + "_result",
        }).encode())

    async def _run_resume_parse(self, task_id: str, task: dict, broadcast: Callable):
        job_id = task["job_id"]
        auth_header = task.get("auth_token")
        req_limit = task.get("input_payload", {}).get("limit", 25)
        try:
            limit = max(1, min(int(req_limit), 100))
        except Exception:
            limit = 25

        await self._update_task(task_id, {"current_step": "fetching_candidates"})
        await broadcast(task_id, {"type": "step", "step": "fetching_candidates", "task_id": task_id})
        candidates = await self._fetch_candidates(job_id, auth_header=auth_header, page_size=limit)

        await self._update_task(task_id, {"current_step": "parsing_resumes"})
        await broadcast(task_id, {
            "type": "step",
            "step": "parsing_resumes",
            "task_id": task_id,
            "count": len(candidates),
        })

        parsed_items = []
        failures = 0
        skill_freq = {}
        education_freq = {}
        years_total = 0
        years_count = 0

        for c in candidates:
            try:
                resume_text = c.get("resume_text") or c.get("resume") or ""
                parsed = await self._parse_resume_skill(resume_text)
                parsed_items.append({
                    "member_id": c.get("member_id"),
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "raw_length": parsed.get("raw_length", 0),
                    "skills": parsed.get("skills", []),
                    "years_experience": parsed.get("years_experience", 0),
                    "education": parsed.get("education", []),
                })
                for sk in parsed.get("skills", []):
                    skill_freq[sk] = skill_freq.get(sk, 0) + 1
                for edu in parsed.get("education", []):
                    education_freq[edu] = education_freq.get(edu, 0) + 1
                years_total += parsed.get("years_experience", 0)
                years_count += 1
            except Exception:
                failures += 1

        parsed_with_text = sum(1 for item in parsed_items if item.get("raw_length", 0) > 0)
        avg_years = round((years_total / years_count), 2) if years_count else 0.0
        top_skills = [k for k, _ in sorted(skill_freq.items(), key=lambda kv: kv[1], reverse=True)[:10]]
        top_education = [k for k, _ in sorted(education_freq.items(), key=lambda kv: kv[1], reverse=True)[:10]]

        output = {
            "mode": "batch_resume_parse",
            "job_id": job_id,
            "requested_limit": limit,
            "total_candidates": len(candidates),
            "parsed_count": len(parsed_items),
            "parsed_with_text_count": parsed_with_text,
            "failed_count": failures,
            "top_skills": top_skills,
            "top_education": top_education,
            "average_years_experience": avg_years,
            "items": parsed_items[:25],
            "metrics": {
                "total_candidates": len(candidates),
                "parsed_count": len(parsed_items),
                "parsed_with_text_count": parsed_with_text,
                "failed_count": failures,
                "avg_years_experience": avg_years,
            },
        }

        await self._update_task(task_id, {"status": "approved", "current_step": "approved", "output": output})
        await broadcast(task_id, {"type": "approved", "task_id": task_id, "output": output})
        await self.kafka.send_and_wait("ai.results", json.dumps({
            "event_type": "ai.completed",
            "trace_id": task.get("trace_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": task.get("recruiter_id"),
            "entity": {"entity_type": "ai_task", "entity_id": task_id},
            "payload": {"task_id": task_id, "status": "approved", "parsed_count": len(parsed_items)},
            "idempotency_key": task_id + "_result",
        }).encode())

    async def _run_match_score(self, task_id: str, task: dict, broadcast: Callable):
        await self._update_task(task_id, {"current_step": "scoring"})
        job = await self._fetch_job(task["job_id"], auth_header=task.get("auth_token"))
        candidate = task.get("input_payload", {})
        score = await self._match_skill(job, [candidate])
        await self._update_task(task_id, {"status": "waiting_approval", "current_step": "waiting_approval",
                                           "output": score[0] if score else {}})
        await broadcast(task_id, {"type": "waiting_approval", "task_id": task_id})

    # ── Skills ────────────────────────────────────────────────
    async def _parse_resume_skill(self, resume_text: str) -> dict:
        """Resume Parser Skill: Extract structured fields from resume text."""
        cleaned = (resume_text or "").strip()
        if not cleaned:
            return {"skills": [], "years_experience": 0, "education": [], "raw_length": 0}

        skill_keywords = [
            "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "SQL", "MongoDB",
            "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Machine Learning",
            "Deep Learning", "NLP", "FastAPI", "Express", "Spring", "Django", "Flask", "C++",
            "Go", "Rust", "GraphQL", "REST", "gRPC", "Spark", "Hadoop", "TensorFlow", "PyTorch"
        ]
        skills = [sk for sk in skill_keywords if sk.lower() in cleaned.lower()]

        years = 0
        matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', cleaned.lower())
        if matches:
            years = max(int(m) for m in matches)

        edu = []
        for degree in ["Bachelor", "Master", "PhD", "B.S.", "M.S.", "MBA", "B.Tech", "M.Tech"]:
            if degree.lower() in cleaned.lower():
                edu.append(degree)

        return {"skills": skills, "years_experience": years, "education": edu, "raw_length": len(cleaned)}

    async def _match_skill(self, job: dict, candidates: list) -> list:
        """Job-Candidate Matching Skill: Compute match score (0-100)."""
        normalized_job_skills = self._normalize_job_skills(job.get("skills") or [])
        job_skills = set(s.lower() for s in normalized_job_skills)
        level_map = {"internship": 0, "entry": 1, "associate": 2, "mid": 3, "senior": 4, "director": 5, "executive": 6}
        target_level = level_map.get(job.get("seniority_level", "mid"), 3)

        scored = []
        for c in candidates:
            parsed = c.get("parsed", {})
            cand_skills = set(s.lower() for s in parsed.get("skills", []))

            skill_score = (len(job_skills & cand_skills) / len(job_skills) * 60) if job_skills else 30.0
            exp_score = min(parsed.get("years_experience", 0) / max(target_level + 1, 1) * 25, 25)
            edu_score = min(len(parsed.get("education", [])) * 5, 15)
            match_score = round(skill_score + exp_score + edu_score, 2)

            scored.append({
                **c,
                "match_score": match_score,
                "skill_overlap": list(job_skills & cand_skills),
                "skill_score": skill_score,
                "experience_score": exp_score,
            })
        return scored

    async def _generate_outreach(self, job: dict, candidate: dict) -> str:
        """Outreach Draft Generator Skill."""
        name = f"{candidate.get('first_name', 'Candidate')} {candidate.get('last_name', '')}".strip()
        job_title = job.get("title", "this role")
        company = job.get("company_name", "our company")
        top_skills = ", ".join(list(candidate.get("skill_overlap", []))[:3]) or "your expertise"
        score = candidate.get("match_score", 0)

        lines = [
            f"Hi {name},",
            "",
            f"I came across your profile and was impressed by your background in {top_skills}.",
            "",
            f"We are hiring a {job_title} at {company} and based on your profile (match score: {score}/100), "
            f"I believe you would be a strong fit.",
            "",
            "This role offers an exciting opportunity to work on impactful distributed systems.",
            "I would love to schedule a quick 20-minute call to tell you more.",
            "",
            "Would you be available this week for a brief conversation?",
            "",
            "Best regards"
        ]
        return "\n".join(lines)

    async def _fetch_job(self, job_id: str, auth_header: str | None = None) -> dict:
        job_url = os.getenv("JOB_SERVICE_URL", "http://job-service:3004")
        headers = {"Authorization": auth_header} if auth_header else {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(f"{job_url}/jobs/get", json={"job_id": job_id}, headers=headers)
                if r.status_code == 200:
                    return r.json().get("data", {})
        except Exception:
            pass
        return {"job_id": job_id, "title": "Unknown Job", "skills": []}

    async def _fetch_candidates(self, job_id: str, auth_header: str | None = None, page_size: int = 100) -> list:
        app_url = os.getenv("APPLICATION_SERVICE_URL", "http://application-service:3005")
        headers = {"Authorization": auth_header} if auth_header else {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{app_url}/applications/byJob",
                    json={"job_id": job_id, "page_size": page_size},
                    headers=headers
                )
                if r.status_code == 200:
                    return r.json().get("data", {}).get("applications", [])
        except Exception:
            pass
        return []

    def _compute_skills_overlap(self, job_skills: list, candidates: list) -> float:
        normalized_job_skills = self._normalize_job_skills(job_skills)
        if not normalized_job_skills or not candidates:
            return 0.0
        total = sum(len(c.get("skill_overlap", [])) for c in candidates) / len(candidates)
        return round(total / max(len(normalized_job_skills), 1) * 100, 1)

    def _normalize_job_skills(self, raw_skills: list) -> list[str]:
        normalized = []
        for item in raw_skills or []:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                name = item.get("skill_name") or item.get("name")
                if isinstance(name, str):
                    normalized.append(name)
        return normalized

    async def _update_task(self, task_id: str, updates: dict):
        updates["updated_at"] = datetime.utcnow()
        await self.db.agent_tasks.update_one({"task_id": task_id}, {"$set": updates})
