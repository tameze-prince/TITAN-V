import asyncio
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping


class SandboxError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    image: str = "python:3.13-slim"
    network: str = "none"
    memory: str = "512m"
    cpus: str = "1.0"
    pids_limit: int = 128
    timeout_seconds: int = 60
    read_only_root: bool = True


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    command: tuple[str, ...]
    workspace: Path
    environment: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class DockerSandbox:
    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        self.policy = policy or SandboxPolicy()

    async def run(self, request: SandboxRequest) -> SandboxResult:
        if not request.command:
            raise SandboxError("Sandbox command cannot be empty")

        workspace = request.workspace.resolve()
        if not workspace.exists() or not workspace.is_dir():
            raise SandboxError(f"Sandbox workspace does not exist: {workspace}")

        command = self._build_command(request, workspace)

        started = asyncio.get_running_loop().time()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.policy.timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise SandboxError(
                f"Sandbox execution exceeded {self.policy.timeout_seconds} seconds"
            ) from exc

        duration_ms = int((asyncio.get_running_loop().time() - started) * 1000)
        return SandboxResult(
            exit_code=process.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
        )

    def _build_command(self, request: SandboxRequest, workspace: Path) -> list[str]:
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            self.policy.network,
            "--memory",
            self.policy.memory,
            "--cpus",
            self.policy.cpus,
            "--pids-limit",
            str(self.policy.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
        ]

        if self.policy.read_only_root:
            command.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])

        command.extend(["--mount", f"type=bind,src={workspace},dst=/workspace"])
        command.extend(["--workdir", "/workspace"])

        for key, value in (request.environment or {}).items():
            if not key or "=" in key or "\x00" in key or "\x00" in value:
                raise SandboxError("Invalid sandbox environment variable")
            command.extend(["--env", f"{key}={value}"])

        command.append(self.policy.image)
        command.extend(request.command)
        return command
