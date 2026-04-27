"""
Owner 2 — Member Profile Service — Test Suite
Run: pytest tests/test_members.py -v
Make sure full project is running: docker compose up -d
"""
import pytest
import requests

BASE = "http://localhost:3002"

def get_token():
    r = requests.post("http://localhost:3001/auth/login", json={
        "email": "ava.shah@example.com",
        "password": "StrongPass#1"
    })
    return r.json()["data"]["access_token"]

@pytest.fixture
def token():
    return get_token()

@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"
    print("✅ Health check passed")

def test_get_member(headers):
    r = requests.post(f"{BASE}/members/get", headers=headers, json={})
    assert r.status_code == 200
    assert r.json()["success"] == True
    print("✅ Get member passed")

def test_get_member_cache(headers):
    r1 = requests.post(f"{BASE}/members/get", headers=headers, json={})
    r2 = requests.post(f"{BASE}/members/get", headers=headers, json={})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("meta", {}).get("cache") == "hit"
    print("✅ Redis cache hit passed")

def test_update_member(headers):
    r = requests.post(f"{BASE}/members/update", headers=headers, json={
        "headline": "Senior Engineer | Updated via pytest"
    })
    assert r.status_code == 200
    assert r.json()["success"] == True
    print("✅ Update member passed")

def test_search_members(headers):
    r = requests.post(f"{BASE}/members/search", headers=headers, json={
        "keyword": "Python",
        "page": 1,
        "page_size": 10
    })
    assert r.status_code == 200
    assert "members" in r.json()["data"]
    print(f"✅ Search passed — {len(r.json()['data']['members'])} results")

def test_no_auth():
    r = requests.post(f"{BASE}/members/get", json={})
    assert r.status_code == 401
    print("✅ Auth required passed")

def test_invalid_token():
    r = requests.post(f"{BASE}/members/get",
        headers={"Authorization": "Bearer invalid_token"},
        json={})
    assert r.status_code == 401
    print("✅ Invalid token passed")

def test_create_member():
    # Register new user first
    r = requests.post("http://localhost:3001/auth/register", json={
        "email": "pytest.owner2@test.com",
        "password": "StrongPass#1",
        "user_type": "member",
        "first_name": "Pytest",
        "last_name": "Owner2"
    })
    if r.status_code in (200, 201):
        token = r.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r2 = requests.post(f"{BASE}/members/create", headers=headers, json={
            "first_name": "Pytest",
            "last_name": "Owner2",
            "email": "pytest.owner2@test.com",
            "city": "San Jose",
            "state": "CA",
            "headline": "Test Member",
            "skills": ["Python", "Docker"]
        })
        assert r2.status_code in (200, 201)
        print("✅ Create member passed")
    else:
        print("⚠️  Create skipped (user exists)")
