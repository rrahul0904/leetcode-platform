data "aws_region" "current" {}

locals {
  tags = merge(var.tags, {
    "rigor:component"   = "ecs-control-plane"
    "rigor:trust-plane" = "control"
  })

  web_environment = [for key, value in var.web_environment : { name = key, value = value }]
  api_environment = [for key, value in var.api_environment : { name = key, value = value }]
  worker_environment = [for key, value in var.worker_environment : { name = key, value = value }]
  api_secrets = [for key, value in var.api_secrets : { name = key, valueFrom = value }]
  worker_secrets = [for key, value in var.worker_secrets : { name = key, valueFrom = value }]
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "enhanced"
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/rigor/${var.name}/web"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/rigor/${var.name}/api"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  count = var.worker_image == null ? 0 : 1

  name              = "/rigor/${var.name}/trusted-worker"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  description = "Internet ingress to Rigor ALB; WAF remains independently authoritative."
  vpc_id      = var.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP bootstrap/redirect ingress"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS ingress"
}

resource "aws_vpc_security_group_egress_rule" "alb_web" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = var.web_security_group_id
  from_port                    = 3001
  to_port                      = 3001
  ip_protocol                  = "tcp"
  description                  = "ALB to Next.js"
}

resource "aws_vpc_security_group_egress_rule" "alb_api" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = var.api_security_group_id
  from_port                    = 8002
  to_port                      = 8002
  ip_protocol                  = "tcp"
  description                  = "ALB to FastAPI"
}

resource "aws_vpc_security_group_ingress_rule" "web_from_alb" {
  security_group_id            = var.web_security_group_id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 3001
  to_port                      = 3001
  ip_protocol                  = "tcp"
  description                  = "Next.js only accepts ALB ingress"
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = var.api_security_group_id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8002
  to_port                      = 8002
  ip_protocol                  = "tcp"
  description                  = "FastAPI only accepts ALB ingress"
}

resource "aws_lb" "this" {
  name               = substr(replace(var.name, "_", "-"), 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = true
  drop_invalid_header_fields = true

  tags = local.tags
}

resource "aws_lb_target_group" "web" {
  name_prefix = "web-"
  port        = 3001
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled             = true
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 20
    timeout             = 5
    matcher             = "200-399"
  }

  deregistration_delay = 30
  tags                 = local.tags
}

resource "aws_lb_target_group" "api" {
  name_prefix = "api-"
  port        = 8002
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled             = true
    path                = "/readyz"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 20
    timeout             = 5
    matcher             = "200"
  }

  deregistration_delay = 30
  tags                 = local.tags
}

resource "aws_lb_listener" "http" {
  count = var.certificate_arn == null ? 1 : 0

  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count = var.certificate_arn == null ? 0 : 1

  load_balancer_arn = aws_lb.this.arn
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
  count = var.certificate_arn == null ? 0 : 1

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

locals {
  active_listener_arn = var.certificate_arn == null ? aws_lb_listener.http[0].arn : aws_lb_listener.https[0].arn
}

resource "aws_lb_listener_rule" "api_paths" {
  listener_arn = local.active_listener_arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/readyz", "/livez", "/health/*", "/local-oidc/*"]
    }
  }
}

resource "aws_lb_listener_rule" "api_host" {
  count = var.api_host == null ? 0 : 1

  listener_arn = local.active_listener_arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    host_header {
      values = [var.api_host]
    }
  }
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.web_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = var.web_image
      essential = true
      portMappings = [{
        containerPort = 3001
        hostPort      = 3001
        protocol      = "tcp"
      }]
      environment = local.web_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.web.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "web"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "node -e \"fetch('http://127.0.0.1:3001/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""]
        interval    = 20
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.api_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [{
        containerPort = 8002
        hostPort      = 8002
        protocol      = "tcp"
      }]
      environment = local.api_environment
      secrets     = local.api_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8002/readyz',timeout=2)); assert d['status']=='ready'\""]
        interval    = 20
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  count = var.worker_image == null ? 0 : 1

  family                   = "${var.name}-trusted-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.worker_task_role_arn

  container_definitions = jsonencode([
    {
      name        = "trusted-worker"
      image       = var.worker_image
      command     = var.worker_command
      essential   = true
      environment = local.worker_environment
      secrets     = local.worker_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker[0].name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_service" "web" {
  name            = "web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.application_subnet_ids
    security_groups  = [var.web_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3001
  }

  health_check_grace_period_seconds = 30
  enable_execute_command             = false
  propagate_tags                     = "SERVICE"
  tags                               = local.tags

  depends_on = [aws_lb_listener.http, aws_lb_listener.https]
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.application_subnet_ids
    security_groups  = [var.api_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8002
  }

  health_check_grace_period_seconds = 30
  enable_execute_command             = false
  propagate_tags                     = "SERVICE"
  tags                               = local.tags

  depends_on = [aws_lb_listener_rule.api_paths]
}

resource "aws_ecs_service" "worker" {
  count = var.worker_image == null ? 0 : 1

  name            = "trusted-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker[0].arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.application_subnet_ids
    security_groups  = [var.worker_security_group_id]
    assign_public_ip = false
  }

  enable_execute_command = false
  propagate_tags         = "SERVICE"
  tags                    = local.tags
}

resource "aws_appautoscaling_target" "web" {
  max_capacity       = 20
  min_capacity       = max(1, min(var.web_desired_count, 2))
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
    target_value       = 60
    scale_in_cooldown  = 120
    scale_out_cooldown = 30
  }
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = 30
  min_capacity       = max(1, min(var.api_desired_count, 2))
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 55
    scale_in_cooldown  = 120
    scale_out_cooldown = 30
  }
}
