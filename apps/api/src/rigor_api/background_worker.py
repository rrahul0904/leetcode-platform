from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from .execution_sqs import SqsJsonClient, SqsReceivedMessage

logger = logging.getLogger("skillforge.background-worker")


class BackgroundJobError(ValueError):
    pass


@dataclass(frozen=True)
class BackgroundJob:
    job_type: str
    payload: dict[str, Any]


def parse_background_job(raw: str) -> BackgroundJob:
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BackgroundJobError("Background job is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise BackgroundJobError("Background job must be a JSON object.")
    job_type = value.get("type")
    payload = value.get("payload", {})
    if not isinstance(job_type, str) or not job_type.strip():
        raise BackgroundJobError("Background job type is required.")
    if not isinstance(payload, dict):
        raise BackgroundJobError("Background job payload must be an object.")
    return BackgroundJob(job_type=job_type.strip(), payload=payload)


@dataclass(frozen=True)
class BackgroundWorkerSettings:
    queue_url: str
    aws_region: str
    wait_seconds: int = 20
    visibility_seconds: int = 60

    @classmethod
    def discover(cls) -> "BackgroundWorkerSettings":
        queue_url = os.getenv("RIGOR_BACKGROUND_QUEUE_URL", "")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
        if not queue_url:
            raise RuntimeError("RIGOR_BACKGROUND_QUEUE_URL is required.")
        if not region:
            raise RuntimeError("AWS_REGION is required.")
        return cls(queue_url=queue_url, aws_region=region)


class BackgroundWorker:
    """Trusted Fargate worker for ordinary SaaS jobs, never candidate source code.

    The first production contract deliberately supports an infrastructure ping only.
    Additional import/export/evaluation handlers must be registered explicitly and
    tested before messages of those types are acknowledged. Unknown messages remain
    visible for retry and eventually move to the queue DLQ.
    """

    def __init__(self, settings: BackgroundWorkerSettings, queue: SqsJsonClient) -> None:
        self.settings = settings
        self.queue = queue

    @classmethod
    def discover(cls) -> "BackgroundWorker":
        settings = BackgroundWorkerSettings.discover()
        queue = SqsJsonClient(queue_url=settings.queue_url, region=settings.aws_region)
        return cls(settings, queue)

    def process(self, message: SqsReceivedMessage) -> bool:
        try:
            job = parse_background_job(message.body)
        except BackgroundJobError:
            logger.exception(
                "background.invalid_job",
                extra={"message_id": message.message_id},
            )
            return False

        if job.job_type != "system.ping":
            logger.error(
                "background.unsupported_job",
                extra={"message_id": message.message_id, "job_type": job.job_type},
            )
            return False

        logger.info(
            "background.ping",
            extra={"message_id": message.message_id, "payload": job.payload},
        )
        self.queue.delete_message(message.receipt_handle)
        return True

    def run_forever(self) -> None:
        logger.info("background.worker_started")
        while True:
            try:
                messages = self.queue.receive_messages(
                    maximum=10,
                    wait_seconds=self.settings.wait_seconds,
                    visibility_timeout=self.settings.visibility_seconds,
                )
                for message in messages:
                    self.process(message)
            except Exception:
                logger.exception("background.poll_failed")
                time.sleep(2)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    BackgroundWorker.discover().run_forever()


if __name__ == "__main__":
    main()
