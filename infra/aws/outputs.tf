output "alb_dns_name" {
  description = "Public URL of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "frontend_url" {
  description = "Access the LinkedIn simulation here"
  value       = "http://${aws_lb.main.dns_name}"
}

output "service_urls" {
  description = "Backend service endpoints"
  value = {
    for name, port in local.services :
    name => "http://${aws_lb.main.dns_name}:${port}"
  }
}

output "rds_endpoint" {
  value = aws_db_instance.mysql.address
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "minio_url" {
  description = "MinIO console for file management"
  value       = "http://${aws_lb.main.dns_name}:9000"
}

output "aws_region" {
  value = var.aws_region
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}
