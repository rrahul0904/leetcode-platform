variable "name_prefix" {
  description = "Stable prefix for trusted staging cache resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the trusted Valkey cache."
  type        = string
}

variable "data_subnet_ids" {
  description = "Private data subnets for ElastiCache."
  type        = list(string)
}

variable "trusted_client_security_group_ids" {
  description = "Security groups allowed to connect to Valkey. Do not include hostile execution nodes."
  type        = set(string)
}

variable "auth_token" {
  description = "Sensitive AUTH token supplied through protected Terraform input."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.auth_token) >= 32 && length(var.auth_token) <= 128
    error_message = "The Valkey AUTH token must contain between 32 and 128 characters."
  }
}

variable "engine_version" {
  description = "ElastiCache Valkey engine version used by staging."
  type        = string
  default     = "8.0"
}

variable "node_type" {
  description = "ElastiCache node type for staging."
  type        = string
  default     = "cache.t4g.small"
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
