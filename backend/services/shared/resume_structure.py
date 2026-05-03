"""Heuristic extraction of About + structured Experience[] from plain resume text (PDF/TXT/DOCX).

This is intentionally lightweight (no LLM): it handles common US-style layouts with SUMMARY / EXPERIENCE
sections and lines like ``Title at Company`` plus date ranges and bullet lines."""
from __future__ import annotations

import json
import re
from typing import Any

_MONTH_NAMES = (
    'january',
    'february',
    'march',
    'april',
    'may',
    'june',
    'july',
    'august',
    'september',
    'october',
    'november',
    'december',
    'jan',
    'feb',
    'mar',
    'apr',
    'jun',
    'jul',
    'aug',
    'sep',
    'sept',
    'oct',
    'nov',
    'dec',
)

_SECTION_HEADERS = (
    (re.compile(r'^\s*(professional\s+)?summary\s*$', re.I), 'summary'),
    (re.compile(r'^\s*profile\s*$', re.I), 'summary'),
    (re.compile(r'^\s*objective\s*$', re.I), 'summary'),
    (re.compile(r'^\s*highlights?\s*$', re.I), 'summary'),
    (re.compile(r'^\s*(work\s+)?experience\s*$', re.I), 'experience'),
    (re.compile(r'^\s*employment(\s+history)?\s*$', re.I), 'experience'),
    (re.compile(r'^\s*professional\s+experience\s*$', re.I), 'experience'),
    (re.compile(r'^\s*relevant\s+experience\s*$', re.I), 'experience'),
    (re.compile(r'^\s*education\s*$', re.I), 'education'),
    (re.compile(r'^\s*academic\s+background\s*$', re.I), 'education'),
    (re.compile(r'^\s*skills?\s*$', re.I), 'skills'),
    (re.compile(r'^\s*technical\s+skills?\s*$', re.I), 'skills'),
    (re.compile(r'^\s*projects?\s*$', re.I), 'projects'),
    (re.compile(r'^\s*certifications?\s*$', re.I), 'certs'),
)


def _norm_lines(text: str) -> list[str]:
    t = text.replace('\x00', ' ')
    t = re.sub(r'\r\n?', '\n', t)
    return [ln.rstrip() for ln in t.split('\n')]


def _is_contact_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 6:
        return False
    if re.search(r'[\d()\-]{10,}', s) and ('@' in s or 'linkedin' in s.lower() or 'github' in s.lower()):
        return True
    if s.count('@') >= 1 and len(s) < 180:
        return True
    if re.search(r'https?://', s) and len(s) < 200:
        return True
    return False


def _blank_experience() -> dict[str, Any]:
    return {
        'title': '',
        'company': '',
        'location': '',
        'employment_type': '',
        'start_month': '',
        'start_year': '',
        'end_month': '',
        'end_year': '',
        'is_current': False,
        'description': '',
    }


def _split_title_company(line: str) -> tuple[str, str]:
    s = line.strip()
    if not s or len(s) > 140:
        return '', ''
    low = s.lower()
    # "Title at Company" (avoid "look at data" — require short left side)
    m = re.match(r'^(.{2,72}?)\s+at\s+(.{2,72})$', s, re.I)
    if m and len(m.group(1).split()) <= 10:
        return m.group(1).strip(), m.group(2).strip()
    # "Title | Company" or "Title — Company"
    if '|' in s and s.count('|') == 1:
        a, b = [x.strip() for x in s.split('|', 1)]
        if 2 <= len(a) <= 80 and 2 <= len(b) <= 80:
            return a, b
    if '—' in s or ' – ' in s:
        sep = '—' if '—' in s else ' – '
        parts = [x.strip() for x in s.split(sep, 1)]
        if len(parts) == 2 and all(2 <= len(x) <= 80 for x in parts):
            # Heuristic: shorter fragment is often title
            a, b = parts
            if len(a) <= len(b):
                return a, b
            return b, a
    # "Company – Title" (dash surrounded by spaces)
    m2 = re.match(r'^(.{2,60})\s+[-–]\s+(.{2,60})$', s)
    if m2:
        left, right = m2.group(1).strip(), m2.group(2).strip()
        if any(w in low for w in ('inc', 'llc', 'ltd', 'corp', 'company', 'technologies', 'labs', 'solutions')):
            return right, left
    return '', ''


def _month_to_num(name: str) -> str:
    n = (name or '').lower()[:3]
    mp = {
        'jan': '1',
        'feb': '2',
        'mar': '3',
        'apr': '4',
        'may': '5',
        'jun': '6',
        'jul': '7',
        'aug': '8',
        'sep': '9',
        'oct': '10',
        'nov': '11',
        'dec': '12',
    }
    return mp.get(n, '')


def _parse_date_range(line: str) -> tuple[str, str, str, str, bool]:
    """Return (start_month, start_year, end_month, end_year, is_current) from one line."""
    s = line.strip()
    # Mon YYYY – Mon YYYY / Present
    m = re.search(
        r'(?i)\b(' + '|'.join(_MONTH_NAMES) + r')[a-z]*\.?\s+(\d{4})\s*[-–—]\s*(?:(' + '|'.join(_MONTH_NAMES) + r')[a-z]*\.?\s+)?(\d{4}|present|current)\b',
        s,
    )
    if m:
        sm = _month_to_num(m.group(1))
        sy = m.group(2)
        em = _month_to_num(m.group(3)) if m.group(3) else ''
        ey_raw = (m.group(4) or '').lower()
        if ey_raw in ('present', 'current'):
            return sm, sy, '', '', True
        return sm, sy, em, m.group(4), False
    # YYYY – YYYY | Present
    m2 = re.search(r'\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|present|current)\b', s, re.I)
    if m2:
        sy = m2.group(1)
        end = m2.group(2).lower()
        if end in ('present', 'current'):
            return '', sy, '', '', True
        return '', sy, '', m2.group(2), False
    m3 = re.search(r'\b(20\d{2}|19\d{2})\b', s)
    if m3:
        return '', m3.group(1), '', '', False
    return '', '', '', '', False


def _label_sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map section key -> (start_line_inclusive, end_line_exclusive)."""
    hits: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        for pat, key in _SECTION_HEADERS:
            if pat.match(ln.strip()):
                hits.append((i, key))
                break
    if not hits:
        return {}
    hits.sort(key=lambda x: x[0])
    spans: dict[str, tuple[int, int]] = {}
    for idx, (start, key) in enumerate(hits):
        end = hits[idx + 1][0] if idx + 1 < len(hits) else len(lines)
        prev = spans.get(key)
        if prev is None or (end - start) > (prev[1] - prev[0]):
            spans[key] = (start, end)
    return spans


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    chunk = lines[start:end]
    return '\n'.join(chunk).strip()


def _extract_summary(lines: list[str], spans: dict[str, tuple[int, int]]) -> str:
    if 'summary' in spans:
        a, b = spans['summary']
        body_start = a + 1
        body_end = b
        for key in ('experience', 'education', 'skills', 'projects', 'certs'):
            if key in spans and spans[key][0] < body_end:
                body_end = min(body_end, spans[key][0])
        raw_lines = lines[body_start:body_end]
        capped: list[str] = []
        for ln in raw_lines:
            s = ln.strip()
            if not s:
                capped.append(ln)
                if len(capped) > 14 and len('\n'.join(capped).strip()) > 200:
                    break
                continue
            t, c = _split_title_company(s)
            if t and c and len(capped) >= 2:
                break
            capped.append(ln)
        text = '\n'.join(capped).strip()
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text[:6000]
    # No SUMMARY header: skip contact lines then take first substantial paragraph
    i = 0
    while i < len(lines) and i < 18 and (_is_contact_line(lines[i]) or len(lines[i].strip()) < 4):
        i += 1
    buf: list[str] = []
    while i < len(lines) and len(buf) < 25:
        ln = lines[i].strip()
        if not ln:
            if len('\n'.join(buf)) > 120:
                break
            i += 1
            continue
        for pat, key in _SECTION_HEADERS:
            if pat.match(ln):
                return re.sub(r'\n{3,}', '\n\n', '\n'.join(buf)).strip()[:6000]
        buf.append(lines[i].rstrip())
        i += 1
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(buf)).strip()[:6000]


def _is_bullet_line(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r'^[\u2022\u2023\u25CF\-\*•]\s*', s) or re.match(r'^\d+[\).\]]\s+', s))


def _strip_bullet(line: str) -> str:
    s = line.strip()
    s = re.sub(r'^[\u2022\u2023\u25CF\-\*•]\s*', '', s)
    s = re.sub(r'^\d+[\).\]]\s+', '', s)
    return s.strip()


def _split_experience_blocks(exp_text: str) -> list[str]:
    if not exp_text.strip():
        return []
    parts = [p.strip() for p in re.split(r'\n{2,}', exp_text) if p.strip()]
    if len(parts) >= 2:
        return parts
    # One blob: split when a new non-bullet line matches "Role at Company"
    lines = exp_text.split('\n')
    chunks: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        t, c = _split_title_company(s) if not _is_bullet_line(s) else ('', '')
        if t and c and cur and sum(1 for x in cur if x.strip()) >= 2:
            chunks.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        chunks.append(cur)
    out = ['\n'.join(b).strip() for b in chunks if b]
    return out if out else [exp_text.strip()]


def _parse_job_block(block: str) -> dict[str, Any]:
    exp = _blank_experience()
    lines = [ln.rstrip() for ln in block.split('\n') if ln.strip()]
    if not lines:
        return exp

    bullets: list[str] = []
    meta: list[str] = []
    for ln in lines:
        if _is_bullet_line(ln):
            bullets.append(_strip_bullet(ln))
        else:
            meta.append(ln.strip())

    if not meta:
        exp['description'] = '\n'.join(bullets)[:12000]
        return exp

    date_idx: int | None = None
    for i, ln in enumerate(meta[:6]):
        if re.search(r'(?:19|20)\d{2}|present|current|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}', ln, re.I):
            date_idx = i
            break

    sm, sy, em, ey, ic = ('', '', '', '', False)
    if date_idx is not None:
        sm, sy, em, ey, ic = _parse_date_range(meta[date_idx])
        exp['start_month'], exp['start_year'], exp['end_month'], exp['end_year'] = sm, sy, em, ey
        exp['is_current'] = ic

    title, company = _split_title_company(meta[0])
    if title or company:
        exp['title'] = title or meta[0][:120]
        exp['company'] = company
    else:
        exp['title'] = meta[0][:120]
        if len(meta) >= 2 and date_idx != 1:
            exp['company'] = meta[1][:120]

    skip = {meta[0]}
    if len(meta) > 1 and exp.get('company') == meta[1]:
        skip.add(meta[1])
    if date_idx is not None:
        skip.add(meta[date_idx])

    loc_hint = ''
    for ln in meta[1:4]:
        if ln in skip or _is_bullet_line(ln):
            continue
        if re.search(r'(?:19|20)\d{2}|present|current', ln, re.I):
            continue
        if len(ln) < 120 and ',' in ln and not _split_title_company(ln)[0]:
            loc_hint = ln
            skip.add(ln)
            break

    if loc_hint:
        exp['location'] = loc_hint[:160]

    desc_parts = bullets[:] if bullets else [ln for ln in meta if ln not in skip]
    desc = '\n'.join(desc_parts).strip()
    if not desc:
        skip_idx = {0}
        if date_idx is not None:
            skip_idx.add(date_idx)
        desc = '\n'.join(meta[i] for i in range(len(meta)) if i not in skip_idx)
    exp['description'] = re.sub(r'\n{3,}', '\n\n', desc)[:12000]
    return exp


def structured_profile_from_resume_text(resume_text: str) -> dict[str, Any]:
    """Return ``{about_summary, experience: [...]}`` aligned with the profile UI."""
    raw = (resume_text or '').strip()
    if not raw:
        return {'about_summary': '', 'experience': []}
    lines = _norm_lines(raw)
    spans = _label_sections(lines)

    about = _extract_summary(lines, spans)

    exp_text = ''
    if 'experience' in spans:
        a, b = spans['experience']
        body_start = a + 1
        body_end = b
        for stop in ('education', 'skills', 'projects', 'certs'):
            if stop in spans and spans[stop][0] < body_end:
                body_end = min(body_end, spans[stop][0])
        exp_text = _slice_lines(lines, body_start, body_end)
    else:
        start = 0
        if 'summary' in spans:
            start = spans['summary'][1]
        if 'education' in spans:
            exp_text = _slice_lines(lines, start, spans['education'][0])
        else:
            exp_text = _slice_lines(lines, start, len(lines))

    if about:
        ap = about.strip()
        et = exp_text.strip()
        if ap and et.lower().startswith(ap[: min(220, len(ap))].lower()):
            exp_text = et[len(ap) :].lstrip('\n')
        elif ap and ap in et:
            exp_text = et.replace(ap, '', 1).strip()

    blocks = _split_experience_blocks(exp_text)
    experiences: list[dict[str, Any]] = []
    for blk in blocks[:6]:
        job = _parse_job_block(blk)
        if any(str(job.get(k) or '').strip() for k in ('title', 'company', 'description')):
            experiences.append(job)

    if not experiences and exp_text.strip():
        # Last resort: one job with description only (trim huge contact blob)
        et = exp_text.strip()
        if len(et) > 800:
            et = et[:8000]
        experiences.append({**_blank_experience(), 'description': et})

    return {'about_summary': about.strip()[:8000], 'experience': experiences}


def merge_skills_from_resume(resume_text: str, existing_skills: list[str] | None, limit: int = 24) -> list[str]:
    """Lightweight skill token merge for skills_json (optional)."""
    from services.shared.resume_parser import extract_keywords  # local import avoid cycles

    text = resume_text or ''
    kws = extract_keywords(text, limit=limit)
    seen: set[str] = set()
    out: list[str] = []
    for s in (existing_skills or []) + kws:
        t = str(s).strip()
        if not t:
            continue
        low = t.lower()
        if low not in seen:
            seen.add(low)
            out.append(t)
        if len(out) >= limit:
            break
    return out
