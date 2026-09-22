import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Workspace:
    project_id: str
    task_id: str
    root: Path


class WorkspaceManager:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure(self, project_id: str, task_id: str) -> Workspace:
        project_uuid = self._validate_id(project_id)
        task_uuid = self._validate_id(task_id)

        workspace_root = self.root / str(project_uuid) / str(task_uuid)
        workspace_root.mkdir(parents=True, exist_ok=True)

        resolved = workspace_root.resolve()
        if not self._is_within_root(resolved):
            raise WorkspaceError("Resolved workspace escapes the configured workspace root")

        metadata = resolved / ".titan-workspace.json"
        if not metadata.exists():
            metadata.write_text(
                json.dumps(
                    {
                        "project_id": str(project_uuid),
                        "task_id": str(task_uuid),
                        "workspace": str(resolved),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        return Workspace(
            project_id=str(project_uuid),
            task_id=str(task_uuid),
            root=resolved,
        )

    def resolve_relative(self, workspace: Workspace, relative_path: str) -> Path:
        if not relative_path or "\x00" in relative_path:
            raise WorkspaceError("Invalid workspace path")

        candidate = (workspace.root / relative_path).resolve()
        if not self._is_within_workspace(candidate, workspace.root):
            raise WorkspaceError("Workspace path escapes the task workspace")
        return candidate

    @staticmethod
    def _validate_id(value: str) -> UUID:
        try:
            return UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise WorkspaceError("Workspace identifiers must be UUIDs") from exc

    def _is_within_root(self, candidate: Path) -> bool:
        return self._is_within_workspace(candidate, self.root)

    @staticmethod
    def _is_within_workspace(candidate: Path, root: Path) -> bool:
        return candidate == root or root in candidate.parents
