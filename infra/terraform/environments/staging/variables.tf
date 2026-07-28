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

variable "tags" {
  description = "Additional staging resource tags."
  type        = map(string)
  default     = {}
}
