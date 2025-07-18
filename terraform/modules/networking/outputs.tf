# Networking Module Outputs

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway"
  value       = aws_internet_gateway.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "database_subnet_ids" {
  description = "IDs of the database subnets"
  value       = aws_subnet.database[*].id
}

output "public_subnet_cidrs" {
  description = "CIDR blocks of the public subnets"
  value       = aws_subnet.public[*].cidr_block
}

output "private_subnet_cidrs" {
  description = "CIDR blocks of the private subnets"
  value       = aws_subnet.private[*].cidr_block
}

output "database_subnet_cidrs" {
  description = "CIDR blocks of the database subnets"
  value       = aws_subnet.database[*].cidr_block
}

output "nat_gateway_ids" {
  description = "IDs of the NAT Gateways"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = "Public IPs of the NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

output "public_route_table_id" {
  description = "ID of the public route table"
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "IDs of the private route tables"
  value       = aws_route_table.private[*].id
}

output "database_route_table_id" {
  description = "ID of the database route table"
  value       = aws_route_table.database.id
}

output "vpc_endpoints" {
  description = "VPC endpoint details"
  value = merge(
    {
      s3_gateway_endpoint_id       = aws_vpc_endpoint.s3.id
      dynamodb_gateway_endpoint_id = aws_vpc_endpoint.dynamodb.id
    },
    {
      for k, v in aws_vpc_endpoint.interface_endpoints : "${k}_interface_endpoint_id" => v.id
    }
  )
}

output "security_groups" {
  description = "Security group IDs for different services"
  value = {
    vpc_endpoints_sg_id = aws_security_group.vpc_endpoints.id
    lambda_sg_id        = aws_security_group.lambda.id
    glue_sg_id          = aws_security_group.glue.id
    sagemaker_sg_id     = aws_security_group.sagemaker.id
    database_sg_id      = aws_security_group.database.id
  }
}

output "network_acls" {
  description = "Network ACL IDs"
  value = {
    private_nacl_id  = aws_network_acl.private.id
    database_nacl_id = aws_network_acl.database.id
  }
}

output "vpc_flow_logs" {
  description = "VPC Flow Logs configuration"
  value = {
    enabled           = var.enable_vpc_flow_logs
    log_group_name    = aws_cloudwatch_log_group.vpc_flow_logs.name
    log_group_arn     = aws_cloudwatch_log_group.vpc_flow_logs.arn
    flow_log_id       = var.enable_vpc_flow_logs ? aws_flow_log.vpc[0].id : null
  }
}

output "network_security_summary" {
  description = "Summary of network security configuration"
  value = {
    vpc_endpoints_count     = length(local.interface_endpoints) + 2 # +2 for S3 and DynamoDB gateway endpoints
    security_groups_count   = 5
    network_acls_count      = 2
    vpc_flow_logs_enabled   = var.enable_vpc_flow_logs
    private_subnets_count   = length(aws_subnet.private)
    database_subnets_count  = length(aws_subnet.database)
    nat_gateways_count      = var.enable_nat_gateway ? length(aws_nat_gateway.main) : 0
  }
}