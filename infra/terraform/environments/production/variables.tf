variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "allowed_origins" {
  description = "Exact production web origins allowed by FastAPI CORS."
  type        = list(string)
}

variable "oidc_issuer" {
  description = "Production OIDC issuer. Must use a production-specific client configuration."
  type        = string
}

variable "oidc_audience" {
  description = "Production API audience."
  type        = string
}

variable "oidc_jwks_url" {
  type     = string
  default  = null
  nullable = true
}

variable "certificate_arn" {
  description = "Production ACM certificate ARN for the application ALB."
  type        = string
  default     = null
  nullable    = true
}

variable "api_host" {
  type     = string
  default  = null
  nullable = true
}

variable "web_image" {
  description = "Immutable production web image, preferably repository@sha256:digest."
  type        = string
  default     = null
  nullable    = true
}

variable "api_image" {
  description = "Immutable production API image, preferably repository@sha256:digest."
  type        = string
  default     = null
  nullable    = true
}

variable "worker_image" {
  description = "Immutable trusted dispatcher image after the queued execution implementation passes staging isolation tests."
  type        = string
  default     = null
  nullable    = true
}

variable "enable_control_plane_compute" {
  description = "Must remain false until async SQS execution is implemented, tested in staging, and explicitly approved for production."
  type        = bool
  default     = false
}

variable "kubernetes_version" {
  type     = string
  default  = null
  nullable = true
}

variable "gvisor_node_ami_id" {
  description = "Validated production AMI with containerd + runsc integration."
  type        = string
  default     = null
  nullable    = true
}

variable "gvisor_node_user_data" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}
