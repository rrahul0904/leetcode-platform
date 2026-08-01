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

  # Amazon VPC CNI NetworkPolicy enforcement is opt-in. Without this setting,
  # Kubernetes accepts the sandbox default-deny policies but does not enforce
  # them. Keep the setting attached to the managed add-on so a newly-created
  # cluster fails safe instead of depending on an out-of-band console change.
  configuration_values = each.value == "vpc-cni" ? jsonencode({
    enableNetworkPolicy = "true"
  }) : null

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
