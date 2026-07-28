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
  description = "Trusted control-plane security groups allowed to connect to Valkey."
  type        = set(string)
}

variable "kms_key_arn" {
  type = string
}

variable "node_type" {
  type    = string
  default = "cache.r7g.large"
}

variable "num_cache_clusters" {
  type    = number
  default = 2
}

variable "snapshot_retention_limit" {
  type    = number
  default = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
