terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state so `terraform apply` is safe to run from CI or teammates'
  # machines without clobbering each other's local state files.
  backend "s3" {
    bucket = "mle-portfolio-tfstate"
    key    = "rag-service/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true  # cost tradeoff: single NAT for a portfolio
                                # project; use one-per-AZ for real prod HA
  enable_dns_hostnames = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project_name}-cluster"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      min_size       = 2
      max_size       = 6
      desired_size   = 3
      instance_types = ["t3.medium"]
      capacity_type  = "SPOT"  # ~70% cost savings, acceptable for stateless
                                # RAG service pods that tolerate interruption
    }
  }

  cluster_endpoint_public_access = true
}

resource "aws_ecr_repository" "rag_service" {
  name                 = "${var.project_name}/rag-service"
  image_tag_mutability = "IMMUTABLE"  # prevents accidental tag overwrites

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "expire_untagged" {
  repository = aws_ecr_repository.rag_service.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_s3_bucket" "dvc_storage" {
  bucket = "${var.project_name}-dvc-storage"
}

resource "aws_s3_bucket_versioning" "dvc_storage" {
  bucket = aws_s3_bucket.dvc_storage.id
  versioning_configuration { status = "Enabled" }
}
