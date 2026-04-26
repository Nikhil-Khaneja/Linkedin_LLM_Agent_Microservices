# API Endpoint Summary — 48 Endpoints

## Auth + API Edge (Owner 1) — 6 endpoints
| Method | Endpoint | Auth |
|--------|----------|------|
| POST | /auth/register | Public |
| POST | /auth/login | Public |
| POST | /auth/refresh | Public |
| POST | /auth/logout | Bearer |
| GET  | /.well-known/jwks.json | Public |
| POST | /gateway/idempotency/check | Bearer |

## Member Profile (Owner 2) — 5 endpoints
| POST | /members/create | Bearer |
| POST | /members/get | Bearer |
| POST | /members/update | Bearer |
| POST | /members/delete | Bearer |
| POST | /members/search | Bearer |

## Recruiter & Company (Owner 3) — 4 endpoints
| POST | /recruiters/create | Bearer |
| POST | /recruiters/get | Bearer |
| POST | /recruiters/update | Bearer |
| POST | /companies/get | Bearer |

## Job Service (Owner 4) — 6 endpoints
| POST | /jobs/create | Bearer |
| POST | /jobs/get | Bearer |
| POST | /jobs/update | Bearer |
| POST | /jobs/search | Bearer |
| POST | /jobs/close | Bearer |
| POST | /jobs/byRecruiter | Bearer |

## Application Service (Owner 5) — 6 endpoints
| POST | /applications/submit | Bearer |
| POST | /applications/get | Bearer |
| POST | /applications/byJob | Bearer |
| POST | /applications/byMember | Bearer |
| POST | /applications/updateStatus | Bearer |
| POST | /applications/addNote | Bearer |

## Messaging + Connections (Owner 6) — 10 endpoints
| POST | /threads/open | Bearer |
| POST | /threads/get | Bearer |
| POST | /threads/byUser | Bearer |
| POST | /messages/list | Bearer |
| POST | /messages/send | Bearer |
| POST | /connections/request | Bearer |
| POST | /connections/accept | Bearer |
| POST | /connections/reject | Bearer |
| POST | /connections/list | Bearer |
| POST | /connections/mutual | Bearer |

## Analytics + Logging (Owner 7) — 6 endpoints
| POST | /events/ingest | Public |
| POST | /analytics/jobs/top | Bearer |
| POST | /analytics/funnel | Bearer |
| POST | /analytics/geo | Bearer |
| POST | /analytics/member/dashboard | Bearer |
| POST | /benchmarks/report | Bearer |

## FastAPI AI Orchestrator (Owner 8) — 5 endpoints
| POST | /ai/tasks/create | Bearer |
| GET  | /ai/tasks/{taskId} | Bearer |
| POST | /ai/tasks/{taskId}/approve | Bearer |
| POST | /ai/tasks/{taskId}/reject | Bearer |
| GET  | /ai/tasks/metrics/approval-rate | Bearer |
| WS   | /ws/ai/tasks/{taskId}?token={jwt} | Query token |

Total: 48 documented endpoints ✅
