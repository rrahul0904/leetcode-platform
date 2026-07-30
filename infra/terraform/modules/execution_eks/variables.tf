variable "name_prefix" {
  description = "Stable prefix for the staging execution cluster."
  type        = string
}

variable "vpc_id" {
  description = "VPC containing the execution cluster."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR used for node security-group rules."
  type        = string
}

variable "control_subnet_ids" {
  description = "Private subnets for trusted controller nodes and EKS control-plane ENIs."
  type        = list(string)
}

variable "execution_subnet_ids" {
  description = "Private no-Internet-route subnets for hostile execution nodes."
  type        = list(string)
}

variable "kubernetes_version" {
  description = "Amazon EKS Kubernetes minor version."
  type        = string
  default     = "1.36"
}

variable "service_ipv4_cidr" {
  description = "Kubernetes service IPv4 CIDR."
  type        = string
  default     = "172.20.0.0/16"
}

variable "endpoint_public_access" {
  description = "Whether the staging EKS API exposes a public endpoint. Prefer false."
  type        = bool
  default     = false
}

variable "endpoint_public_access_cidrs" {
  description = "Explicit CIDRs allowed when the EKS public endpoint is enabled."
  type        = list(string)
  default     = []
}

variable "cluster_admin_principal_arn" {
  description = "Optional IAM principal granted cluster-admin access through EKS access entries."
  type        = string
  default     = ""
}

variable "trusted_instance_types" {
  description = "Instance types allowed for trusted execution-controller nodes."
  type        = list(string)
  default     = ["m7i.large"]
}

variable "trusted_min_size" {
  type    = number
  default = 2
}

variable "trusted_desired_size" {
  type    = number
  default = 2
}

variable "trusted_max_size" {
  type    = number
  default = 4
}

variable "execution_node_ami_id" {
  description = "Custom EKS-compatible AL2023 AMI prebuilt with runsc/containerd integration. Empty disables the execution node group."
  type        = string
  default     = ""
}

variable "execution_instance_type" {
  description = "Instance type for dedicated hostile-execution nodes."
  type        = string
  default     = "m7i.large"
}

variable "execution_min_size" {
  type    = number
  default = 0
}

variable "execution_desired_size" {
  type    = number
  default = 0
}

variable "execution_max_size" {
  type    = number
  default = 10
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
