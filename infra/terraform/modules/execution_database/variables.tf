variable "name_prefix" {
  description = "Stable prefix for staging database resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the staging application/execution database."
  type        = string
}

variable "data_subnet_ids" {
  description = "Private data subnets for RDS."
  type        = list(string)
}

variable "trusted_client_security_group_ids" {
  description = "Only security groups allowed to initiate PostgreSQL connections. Do not include hostile execution-node groups."
  type        = set(string)
}

variable "engine_version" {
  description = "RDS PostgreSQL engine version."
  type        = string
  default     = "18.4"
}

variable "instance_class" {
  description = "RDS instance class for staging."
  type        = string
  default     = "db.t4g.medium"
}

variable "allocated_storage_gib" {
  type    = number
  default = 30
}

variable "max_allocated_storage_gib" {
  type    = number
  default = 100
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "multi_az" {
  description = "Enable Multi-AZ for staging when production-like HA validation is required."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
