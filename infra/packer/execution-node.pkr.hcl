packer {
  required_version = ">= 1.11.0"

  required_plugins {
    amazon = {
      version = ">= 1.3.0, < 2.0.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

variable "instance_type" {
  type    = string
  default = "m7i.large"
}

variable "gvisor_archive_url" {
  type        = string
  description = "Immutable HTTPS URL for the gVisor tar.bz2 release archive."

  validation {
    condition     = can(regex("^https://", var.gvisor_archive_url))
    error_message = "The gVisor archive URL must use HTTPS."
  }
}

variable "gvisor_sha256" {
  type        = string
  description = "Lowercase SHA-256 checksum of the exact gVisor archive."

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.gvisor_sha256))
    error_message = "The gVisor checksum must be a 64-character lowercase hexadecimal SHA-256."
  }
}

variable "ami_name_prefix" {
  type    = string
  default = "rigor-eks-gvisor"
}

source "amazon-ebs" "execution_node" {
  region        = var.aws_region
  instance_type = var.instance_type
  ssh_username  = "ec2-user"

  source_ami_filter {
    filters = {
      architecture        = "x86_64"
      name                = "amazon-eks-node-al2023-x86_64-standard-${var.kubernetes_version}-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["602401143452"]
  }

  ami_name = "${var.ami_name_prefix}-${var.kubernetes_version}-${formatdate("YYYYMMDDhhmmss", timestamp())}"

  imds_support = "v2.0"

  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_type           = "gp3"
    volume_size           = 60
    delete_on_termination = true
    encrypted             = true
  }

  tags = {
    Name                  = "${var.ami_name_prefix}-${var.kubernetes_version}"
    Plane                 = "untrusted-execution"
    "rigor.io/gvisor"     = "true"
    "rigor.io/kubernetes" = var.kubernetes_version
  }
}

build {
  name    = "rigor-gvisor-execution-node"
  sources = ["source.amazon-ebs.execution_node"]

  provisioner "shell" {
    environment_vars = [
      "GVISOR_ARCHIVE_URL=${var.gvisor_archive_url}",
      "GVISOR_SHA256=${var.gvisor_sha256}",
    ]
    script = "${path.root}/scripts/install-gvisor.sh"
  }

  provisioner "shell" {
    inline = [
      "set -euo pipefail",
      "sudo /usr/local/bin/runsc --version",
      "test -x /usr/local/bin/containerd-shim-runsc-v1",
      "test -d /usr/local/bin/gvisor-bin",
      "sudo grep -F 'io.containerd.runsc.v1' /etc/eks/nodeadm.d/20-runsc.yaml",
      "sudo grep -F 'runtimes.runsc' /etc/eks/nodeadm.d/20-runsc.yaml",
    ]
  }
}
