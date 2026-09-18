variable "zone_id" {
  type = string
}

variable "record_name" {
  type = string
}

variable "alias_dns_name" {
  type = string
}

variable "alias_zone_id" {
  type = string
}

resource "aws_route53_record" "this" {
  zone_id = var.zone_id
  name    = var.record_name
  type    = "A"

  alias {
    name                   = var.alias_dns_name
    zone_id                = var.alias_zone_id
    evaluate_target_health = true
  }
}
