resource "aws_ecr_repository" "backend" {
  name                 = "${var.project}/backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = false }
  tags = { Name = "${var.project}-backend" }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project}/frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = false }
  tags = { Name = "${var.project}-frontend" }
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}
