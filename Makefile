.PHONY: infra-up services-up frontend-up observability-up up down seed-demo seed-perf reset test wait apply-schema apply-mongo topics bootstrap kafka-test verify-ecs-ec2

verify-ecs-ec2:
	./scripts/verify_ecs_ec2_local.sh

infra-up:
	docker compose up -d mysql mongo redis kafka prometheus grafana
	python3 scripts/wait_for_stack.py mysql mongo redis kafka prometheus grafana

apply-schema:
	./scripts/apply_mysql_schema.sh

apply-mongo:
	./scripts/apply_mongo_init.sh

topics:
	./scripts/create_kafka_topics.sh

services-up:
	docker compose up --build -d auth_service member_profile_service recruiter_company_service jobs_service applications_service messaging_connections_service analytics_service ai_orchestrator_service
	python3 scripts/wait_for_stack.py auth_service member_profile_service recruiter_company_service jobs_service applications_service messaging_connections_service analytics_service ai_orchestrator_service

frontend-up:
	docker compose up -d frontend
	python3 scripts/wait_for_stack.py frontend

observability-up:
	docker compose up -d prometheus grafana

bootstrap:
	./scripts/bootstrap_local.sh

up:
	docker compose up --build -d

down:
	docker compose down

seed-demo:
	./scripts/run_seed_demo.sh

seed-perf:
	python3 scripts/seed_perf_data.py

reset:
	python3 scripts/reset_dev_state.py
	rm -f backend/data/*.json
	docker compose down -v

test:
	pytest -q


kafka-test:
	./scripts/test_kafka_stack.sh
