resource "aws_ecs_cluster" "main" {
  name = var.project
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

# Service Connect namespace — services find each other as kafka:9092, auth_service:8001, etc.
resource "aws_service_discovery_private_dns_namespace" "app" {
  name = "linkedin.local"
  vpc  = aws_vpc.main.id
}
