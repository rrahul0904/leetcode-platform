variable "name_prefix" {
  description = "Environment-qualified prefix for execution image repositories."
  type        = string
}

variable "untagged_image_retention_days" {
  description = "Days to retain untagged execution images before lifecycle cleanup."
  type        = number
  default     = 7

  validation {
    condition     = var.untagged_image_retention_days >= 1
    error_message = "The untagged image retention period must be at least one day."
  }
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
