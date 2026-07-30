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
