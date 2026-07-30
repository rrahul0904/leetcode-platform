variable "aws_region" {
  description = "AWS region used by the staging control and execution planes."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Stable resource-name prefix for staging."
  type        = string
  default     = "rigor-staging"
}

variable "enable_execution_staging_infrastructure" {
  description = "Explicit opt-in for the cost-bearing VPC/EKS/RDS staging execution stack."
  type        = bool
  default     = false
}

variable "execution_node_ami_id" {
  description = "Custom EKS-compatible AL2023 AMI prebuilt with runsc/containerd integration. Required when the staging execution stack is enabled."
  type        = string
  default     = ""

  validation {
    condition     = var.execution_node_ami_id == "" || startswith(var.execution_node_ami_id, "ami-")
    error_message = "execution_node_ami_id must be empty or an EC2 AMI ID beginning with ami-."
  }
}

variable "cluster_admin_principal_arn" {
  description = "Optional IAM principal granted EKS cluster-admin access through the access-entry API."
  type        = string
  default     = ""
}

variable "eks_public_access_cidrs" {
  description = "Explicit CIDRs for the EKS public API endpoint. Empty keeps the endpoint private-only."
  type        = list(string)
  default     = []
}

variable "additional_database_client_security_group_ids" {
  description = "Optional trusted application/migration security groups allowed to connect to staging RDS. Hostile execution-node groups must never be included."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Additional staging resource tags."
  type        = map(string)
  default     = {}
}
