locals {
  tags = merge(var.tags, { "rigor:component" = "observability" })
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "execution_queue_depth" {
  alarm_name          = "${var.name}-execution-queue-depth"
  alarm_description   = "Execution backlog is above the normal operating envelope."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.queue_depth_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.execution_queue_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "execution_oldest_message" {
  alarm_name          = "${var.name}-execution-oldest-message"
  alarm_description   = "Candidates are waiting too long for an execution sandbox to start."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.queue_age_threshold_seconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.execution_queue_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "execution_dlq" {
  alarm_name          = "${var.name}-execution-dlq"
  alarm_description   = "At least one execution message reached the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.execution_dlq_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name}-rds-cpu"
  alarm_description   = "Canonical PostgreSQL CPU is persistently high."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.db_cpu_threshold_percent
  treat_missing_data  = "missing"

  dimensions = {
    DBInstanceIdentifier = var.db_instance_identifier
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${var.name}-rds-free-storage"
  alarm_description   = "Canonical PostgreSQL free storage is low."
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "LessThanThreshold"
  threshold           = var.db_free_storage_threshold_bytes
  treat_missing_data  = "missing"

  dimensions = {
    DBInstanceIdentifier = var.db_instance_identifier
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "valkey_engine_cpu" {
  alarm_name          = "${var.name}-valkey-engine-cpu"
  alarm_description   = "Valkey engine CPU is persistently high."
  namespace           = "AWS/ElastiCache"
  metric_name         = "EngineCPUUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  treat_missing_data  = "missing"

  dimensions = {
    ReplicationGroupId = var.valkey_replication_group_id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
