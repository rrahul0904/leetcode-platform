variable "name" { type = string }
variable "execution_queue_name" { type = string }
variable "execution_dlq_name" { type = string }
variable "db_instance_identifier" { type = string }
variable "valkey_replication_group_id" { type = string }

variable "queue_depth_threshold" {
  type    = number
  default = 100
}

variable "queue_age_threshold_seconds" {
  type    = number
  default = 60
}

variable "db_cpu_threshold_percent" {
  type    = number
  default = 80
}

variable "db_free_storage_threshold_bytes" {
  type    = number
  default = 21474836480
}

variable "tags" {
  type    = map(string)
  default = {}
}
