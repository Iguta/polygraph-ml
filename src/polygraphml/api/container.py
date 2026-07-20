from __future__ import annotations

from dataclasses import dataclass

from polygraphml.benchmarks.catalog import BenchmarkCatalog
from polygraphml.config import Settings
from polygraphml.queueing import AuditQueue, LocalAuditQueue, SqsAuditQueue
from polygraphml.services.audits import AuditService
from polygraphml.services.projects import ProjectService
from polygraphml.storage.artifacts import ArtifactStore, LocalArtifactStore, S3ArtifactStore
from polygraphml.storage.base import DomainRepository
from polygraphml.storage.dynamodb import DynamoRepository
from polygraphml.storage.repository import SqliteRepository


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    repository: DomainRepository
    artifacts: ArtifactStore
    queue: AuditQueue
    projects: ProjectService
    audits: AuditService
    benchmarks: BenchmarkCatalog


def build_container(settings: Settings) -> AppContainer:
    if settings.storage_backend == "aws":
        if not settings.dynamodb_table:
            raise ValueError("AWS mode requires a DynamoDB table.")
        repository: DomainRepository = DynamoRepository(
            settings.dynamodb_table, settings.aws_region
        )
    else:
        repository = SqliteRepository(settings.database_path)
    if settings.storage_backend == "aws":
        if not settings.s3_bucket:
            raise ValueError("AWS mode requires an S3 bucket.")
        artifacts: ArtifactStore = S3ArtifactStore(
            settings.s3_bucket, settings.aws_region, settings.artifact_root
        )
    else:
        artifacts = LocalArtifactStore(settings.artifact_root)
    if settings.storage_backend == "aws":
        if not settings.sqs_queue_url or not settings.sqs_dlq_url:
            raise ValueError("AWS mode requires SQS queue and DLQ URLs.")
        queue: AuditQueue = SqsAuditQueue(
            settings.sqs_queue_url,
            settings.sqs_dlq_url,
            settings.worker_lease_seconds,
            region=settings.aws_region,
        )
    else:
        if not isinstance(repository, SqliteRepository):
            raise TypeError("Local queue requires the SQLite repository.")
        queue = LocalAuditQueue(repository, settings.worker_lease_seconds)
    benchmarks = BenchmarkCatalog()
    return AppContainer(
        settings=settings,
        repository=repository,
        artifacts=artifacts,
        queue=queue,
        projects=ProjectService(settings, repository, artifacts, benchmarks),
        audits=AuditService(repository, queue),
        benchmarks=benchmarks,
    )
