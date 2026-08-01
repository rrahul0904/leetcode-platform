variable "name_prefix" {
  description = "Stable prefix for staging execution-network resources."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR for the staging execution VPC."
  type        = string
  default     = "10.72.0.0/16"
}

variable "control_subnet_cidrs" {
  description = "Private trusted-control subnet CIDRs, one per availability zone."
  type        = list(string)
  default     = ["10.72.0.0/20", "10.72.16.0/20"]

  validation {
    condition     = length(var.control_subnet_cidrs) >= 2
    error_message = "At least two control subnets are required."
  }
}

variable "execution_subnet_cidrs" {
  description = "Private hostile-execution subnet CIDRs with no default Internet route."
  type        = list(string)
  default     = ["10.72.32.0/20", "10.72.48.0/20"]

  validation {
    condition     = length(var.execution_subnet_cidrs) >= 2
    error_message = "At least two execution subnets are required."
  }
}

variable "data_subnet_cidrs" {
  description = "Private database subnet CIDRs."
  type        = list(string)
  default     = ["10.72.64.0/20", "10.72.80.0/20"]

  validation {
    condition     = length(var.data_subnet_cidrs) >= 2
    error_message = "At least two data subnets are required."
  }
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
