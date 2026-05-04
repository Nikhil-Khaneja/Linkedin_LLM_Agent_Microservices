# ── Kafka ─────────────────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "kafka" {
  family                   = "${var.project}-kafka"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "kafka"
    image     = "apache/kafka:4.2.0"
    essential = true
    portMappings = [
      { containerPort = 9092, name = "kafka-broker" },
      { containerPort = 9093, name = "kafka-controller" }
    ]
    environment = [
      { name = "KAFKA_NODE_ID",                              value = "1" },
      { name = "KAFKA_PROCESS_ROLES",                        value = "broker,controller" },
      { name = "KAFKA_LISTENERS",                            value = "PLAINTEXT://:9092,CONTROLLER://:9093" },
      { name = "KAFKA_ADVERTISED_LISTENERS",                 value = "PLAINTEXT://kafka:9092" },
      { name = "KAFKA_CONTROLLER_LISTENER_NAMES",            value = "CONTROLLER" },
      { name = "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP",       value = "PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT" },
      { name = "KAFKA_CONTROLLER_QUORUM_VOTERS",             value = "1@localhost:9093" },
      { name = "KAFKA_INTER_BROKER_LISTENER_NAME",           value = "PLAINTEXT" },
      { name = "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR",     value = "1" },
      { name = "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR", value = "1" },
      { name = "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR",        value = "1" },
      { name = "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS",     value = "0" },
      { name = "KAFKA_AUTO_CREATE_TOPICS_ENABLE",            value = "true" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "kafka"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1"]
      interval    = 30
      timeout     = 10
      retries     = 5
      startPeriod = 30
    }
  }])
}

resource "aws_service_discovery_service" "kafka" {
  name = "kafka"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.app.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}

resource "aws_ecs_service" "kafka" {
  name                               = "${var.project}-kafka"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.kafka.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 60

  network_configuration {
    subnets          = [aws_subnet.private_a.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.kafka.arn
  }
}

# ── MongoDB ───────────────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "mongo" {
  family                   = "${var.project}-mongo"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "mongo"
    image     = "mongo:7"
    essential = true
    portMappings = [{ containerPort = 27017, name = "mongo" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "mongo"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "mongosh --quiet --eval \"db.adminCommand('ping').ok\" | grep 1"]
      interval    = 15
      timeout     = 5
      retries     = 5
      startPeriod = 20
    }
  }])
}

resource "aws_service_discovery_service" "mongo" {
  name = "mongo"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.app.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}

resource "aws_ecs_service" "mongo" {
  name            = "${var.project}-mongo"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mongo.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_a.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.mongo.arn
  }
}

# ── MinIO ─────────────────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "minio" {
  family                   = "${var.project}-minio"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "minio"
    image     = "minio/minio:latest"
    essential = true
    command   = ["server", "/data", "--console-address", ":9001"]
    portMappings = [
      { containerPort = 9000, name = "minio-api" },
      { containerPort = 9001, name = "minio-console" }
    ]
    environment = [
      { name = "MINIO_ROOT_USER",     value = "minioadmin" },
      { name = "MINIO_ROOT_PASSWORD", value = "minioadmin" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "minio"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null"]
      interval    = 15
      timeout     = 5
      retries     = 5
      startPeriod = 20
    }
  }])
}

resource "aws_service_discovery_service" "minio" {
  name = "minio"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.app.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}

resource "aws_ecs_service" "minio" {
  name            = "${var.project}-minio"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.minio.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  load_balancer {
    target_group_arn = aws_lb_target_group.minio.arn
    container_name   = "minio"
    container_port   = 9000
  }

  network_configuration {
    subnets          = [aws_subnet.private_a.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.minio.arn
  }

  depends_on = [aws_lb_listener.minio]
}
