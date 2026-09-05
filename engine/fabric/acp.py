"""Minimal fail-closed Agent Client Protocol v1 subprocess client.

This client owns protocol framing and DDE-side file/permission mediation only.
It does not select a provider, grant capabilities, or persist a WorkerSession;
those authorities live in the surrounding Fabric services.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from engine.core.errors import DdeError
from engine.workspaces.paths import resolve_within_workspace

ACP_PROTOCOL_VERSION = 1
ACP_TIMEOUT_SECONDS = 120.0
MAX_ACP_FILE_READ_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class AcpPermissionDecision:
    selected_option_id: str | None = None


class AcpPermissionMediator(Protocol):
    async def decide(
        self, *, method: str, params: dict[str, object]
    ) -> AcpPermissionDecision: ...


class DenyAllAcpPermissions:
    async def decide(
        self, *, method: str, params: dict[str, object]
    ) -> AcpPermissionDecision:
        return AcpPermissionDecision()


@dataclass(frozen=True)
class AcpPromptResult:
    session_id: str
    text: str
    reasoning: str
    stop_reason: str | None
    updates: tuple[dict[str, object], ...]


class AcpClient:
    def __init__(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        permission_mediator: AcpPermissionMediator | None = None,
        allow_file_reads: bool = True,
        allow_file_writes: bool = False,
        timeout_seconds: float = ACP_TIMEOUT_SECONDS,
    ) -> None:
        if not command:
            raise ValueError("ACP command cannot be empty")
        self.command = command
        self.cwd = cwd.resolve()
        self.permission_mediator = permission_mediator or DenyAllAcpPermissions()
        self.allow_file_reads = allow_file_reads
        self.allow_file_writes = allow_file_writes
        self.timeout_seconds = timeout_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._updates: list[dict[str, object]] = []
        self.initialize_result: dict[str, object] | None = None

    async def start(self) -> dict[str, object]:
        if self._process is not None:
            return self.initialize_result or {}
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command,
                cwd=self.cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "ACP server process could not be started",
                retryable=False,
                details={"command": list(self.command), "error": str(exc)},
            ) from exc
        self._process = process
        result = await self.request(
            "initialize",
            {
                "protocolVersion": ACP_PROTOCOL_VERSION,
                "clientCapabilities": {
                    "fs": {
                        "readTextFile": self.allow_file_reads,
                        "writeTextFile": self.allow_file_writes,
                    }
                },
                "clientInfo": {
                    "name": "dde",
                    "title": "DDE AI Conversation Fabric",
                    "version": "rev3",
                },
            },
        )
        self.initialize_result = result
        return result

    async def new_session(
        self, *, mcp_servers: list[dict[str, object]] | None = None
    ) -> str:
        await self.start()
        result = await self.request(
            "session/new",
            {"cwd": str(self.cwd), "mcpServers": mcp_servers or []},
        )
        session_id = result.get("sessionId")
        if not isinstance(session_id, str) or not session_id.strip():
            raise DdeError("PROVIDER_ERROR", "ACP session/new returned no sessionId")
        return session_id

    async def resume_session(self, session_id: str) -> dict[str, object]:
        await self.start()
        return await self.request(
            "session/resume", {"sessionId": session_id, "cwd": str(self.cwd)}
        )

    async def load_session(self, session_id: str) -> dict[str, object]:
        await self.start()
        return await self.request(
            "session/load", {"sessionId": session_id, "cwd": str(self.cwd)}
        )

    async def fork_session(self, session_id: str) -> str:
        await self.start()
        result = await self.request(
            "session/fork", {"sessionId": session_id, "cwd": str(self.cwd)}
        )
        forked = result.get("sessionId")
        if not isinstance(forked, str) or not forked:
            raise DdeError("PROVIDER_ERROR", "ACP session/fork returned no sessionId")
        return forked

    async def prompt(self, session_id: str, text: str) -> AcpPromptResult:
        if not text.strip():
            raise DdeError("VALIDATION_FAILED", "ACP prompt cannot be empty")
        await self.start()
        self._updates.clear()
        result = await self.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}],
            },
        )
        assistant: list[str] = []
        reasoning: list[str] = []
        for update in self._updates:
            payload = update.get("update")
            if not isinstance(payload, dict):
                continue
            kind = payload.get("sessionUpdate")
            content = payload.get("content")
            chunk = content.get("text") if isinstance(content, dict) else None
            if not isinstance(chunk, str):
                continue
            if kind == "agent_message_chunk":
                assistant.append(chunk)
            elif kind == "agent_thought_chunk":
                reasoning.append(chunk)
        stop = result.get("stopReason")
        return AcpPromptResult(
            session_id=session_id,
            text="".join(assistant),
            reasoning="".join(reasoning),
            stop_reason=stop if isinstance(stop, str) else None,
            updates=tuple(self._updates),
        )

    async def cancel(self, session_id: str) -> None:
        await self.start()
        await self.request("session/cancel", {"sessionId": session_id})

    async def close_session(self, session_id: str) -> None:
        await self.start()
        await self.request("session/close", {"sessionId": session_id})

    async def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin:
            process.stdin.close()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3.0)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def request(
        self, method: str, params: dict[str, object]
    ) -> dict[str, object]:
        self._require_process()
        message_id = self._next_id
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": message_id, "method": method, "params": params}
        )
        try:
            return await asyncio.wait_for(
                self._wait_for_response(message_id), timeout=self.timeout_seconds
            )
        except TimeoutError as exc:
            raise DdeError(
                "PROVIDER_TIMEOUT",
                f"ACP request {method} timed out",
                retryable=True,
            ) from exc

    async def _wait_for_response(self, message_id: int) -> dict[str, object]:
        process = self._require_process()
        if process.stdout is None:
            raise DdeError("PROVIDER_ERROR", "ACP stdout is unavailable")
        while True:
            line = await process.stdout.readline()
            if not line:
                stderr = ""
                if process.stderr:
                    try:
                        stderr = (await process.stderr.read()).decode(errors="replace")[
                            -4000:
                        ]
                    except Exception:  # noqa: BLE001 - diagnostic only
                        stderr = ""
                raise DdeError(
                    "PROVIDER_ERROR",
                    "ACP server closed before replying",
                    details={"returncode": process.returncode, "stderr": stderr},
                )
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DdeError("PROVIDER_ERROR", "ACP emitted malformed JSON") from exc
            if not isinstance(message, dict):
                continue
            if message.get("id") == message_id and (
                "result" in message or "error" in message
            ):
                error = message.get("error")
                if isinstance(error, dict):
                    raise DdeError(
                        "PROVIDER_ERROR",
                        str(error.get("message") or "ACP request failed"),
                        details={"acp_error": error},
                    )
                result = message.get("result")
                return result if isinstance(result, dict) else {}
            await self._handle_server_message(message)

    async def _handle_server_message(self, message: dict[str, object]) -> None:
        method = message.get("method")
        if not isinstance(method, str):
            return
        params = message.get("params")
        params_dict = params if isinstance(params, dict) else {}
        if method == "session/update":
            self._updates.append(params_dict)
            return
        message_id = message.get("id")
        if not isinstance(message_id, (str, int)):
            return
        if method == "session/request_permission":
            decision = await self.permission_mediator.decide(
                method=method, params=params_dict
            )
            if decision.selected_option_id:
                result: dict[str, object] = {
                    "outcome": {
                        "outcome": "selected",
                        "optionId": decision.selected_option_id,
                    }
                }
            else:
                result = {"outcome": {"outcome": "cancelled"}}
            self._send({"jsonrpc": "2.0", "id": message_id, "result": result})
            return
        if method == "fs/read_text_file":
            await self._handle_read(message_id, params_dict)
            return
        if method == "fs/write_text_file":
            await self._handle_write(message_id, params_dict)
            return
        # Terminal and unknown callbacks are not granted implicitly.
        self._send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32601,
                    "message": f"DDE denies unsupported ACP client method {method}",
                },
            }
        )

    async def _handle_read(
        self, message_id: str | int, params: dict[str, object]
    ) -> None:
        if not self.allow_file_reads:
            self._send_error(message_id, "ACP file reads are disabled")
            return
        try:
            path = self._relative_workspace_path(params.get("path"))
            target = resolve_within_workspace(self.cwd, path)
            if not target.is_file():
                content = ""
            else:
                if target.stat().st_size > MAX_ACP_FILE_READ_BYTES:
                    raise DdeError(
                        "RESOURCE_EXHAUSTION", "ACP file read exceeds bounded size"
                    )
                content = target.read_text(encoding="utf-8")
            line = params.get("line")
            limit = params.get("limit")
            if isinstance(line, int) and line > 1:
                rows = content.splitlines(keepends=True)
                start = line - 1
                end = start + limit if isinstance(limit, int) and limit >= 0 else None
                content = "".join(rows[start:end])
            self._send(
                {"jsonrpc": "2.0", "id": message_id, "result": {"content": content}}
            )
        except (OSError, UnicodeError, DdeError) as exc:
            self._send_error(message_id, str(exc))

    async def _handle_write(
        self, message_id: str | int, params: dict[str, object]
    ) -> None:
        if not self.allow_file_writes:
            self._send_error(message_id, "ACP file writes are disabled")
            return
        decision = await self.permission_mediator.decide(
            method="fs/write_text_file", params=params
        )
        if decision.selected_option_id is None:
            self._send_error(
                message_id, "ACP file write denied by DDE permission policy"
            )
            return
        try:
            path = self._relative_workspace_path(params.get("path"))
            content = params.get("content")
            if not isinstance(content, str):
                raise DdeError(
                    "VALIDATION_FAILED", "ACP file write content must be text"
                )
            target = resolve_within_workspace(self.cwd, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self._send({"jsonrpc": "2.0", "id": message_id, "result": None})
        except (OSError, DdeError) as exc:
            self._send_error(message_id, str(exc))

    def _relative_workspace_path(self, value: object) -> str:
        if not isinstance(value, str) or not value:
            raise DdeError("VALIDATION_FAILED", "ACP file callback requires a path")
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                return candidate.resolve().relative_to(self.cwd).as_posix()
            except ValueError as exc:
                raise DdeError(
                    "POLICY_DENIED", "ACP path escapes authorized workspace"
                ) from exc
        return value

    def _send_error(self, message_id: str | int, message: str) -> None:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32602, "message": message},
            }
        )

    def _send(self, message: dict[str, object]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise DdeError("PROVIDER_ERROR", "ACP stdin is unavailable")
        process.stdin.write(
            (json.dumps(message, separators=(",", ":")) + "\n").encode()
        )

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise DdeError("PROVIDER_ERROR", "ACP client has not started")
        return self._process
