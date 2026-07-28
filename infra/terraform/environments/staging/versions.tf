terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.55.0"
    }
  }

  # Configure bucket/key/region/locking explicitly during terraform init.
  # State infrastructure is intentionally not bootstrapped by this stack.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Rigor"
      Environment = "staging"
      ManagedBy   = "Terraform"
    }
  }
}
