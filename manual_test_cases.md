# LinkedIn Prototype - Manual Test Case Document

This document outlines the manual testing scenarios to verify the core functionality of the LinkedIn Prototype project. The tests cover both the Frontend UI and Backend APIs.

## Prerequisites
- The local infrastructure (MySQL, Mongo, Redis, Kafka, MinIO) must be running.
- All backend services (Owners 1-8) must be up and healthy.
- The frontend must be accessible at `http://localhost:5173`.
- Grafana must be accessible at `http://localhost:3000`.

---

## Scenario 1: User Registration and Authentication (Owner 1)
**Objective**: Verify that a new user can register, log in, and receive valid authentication tokens.

**Steps**:
1. Open the frontend at `http://localhost:5173`.
2. Navigate to the Registration page.
3. Register a new user with the following details:
   - Email: `testuser@example.com`
   - Password: `StrongPass#1`
   - First Name: `Test`
   - Last Name: `User`
   - User Type: `member` (or `recruiter`)
4. Verify that the registration is successful and you are redirected to the Login page.
5. Log in using the credentials created above.
6. **Expected Result**: Login succeeds. A JWT token is issued, and the user is redirected to the dashboard.

---

## Scenario 2: Member Profile Management (Owner 2)
**Objective**: Verify that a user can create and view their member profile.

**Steps**:
1. Log in as the member created in Scenario 1.
2. Navigate to the Profile section.
3. Fill in profile details:
   - Headline: `Software Engineer`
   - About: `Experienced developer in Python and React.`
   - Skills: `Python`, `React`, `Kafka`
   - Location: `San Francisco, CA`
4. Save the profile.
5. **Expected Result**: The profile is saved successfully, and the details are correctly reflected on the user's profile view.

---

## Scenario 3: Recruiter and Company Operations (Owner 3)
**Objective**: Verify that a recruiter can be created and associated with a company.

**Steps**:
1. Register and log in as a user with the `recruiter` type.
2. Navigate to the Company/Recruiter setup page.
3. Create a new recruiter profile associated with a company (e.g., "Tech Corp", Industry: "Software", Size: "medium").
4. **Expected Result**: The recruiter profile is created successfully and linked to the specified company.

---

## Scenario 4: Job Posting and Searching (Owner 4)
**Objective**: Verify that recruiters can post jobs and members can search for them.

**Steps**:
1. Log in as the `recruiter`.
2. Navigate to the Jobs section and click "Post a Job".
3. Fill in job details (Title: "Backend Engineer", Skills Required: "Python, Kafka", Location: "Remote").
4. Submit the job posting.
5. Log out and log back in as the `member`.
6. Navigate to Job Search.
7. Search for the keyword "Backend" or "Python".
8. **Expected Result**: The previously created job posting appears in the search results.

---

## Scenario 5: Job Application Flow (Owner 5)
**Objective**: Verify that a member can apply to a job and the recruiter can view the application.

**Steps**:
1. As the `member`, click on the "Backend Engineer" job from the search results.
2. Click "Apply" and submit the application with a cover letter.
3. Log out and log back in as the `recruiter`.
4. Navigate to the specific job posting and view applications.
5. **Expected Result**: The member's application is visible to the recruiter. The recruiter can update the application status to "Reviewing".

---

## Scenario 6: Messaging and Connections (Owner 6)
**Objective**: Verify real-time messaging and connection requests between users.

**Steps**:
1. As the `member`, navigate to the recruiter's profile and send a "Connection Request" with a custom message.
2. Log out and log in as the `recruiter`.
3. Check the Connections tab and accept the incoming request.
4. Open the Messaging interface.
5. Send a direct message to the member.
6. **Expected Result**: The connection is successfully established, and messages are delivered and visible in the thread.

---

## Scenario 7: AI Orchestrator Task (Owner 8)
**Objective**: Verify that the AI Orchestrator can process background tasks (e.g., shortlisting candidates).

**Steps**:
1. As the `recruiter`, go to the job posting with active applications.
2. Trigger the "AI Shortlist" action for the job.
3. Wait a few moments and monitor the task status.
4. **Expected Result**: The task enters the `awaiting_approval` state. The recruiter can review the AI's drafted response/shortlist and click "Approve". The final state should update to `approved`.

---

## Scenario 8: Observability and Analytics (Owner 7)
**Objective**: Verify that system events are being tracked and metrics are visible in Grafana.

**Steps**:
1. Open Grafana at `http://localhost:3000`.
2. Navigate to the main dashboard.
3. **Expected Result**:
   - Request traffic from the above interactions is visible.
   - Cache hit rate charts display data.
   - The p95 latency charts reflect recent API calls.
4. (Optional API Check): Hit the `GET /ops/metrics` or `GET /ops/cache-stats` endpoint on any backend service (e.g., `http://localhost:8001/ops/cache-stats`) and verify it returns structured metric data.
