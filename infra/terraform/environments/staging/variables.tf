variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "allowed_origins" {
  description = "Exact staging web origins allowed by FastAPI CORS."
  type        = list(string)
}

variable "oidc_issuer" {
  description = "Staging OIDC issuer. Must not be the production issuer/client."
  type        = string
}

variable "oidc_audience" {
  description = "Staging API audience."
  type        = string
}

variable "oidc_jwks_url" {
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

variable "web_image" {
  description = "Immutable staging web image, preferably repository@sha256:digest."
  type        = string
  default     = null
  nullable    = true
}

variable "api_image" {
  description = "Immutable staging API image, preferably repository@sha256:digest."
  type        = string
  default     = null
  nullable    = true
}

variable "worker_image" {
  description = "Trusted execution dispatcher image after the async worker is implemented."
  type        = string
  default     = null
  nullable    = true
}

variable "enable_control_plane_compute" {
  description = "Remain false until queued execution replaces inline candidate execution."
  type        = bool
  default     = false
}

variable "kubernetes_version" {
  type     = string
  default  = null
  nullable = true
}

variable "gvisor_node_ami_id" {
  description = "Validated staging AMI with runsc/containerd integration."
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
