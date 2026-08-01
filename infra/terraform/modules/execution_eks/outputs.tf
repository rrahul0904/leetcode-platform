output "cluster_name" {
  description = "Staging execution EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Staging execution EKS API endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 cluster certificate authority data."
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "EKS-managed cluster security group ID."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "trusted_node_security_group_id" {
  description = "Security group attached only to trusted controller nodes."
  value       = aws_security_group.trusted_nodes.id
}

output "execution_node_security_group_id" {
  description = "Security group attached only to hostile execution nodes."
  value       = aws_security_group.execution_nodes.id
}

output "trusted_node_role_arn" {
  description = "IAM role used by trusted EKS nodes."
  value       = aws_iam_role.trusted_nodes.arn
}

output "execution_node_role_arn" {
  description = "IAM role used by hostile execution nodes; it intentionally has no queue/database application policy."
  value       = aws_iam_role.execution_nodes.arn
}

output "execution_node_group_enabled" {
  description = "Whether a custom gVisor-ready execution AMI was supplied and the node group is declared."
  value       = var.execution_node_ami_id != ""
}
