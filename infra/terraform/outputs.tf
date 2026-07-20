output "api_url" { value = "https://${var.api_hostname}" }
output "artifact_bucket" { value = aws_s3_bucket.artifacts.id }
output "state_table" { value = aws_dynamodb_table.state.name }
output "audit_queue_url" { value = aws_sqs_queue.audit.url }
output "audit_dlq_url" { value = aws_sqs_queue.dlq.url }
output "queue_visibility_seconds" { value = var.queue_visibility_seconds }
output "openai_secret_arn" {
  value     = aws_secretsmanager_secret.openai.arn
  sensitive = true
}
output "api_repository_url" { value = aws_ecr_repository.api.repository_url }
output "worker_repository_url" { value = aws_ecr_repository.worker.repository_url }
