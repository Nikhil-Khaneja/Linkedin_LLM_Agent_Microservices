#!/usr/bin/env python3
"""
Complete seed script — LinkedIn Simulation (Person 4)
Seeds members, jobs, applications, analytics events.
Usage: python3 scripts/seed_full_data.py
"""
import json, random, time, uuid, requests

BASE = {
    'auth':      'http://localhost:8001',
    'member':    'http://localhost:8002',
    'recruiter': 'http://localhost:8003',
    'jobs':      'http://localhost:8004',
    'apps':      'http://localhost:8005',
    'analytics': 'http://localhost:8007',
}

def post(svc, path, body=None, headers=None):
    try:
        r = requests.post(f"{BASE[svc]}{path}", json=body or {}, headers=headers or {}, timeout=15)
        return r.json()
    except Exception as e:
        print(f"  ERR {svc}{path}: {e}")
        return {}

def get_token(email, password):
    r = post('auth', '/auth/login', {'email': email, 'password': password})
    return r.get('data', {}).get('access_token', '')

def ah(t):
    return {'Authorization': f'Bearer {t}', 'Content-Type': 'application/json'}

# ── Data pools ────────────────────────────────────────────────────────────────
MEMBERS = [
    ('ava@example.com',       'StrongPass#1', 'Ava',     'Shah',     'Senior Python Engineer',        'San Francisco, CA', ['Python','FastAPI','Kafka','Redis']),
    ('member1@seed.example.com', 'SeedPass#1', 'Liam',   'Johnson',  'React Frontend Developer',      'New York, NY',      ['React','TypeScript','GraphQL','CSS']),
    ('member2@seed.example.com', 'SeedPass#1', 'Sophia', 'Williams', 'DevOps Engineer',               'Austin, TX',        ['AWS','Docker','Kubernetes','Terraform']),
    ('member3@seed.example.com', 'SeedPass#1', 'Noah',   'Brown',    'Data Scientist',                'Seattle, WA',       ['Python','ML','SQL','TensorFlow']),
    ('member4@seed.example.com', 'SeedPass#1', 'Emma',   'Garcia',   'Backend Engineer',              'Chicago, IL',       ['Java','Spring Boot','MySQL','Redis']),
    ('member5@seed.example.com', 'SeedPass#1', 'Mason',  'Miller',   'ML Engineer',                   'San Francisco, CA', ['Python','PyTorch','MLflow','Docker']),
    ('member6@seed.example.com', 'SeedPass#1', 'Olivia', 'Davis',    'Full Stack Developer',          'Remote',            ['React','Node.js','PostgreSQL','AWS']),
    ('member7@seed.example.com', 'SeedPass#1', 'James',  'Wilson',   'Cloud Architect',               'Boston, MA',        ['AWS','GCP','Terraform','Kubernetes']),
    ('member8@seed.example.com', 'SeedPass#1', 'Isabella','Moore',   'Security Engineer',             'Austin, TX',        ['Security','Python','SIEM','Splunk']),
    ('member9@seed.example.com', 'SeedPass#1', 'Ethan',  'Taylor',   'iOS Developer',                 'San Francisco, CA', ['Swift','iOS','SwiftUI','Firebase']),
    ('member10@seed.example.com','SeedPass#1', 'Mia',    'Anderson', 'Android Developer',             'Remote',            ['Kotlin','Android','Firebase','Java']),
    ('member11@seed.example.com','SeedPass#1', 'Lucas',  'Thomas',   'Site Reliability Engineer',     'Seattle, WA',       ['SRE','Kubernetes','Prometheus','Go']),
    ('member12@seed.example.com','SeedPass#1', 'Charlotte','Lee',    'Data Engineer',                 'New York, NY',      ['Spark','Kafka','Airflow','Python']),
    ('member13@seed.example.com','SeedPass#1', 'Aiden',  'Harris',   'Platform Engineer',             'Chicago, IL',       ['Go','gRPC','Docker','Kafka']),
    ('member14@seed.example.com','SeedPass#1', 'Amelia', 'Martin',   'QA Engineer',                   'Remote',            ['Selenium','Python','Jest','Testing']),
    ('member15@seed.example.com','SeedPass#1', 'Logan',  'Thompson', 'Engineering Manager',           'San Francisco, CA', ['Leadership','Agile','System Design']),
    ('member16@seed.example.com','SeedPass#1', 'Harper', 'White',    'Product Manager',               'New York, NY',      ['Product Strategy','Agile','Analytics']),
    ('member17@seed.example.com','SeedPass#1', 'Jackson','Lopez',    'Solutions Architect',           'Austin, TX',        ['AWS','Architecture','Python','APIs']),
    ('member18@seed.example.com','SeedPass#1', 'Evelyn', 'Patel',    'Frontend Engineer',             'Remote',            ['Vue.js','React','CSS','JavaScript']),
    ('member19@seed.example.com','SeedPass#1', 'Priya',  'Kumar',    'Backend Python Engineer',       'Seattle, WA',       ['Python','FastAPI','PostgreSQL','Redis']),
]

RESUME_TEXTS = [
    "Senior software engineer with 6 years in Python and distributed systems. Built Kafka-based event pipelines processing 2M+ events/day. Expert in FastAPI, Redis, and Docker.",
    "Frontend developer with 4 years in React and TypeScript. Built high-performance UIs for e-commerce platforms with 500K daily users. Strong in accessibility and design systems.",
    "DevOps engineer with AWS and Kubernetes expertise. Reduced deployment time by 70% through CI/CD automation. Expert in Terraform and Prometheus/Grafana monitoring.",
    "Data scientist with 5 years in ML model development. Published NLP research. Proficient in Python, TensorFlow, SQL for large-scale data analysis.",
    "Backend engineer focused on scalable microservices. Experience with Java Spring Boot and Go. Led migration from monolith to microservices for fintech startup.",
    "ML engineer specializing in recommendation systems and NLP. Deployed models to production using MLflow and Kubernetes. Python and PyTorch specialist.",
    "Full stack developer with React and Node.js expertise. Built 3 SaaS products from scratch. Experience with MongoDB, Redis, and AWS pipelines.",
    "AWS Solutions Architect certified cloud architect. Designed multi-region HA architectures. Expert in cost optimization and security best practices.",
    "Security engineer specializing in AppSec and penetration testing. OSCP certified. Experience with SIEM tools, threat modeling, and secure SDLC.",
    "iOS developer with 6 years building consumer apps. Multiple App Store featured apps with 100K+ downloads. Expert in Swift and SwiftUI.",
    "Android developer with 5 years building consumer apps on Kotlin. Led Android team at Series B startup. Expert in Firebase and REST API integration.",
    "SRE with focus on reliability and performance. Reduced MTTR by 60% through improved observability. Expert in Kubernetes and Prometheus.",
    "Data engineer building large-scale pipelines. Experience with Spark, Kafka, and Airflow processing 10TB+ daily. Strong Python and SQL skills.",
    "Platform engineer building internal developer tools. Experience with Go, gRPC, and Docker. Improved developer productivity by 40%.",
    "QA engineer with automation expertise. Built test frameworks reducing QA time by 50%. Expert in Selenium, Jest, and Python testing.",
    "Engineering manager leading teams of 8-12 engineers. Delivered 3 major platform launches on time. Strong in Agile and technical roadmapping.",
    "Product manager with 7 years experience. Grew DAU by 3x through data-driven product decisions. Expert in Agile and user research.",
    "Solutions architect with AWS expertise. Designed architectures for Fortune 500 clients. Strong in system design and API strategy.",
    "Frontend engineer with Vue.js and React expertise. Built component libraries used by 20+ teams. Strong focus on performance and UX.",
    "Backend Python engineer with FastAPI and PostgreSQL expertise. Built high-throughput APIs serving 1M+ requests/day.",
]

JOBS = [
    ('job_001','Senior Python Engineer','Build scalable backend systems using Python, FastAPI, and Kafka. You will design high-throughput APIs and data pipelines.','senior','full_time','San Francisco, CA','hybrid',['Python','FastAPI','Kafka','Redis','Docker']),
    ('job_002','React Frontend Developer','Build modern UIs with React and TypeScript. Work closely with design to create pixel-perfect experiences.','mid','full_time','New York, NY','remote',['React','TypeScript','GraphQL','CSS']),
    ('job_003','DevOps Engineer','Own our AWS infrastructure and CI/CD pipelines. Drive automation and reliability across all services.','senior','full_time','Austin, TX','onsite',['AWS','Docker','Kubernetes','Terraform']),
    ('job_004','Data Scientist','Build and ship ML models that drive business decisions. Work with petabytes of user data.','mid','full_time','Seattle, WA','hybrid',['Python','ML','SQL','TensorFlow']),
    ('job_005','Backend Engineer','Design REST APIs and microservices powering our core platform at scale.','mid','full_time','San Francisco, CA','remote',['Python','MySQL','Redis','Docker']),
    ('job_006','Machine Learning Engineer','Deploy ML models to production. Own the ML platform and model serving infrastructure.','senior','full_time','San Francisco, CA','hybrid',['Python','TensorFlow','MLOps','Kubernetes']),
    ('job_007','Full Stack Developer','Build end-to-end features across React frontend and Node.js backend.','mid','full_time','Chicago, IL','remote',['React','Node.js','PostgreSQL','AWS']),
    ('job_008','Cloud Architect','Design multi-region cloud infrastructure on AWS and GCP. Drive cloud cost optimization.','senior','full_time','Remote','remote',['AWS','GCP','Terraform','Architecture']),
    ('job_009','Product Manager','Lead product strategy and roadmap for our core hiring platform.','senior','full_time','New York, NY','hybrid',['Product Strategy','Agile','Analytics','Roadmapping']),
    ('job_010','Security Engineer','Build and maintain security infrastructure. Lead AppSec program and penetration testing.','senior','full_time','Austin, TX','onsite',['Security','Python','SIEM','Penetration Testing']),
    ('job_011','iOS Developer','Ship consumer iOS apps used by millions. Own the iOS platform and design system.','mid','full_time','San Francisco, CA','hybrid',['Swift','iOS','SwiftUI','Firebase']),
    ('job_012','Android Developer','Build and maintain our Android app. Drive performance and quality improvements.','mid','full_time','Remote','remote',['Kotlin','Android','Firebase','Java']),
    ('job_013','Site Reliability Engineer','Ensure 99.99% uptime for our production systems. Build world-class observability.','senior','full_time','Seattle, WA','hybrid',['SRE','Kubernetes','Prometheus','Go']),
    ('job_014','Data Engineer','Build real-time data pipelines processing billions of events per day.','mid','full_time','Boston, MA','hybrid',['Spark','Kafka','Airflow','Python']),
    ('job_015','Engineering Manager','Lead and grow a high-performing team of 10 engineers on our core platform.','senior','full_time','San Francisco, CA','hybrid',['Leadership','Agile','System Design','Mentoring']),
]

def main():
    print("=" * 60)
    print("FULL SEED SCRIPT — LinkedIn Simulation")
    print("=" * 60)

    # ── Step 1: Recruiter ────────────────────────────────────────────────────
    print("\n[1/5] Setting up recruiter...")
    post('auth', '/auth/register', {
        'email':'recruiter@example.com','password':'RecruiterPass#1',
        'user_type':'recruiter','first_name':'Morgan','last_name':'Lee',
        'company_name':'Northstar Labs'
    })
    rec_tok = get_token('recruiter@example.com','RecruiterPass#1')
    RH = ah(rec_tok)
    post('recruiter','/recruiters/create',{
        'name':'Morgan Lee','email':'recruiter@example.com',
        'company_name':'Northstar Labs','company_industry':'Software',
        'company_size':'medium','access_level':'admin'
    }, RH)
    print("  ✓ Recruiter ready (Morgan Lee @ Northstar Labs)")

    # ── Step 2: Members ──────────────────────────────────────────────────────
    print(f"\n[2/5] Creating {len(MEMBERS)} members...")
    member_tokens = []
    member_ids    = []
    for i,(email,pwd,fn,ln,headline,loc,skills) in enumerate(MEMBERS):
        post('auth','/auth/register',{
            'email':email,'password':pwd,
            'user_type':'member','first_name':fn,'last_name':ln
        })
        tok = get_token(email,pwd)
        if not tok:
            print(f"  SKIP {email} — login failed")
            continue
        r = post('member','/members/create',{
            'first_name':fn,'last_name':ln,'email':email,
            'headline':headline,'location_text':loc,
            'about_text':RESUME_TEXTS[i % len(RESUME_TEXTS)],
            'skills_json':skills,
            'resume_text':RESUME_TEXTS[i % len(RESUME_TEXTS)],
            'current_title':headline,'current_company':'Various',
        }, ah(tok))
        mid = (r.get('data') or {}).get('member_id')
        if mid:
            member_ids.append(mid)
            member_tokens.append(tok)
            print(f"  ✓ {fn} {ln} ({email}) → {mid}")
        else:
            print(f"  WARN {email}: {r}")
        time.sleep(0.05)
    print(f"  Total: {len(member_ids)} members created")

    # ── Step 3: Jobs (SQL file) ──────────────────────────────────────────────
    print(f"\n[3/5] Writing {len(JOBS)} jobs to /tmp/seed_jobs_full.sql...")
    sql = ["USE linkedin_sim;"]
    for jid,title,desc,seniority,emp_type,loc,work_mode,skills in JOBS:
        pj = json.dumps({
            'job_id':jid,'company_id':'cmp_1b389841','recruiter_id':'rec_120',
            'title':title,'description_text':desc,'seniority_level':seniority,
            'employment_type':emp_type,'location_text':loc,'location':loc,
            'work_mode':work_mode,'status':'open','version':1,
            'skills_required':skills,'company_name':'Northstar Labs',
        }).replace("'","\\'")
        sql.append(
            f"INSERT IGNORE INTO jobs (job_id,company_id,recruiter_id,title,"
            f"description_text,seniority_level,employment_type,location_text,"
            f"work_mode,status,version,payload_json) VALUES "
            f"('{jid}','cmp_1b389841','rec_120','{title}','{desc}',"
            f"'{seniority}','{emp_type}','{loc}','{work_mode}',"
            f"'open',1,'{pj}');"
        )
    with open('/tmp/seed_jobs_full.sql','w') as f:
        f.write('\n'.join(sql))
    print("  ✓ /tmp/seed_jobs_full.sql written")
    print("  → Now run:")
    print("    docker compose cp /tmp/seed_jobs_full.sql mysql:/tmp/")
    print("    docker compose exec mysql mysql -uroot -proot linkedin_sim -e \"source /tmp/seed_jobs_full.sql\"")

    job_ids = [j[0] for j in JOBS]

    # ── Step 4: Applications ─────────────────────────────────────────────────
    print(f"\n[4/5] Submitting applications...")
    app_count = 0
    for i,(tok,mid) in enumerate(zip(member_tokens, member_ids)):
        # Each member applies to 4-6 random jobs
        num = random.randint(4,6)
        apply_to = random.sample(job_ids, min(num, len(job_ids)))
        MH = ah(tok)
        for jid in apply_to:
            idem = uuid.uuid4().hex
            r = post('apps','/applications/submit',{
                'job_id':jid,'member_id':mid,
                'resume_ref':'resume.pdf',
                'cover_letter':'I am excited about this opportunity and believe my skills are a strong match for this role.',
            },{**MH,'Idempotency-Key':idem})
            if r.get('success'):
                app_count += 1
        time.sleep(0.1)
    print(f"  ✓ {app_count} applications submitted")

    # ── Step 5: Analytics events ─────────────────────────────────────────────
    print("\n[5/5] Ingesting analytics events...")
    AH = ah(rec_tok)
    event_count = 0
    cities = ['San Francisco','New York','Austin','Seattle','Chicago','Boston','Remote']

    for jid in job_ids:
        # job.viewed events (10-40 per job)
        for _ in range(random.randint(10,40)):
            mid = random.choice(member_ids) if member_ids else 'anon'
            city = random.choice(cities)
            post('analytics','/events/ingest',{
                'event_type':'job.viewed',
                'actor_id':mid,
                'entity':{'entity_type':'job','entity_id':jid},
                'payload':{'job_id':jid,'location':city,'city':city},
                'idempotency_key':uuid.uuid4().hex,
            }, AH)
            event_count += 1

        # job.saved events (3-15 per job)
        for _ in range(random.randint(3,15)):
            mid = random.choice(member_ids) if member_ids else 'anon'
            post('analytics','/events/ingest',{
                'event_type':'job.saved',
                'actor_id':mid,
                'entity':{'entity_type':'job','entity_id':jid},
                'payload':{'job_id':jid,'member_id':mid},
                'idempotency_key':uuid.uuid4().hex,
            }, AH)
            event_count += 1

    # profile.viewed events for members
    for mid in member_ids[:10]:
        for _ in range(random.randint(5,20)):
            viewer = random.choice(member_ids)
            post('analytics','/events/ingest',{
                'event_type':'profile.viewed',
                'actor_id':viewer,
                'entity':{'entity_type':'member','entity_id':mid},
                'payload':{'member_id':mid,'viewer_id':viewer},
                'idempotency_key':uuid.uuid4().hex,
            }, AH)
            event_count += 1

    print(f"  ✓ {event_count} analytics events ingested")

    print("\n" + "=" * 60)
    print("SEED COMPLETE!")
    print("=" * 60)
    print(f"  Members:      {len(member_ids)}")
    print(f"  Jobs:         {len(job_ids)} (run SQL file above if not visible)")
    print(f"  Applications: {app_count}")
    print(f"  Events:       {event_count}")
    print("\nLogin credentials:")
    print("  Member:    ava@example.com / StrongPass#1")
    print("  Recruiter: recruiter@example.com / RecruiterPass#1")
    print("\nOpen: http://localhost:5173")

if __name__ == '__main__':
    main()
