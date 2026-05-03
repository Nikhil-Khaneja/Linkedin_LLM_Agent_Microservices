# ── Application Load Balancer ─────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.project}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  tags               = { Name = "${var.project}-alb" }
}

# ── Frontend (port 80) ────────────────────────────────────────────────────────
resource "aws_lb_target_group" "frontend" {
  name        = "${var.project}-frontend"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
  }
}

resource "aws_lb_listener" "frontend" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# ── Backend services (ports 8001-8008) ───────────────────────────────────────
resource "aws_lb_target_group" "svc" {
  for_each = local.services

  name        = "${var.project}-${substr(each.key, 0, 18)}"
  port        = each.value
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = "/ops/healthz"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
    matcher             = "200"
  }
}

resource "aws_lb_listener" "svc" {
  for_each = local.services

  load_balancer_arn = aws_lb.main.arn
  port              = each.value
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.svc[each.key].arn
  }
}

# ── MinIO public access for presigned URLs (port 9000) ───────────────────────
resource "aws_lb_target_group" "minio" {
  name        = "${var.project}-minio"
  port        = 9000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = "/minio/health/live"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    matcher             = "200"
  }
}

resource "aws_lb_listener" "minio" {
  load_balancer_arn = aws_lb.main.arn
  port              = 9000
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.minio.arn
  }
}
