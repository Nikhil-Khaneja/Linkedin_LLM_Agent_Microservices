# ── Per-service task definition + ECS service (one per backend service) ───────
locals {
  service_commands = {
    auth_service                  = "uvicorn services.auth_service.app.main:app --host 0.0.0.0 --port 8001"
    member_profile_service        = "uvicorn services.member_profile_service.app.main:app --host 0.0.0.0 --port 8002"
    recruiter_company_service     = "uvicorn services.recruiter_company_service.app.main:app --host 0.0.0.0 --port 8003"
    jobs_service                  = "uvicorn services.jobs_service.app.main:app --host 0.0.0.0 --port 8004"
    applications_service          = "uvicorn services.applications_service.app.main:app --host 0.0.0.0 --port 8005"
    messaging_connections_service = "uvicorn services.messaging_connections_service.app.main:app --host 0.0.0.0 --port 8006"
    analytics_service             = "uvicorn services.analytics_service.app.main:app --host 0.0.0.0 --port 8007"
    ai_orchestrator_service       = "uvicorn services.ai_orchestrator_service.app.main:app --host 0.0.0.0 --port 8008"
  }
}

resource "aws_ecs_task_definition" "svc" {
  for_each = local.services

  family                   = "${var.project}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = "${aws_ecr_repository.backend.repository_url}:latest"
    essential = true
    command   = split(" ", local.service_commands[each.key])
    portMappings = [{ containerPort = each.value, name = each.key }]

    environment = concat(local.common_env, [
      { name = "SERVICE_NAME",    value = each.key },
      { name = "MYSQL_HOST",      value = aws_db_instance.mysql.address },
      { name = "MYSQL_PASSWORD",  value = var.db_password },
      { name = "REDIS_URL",       value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
      { name = "MONGO_URL",       value = "mongodb://mongo.linkedin.local:27017" },
      { name = "MINIO_PUBLIC_ENDPOINT", value = "${aws_lb.main.dns_name}:9000" },
      { name = "OWNER1_JWKS_URL", value = "http://auth_service.linkedin.local:8001/.well-known/jwks.json" },
      { name = "OPENROUTER_API_KEY", value = var.openrouter_api_key },
      { name = "PUBLIC_BASE_URL", value = "http://${aws_lb.main.dns_name}" },
      { name = "MESSAGING_SERVICE_URL", value = "http://messaging_connections_service.linkedin.local:8006" },
    ])

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = each.key
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${each.value}/ops/healthz', timeout=2)\""]
      interval    = 30
      timeout     = 5
      retries     = 5
      startPeriod = 60
    }
  }])

  depends_on = [aws_db_instance.mysql, aws_elasticache_cluster.redis]
}

resource "aws_service_discovery_service" "svc" {
  for_each = local.services

  name = each.key
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.app.id
    routing_policy = "MULTIVALUE"
    dns_records { ttl = 10; type = "A" }
  }
  health_check_custom_config { failure_threshold = 1 }
}

resource "aws_ecs_service" "svc" {
  for_each = local.services

  name                              = "${var.project}-${each.key}"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.svc[each.key].arn
  desired_count                     = 1
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 120

  load_balancer {
    target_group_arn = aws_lb_target_group.svc[each.key].arn
    container_name   = each.key
    container_port   = each.value
  }

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.svc[each.key].arn
  }

  depends_on = [
    aws_ecs_service.kafka,
    aws_ecs_service.mongo,
    aws_ecs_service.minio,
    aws_lb_listener.svc,
  ]
}

# ── Frontend ──────────────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.frontend.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = 80, name = "frontend" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "frontend"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -fsS http://127.0.0.1:80/ >/dev/null"]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 10
    }
  }])
}

resource "aws_ecs_service" "frontend" {
  name                              = "${var.project}-frontend"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.frontend.arn
  desired_count                     = 1
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 30

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  depends_on = [aws_lb_listener.frontend]
}
