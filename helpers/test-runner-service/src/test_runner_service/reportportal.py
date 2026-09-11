"""Read ReportPortal launch status without coupling the runner to the pytest agent."""

from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from test_runner_service.models import ReportPortalStatus
from test_runner_service.settings import Settings


class _Launch(BaseModel):
    id: int = Field(gt=0)
    name: str
    status: str


class _LaunchPage(BaseModel):
    content: list[_Launch]


def launches_url(settings: Settings) -> str | None:
    if not settings.reportportal_enabled or settings.reportportal_public_url is None:
        return None
    origin = str(settings.reportportal_public_url).rstrip("/")
    return f"{origin}/ui/#{settings.reportportal_project}/launches/all"


def read_reportportal_result(settings: Settings, operation_id: str) -> dict[str, object]:
    """Look up this operation only; reporting errors must not replace the pytest outcome."""
    if not settings.reportportal_enabled:
        return {}
    try:
        launch = _find_launch(settings, operation_id)
        if launch is None:
            return {
                "reportportal_status": ReportPortalStatus.UNAVAILABLE,
                "reportportal_message": "No ReportPortal launch was found for this operation",
            }
        finished = launch.status in {"PASSED", "FAILED", "SKIPPED", "WARN", "INFO"}
        return {
            "reportportal_status": (
                ReportPortalStatus.FINISHED if finished else ReportPortalStatus.INCOMPLETE
            ),
            "reportportal_url": f"{launches_url(settings)}/{launch.id}",
            "reportportal_message": (
                "ReportPortal launch finished; delivery of every log is not verified"
                if finished
                else "ReportPortal launch is still running or was interrupted"
            ),
        }
    except Exception:
        # Never propagate response bodies, request headers, or credentials to operation state.
        return {
            "reportportal_status": ReportPortalStatus.UNAVAILABLE,
            "reportportal_message": "Could not read ReportPortal launch; check service access",
        }


def _find_launch(settings: Settings, operation_id: str) -> _Launch | None:
    endpoint = settings.reportportal_endpoint
    token = settings.reportportal_api_key
    if endpoint is None or endpoint.host is None or token is None:
        raise ValueError("ReportPortal connection is not configured")
    connection_type = HTTPSConnection if endpoint.scheme == "https" else HTTPConnection
    connection = connection_type(endpoint.host, endpoint.port, timeout=5)
    query = urlencode({"filter.eq.name": operation_id, "page.size": 2})
    prefix = (endpoint.path or "").rstrip("/")
    path = f"{prefix}/api/v1/{settings.reportportal_project}/launch?{query}"
    try:
        # http.client does not follow redirects; credentials stay on the configured endpoint.
        connection.request(
            "GET", path, headers={"Authorization": f"Bearer {token.get_secret_value()}"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("ReportPortal lookup failed")
        page = _LaunchPage.model_validate_json(response.read(65_537))
        matches = [launch for launch in page.content if launch.name == operation_id]
        return matches[0] if len(matches) == 1 else None
    finally:
        connection.close()
