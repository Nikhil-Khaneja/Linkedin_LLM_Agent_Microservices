# Recruiter & Company Service (Owner 3)

## Overview

This service is responsible for: - Managing recruiter identity -
Managing company metadata - Handling recruiter access levels -
Publishing recruiter-related events

It is a core service required before job creation and recruiter
workflows.

------------------------------------------------------------------------

## Tech Stack

-   Node.js (Express)
-   MySQL (Primary DB)
-   Redis (Caching)
-   Kafka (Event Streaming)
-   Docker

------------------------------------------------------------------------

## Base URL

http://localhost:3003

Swagger UI: http://localhost:3003/api-docs

------------------------------------------------------------------------

## Authentication

All endpoints require JWT issued by the Auth Service (Owner 1).

### Steps:

1.  Go to Auth Swagger: http://localhost:3001/api-docs
2.  Register or login
3.  Copy access_token
4.  In Recruiter Service Swagger → Click **Authorize**
5.  Paste: Bearer `<access_token>`{=html}

------------------------------------------------------------------------

## Standard Response Format

### Success

{ "success": true, "trace_id": "trc_xxx", "data": {} }

### Error

{ "success": false, "trace_id": "trc_xxx", "error": { "code":
"validation_error", "message": "One or more request fields are
invalid.", "details": {}, "retryable": false } }

------------------------------------------------------------------------

## Endpoints

### 1. POST /recruiters/create

Creates recruiter and associated company.

Required Fields: - recruiter_id - name - email - company_name -
access_level

Example: { "recruiter_id": "rec_120", "name": "Morgan Lee", "email":
"morgan@example.com", "phone": "+14085550000", "company_name":
"Northstar Labs", "company_industry": "Software", "company_size":
"medium", "access_level": "admin" }

------------------------------------------------------------------------

### 2. POST /recruiters/get

Fetch recruiter profile.

Example: { "recruiter_id": "rec_120" }

------------------------------------------------------------------------

### 3. POST /recruiters/update

Update recruiter or company data.

Example: { "recruiter_id": "rec_120", "phone": "+14085559999",
"company_size": "large" }

------------------------------------------------------------------------

### 4. POST /companies/get

Fetch company metadata.

Example: { "company_id": "cmp_120" }

Response includes: - company details - recruiter_count - cache status

------------------------------------------------------------------------

## Validation Rules

-   recruiter_id → must follow rec\_`<id>`{=html}
-   company_id → must follow cmp\_`<id>`{=html}
-   email → valid + unique
-   company_size → startup \| small \| medium \| large \| enterprise
-   access_level → admin \| recruiter \| reviewer

------------------------------------------------------------------------

## Error Cases

Validation Error: { "code": "validation_error" }

Duplicate Email: { "code": "duplicate_recruiter_email" }

Unauthorized: { "code": "auth_required" }

Forbidden: { "code": "forbidden" }

Not Found: { "code": "not_found" }

------------------------------------------------------------------------

## Caching

-   Endpoint: /companies/get
-   First call → cache: miss
-   Subsequent calls → cache: hit

------------------------------------------------------------------------

## Kafka Events

-   recruiter.created
-   recruiter.updated

------------------------------------------------------------------------

## Run Instructions

docker compose up --build

------------------------------------------------------------------------

## Test Flow

1.  Register user (Auth service)
2.  Copy token
3.  Authorize in Swagger
4.  Test endpoints:
    -   /recruiters/create
    -   /recruiters/get
    -   /recruiters/update
    -   /companies/get

------------------------------------------------------------------------

## Notes

-   Each user can create only one recruiter profile
-   Company ID auto-generated if not provided
-   DB schema differs internally but mapped to API contract
