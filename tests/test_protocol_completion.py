"""End-to-end protocol completion tests with a scripted subject.

Every protocol must run to completion with a perfect subject, and a subject
who fails SART practice twice must still continue (the practice gate records
a flag instead of aborting the run).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.acquisition.protocol_engine import ProtocolEngine
from bsense_dataset_studio.acquisition.session import AcquisitionSession, SessionState
from bsense_dataset_studio.protocols import build, list_protocols
from bsense_dataset_studio.storage import plan_run_storage


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value


class FakeRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path

    def start(self, *, timeout: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"XDF:")

    def stop(self) -> None:
        pass


class FakePublisher:
    def __init__(self, path: Path) -> None:
        self.path = path

    def publish(self, marker: object) -> None:
        pass

    def close(self) -> None:
        pass


def _form_values(step) -> dict[str, object]:
    values: dict[str, object] = {}
    for field in step.fields:
        if not field.required:
            values[field.key] = ""
            continue
        if field.kind == "boolean":
            values[field.key] = True
        elif field.kind == "choice":
            values[field.key] = "first_test" if "first_test" in field.choices else field.choices[0]
        elif field.kind in {"rating", "number"}:
            low = field.minimum if field.minimum is not None else 0
            high = field.maximum if field.maximum is not None else low + 1
            values[field.key] = str((low + high) / 2)
        else:
            values[field.key] = "12:00"
    return values


def run_protocol(task: str, *, respond: bool) -> AcquisitionSession:
    clock = FakeClock()
    directory = tempfile.mkdtemp()
    storage = plan_run_storage(directory, "P001", "01", task, "001")
    protocol = build(task)
    session = AcquisitionSession(
        storage,
        protocol,
        participant_id="P001",
        session_id="01",
        run_id="001",
        recorder_factory=FakeRecorder,
        publisher_factory=FakePublisher,
        quality_builder=None,
        clock=clock,
    )
    engine = ProtocolEngine(session, protocol, clock=clock)
    engine.start()
    guard = 0
    while not engine.finished and guard < 5000:
        guard += 1
        step = engine.current_step
        if step is None:
            break
        if step.event == "sart_stimulus":
            if respond and step.metadata["should_respond"]:
                clock.value += 0.3
                engine.handle_response("space")
            clock.value += float(step.duration_s or 1.0) + 0.01
            engine.tick()
        elif step.event == "pvt_start":
            end = engine._pvt_end_at or clock.value
            while not engine.finished and clock.value < end:
                clock.value += 0.05
                engine.tick()
                if engine._pvt_stimulus_at is not None and respond:
                    clock.value += 0.25
                    engine.handle_response("space")
            clock.value = end + 0.01
            engine.tick()
        elif step.advance_mode == "timed":
            clock.value += float(step.duration_s or 0) + 0.01
            engine.tick()
        else:
            engine.advance(_form_values(step))
    return session


class ProtocolCompletionTests(unittest.TestCase):
    def test_every_protocol_completes_with_perfect_subject(self) -> None:
        tasks = [spec.task for spec in list_protocols()]
        self.assertGreaterEqual(len(tasks), 2)
        for task in tasks:
            with self.subTest(task=task):
                session = run_protocol(task, respond=True)
                self.assertEqual(session.state, SessionState.FINALIZED)
                self.assertEqual(session.context_values.get("completion_status"), "completed")

    def test_failing_sart_practice_continues_instead_of_aborting(self) -> None:
        session = run_protocol("m6_readiness_reference", respond=False)
        self.assertEqual(session.state, SessionState.FINALIZED)
        self.assertEqual(session.context_values.get("completion_status"), "completed")
        self.assertIsNone(session.context_values.get("abort_reason"))
        self.assertIs(session.context_values.get("practice_criterion_met"), False)
        self.assertEqual(session.context_values.get("practice_attempts"), 2)


if __name__ == "__main__":
    unittest.main()
