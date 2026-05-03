from __future__ import annotations

import json
import os
from typing import Any

import httpx

from services.shared.observability import get_logger, log_event


class OpenRouterClient:
    def __init__(self, model: str | None = None, public_base_url: str | None = None):
        self.logger = get_logger('ai_openrouter')
        self.model = model or os.environ.get('OPENROUTER_MODEL', 'google/gemini-2.5-flash')
        self.public_base_url = public_base_url or os.environ.get('PUBLIC_BASE_URL', '')
        self._api_key = self._read_api_key()

    def _read_api_key(self) -> str:
        raw = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPEN_ROUTER_API_KEY') or ''
        return str(raw).strip()

    def refresh(self) -> None:
        self._api_key = self._read_api_key()
        self.model = os.environ.get('OPENROUTER_MODEL', self.model)
        self.public_base_url = os.environ.get('PUBLIC_BASE_URL', self.public_base_url)

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return 'openrouter' if self.enabled else 'embedding+rules'

    async def generate(self, job: dict, shortlist: list[dict], task_type: str, *, trace_id: str) -> dict[str, Any] | None:
        self.refresh()
        if not self.enabled:
            return None
        prompt = {
            'job': {
                'job_id': job.get('job_id'),
                'title': job.get('title'),
                'description': job.get('description') or job.get('description_text'),
                'skills_required': job.get('skills_required') or job.get('skills') or [],
                'location': job.get('location') or ', '.join([value for value in [job.get('city'), job.get('state')] if value]),
                'seniority_level': job.get('seniority_level'),
            },
            'task_type': task_type,
            'candidates': [
                {
                    'candidate_id': candidate.get('candidate_id'),
                    'name': candidate.get('name'),
                    'headline': candidate.get('headline'),
                    'resume_text': candidate.get('resume_text', ''),
                    'parsed_resume': candidate.get('resume_parsed', {}),
                    'skill_overlap': list(candidate.get('skill_overlap') or []),
                    'missing_skills': list(candidate.get('missing_skills') or []),
                    'baseline_score': candidate.get('match_score'),
                    'embedding_similarity': candidate.get('embedding_similarity'),
                    'rationale': candidate.get('rationale'),
                }
                for candidate in shortlist[:8]
            ],
        }
        system = (
            'You are a recruiter copilot. Return strict JSON with keys shortlist and outreach_drafts. '
            'shortlist must be an array of objects with candidate_id, first_name, last_name, headline, '
            'skill_overlap, missing_skills, match_score, rationale. '
            'Use the embedding/rules baseline already provided, and improve narrative quality without inventing facts. '
            'outreach_drafts must be an array of objects with candidate_id, name, message, draft. '
            'Keep tone professional and concise.'
        )
        log_event(self.logger, 'openrouter_request_start', trace_id=trace_id, model=self.model, candidates=len(shortlist), task_type=task_type)
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self._api_key}',
                    'Content-Type': 'application/json',
                    **({'HTTP-Referer': self.public_base_url} if self.public_base_url else {}),
                    'X-Title': 'LinkedIn Recruiter Copilot',
                },
                json={
                    'model': self.model,
                    'response_format': {'type': 'json_object'},
                    'messages': [
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': json.dumps(prompt)},
                    ],
                    'temperature': 0.2,
                },
            )
            log_event(self.logger, 'openrouter_response_received', trace_id=trace_id, status_code=response.status_code)
            response.raise_for_status()
            data = response.json()
            content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '{}')
            if isinstance(content, list):
                content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
            parsed = json.loads(content)
            result = parsed if isinstance(parsed, dict) else None
            log_event(self.logger, 'openrouter_request_success', trace_id=trace_id, has_shortlist=bool((result or {}).get('shortlist')))
            return result

    async def coach_generate(self, member: dict, job: dict, missing_skills: list[str], *, trace_id: str) -> dict[str, Any] | None:
        """Career Coach prompt — returns {suggested_headline, resume_tips} or None.

        Separate from generate() because the coach is a synchronous one-shot call
        from the member-facing flow; 30s timeout is deliberate (see Q4 decision).
        """
        self.refresh()
        if not self.enabled:
            return None
        prompt = {
            'member': {
                'first_name': member.get('first_name'),
                'last_name': member.get('last_name'),
                'headline': member.get('headline'),
                'skills': member.get('skills_json') or member.get('skills') or [],
                'current_title': member.get('current_title'),
                'current_company': member.get('current_company'),
                'about': member.get('about_text') or member.get('about'),
                'location': member.get('location') or member.get('location_text'),
            },
            'target_job': {
                'title': job.get('title'),
                'description': job.get('description') or job.get('description_text'),
                'seniority_level': job.get('seniority_level'),
                'skills_required': job.get('skills_required') or job.get('skills') or [],
            },
            'missing_skills': list(missing_skills or []),
        }
        system = (
            'You are a career coach for a member applying to a specific job. '
            'Return strict JSON with keys suggested_headline (string, max 100 chars) '
            'and resume_tips (array of 2-4 short, actionable strings). '
            'Base suggestions only on the member profile and job data provided; do not invent facts. '
            'Do NOT include fields other than suggested_headline and resume_tips.'
        )
        log_event(self.logger, 'openrouter_coach_start', trace_id=trace_id, model=self.model, missing_skill_count=len(prompt['missing_skills']))
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self._api_key}',
                    'Content-Type': 'application/json',
                    **({'HTTP-Referer': self.public_base_url} if self.public_base_url else {}),
                    'X-Title': 'LinkedIn Career Coach',
                },
                json={
                    'model': self.model,
                    'response_format': {'type': 'json_object'},
                    'messages': [
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': json.dumps(prompt)},
                    ],
                    'temperature': 0.4,
                },
            )
            log_event(self.logger, 'openrouter_coach_response', trace_id=trace_id, status_code=response.status_code)
            response.raise_for_status()
            data = response.json()
            content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '{}')
            if isinstance(content, list):
                content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
