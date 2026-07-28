from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .. import __version__
from ..annotations import AnnotationStore
from ..protocols import Protocol
from ..quality.offline import save_quality_from_xdf
from ..schemas.experiment import ExperimentContext
from ..schemas.markers import Marker
from ..storage import RunStorage, prepare_run_storage
from .marker_outlet import MarkerPublisher
from .recorder import Recorder


class SessionState(str, Enum):
    NEW = "new"
    PREPARED = "prepared"
    RECORDING = "recording"
    STOPPED = "stopped"
    FINALIZED = "finalized"
    ABORTED = "aborted"
    FAILED = "failed"


def lsl_clock() -> float:
    from pylsl import local_clock

    return float(local_clock())


class AcquisitionSession:
    """Own one append-only run and its recorder, markers and context."""

    def __init__(
        self,
        storage: RunStorage,
        protocol: Protocol,
        *,
        participant_id: str,
        session_id: str,
        run_id: str,
        recorder_factory: Callable[[Path], Any] = Recorder,
        publisher_factory: Callable[[Path], Any] = MarkerPublisher,
        quality_builder: Callable[[Path, Path], Path] | None = save_quality_from_xdf,
        clock: Callable[[], float] = lsl_clock,
    ) -> None:
        self.storage = storage
        self.protocol = protocol
        self.participant_id = participant_id
        self.session_id = session_id
        self.run_id = run_id
        self._recorder_factory = recorder_factory
        self._publisher_factory = publisher_factory
        self._quality_builder = quality_builder
        self._clock = clock
        self._recorder: Any | None = None
        self._publisher: Any | None = None
        self.state = SessionState.NEW
        self.context_values: dict[str, Any] = {
            "collection_started_at": None,
            "collection_finished_at": None,
            "completion_status": None,
        }

    def prepare(self) -> None:
        if self.state is not SessionState.NEW:
            raise RuntimeError(f"当前状态不能准备采集：{self.state.value}")
        conflicts = [
            path
            for path in (
                self.storage.xdf,
                self.storage.context,
                self.storage.events,
                self.storage.quality,
            )
            if path.exists()
        ]
        if conflicts:
            raise FileExistsError(f"本次 Run 已存在数据，拒绝覆盖：{conflicts[0]}")
        prepare_run_storage(self.storage)
        self.state = SessionState.PREPARED

    def start(self, *, timeout: float = 5.0) -> None:
        if self.state is SessionState.NEW:
            self.prepare()
        if self.state is not SessionState.PREPARED:
            raise RuntimeError(f"当前状态不能启动采集：{self.state.value}")
        try:
            # Marker outlet must exist before Recorder discovers required streams.
            self._publisher = self._publisher_factory(self.storage.events)
            self._recorder = self._recorder_factory(self.storage.xdf)
            self._recorder.start(timeout=timeout)
        except Exception as exc:
            # A leaked marker outlet would surface as a duplicate stream on retry.
            self._close_publisher()
            self.context_values["collection_finished_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            self.context_values["completion_status"] = "start_failed"
            self.context_values["start_failure"] = str(exc)
            self.state = SessionState.FAILED
            self._write_context_once()
            raise
        self.context_values["collection_started_at"] = datetime.now(timezone.utc).isoformat()
        self.state = SessionState.RECORDING

    def publish(
        self,
        event: str,
        *,
        event_code: int | None = None,
        payload: Mapping[str, Any] | None = None,
        timestamp: float | None = None,
    ) -> Marker:
        if self.state is not SessionState.RECORDING or self._publisher is None:
            raise RuntimeError("Marker 只能在录制期间写入")
        marker = Marker(
            event=event,
            timestamp=self._clock() if timestamp is None else float(timestamp),
            participant_id=self.participant_id,
            session_id=self.session_id,
            run_id=self.run_id,
            task=self.protocol.task,
            event_code=event_code,
            payload=dict(payload or {}),
        )
        self._publisher.publish(marker)
        return marker

    def merge_context(self, values: Mapping[str, Any]) -> None:
        self.context_values.update(values)

    def annotate(
        self,
        annotation_type: str,
        note: str = "",
        *,
        start_timestamp: float | None = None,
        end_timestamp: float | None = None,
        affected_modalities: tuple[str, ...] = ("eeg", "fnirs", "motion"),
        exclude_from_training: bool = False,
        severity: str = "minor",
    ) -> dict[str, object]:
        if self.state is not SessionState.RECORDING:
            raise RuntimeError("人工标注只能在录制期间添加")
        now = self._clock()
        row = AnnotationStore(self.storage.annotations).append(
            annotation_type,
            note,
            start_timestamp=start_timestamp if start_timestamp is not None else now,
            end_timestamp=end_timestamp if end_timestamp is not None else now,
            affected_modalities=affected_modalities,
            exclude_from_training=exclude_from_training,
            severity=severity,
        )
        self.publish(
            "operator_annotation",
            event_code=900,
            payload=row,
            timestamp=now,
        )
        return row

    def stop(self) -> None:
        if self.state is not SessionState.RECORDING:
            raise RuntimeError(f"当前状态不能停止录制：{self.state.value}")
        assert self._recorder is not None
        try:
            self._recorder.stop()
        except Exception:
            self.state = SessionState.FAILED
            raise
        finally:
            self._close_publisher()
        summary = getattr(self._recorder, "summary", None)
        if callable(summary):
            self.context_values["recorder_summary"] = summary()
        self.state = SessionState.STOPPED

    def _close_publisher(self) -> None:
        publisher, self._publisher = self._publisher, None
        if publisher is None:
            return
        close = getattr(publisher, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def finalize(self, *, completion_status: str = "completed") -> Path:
        if self.state is SessionState.RECORDING:
            self.stop()
        if self.state not in {SessionState.STOPPED, SessionState.ABORTED}:
            raise RuntimeError(f"当前状态不能完成记录：{self.state.value}")
        self.context_values["collection_finished_at"] = datetime.now(timezone.utc).isoformat()
        self.context_values["completion_status"] = completion_status
        quality_error: Exception | None = None
        if self._quality_builder is not None and self.storage.xdf.exists():
            try:
                self._quality_builder(self.storage.xdf, self.storage.quality)
            except Exception as exc:
                quality_error = exc
                self.context_values["quality_generation_error"] = str(exc)
        self._write_context_once()
        if quality_error is not None:
            self.state = SessionState.FAILED
            raise RuntimeError("XDF 已保存，但质量报告生成失败") from quality_error
        self.state = SessionState.FINALIZED
        return self.storage.context

    def _write_context_once(self) -> None:
        context = ExperimentContext(
            participant_id=self.participant_id,
            session_id=self.session_id,
            run_id=self.run_id,
            task=self.protocol.task,
            protocol_version=self.protocol.version,
            software_version=__version__,
            values=self.context_values,
        )
        _write_json_once(self.storage.context, context.to_dict())

    def abort(self, reason: str) -> Path:
        if self.state is SessionState.RECORDING:
            self.publish("run_aborted", payload={"reason": reason})
            self.stop()
        self.context_values["abort_reason"] = reason
        self.state = SessionState.ABORTED
        return self.finalize(completion_status="aborted")


def _write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(dict(payload), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
