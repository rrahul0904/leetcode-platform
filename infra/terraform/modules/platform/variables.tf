variable "name" { type = string }
variable "environment" { type = string }
variable "vpc_cidr" { type = string }
variable "az_count" { type = number }
variable "enable_nat_gateway_per_az" { type = bool }

variable "enable_control_plane_compute" {
  description = "Create ECS/ALB/WAF only after queued execution dispatch is implemented and production-safe."
  type        = bool
  default     = false
}

variable "web_image" {
  type     = string
  default  = null
  nullable = true
}

variable "api_image" {
  type     = string
  default  = null
  nullable = true
}

variable "worker_image" {
  type     = string
  default  = null
  nullable = true
}

variable "certificate_arn" {
  type     = string
  default  = null
  nullable = true
}

variable "api_host" {
  type     = string
  default  = null
  nullable = true
}

variable "allowed_origins" { type = list(string) }
variable "oidc_issuer" { type = string }
variable "oidc_audience" { type = string }

variable "oidc_jwks_url" {
  type     = string
  default  = null
  nullable = true
}

variable "rds_instance_class" { type = string }
variable "rds_multi_az" { type = bool }
variable "rds_deletion_protection" { type = bool }
variable "valkey_node_type" { type = string }
variable "valkey_cache_clusters" { type = number }

variable "kubernetes_version" {
  type     = string
  default  = null
  nullable = true
}

variable "gvisor_node_ami_id" {
  type     = string
  default  = null
  nullable = true
}

variable "gvisor_node_user_data" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "execution_node_min_size" { type = number }
variable "execution_node_desired_size" { type = number }
variable "execution_node_max_size" { type = number }

variable "tags" {
  type    = map(string)
  default = {}
}
