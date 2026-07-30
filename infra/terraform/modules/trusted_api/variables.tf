variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "ingress_subnet_ids" { type = list(string) }
variable "control_subnet_ids" { type = list(string) }
variable "image" {
  type        = string
  description = "Digest-pinned FastAPI image."
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "The API image must be pinned by sha256 digest."
  }
}
variable "certificate_arn" { type = string }
variable "allowed_ingress_cidrs" { type = list(string) }
variable "database_secret_arn" { type = string }
variable "valkey_url_secret_arn" { type = string }
variable "oidc_issuer" { type = string }
variable "oidc_audience" { type = string }
variable "container_port" { type = number, default = 8002 }
variable "desired_count" { type = number, default = 2 }
variable "tags" { type = map(string), default = {} }
