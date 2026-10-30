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

variable "web_domain" {
  type = string
}

variable "web_image" {
  type = string
}

variable "clerk_publishable_key" {
  type = string
}
