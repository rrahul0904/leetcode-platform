variable "name" {
  type = string
}

variable "resource_arn" {
  description = "Regional ALB ARN protected by this WAF ACL."
  type        = string
}

variable "api_rate_limit" {
  description = "Coarse per-IP API requests per WAF rate window; application identity quotas remain authoritative."
  type        = number
  default     = 3000
}

variable "execution_rate_limit" {
  description = "Coarse per-IP execution requests per WAF rate window."
  type        = number
  default     = 300
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  tags = merge(var.tags, { "rigor:component" = "waf" })
}

resource "aws_wafv2_regex_pattern_set" "execution" {
  name  = "${var.name}-execution-paths"
  scope = "REGIONAL"

  regular_expression {
    regex_string = "^/api/v1/questions/[^/]+/(run|submissions)$"
  }

  tags = local.tags
}

resource "aws_wafv2_web_acl" "this" {
  name  = var.name
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "aws-common-rule-set"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-known-bad-inputs"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-ip-reputation"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "execution-rate-limit"
    priority = 40

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.execution_rate_limit
        aggregate_key_type = "IP"

        scope_down_statement {
          regex_pattern_set_reference_statement {
            arn = aws_wafv2_regex_pattern_set.execution.arn
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-execution-rate"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "api-rate-limit"
    priority = 50

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.api_rate_limit
        aggregate_key_type = "IP"

        scope_down_statement {
          byte_match_statement {
            positional_constraint = "STARTS_WITH"
            search_string         = "/api/"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-api-rate"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = var.name
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

resource "aws_wafv2_web_acl_association" "this" {
  resource_arn = var.resource_arn
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}

output "web_acl_arn" {
  value = aws_wafv2_web_acl.this.arn
}
