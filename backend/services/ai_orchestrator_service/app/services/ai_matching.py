from __future__ import annotations

from dataclasses import dataclass

from services.ai_orchestrator_service.app.services.ai_embeddings import HashingEmbeddingService
from services.ai_orchestrator_service.app.services.ai_resume_intelligence import (
    collect_resume_text,
    extract_keywords,
    job_skills,
    normalize_skill,
    parse_resume,
    seniority_target_years,
)


@dataclass(slots=True)
class CandidateArtifacts:
    candidate: dict
    parsed_resume: dict
    resume_text: str
    embedding_similarity: float


class CandidateMatchingService:
    """Separated ranking layer: embedding similarity + rules.

    The ranking path is intentionally isolated from orchestration so it can evolve
    into a standalone microservice later without changing the AI orchestration API.
    """

    def __init__(self, embedding_service: HashingEmbeddingService | None = None):
        self.embedding_service = embedding_service or HashingEmbeddingService()

    def _job_text(self, job: dict) -> str:
        skills = ', '.join(job_skills(job))
        return '\n'.join([
            str(job.get('title') or ''),
            str(job.get('description') or job.get('description_text') or ''),
            str(job.get('location') or job.get('location_text') or ''),
            str(job.get('seniority_level') or ''),
            f'Skills: {skills}',
        ]).strip()

    def _location_bonus(self, job: dict, member: dict) -> int:
        job_location = str(job.get('location') or job.get('location_text') or '').lower()
        member_location = str(member.get('location') or ', '.join([str(member.get('city') or ''), str(member.get('state') or '')])).lower()
        work_mode = str(job.get('work_mode') or '').lower()
        if 'remote' in work_mode:
            return 8
        if job_location and member_location and (job_location in member_location or member_location in job_location):
            return 8
        return 0

    def _skill_scores(self, job: dict, parsed_resume: dict) -> tuple[list[str], list[str], float]:
        required = job_skills(job)
        req_norm = {normalize_skill(skill): skill for skill in required}
        cand_norm = {normalize_skill(skill): skill for skill in parsed_resume.get('skills') or []}
        matched_norm = [norm for norm in req_norm if norm in cand_norm]
        missing_norm = [norm for norm in req_norm if norm not in cand_norm]
        matched = [req_norm[norm] for norm in matched_norm][:10]
        missing = [req_norm[norm] for norm in missing_norm][:10]
        ratio = (len(matched_norm) / max(1, len(req_norm))) if req_norm else min(1.0, len(cand_norm) / 5.0)
        return matched, missing, ratio

    def _keyword_overlap(self, job: dict, resume_text: str) -> list[str]:
        job_kw = extract_keywords(' '.join([str(job.get('title') or ''), str(job.get('description') or job.get('description_text') or '')]), 16)
        cand_kw = set(extract_keywords(resume_text, 28))
        return [kw for kw in job_kw if kw in cand_kw][:8]

    def _experience_score(self, job: dict, parsed_resume: dict) -> tuple[int, float]:
        minimum, maximum = seniority_target_years(job.get('seniority_level'))
        years = float(parsed_resume.get('years_experience') or 0)
        if years >= minimum:
            score = 15
            if years <= maximum + 3:
                score += 5
        else:
            score = max(0, int(years * 3))
        return score, years

    def _education_score(self, parsed_resume: dict) -> int:
        return 4 if parsed_resume.get('education') else 0

    def score_candidate(self, job: dict, member: dict, parsed_resume: dict, resume_text: str) -> tuple[int, list[str], list[str], list[str], str, float]:
        matched, missing, skill_ratio = self._skill_scores(job, parsed_resume)
        job_text = self._job_text(job)
        embedding_similarity = max(0.0, self.embedding_service.similarity(job_text, resume_text))
        keyword_overlap = self._keyword_overlap(job, resume_text)
        experience_score, years = self._experience_score(job, parsed_resume)
        score = 20
        score += round(skill_ratio * 35)
        score += round(embedding_similarity * 25)
        score += experience_score
        score += self._location_bonus(job, member)
        score += self._education_score(parsed_resume)
        score += min(8, len(keyword_overlap) * 2)
        score = max(0, min(100, int(score)))

        rationale_bits: list[str] = []
        if matched:
            rationale_bits.append(f"Matched skills: {', '.join(matched[:4])}")
        rationale_bits.append(f"Embedding similarity: {round(embedding_similarity * 100)}%")
        if years:
            rationale_bits.append(f"Approx. {years} years experience")
        if parsed_resume.get('education'):
            rationale_bits.append(f"Education: {parsed_resume['education']}")
        rationale = '. '.join(rationale_bits) if rationale_bits else 'Limited structured resume details; score based on available resume text and profile data.'
        return score, matched, missing, keyword_overlap, rationale, embedding_similarity

    def build_candidate(self, application: dict, member: dict, job: dict, source_rank: int) -> CandidateArtifacts:
        full_name = ' '.join([
            part for part in [application.get('first_name') or member.get('first_name'), application.get('last_name') or member.get('last_name')] if part
        ]).strip()
        resume_text = collect_resume_text(application, member)
        parsed_resume = parse_resume(resume_text, member, application).as_dict()
        match_score, matched, missing, keyword_overlap, rationale, embedding_similarity = self.score_candidate(job, member, parsed_resume, resume_text)
        candidate = {
            'candidate_id': application.get('member_id'),
            'application_id': application.get('application_id'),
            'name': full_name or application.get('member_id'),
            'first_name': application.get('first_name') or member.get('first_name') or (full_name.split(' ', 1)[0] if full_name else application.get('member_id')),
            'last_name': application.get('last_name') or member.get('last_name') or (full_name.split(' ', 1)[1] if ' ' in full_name else ''),
            'headline': application.get('headline') or member.get('headline'),
            'resume_url': application.get('resume_url') or application.get('resume_ref') or member.get('resume_url'),
            'resume_text': resume_text[:1200],
            'resume_parsed': parsed_resume,
            'skill_overlap': list(matched),
            'missing_skills': list(missing),
            'keyword_overlap': list(keyword_overlap),
            'match_score': match_score,
            'embedding_similarity': round(embedding_similarity, 4),
            'rationale': rationale,
            'education': parsed_resume.get('education'),
            'years_experience': parsed_resume.get('years_experience'),
            'profile_photo_url': application.get('profile_photo_url') or member.get('profile_photo_url'),
            'location': member.get('location') or ', '.join([value for value in [member.get('city'), member.get('state')] if value]),
            'source_rank': source_rank,
        }
        if not candidate['skill_overlap']:
            candidate['skill_overlap'] = list((parsed_resume.get('skills') or [])[:5])
        return CandidateArtifacts(
            candidate=candidate,
            parsed_resume=parsed_resume,
            resume_text=resume_text,
            embedding_similarity=embedding_similarity,
        )
