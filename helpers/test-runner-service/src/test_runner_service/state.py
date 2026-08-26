import json
import os
from pathlib import Path

from test_runner_service.models import OperationState, OperationStatus


class StateStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.state_file = directory / "current.json"
        self.log_file = directory / "current.log"

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            self.log_file.touch()

    def read(self) -> OperationState | None:
        try:
            content = self.state_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return OperationState.model_validate_json(content)

    def write(self, state: OperationState) -> None:
        temporary = self.state_file.with_suffix(".json.tmp")
        payload = state.model_dump(mode="json")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.state_file)

    def reset_log(self) -> None:
        temporary = self.log_file.with_suffix(".log.tmp")
        temporary.write_text("", encoding="utf-8")
        temporary.replace(self.log_file)

    def mark_interrupted(self) -> OperationState | None:
        state = self.read()
        if state is None or state.status.is_terminal:
            return state
        interrupted = state.model_copy(
            update={
                "status": OperationStatus.INTERRUPTED,
                "message": "The service restarted while the operation was active",
            }
        )
        self.write(interrupted)
        return interrupted
