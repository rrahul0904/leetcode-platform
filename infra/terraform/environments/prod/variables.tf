variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "skillforge-prod"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "route53_zone_id" {
  type = string
}

variable "api_domain" {
  type = string
}

variable "api_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "valkey_auth_token" {
  type      = string
  sensitive = true
}

variable "clerk_issuer" {
  type = string
}

variable "clerk_jwks_url" {
  type = string
}

variable "jwt_audience" {
  type = string
}

variable "enable_execution_production_infrastructure" {
  description = "Explicit opt-in for the cost-bearing isolated EKS execution plane. Production deployment must enable this before candidate execution is exposed."
  type        = bool
  default     = false
}

variable "execution_node_ami_id" {
  description = "Custom EKS-compatible AL2023 AMI prebuilt with runsc/containerd integration. Required when the production execution plane is enabled."
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

variable "additional_execution_database_client_security_group_ids" {
  description = "Optional trusted migration/operator security groups allowed to reach the isolated execution database. Never include hostile execution nodes."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Additional production resource tags."
  type        = map(string)
  default     = {}
}
