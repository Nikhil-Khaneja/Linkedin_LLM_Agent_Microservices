# One ECR repository per Python microservice (matches backend/Dockerfile --target names).
resource "aws_ecr_repository" "backend_svc" {
  for_each = local.services

  name                 = "${var.project}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = false }
  tags = { Name = "${var.project}-${each.key}" }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project}/frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = false }
  tags = { Name = "${var.project}-frontend" }
}

output "ecr_backend_repositories" {
  description = "service name → ECR repository URL"
  value       = { for k, r in aws_ecr_repository.backend_svc : k => r.repository_url }
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}
