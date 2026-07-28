variable "name" {
  description = "Environment-qualified Rigor infrastructure name."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR for the control/execution VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones used by the environment."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "Rigor environments must use two or three availability zones."
  }
}

variable "enable_nat_gateway_per_az" {
  description = "Use one NAT gateway per AZ for trusted application subnets. Production should keep this true."
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
