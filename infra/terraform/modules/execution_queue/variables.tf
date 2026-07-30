variable "name_prefix" {
  description = "Environment-qualified prefix, for example rigor-staging."
  type        = string

  validation {
    condition     = length(var.name_prefix) >= 3 && length(var.name_prefix) <= 60
    error_message = "name_prefix must be between 3 and 60 characters."
  }
}

variable "visibility_timeout_seconds" {
  description = "SQS visibility timeout. It must exceed the normal dispatcher processing window."
  type        = number
  default     = 120

  validation {
    condition     = var.visibility_timeout_seconds >= 30 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds must be between 30 and 43200 seconds."
  }
}

variable "message_retention_seconds" {
  description = "Retention for normal execution requests."
  type        = number
  default     = 345600
}

variable "dlq_retention_seconds" {
  description = "Retention for messages requiring operator investigation."
  type        = number
  default     = 1209600
}

variable "max_receive_count" {
  description = "Delivery attempts before SQS moves a message to the DLQ."
  type        = number
  default     = 5

  validation {
    condition     = var.max_receive_count >= 2 && var.max_receive_count <= 20
    error_message = "max_receive_count must be between 2 and 20."
  }
}

variable "queue_depth_alarm_threshold" {
  description = "Visible execution messages that trigger the queue-backlog alarm."
  type        = number
  default     = 25

  validation {
    condition     = var.queue_depth_alarm_threshold >= 1
    error_message = "queue_depth_alarm_threshold must be at least 1."
  }
}

variable "oldest_message_age_alarm_seconds" {
  description = "Age of the oldest queued execution that triggers a latency alarm."
  type        = number
  default     = 120

  validation {
    condition     = var.oldest_message_age_alarm_seconds >= 30
    error_message = "oldest_message_age_alarm_seconds must be at least 30 seconds."
  }
}

variable "alarm_actions" {
  description = "Optional SNS/action ARNs invoked by execution queue alarms."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
