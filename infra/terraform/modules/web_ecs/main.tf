variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "web_image" {
  type = string
}

variable "certificate_arn" {
  type = string
}

variable "backend_origin" {
  type = string
}

variable "clerk_issuer" {
  type = string
}

variable "clerk_publishable_key" {
  type = string
}

variable "clerk_secret_arn" {
  type = string
}

variable "desired_count" {
  type    = number
  default = 2
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/skillforge/${var.name}/web"
  retention_in_days = 30
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-web-alb-"
  description = "HTTPS ingress for the SkillForge web front door"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Redirect public HTTP to HTTPS"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Public HTTPS only"
  }
}

resource "aws_security_group" "web" {
  name_prefix = "${var.name}-web-"
  description = "Non-public web workloads may be reached by ALB only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 3001
    to_port         = 3001
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "Only web ALB can access Next.js"
  }

  # Clerk identity and the HTTPS backend are called from private NAT subnets.
  #trivy:ignore:AVD-AWS-0104
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Clerk API and the trusted backend via TLS"
  }
}

resource "aws_vpc_security_group_egress_rule" "alb_to_web" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = 3001
  to_port                      = 3001
  description                  = "ALB to web Fargate tasks"
}

# Public HTTPS edge, with regional WAF provisioned by its parent.
#trivy:ignore:AVD-AWS-0053
resource "aws_lb" "web" {
  name                       = substr("${var.name}-web", 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  drop_invalid_header_fields = true
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.public_subnet_ids
}

resource "aws_lb_target_group" "web" {
  name        = substr("${var.name}-web", 0, 32)
  port        = 3001
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "redirect" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.web.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_iam_role" "execution" {
  name_prefix = "${var.name}-web-execution-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "clerk_secret" {
  name = "read-clerk-server-key"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.clerk_secret_arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name_prefix = "${var.name}-web-task-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

data "aws_region" "current" {}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "web"
    image     = var.web_image
    essential = true
    readonlyRootFilesystem = true
    portMappings = [{
      containerPort = 3001
      protocol      = "tcp"
    }]
    environment = [
      { name = "RIGOR_BACKEND_ORIGIN", value = var.backend_origin },
      { name = "RIGOR_CLERK_ISSUER", value = var.clerk_issuer },
      { name = "NEXT_PUBLIC_RIGOR_AUTH_MODE", value = "clerk" },
      { name = "NEXT_PUBLIC_RIGOR_API_URL", value = "/api/backend" },
      { name = "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", value = var.clerk_publishable_key }
    ]
    secrets = [{
      name      = "CLERK_SECRET_KEY"
      valueFrom = var.clerk_secret_arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.web.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "web"
      }
    }
  }])
}

resource "aws_ecs_service" "web" {
  name                 = "${var.name}-web"
  cluster              = aws_ecs_cluster.this.id
  task_definition      = aws_ecs_task_definition.web.arn
  desired_count        = var.desired_count
  launch_type          = "FARGATE"
  health_check_grace_period_seconds = 90

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.web.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3001
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]
}

resource "aws_appautoscaling_target" "web" {
  max_capacity       = 6
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "web_cpu" {
  name               = "${var.name}-web-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web.resource_id
  scalable_dimension = aws_appautoscaling_target.web.scalable_dimension
  service_namespace  = aws_appautoscaling_target.web.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 60
  }
}

output "service_name" {
  value = aws_ecs_service.web.name
}

output "alb_arn" {
  value = aws_lb.web.arn
}

output "alb_dns_name" {
  value = aws_lb.web.dns_name
}

output "alb_zone_id" {
  value = aws_lb.web.zone_id
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}
