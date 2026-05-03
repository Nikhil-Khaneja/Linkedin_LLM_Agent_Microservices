variable "aws_region" {
  default = "us-east-1"
}

variable "project" {
  default = "linkedin-sim"
}

variable "openrouter_api_key" {
  description = "OpenRouter API key for AI service"
  default     = ""
  sensitive   = true
}

variable "db_password" {
  description = "RDS MySQL root password"
  default     = "LinkedInSim2026!"
  sensitive   = true
}

locals {
  az_a = data.aws_availability_zones.available.names[0]
  az_b = data.aws_availability_zones.available.names[1]

  # All 8 backend services: name → port
  services = {
    auth_service                 = 8001
    member_profile_service       = 8002
    recruiter_company_service    = 8003
    jobs_service                 = 8004
    applications_service         = 8005
    messaging_connections_service = 8006
    analytics_service            = 8007
    ai_orchestrator_service      = 8008
  }

  # Common env block injected into every service task
  common_env = [
    { name = "EVENT_BUS_MODE",   value = "kafka" },
    { name = "KAFKA_BOOTSTRAP_SERVERS", value = "kafka:9092" },
    { name = "CACHE_MODE",       value = "redis" },
    { name = "MONGO_DATABASE",   value = "linkedin_sim_docs" },
    { name = "MINIO_ENDPOINT",   value = "minio:9000" },
    { name = "MINIO_ROOT_USER",  value = "minioadmin" },
    { name = "MINIO_ROOT_PASSWORD", value = "minioadmin" },
    { name = "MINIO_BUCKET_PROFILE", value = "profile-media" },
    { name = "MINIO_BUCKET_RESUME",  value = "resume-media" },
    { name = "MINIO_SECURE",     value = "false" },
    { name = "APP_VERSION",      value = "1.0.0" },
    { name = "JWT_ISSUER",       value = "owner1-auth" },
    { name = "JWT_AUDIENCE",     value = "linkedin-clone" },
    { name = "MYSQL_PORT",       value = "3306" },
    { name = "MYSQL_DATABASE",   value = "linkedin_sim" },
    { name = "MYSQL_USER",       value = "root" },
  ]
}
