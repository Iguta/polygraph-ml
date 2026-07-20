from __future__ import annotations

import asyncio

from polygraphml.config import get_settings
from polygraphml.queueing import AuditQueue, LocalAuditQueue, SqsAuditQueue
from polygraphml.storage.artifacts import ArtifactStore, LocalArtifactStore, S3ArtifactStore
from polygraphml.storage.base import DomainRepository
from polygraphml.storage.dynamodb import DynamoRepository
from polygraphml.storage.repository import SqliteRepository
from polygraphml.worker.coordinator import AuditCoordinator, run_polling_worker


async def main() -> None:
    settings = get_settings()
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
    coordinator = AuditCoordinator(
        settings,
        repository,
        artifacts,
        queue,
    )
    await run_polling_worker(coordinator, queue, settings.worker_poll_seconds)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
