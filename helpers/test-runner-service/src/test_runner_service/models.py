from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
SCENARIO_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


class OperationType(StrEnum):
    BUILD_IMAGE = "build_image"
    PULL_IMAGE = "pull_image"
    RUN_TESTS = "run_tests"


class OperationStatus(StrEnum):
    BUILDING = "building"
    PULLING = "pulling"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        return self in {
            self.SUCCEEDED,
            self.PASSED,
            self.FAILED,
            self.CANCELLED,
            self.TIMED_OUT,
            self.INFRASTRUCTURE_ERROR,
            self.INTERRUPTED,
        }


class ReportStatus(StrEnum):
    PUBLISHED = "published"
    FAILED = "failed"


class ReportPortalStatus(StrEnum):
    FINISHED = "finished"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class TestSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0


class OperationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    operation_id: str
    run_id: str | None = None
    operation_type: OperationType
    status: OperationStatus
    created_at: datetime
    started_at: datetime
    finished_at: datetime | None = None
    image_reference: str | None = None
    image_digest: str | None = None
    stand: str | None = None
    scenario: str | None = None
    container_name: str | None = None
    exit_code: int | None = None
    artifact_directory: str | None = None
    summary: TestSummary | None = None
    junit_message: str | None = None
    report_status: ReportStatus | None = None
    report_url: str | None = None
    report_message: str | None = None
    reportportal_status: ReportPortalStatus | None = None
    reportportal_url: str | None = None
    reportportal_message: str | None = None
    message: str | None = None

    @classmethod
    def started(
        cls,
        operation_id: str,
        operation_type: OperationType,
        status: OperationStatus,
        *,
        run_id: str | None = None,
        image_reference: str | None = None,
        stand: str | None = None,
        scenario: str | None = None,
        container_name: str | None = None,
        message: str | None = None,
    ) -> OperationState:
        now = datetime.now(UTC)
        return cls(
            operation_id=operation_id,
            run_id=run_id,
            operation_type=operation_type,
            status=status,
            created_at=now,
            started_at=now,
            image_reference=image_reference,
            stand=stand,
            scenario=scenario,
            container_name=container_name,
            message=message,
        )


class BuildImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: Literal["working-tree"] = "working-tree"


class PullImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str = Field(min_length=1, max_length=512)


class RunTestsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: str = Field(
        min_length=1,
        max_length=512,
        examples=["sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"],
    )
    stand: str = Field(pattern=NAME_PATTERN, max_length=128, examples=["virtual-stand"])
    scenario: str = Field(
        pattern=SCENARIO_PATTERN,
        max_length=128,
        examples=["virtual-smoke"],
    )


class AcceptedOperation(BaseModel):
    operation_id: str
    status: OperationStatus
    current_url: str = "/v1/current"
    events_url: str = "/v1/current/events"


class ArtifactItem(BaseModel):
    name: str
    size: int
    download_url: str


class ArtifactList(BaseModel):
    items: list[ArtifactItem]


class ArtifactRun(BaseModel):
    run_id: str
    modified_at: datetime
    items: list[ArtifactItem]


class ArtifactRunList(BaseModel):
    items: list[ArtifactRun]


class UiConfig(BaseModel):
    allure_reports_url: str | None = None
    reportportal_launches_url: str | None = None
