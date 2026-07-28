variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Trusted control-plane security groups allowed to connect to PostgreSQL."
  type        = set(string)
}

variable "kms_key_arn" {
  type = string
}

variable "engine_version" {
  type    = string
  default = "18"
}

variable "instance_class" {
  type    = string
  default = "db.r7g.large"
}

variable "allocated_storage_gib" {
  type    = number
  default = 100
}

variable "max_allocated_storage_gib" {
  type    = number
  default = 500
}

variable "multi_az" {
  type    = bool
  default = true
}

variable "backup_retention_days" {
  type    = number
  default = 14
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "skip_final_snapshot" {
  type    = bool
  default = false
}

variable "performance_insights_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
