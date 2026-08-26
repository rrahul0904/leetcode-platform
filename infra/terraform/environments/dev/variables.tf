variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
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
