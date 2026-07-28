variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "application_subnet_ids" {
  type = list(string)
}

variable "web_image" {
  description = "Immutable ECR image reference (prefer digest) for Next.js."
  type        = string
}

variable "api_image" {
  description = "Immutable ECR image reference (prefer digest) for FastAPI."
  type        = string
}

variable "worker_image" {
  description = "Immutable ECR image reference for trusted dispatcher. Null leaves worker service uncreated."
  type        = string
  default     = null
  nullable    = true
}

variable "ecs_execution_role_arn" {
  type = string
}

variable "web_task_role_arn" {
  type = string
}

variable "api_task_role_arn" {
  type = string
}

variable "worker_task_role_arn" {
  type = string
}

variable "certificate_arn" {
  description = "ACM certificate for ALB HTTPS. Null is allowed only for bootstrap/staging plans."
  type        = string
  default     = null
  nullable    = true
}

variable "api_host" {
  description = "Optional api.example.com host-header route to FastAPI."
  type        = string
  default     = null
  nullable    = true
}

variable "web_environment" {
  type    = map(string)
  default = {}
}

variable "api_environment" {
  type    = map(string)
  default = {}
}

variable "worker_environment" {
  type    = map(string)
  default = {}
}

variable "api_secrets" {
  description = "Map of container environment variable to Secrets Manager valueFrom ARN/json-key reference."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "worker_secrets" {
  type      = map(string)
  default   = {}
  sensitive = true
}

variable "web_desired_count" {
  type    = number
  default = 2
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}
