#!/usr/bin/env python3
"""Quick fix — register members with brand new emails that don't conflict with seeded data"""
import base64, json, random, time, uuid, requests

BASE = {
    'auth':      'http://localhost:8001',
    'member':    'http://localhost:8002',
    'apps':      'http://localhost:8005',
    'analytics': 'http://localhost:8007',
}

def post(svc, path, body=None, headers=None):
    try:
        r = requests.post(f"{BASE[svc]}{path}", json=body or {}, headers=headers or {}, timeout=15)
        return r.json()
    except Exception as e:
        print(f"  ERR: {e}")
        return {}

def get_token(email, pwd):
    r = post('auth', '/auth/login', {'email': email, 'password': pwd})
    return r.get('data', {}).get('access_token', '')

def get_mid(tok):
    try:
        p = tok.split('.')[1] + '=='
        return json.loads(base64.b64decode(p)).get('sub', '')
    except:
        return ''

def ah(t):
    return {'Authorization': f'Bearer {t}', 'Content-Type': 'application/json'}

# Use unique emails that won't conflict with seed_perf_data.py
# seed_perf_data uses member1@seed.example.com → member10000@seed.example.com
# We use demo1@linkedin.example.com etc.
MEMBERS = [
    ('demo1@linkedin.example.com',  'DemoPass#1!', 'Liam',     'Johnson',  'React Frontend Developer',  'New York, NY',      ['React','TypeScript','GraphQL']),
    ('demo2@linkedin.example.com',  'DemoPass#1!', 'Sophia',   'Williams', 'DevOps Engineer',           'Austin, TX',        ['AWS','Docker','Kubernetes']),
    ('demo3@linkedin.example.com',  'DemoPass#1!', 'Noah',     'Brown',    'Data Scientist',            'Seattle, WA',       ['Python','ML','SQL']),
    ('demo4@linkedin.example.com',  'DemoPass#1!', 'Emma',     'Garcia',   'Backend Engineer',          'Chicago, IL',       ['Java','Spring Boot','MySQL']),
    ('demo5@linkedin.example.com',  'DemoPass#1!', 'Mason',    'Miller',   'ML Engineer',               'San Francisco, CA', ['Python','PyTorch','MLflow']),
    ('demo6@linkedin.example.com',  'DemoPass#1!', 'Olivia',   'Davis',    'Full Stack Developer',      'Remote',            ['React','Node.js','PostgreSQL']),
    ('demo7@linkedin.example.com',  'DemoPass#1!', 'James',    'Wilson',   'Cloud Architect',           'Boston, MA',        ['AWS','GCP','Terraform']),
    ('demo8@linkedin.example.com',  'DemoPass#1!', 'Isabella', 'Moore',    'Security Engineer',         'Austin, TX',        ['Security','Python','SIEM']),
    ('demo9@linkedin.example.com',  'DemoPass#1!', 'Ethan',    'Taylor',   'iOS Developer',             'San Francisco, CA', ['Swift','iOS','SwiftUI']),
    ('demo10@linkedin.example.com', 'DemoPass#1!', 'Mia',      'Anderson', 'Android Developer',         'Remote',            ['Kotlin','Android','Firebase']),
    ('demo11@linkedin.example.com', 'DemoPass#1!', 'Lucas',    'Thomas',   'SRE',                       'Seattle, WA',       ['SRE','Kubernetes','Prometheus']),
    ('demo12@linkedin.example.com', 'DemoPass#1!', 'Charlotte','Lee',      'Data Engineer',             'New York, NY',      ['Spark','Kafka','Airflow']),
    ('demo13@linkedin.example.com', 'DemoPass#1!', 'Aiden',    'Harris',   'Platform Engineer',         'Chicago, IL',       ['Go','gRPC','Docker']),
    ('demo14@linkedin.example.com', 'DemoPass#1!', 'Amelia',   'Martin',   'QA Engineer',               'Remote',            ['Selenium','Python','Jest']),
    ('demo15@linkedin.example.com', 'DemoPass#1!', 'Logan',    'Thompson', 'Engineering Manager',       'San Francisco, CA', ['Leadership','Agile']),
]

REAL_JOB_IDS   = [f'job_{i:03d}' for i in range(1, 16)]
SEEDED_JOB_IDS = [f'job_seed_{i:05d}' for i in range(1, 51)]
ALL_JOBS       = REAL_JOB_IDS + SEEDED_JOB_IDS
SEEDED_MIDS    = [f'mem_seed_{i:05d}' for i in range(1, 201)]
CITIES         = ['San Francisco','New York','Austin','Seattle','Chicago','Boston','Remote','Denver']

print("Registering 15 demo members with fresh emails...")
member_tokens = []
member_ids    = []

for email, pwd, fn, ln, headline, loc, skills in MEMBERS:
    r = post('auth', '/auth/register', {
        'email': email, 'password': pwd,
        'user_type': 'member', 'first_name': fn, 'last_name': ln
    })
    tok = get_token(email, pwd)
    if not tok:
        print(f"  SKIP {email}")
        continue
    mid = get_mid(tok)
    post('member', '/members/create', {
        'first_name': fn, 'last_name': ln, 'email': email,
        'headline': headline, 'location_text': loc,
        'about_text': f'{headline} with strong technical background.',
        'skills_json': skills, 'resume_text': f'{fn} {ln} — {headline}. Skills: {", ".join(skills)}.',
        'current_title': headline, 'current_company': 'Various',
    }, ah(tok))
    member_tokens.append(tok)
    member_ids.append(mid)
    print(f"  ✓ {fn} {ln} ({email}) → {mid}")
    time.sleep(0.05)

print(f"\nSubmitting applications ({len(member_ids)} members → jobs)...")
app_count = 0
for tok, mid in zip(member_tokens, member_ids):
    MH = ah(tok)
    for jid in random.sample(ALL_JOBS, min(10, len(ALL_JOBS))):
        r = post('apps', '/applications/submit', {
            'job_id': jid, 'member_id': mid,
            'resume_ref': 'resume.pdf',
            'cover_letter': 'I am excited about this role and my skills are a strong match.',
        }, {**MH, 'Idempotency-Key': uuid.uuid4().hex})
        if r.get('success'):
            app_count += 1
    time.sleep(0.05)
print(f"✓ {app_count} applications submitted")

print("\nIngesting analytics events...")
rec = post('auth', '/auth/login', {'email':'recruiter@example.com','password':'RecruiterPass#1'})
rec_tok = rec.get('data',{}).get('access_token','')
AH = ah(rec_tok)
event_count = 0

for jid in REAL_JOB_IDS:
    for _ in range(random.randint(20,60)):
        mid = random.choice(SEEDED_MIDS + member_ids)
        post('analytics','/events/ingest',{
            'event_type':'job.viewed','actor_id':mid,
            'entity':{'entity_type':'job','entity_id':jid},
            'payload':{'job_id':jid,'location':random.choice(CITIES),'city':random.choice(CITIES)},
            'idempotency_key':uuid.uuid4().hex,
        }, AH)
        event_count += 1
    for _ in range(random.randint(5,20)):
        mid = random.choice(SEEDED_MIDS)
        post('analytics','/events/ingest',{
            'event_type':'job.saved','actor_id':mid,
            'entity':{'entity_type':'job','entity_id':jid},
            'payload':{'job_id':jid,'member_id':mid},
            'idempotency_key':uuid.uuid4().hex,
        }, AH)
        event_count += 1

for i in range(1, 101):
    jid = f'job_seed_{i:05d}'
    mid = random.choice(SEEDED_MIDS)
    for _ in range(random.randint(5,25)):
        post('analytics','/events/ingest',{
            'event_type':'job.viewed','actor_id':mid,
            'entity':{'entity_type':'job','entity_id':jid},
            'payload':{'job_id':jid,'location':random.choice(CITIES),'city':random.choice(CITIES)},
            'idempotency_key':uuid.uuid4().hex,
        }, AH)
        event_count += 1

print(f"✓ {event_count} analytics events ingested")

print(f"""
========================================
DONE!
  Members registered: {len(member_ids)}
  Applications:       {app_count}
  Events:             {event_count}

Login credentials:
  ava@example.com       / StrongPass#1
  demo1@linkedin.example.com / DemoPass#1!
  recruiter@example.com / RecruiterPass#1

Open: http://localhost:5173
========================================""")
