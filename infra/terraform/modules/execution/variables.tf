variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "subnet_ids" {
  description = "Isolated execution subnets with no default internet route."
  type        = list(string)
}

variable "kms_key_arn" {
  description = "Execution-plane KMS key for EKS secret envelope encryption."
  type        = string
}

variable "kubernetes_version" {
  description = "Pin to an EKS-supported version before apply. Null lets AWS select the account default and is intended only for planning/bootstrap."
  type        = string
  default     = null
  nullable    = true
}

variable "orchestrator_principal_arn" {
  description = "Trusted dispatcher IAM principal granted namespace-scoped EKS edit access."
  type        = string
  default     = null
  nullable    = true
}

variable "gvisor_node_ami_id" {
  description = "Validated custom AMI with containerd + runsc installed. No execution node group is created until supplied."
  type        = string
  default     = null
  nullable    = true
}

variable "gvisor_node_user_data" {
  description = "Bootstrap/nodeadm user-data for the validated custom execution-node AMI."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "node_instance_types" {
  type    = list(string)
  default = ["m7i.large"]
}

variable "node_min_size" {
  type    = number
  default = 0
}

variable "node_desired_size" {
  type    = number
  default = 0
}

variable "node_max_size" {
  type    = number
  default = 20
}

variable "tags" {
  type    = map(string)
  default = {}
}
