variable "name" {
  type = string
}

variable "execution_queue_arn" {
  type = string
}

variable "platform_bucket_arn" {
  type = string
}

variable "execution_bucket_arn" {
  type = string
}

variable "platform_kms_key_arn" {
  type = string
}

variable "execution_kms_key_arn" {
  type = string
}

variable "runtime_secret_arns" {
  description = "Secrets ECS may inject at task startup; candidate pods never receive these permissions."
  type        = set(string)
  default     = []
}

variable "execution_cluster_name" {
  description = "Private execution cluster name used to scope trusted worker DescribeCluster permission."
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
