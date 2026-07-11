output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  value = aws_ecr_repository.rag_service.repository_url
}

output "dvc_bucket_name" {
  value = aws_s3_bucket.dvc_storage.bucket
}
