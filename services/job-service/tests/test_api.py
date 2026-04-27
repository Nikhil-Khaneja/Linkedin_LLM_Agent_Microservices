"""
Tests for Job Service API
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_check(self):
        """Test that health check returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "job-service"


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root(self):
        """Test root endpoint returns service info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data


class TestJobCreate:
    """Test job creation endpoint"""

    def test_create_job_validation(self):
        """Test that invalid requests are rejected"""
        # Missing required fields
        response = client.post("/api/v1/jobs/create", json={})
        assert response.status_code == 422

    def test_create_job_invalid_company_id(self):
        """Test that invalid company_id format is rejected"""
        response = client.post("/api/v1/jobs/create", json={
            "company_id": "invalid",
            "recruiter_id": "rec_001",
            "title": "Test Job",
            "description": "A test job description that is long enough to pass validation.",
            "location": "San Jose, CA",
            "skills_required": ["Python"]
        })
        assert response.status_code == 422


class TestJobSearch:
    """Test job search endpoint"""

    def test_search_jobs_validation(self):
        """Test search with valid parameters"""
        response = client.post("/api/v1/jobs/search", json={
            "page": 1,
            "page_size": 10
        })
        # Will fail without DB, but validates request parsing
        assert response.status_code in [200, 500]

    def test_search_jobs_invalid_page(self):
        """Test search with invalid page number"""
        response = client.post("/api/v1/jobs/search", json={
            "page": 0,  # Invalid
            "page_size": 10
        })
        assert response.status_code == 422


class TestJobGet:
    """Test job get endpoint"""

    def test_get_job_validation(self):
        """Test get job with valid parameters"""
        response = client.post("/api/v1/jobs/get", json={
            "job_id": "job_001"
        })
        # Will return 404 or 500 without DB, but validates request parsing
        assert response.status_code in [200, 404, 500]

    def test_get_job_invalid_format(self):
        """Test get job with invalid job_id format"""
        response = client.post("/api/v1/jobs/get", json={
            "job_id": "invalid"
        })
        assert response.status_code == 422


# Run tests with: pytest tests/test_api.py -v
