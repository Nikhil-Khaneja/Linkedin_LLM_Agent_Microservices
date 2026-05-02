# Review-driven fixes applied

This bundle includes a focused round of code fixes against the earlier senior-review rejection.

## Fixed in this iteration

### Auth and bearer JWTs
- Removed hard-coded `dev-*` bearer tokens from runtime code.
- Added `services.shared.auth` with RS256 JWT issuance and verification.
- Owner 1 now issues real bearer tokens from `/auth/register`, `/auth/login`, and `/auth/refresh`.
- All protected APIs continue to use shared `require_auth()`, which now validates JWTs instead of checking static strings.
- Added JWKS/public-key support so services can validate tokens offline and can be pointed at Owner 1 via `OWNER1_JWKS_URL`.

### Frontend/backend integration
- Frontend now stores a real access token returned from Owner 1.
- Removed hard-coded dev-token selection from the frontend.
- Added login/register-driven token handling in `frontend/src/App.tsx`.
- Updated `frontend/src/api.ts` so Authorization headers are only attached when a token is available.

### Runtime safety improvements
- Kafka producer lifecycle is now reused instead of creating a fresh producer per publish.
- Memory Kafka mode is still available, but only in test mode.
- Memory cache mode is now test-only.
- Memory document-store mode is now test-only.
- Strengthened owner-service authorization checks for job creation/update/close, member creation, connection requests, and AI approvals.

### Test and seed updates
- Updated API tests to use real JWTs instead of `dev-*` tokens.
- Updated seed scripts to generate real JWTs for local bootstrap.
- Re-ran backend compile and API smoke tests after the auth/runtime changes.

## Still not fully solved in this iteration
- No true outbox pattern yet for DB-write + Kafka publish durability.
- Analytics still compute some responses from stored events instead of fully materialized rollups.
- Multi-account AWS deployment is documented and configurable, but not end-to-end validated in this sandbox.
- Frontend source was updated, but a full npm production build was not completed in this environment.

## Approval level
This iteration is materially stronger than the previous package and closes the most obvious bearer-auth and runtime-fallback flaws, but it is still best described as a strong class-project implementation rather than a fully hardened production system.
