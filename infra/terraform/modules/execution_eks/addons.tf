locals {
  managed_addons = toset([
    "coredns",
    "eks-pod-identity-agent",
    "kube-proxy",
    "vpc-cni",
  ])
}

resource "aws_eks_addon" "managed" {
  for_each = local.managed_addons

  cluster_name = aws_eks_cluster.this.name
  addon_name   = each.value

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}

resource "aws_iam_role" "cloudwatch_observability" {
  name = "${var.name_prefix}-cloudwatch-observability"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "pods.eks.amazonaws.com"
      }
      Action = [
        "sts:AssumeRole",
        "sts:TagSession",
      ]
    }]
  })

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_observability" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_eks_addon" "cloudwatch_observability" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "amazon-cloudwatch-observability"

  pod_identity_association {
    role_arn        = aws_iam_role.cloudwatch_observability.arn
    service_account = "cloudwatch-agent"
  }

  depends_on = [
    aws_eks_addon.managed["eks-pod-identity-agent"],
    aws_iam_role_policy_attachment.cloudwatch_observability,
  ]

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}
