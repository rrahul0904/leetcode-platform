resource "terraform_data" "execution_staging_guard" {
  count = var.enable_execution_staging_infrastructure ? 1 : 0

  input = var.execution_node_ami_id

  lifecycle {
    precondition {
      condition     = var.execution_node_ami_id != ""
      error_message = "A custom EKS-compatible AMI prebuilt with runsc/containerd integration is required before enabling the hostile execution node group."
    }
  }
}

module "execution_network" {
  count  = var.enable_execution_staging_infrastructure ? 1 : 0
  source = "../../modules/execution_network"

  name_prefix = var.name_prefix
  tags = merge(var.tags, {
    Plane = "execution"
  })

  depends_on = [terraform_data.execution_staging_guard]
}

module "execution_eks" {
  count  = var.enable_execution_staging_infrastructure ? 1 : 0
  source = "../../modules/execution_eks"

  name_prefix          = "${var.name_prefix}-execution"
  vpc_id               = module.execution_network[0].vpc_id
  vpc_cidr             = module.execution_network[0].vpc_cidr
  control_subnet_ids   = module.execution_network[0].control_subnet_ids
  execution_subnet_ids = module.execution_network[0].execution_subnet_ids

  kubernetes_version           = "1.36"
  execution_node_ami_id        = var.execution_node_ami_id
  execution_min_size           = 1
  execution_desired_size       = 1
  execution_max_size           = 10
  cluster_admin_principal_arn  = var.cluster_admin_principal_arn
  endpoint_public_access       = length(var.eks_public_access_cidrs) > 0
  endpoint_public_access_cidrs = var.eks_public_access_cidrs

  tags = merge(var.tags, {
    Plane = "execution"
  })
}

module "execution_database" {
  count  = var.enable_execution_staging_infrastructure ? 1 : 0
  source = "../../modules/execution_database"

  name_prefix     = var.name_prefix
  vpc_id          = module.execution_network[0].vpc_id
  data_subnet_ids = module.execution_network[0].data_subnet_ids

  trusted_client_security_group_ids = setunion(
    toset([module.execution_eks[0].trusted_node_security_group_id]),
    var.additional_database_client_security_group_ids,
  )

  engine_version = "18.4"

  tags = merge(var.tags, {
    Plane = "data"
  })
}

resource "aws_iam_role" "execution_controller" {
  count = var.enable_execution_staging_infrastructure ? 1 : 0

  name = "${var.name_prefix}-execution-controller"

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

resource "aws_iam_role_policy" "execution_controller_publish" {
  count = var.enable_execution_staging_infrastructure ? 1 : 0

  name   = "execution-publish"
  role   = aws_iam_role.execution_controller[0].id
  policy = module.execution_queue.publisher_policy_json
}

resource "aws_iam_role_policy" "execution_controller_consume" {
  count = var.enable_execution_staging_infrastructure ? 1 : 0

  name   = "execution-consume"
  role   = aws_iam_role.execution_controller[0].id
  policy = module.execution_queue.consumer_policy_json
}

resource "aws_eks_pod_identity_association" "execution_controller" {
  count = var.enable_execution_staging_infrastructure ? 1 : 0

  cluster_name    = module.execution_eks[0].cluster_name
  namespace       = "rigor-system"
  service_account = "execution-controller"
  role_arn        = aws_iam_role.execution_controller[0].arn

  depends_on = [
    aws_iam_role_policy.execution_controller_publish,
    aws_iam_role_policy.execution_controller_consume,
  ]
}
