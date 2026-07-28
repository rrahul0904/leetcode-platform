locals {
  tags = merge(var.tags, {
    "rigor:component"   = "execution-plane"
    "rigor:trust-plane" = "hostile-execution"
  })

  create_execution_nodes = var.gvisor_node_ami_id != null && var.gvisor_node_user_data != null
}

data "aws_iam_policy_document" "cluster_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name_prefix        = "${var.name}-execution-cluster-"
  assume_role_policy = data.aws_iam_policy_document.cluster_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

data "aws_iam_policy_document" "cluster_kms" {
  statement {
    sid    = "UseExecutionEnvelopeKey"
    effect = "Allow"
    actions = [
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "cluster_kms" {
  name   = "execution-envelope-kms"
  role   = aws_iam_role.cluster.id
  policy = data.aws_iam_policy_document.cluster_kms.json
}

resource "aws_security_group" "cluster" {
  name_prefix = "${var.name}-execution-cluster-"
  description = "Additional security group for the private execution EKS control plane."
  vpc_id      = var.vpc_id

  egress {
    description = "Private VPC control traffic only"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = local.tags
}

resource "aws_eks_cluster" "this" {
  name     = "${var.name}-execution"
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = false
  }

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  encryption_config {
    provider {
      key_arn = var.kms_key_arn
    }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]

  tags = local.tags

  depends_on = [
    aws_iam_role_policy_attachment.cluster,
    aws_iam_role_policy.cluster_kms,
  ]
}

data "aws_iam_policy_document" "node_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name_prefix        = "${var.name}-execution-node-"
  assume_role_policy = data.aws_iam_policy_document.node_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_security_group" "execution_nodes" {
  name_prefix = "${var.name}-execution-node-"
  description = "Execution nodes have no internet route; pod egress is additionally default-denied."
  vpc_id      = var.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "nodes_private_vpc" {
  security_group_id = aws_security_group.execution_nodes.id
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
  description       = "Private VPC services only; execution route tables have no internet path"
}

resource "aws_vpc_security_group_egress_rule" "nodes_s3_endpoint" {
  security_group_id = aws_security_group.execution_nodes.id
  prefix_list_id    = var.s3_prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "TLS to S3 through the VPC gateway endpoint for ECR image layers"
}

resource "aws_vpc_security_group_ingress_rule" "nodes_self" {
  security_group_id            = aws_security_group.execution_nodes.id
  referenced_security_group_id = aws_security_group.execution_nodes.id
  ip_protocol                  = "-1"
  description                  = "Node/CNI traffic; candidate pods remain isolated by Kubernetes NetworkPolicy"
}

resource "aws_vpc_security_group_ingress_rule" "cluster_from_nodes" {
  security_group_id            = aws_security_group.cluster.id
  referenced_security_group_id = aws_security_group.execution_nodes.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Kubelet/node access to private Kubernetes API"
}

resource "aws_vpc_security_group_ingress_rule" "nodes_from_cluster" {
  security_group_id            = aws_security_group.execution_nodes.id
  referenced_security_group_id = aws_security_group.cluster.id
  from_port                    = 10250
  to_port                      = 10250
  ip_protocol                  = "tcp"
  description                  = "Private control-plane kubelet management"
}

resource "aws_launch_template" "gvisor" {
  count = local.create_execution_nodes ? 1 : 0

  name_prefix = "${var.name}-gvisor-"
  image_id    = var.gvisor_node_ami_id
  user_data   = base64encode(var.gvisor_node_user_data)

  vpc_security_group_ids = [
    aws_security_group.execution_nodes.id,
    aws_eks_cluster.this.vpc_config[0].cluster_security_group_id,
  ]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      encrypted             = true
      delete_on_termination = true
      volume_size           = 40
      volume_type           = "gp3"
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.tags, {
      "rigor:gvisor-validated" = "required-before-apply"
    })
  }

  tags = local.tags
}

resource "aws_eks_node_group" "gvisor" {
  count = local.create_execution_nodes ? 1 : 0

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "gvisor"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = var.node_instance_types

  launch_template {
    id      = aws_launch_template.gvisor[0].id
    version = aws_launch_template.gvisor[0].latest_version
  }

  scaling_config {
    min_size     = var.node_min_size
    desired_size = var.node_desired_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "rigor.dev/workload" = "untrusted-execution"
    "rigor.dev/runtime"  = "gvisor"
  }

  taint {
    key    = "rigor.dev/untrusted-execution"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  tags = local.tags

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_ecr,
    aws_iam_role_policy_attachment.node_cni,
  ]
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "vpc-cni"

  configuration_values = jsonencode({
    enableNetworkPolicy = "true"
  })

  tags = local.tags
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "kube-proxy"
  tags         = local.tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "coredns"
  tags         = local.tags
}

resource "aws_eks_access_entry" "orchestrator" {
  count = var.orchestrator_principal_arn == null ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.orchestrator_principal_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "orchestrator" {
  count = var.orchestrator_principal_arn == null ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.orchestrator_principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["rigor-execution"]
  }

  depends_on = [aws_eks_access_entry.orchestrator]
}
