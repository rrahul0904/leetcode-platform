resource "aws_kms_key" "eks" {
  description             = "${var.name_prefix} EKS Kubernetes secret encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-eks"
    Plane = "execution"
  })
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.name_prefix}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.name_prefix}/cluster"
  retention_in_days = 30

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}

resource "aws_iam_role" "cluster" {
  name = "${var.name_prefix}-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "trusted_nodes" {
  name = "${var.name_prefix}-trusted-nodes"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}

resource "aws_iam_role" "execution_nodes" {
  name = "${var.name_prefix}-execution-nodes"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, {
    Plane = "untrusted-execution"
  })
}

locals {
  node_policy_arns = toset([
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly",
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
  ])
}

resource "aws_iam_role_policy_attachment" "trusted_nodes" {
  for_each = local.node_policy_arns

  role       = aws_iam_role.trusted_nodes.name
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "execution_nodes" {
  for_each = local.node_policy_arns

  role       = aws_iam_role.execution_nodes.name
  policy_arn = each.value
}

resource "aws_security_group" "trusted_nodes" {
  name_prefix = "${var.name_prefix}-trusted-node-"
  description = "Trusted execution-controller EKS nodes."
  vpc_id      = var.vpc_id

  ingress {
    description = "Trusted node-to-node traffic"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    self        = true
  }

  egress {
    description = "Route-table constrained node egress"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-trusted-nodes"
    Plane = "trusted-control"
  })
}

resource "aws_security_group" "execution_nodes" {
  name_prefix = "${var.name_prefix}-execution-node-"
  description = "Dedicated hostile-execution EKS nodes."
  vpc_id      = var.vpc_id

  ingress {
    description = "Execution node-to-node traffic"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    self        = true
  }

  # 0.0.0.0/0 here is a security-group permission, not a route. The execution
  # subnet route table has no Internet/NAT default route; it contains only VPC
  # local routing plus the S3 gateway endpoint required for ECR image layers.
  egress {
    description = "Route-table constrained node egress"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-execution-nodes"
    Plane = "untrusted-execution"
  })
}

resource "aws_eks_cluster" "this" {
  name     = var.name_prefix
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = false
  }

  kubernetes_network_config {
    service_ipv4_cidr = var.service_ipv4_cidr
  }

  vpc_config {
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.endpoint_public_access ? var.endpoint_public_access_cidrs : []
    subnet_ids              = var.control_subnet_ids
  }

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  depends_on = [
    aws_cloudwatch_log_group.cluster,
    aws_iam_role_policy_attachment.cluster,
  ]

  tags = merge(var.tags, {
    Plane = "execution"
  })
}

resource "aws_security_group_rule" "trusted_from_cluster_kubelet" {
  type                     = "ingress"
  description              = "EKS control plane to trusted kubelet"
  security_group_id        = aws_security_group.trusted_nodes.id
  source_security_group_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  protocol                 = "tcp"
  from_port                = 10250
  to_port                  = 10250
}

resource "aws_security_group_rule" "execution_from_cluster_kubelet" {
  type                     = "ingress"
  description              = "EKS control plane to execution kubelet"
  security_group_id        = aws_security_group.execution_nodes.id
  source_security_group_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  protocol                 = "tcp"
  from_port                = 10250
  to_port                  = 10250
}

resource "aws_security_group_rule" "cluster_from_trusted_nodes" {
  type                     = "ingress"
  description              = "Trusted nodes to Kubernetes API"
  security_group_id        = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  source_security_group_id = aws_security_group.trusted_nodes.id
  protocol                 = "tcp"
  from_port                = 443
  to_port                  = 443
}

resource "aws_security_group_rule" "cluster_from_execution_nodes" {
  type                     = "ingress"
  description              = "Execution nodes to Kubernetes API for kubelet operation"
  security_group_id        = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  source_security_group_id = aws_security_group.execution_nodes.id
  protocol                 = "tcp"
  from_port                = 443
  to_port                  = 443
}

resource "aws_launch_template" "trusted" {
  name_prefix = "${var.name_prefix}-trusted-"

  vpc_security_group_ids = [aws_security_group.trusted_nodes.id]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      delete_on_termination = true
      encrypted             = true
      volume_size           = 40
      volume_type           = "gp3"
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name  = "${var.name_prefix}-trusted-node"
      Plane = "trusted-control"
    })
  }

  tags = var.tags
}

resource "aws_eks_node_group" "trusted" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "trusted-control"
  node_role_arn   = aws_iam_role.trusted_nodes.arn
  subnet_ids      = var.control_subnet_ids
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  instance_types  = var.trusted_instance_types

  scaling_config {
    desired_size = var.trusted_desired_size
    min_size     = var.trusted_min_size
    max_size     = var.trusted_max_size
  }

  update_config {
    max_unavailable_percentage = 50
  }

  labels = {
    workload = "trusted-execution-control"
  }

  taint {
    key    = "workload"
    value  = "trusted-execution-control"
    effect = "NO_SCHEDULE"
  }

  launch_template {
    id      = aws_launch_template.trusted.id
    version = tostring(aws_launch_template.trusted.latest_version)
  }

  depends_on = [
    aws_iam_role_policy_attachment.trusted_nodes,
    aws_security_group_rule.trusted_from_cluster_kubelet,
    aws_security_group_rule.cluster_from_trusted_nodes,
  ]

  tags = merge(var.tags, {
    Plane = "trusted-control"
  })
}

locals {
  execution_node_user_data = <<-EOT
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="RIGORBOUNDARY"

--RIGORBOUNDARY
Content-Type: application/node.eks.aws

---
apiVersion: node.eks.aws/v1alpha1
kind: NodeConfig
spec:
  cluster:
    name: ${aws_eks_cluster.this.name}
    apiServerEndpoint: ${aws_eks_cluster.this.endpoint}
    certificateAuthority: ${aws_eks_cluster.this.certificate_authority[0].data}
    cidr: ${var.service_ipv4_cidr}
  kubelet:
    flags:
    - --node-labels=workload=untrusted-execution,rigor.io/gvisor=true
    - --register-with-taints=workload=untrusted-execution:NoSchedule

--RIGORBOUNDARY--
EOT
}

resource "aws_launch_template" "execution" {
  count = var.execution_node_ami_id == "" ? 0 : 1

  name_prefix   = "${var.name_prefix}-execution-"
  image_id      = var.execution_node_ami_id
  instance_type = var.execution_instance_type
  user_data     = base64encode(local.execution_node_user_data)

  vpc_security_group_ids = [aws_security_group.execution_nodes.id]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      delete_on_termination = true
      encrypted             = true
      volume_size           = 60
      volume_type           = "gp3"
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name  = "${var.name_prefix}-execution-node"
      Plane = "untrusted-execution"
    })
  }

  tags = var.tags
}

resource "aws_eks_node_group" "execution" {
  count = var.execution_node_ami_id == "" ? 0 : 1

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "untrusted-execution"
  node_role_arn   = aws_iam_role.execution_nodes.arn
  subnet_ids      = var.execution_subnet_ids
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = var.execution_desired_size
    min_size     = var.execution_min_size
    max_size     = var.execution_max_size
  }

  update_config {
    max_unavailable_percentage = 50
  }

  labels = {
    workload          = "untrusted-execution"
    "rigor.io/gvisor" = "true"
  }

  taint {
    key    = "workload"
    value  = "untrusted-execution"
    effect = "NO_SCHEDULE"
  }

  launch_template {
    id      = aws_launch_template.execution[0].id
    version = tostring(aws_launch_template.execution[0].latest_version)
  }

  depends_on = [
    aws_iam_role_policy_attachment.execution_nodes,
    aws_security_group_rule.execution_from_cluster_kubelet,
    aws_security_group_rule.cluster_from_execution_nodes,
  ]

  tags = merge(var.tags, {
    Plane = "untrusted-execution"
  })
}

resource "aws_eks_access_entry" "admin" {
  count = var.cluster_admin_principal_arn == "" ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.cluster_admin_principal_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  count = var.cluster_admin_principal_arn == "" ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.cluster_admin_principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.admin]
}
