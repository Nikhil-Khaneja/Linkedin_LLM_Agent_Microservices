# Automated DB Setup and Local Bootstrap

This repo now includes automation for local infra bootstrapping.

## What is automated

- MySQL startup
- MySQL schema creation
- MySQL secondary indexes and views
- MongoDB collection creation
- MongoDB index creation
- Kafka topic creation
- backend service startup
- frontend startup
- demo data seeding

## Files involved

- `docker-compose.yml`
- `infra/mysql/001_init.sql`
- `infra/mysql/002_indexes.sql`
- `infra/mysql/003_constraints_and_views.sql`
- `infra/mongo/init.js`
- `scripts/wait_for_stack.py`
- `scripts/apply_mysql_schema.sh`
- `scripts/apply_mongo_init.sh`
- `scripts/create_kafka_topics.sh`
- `scripts/bootstrap_local.sh`

## One-command local start

```bash
cp .env.example .env
chmod +x scripts/bootstrap_local.sh
./scripts/bootstrap_local.sh
```

## Notes

The current runtime still uses file-backed persistence in `backend/services/shared/persist.py`.
That means the infra is provisioned and initialized automatically, but durable service state is not yet committed into MySQL/Mongo by the application code.
