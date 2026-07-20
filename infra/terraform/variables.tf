variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Short environment name."
  type        = string
  default     = "hackathon"
}

variable "api_image" {
  description = "Immutable ECR API image URI including sha256 digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "api_image must be pinned by sha256 digest."
  }
}

variable "worker_image" {
  description = "Immutable ECR worker image URI including sha256 digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.worker_image))
    error_message = "worker_image must be pinned by sha256 digest."
  }
}

variable "cors_origins" {
  description = "Comma-separated Vercel preview/production origins."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the API hostname."
  type        = string
}

variable "api_hostname" {
  description = "Public API hostname covered by the ACM certificate."
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 public hosted zone that owns api_hostname."
  type        = string
}

variable "artifact_retention_days" {
  description = "Days before user artifacts expire."
  type        = number
  default     = 7
}

variable "queue_visibility_seconds" {
  description = "SQS visibility and worker lease duration derived from captured audit timing."
  type        = number
  default     = 300
  validation {
    condition     = var.queue_visibility_seconds >= 60 && var.queue_visibility_seconds <= 43200
    error_message = "queue_visibility_seconds must be between 60 and 43200."
  }
}

variable "session_rate_limit_per_five_minutes" {
  description = "Maximum anonymous session-creation requests per source IP per five minutes."
  type        = number
  default     = 100
}

variable "api_rate_limit_per_five_minutes" {
  description = "Maximum API requests per source IP per five minutes."
  type        = number
  default     = 2000
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "worker_desired_count" {
  type    = number
  default = 1
}
