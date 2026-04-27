// AUTOMATED BY AI — single source of truth for all API URLs.
// Never hardcode service URLs elsewhere; always import from here.

const API_BASE = process.env.REACT_APP_API_BASE_URL || "";

export const API = {
  // Auth (owner1)
  login:    `${API_BASE}/api/v1/auth/login`,
  register: `${API_BASE}/api/v1/auth/register`,
  refresh:  `${API_BASE}/api/v1/auth/refresh`,

  // Members (owner2)
  members:  `${API_BASE}/api/v1/members`,

  // Recruiters (owner3)
  recruiters: `${API_BASE}/api/v1/recruiters`,
  companies:  `${API_BASE}/api/v1/companies`,

  // Jobs (owner4)
  jobs:     `${API_BASE}/api/v1/jobs`,

  // Applications (owner5)
  applications: `${API_BASE}/api/v1/applications`,

  // Analytics (owner7)
  analytics:    `${API_BASE}/api/v1/analytics`,
  events:       `${API_BASE}/api/v1/events`,

  // AI Agent (owner8)
  agent:        `${API_BASE}/api/v1/agent`,
};
