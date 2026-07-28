import json
import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.acquisition.protocol_engine import ProtocolEngine
from bsense_dataset_studio.acquisition.session import AcquisitionSession, SessionState
from bsense_dataset_studio.protocols.definitions import InputField, Protocol, ProtocolStep
from bsense_dataset_studio.storage import plan_run_storage


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class FakeRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.started = False
        self.stopped = False

    def start(self, *, timeout: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"XDF:")
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakePublisher:
    def __init__(self, path: Path, markers: list[object]) -> None:
        self.path = path
        self.markers = markers

    def publish(self, marker: object) -> None:
        self.markers.append(marker)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(marker.to_dict(), ensure_ascii=False) + "\n")


class FailingRecorder(FakeRecorder):
    def start(self, *, timeout: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"XDF:")
        raise RuntimeError("missing stream")


class ClosablePublisher(FakePublisher):
    def __init__(self, path: Path, markers: list[object]) -> None:
        super().__init__(path, markers)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class AcquisitionSessionTests(unittest.TestCase):
    def test_form_sart_and_finalize_are_one_append_only_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = plan_run_storage(root, "P001", "01", "m6_readiness_field", "001")
            protocol = Protocol(
                "m6_readiness_field",
                "test",
                "test",
                "2.0",
                (
                    ProtocolStep(
                        "KSS",
                        "填写",
                        None,
                        "context_start",
                        1,
                        advance_mode="form",
                        completion_event="context",
                        completion_code=2,
                        fields=(InputField("kss_score", "KSS", "rating", 1, 9),),
                    ),
                    ProtocolStep(
                        "1",
                        "按空格",
                        1.0,
                        "sart_stimulus",
                        721,
                        block="sart_assessment",
                        trial=1,
                        response_key="space",
                        metadata={
                            "stimulus": "1",
                            "should_respond": True,
                            "trial_kind": "assessment",
                            "response_event": "sart_response",
                            "response_code": 722,
                            "result_event": "sart_trial_result",
                            "result_code": 723,
                        },
                    ),
                    ProtocolStep("完成", "保存", 0.1, "experiment_end", 11),
                ),
            )
            clock = FakeClock()
            markers: list[object] = []
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="001",
                recorder_factory=FakeRecorder,
                publisher_factory=lambda path: FakePublisher(path, markers),
                quality_builder=None,
                clock=clock,
            )
            engine = ProtocolEngine(session, protocol, clock=clock)
            engine.start()
            clock.value = 101.0
            engine.advance({"kss_score": "7"})
            clock.value = 101.4
            engine.handle_response("space")
            clock.value = 102.0
            engine.advance()
            clock.value = 102.2
            engine.tick()

            self.assertTrue(engine.finished)
            self.assertEqual(session.state, SessionState.FINALIZED)
            payload = json.loads(storage.context.read_text(encoding="utf-8"))
            self.assertEqual(payload["values"]["kss_score"], 7.0)
            results = [item for item in markers if item.event == "sart_trial_result"]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].payload["outcome"], "hit")
            self.assertEqual(results[0].payload["response_count"], 1)
            self.assertIn("stimulus_onset_timestamp", results[0].payload)

    def test_existing_run_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(
                directory,
                "P001",
                "01",
                "m6_readiness_reference",
                "001",
            )
            storage.raw_directory.mkdir(parents=True)
            storage.xdf.write_bytes(b"existing")
            protocol = Protocol("test", "test", "test", "2.0", ())
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="001",
                recorder_factory=FakeRecorder,
                publisher_factory=lambda path: FakePublisher(path, []),
                quality_builder=None,
            )
            with self.assertRaises(FileExistsError):
                session.prepare()

    def test_pvt_emits_explicit_stimulus_response_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(
                directory,
                "P001",
                "01",
                "m6_readiness_reference",
                "002",
            )
            protocol = Protocol(
                "m6_readiness_reference",
                "test",
                "test",
                "2.0",
                (
                    ProtocolStep(
                        "+",
                        "PVT",
                        2.0,
                        "pvt_start",
                        740,
                        response_key="space",
                        completion_event="pvt_end",
                        completion_code=744,
                        metadata={
                            "duration_s": 2.0,
                            "isi_min_s": 0.1,
                            "isi_max_s": 0.1,
                            "response_timeout_s": 1.0,
                            "stimulus_event": "pvt_stimulus",
                            "stimulus_code": 741,
                            "response_event": "pvt_response",
                            "response_code": 742,
                            "result_event": "pvt_trial_result",
                            "result_code": 743,
                        },
                    ),
                ),
            )
            clock = FakeClock()
            markers: list[object] = []
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="002",
                recorder_factory=FakeRecorder,
                publisher_factory=lambda path: FakePublisher(path, markers),
                quality_builder=None,
                clock=clock,
            )
            engine = ProtocolEngine(session, protocol, clock=clock)
            engine.start()
            clock.value = 100.1
            snapshot = engine.tick()
            self.assertTrue(snapshot.pvt_stimulus_active)
            clock.value = 100.35
            engine.handle_response("space")
            clock.value = 102.0
            engine.tick()
            results = [item for item in markers if item.event == "pvt_trial_result"]
            self.assertGreaterEqual(len(results), 1)
            self.assertTrue(results[0].payload["responded"])
            self.assertFalse(results[0].payload["timeout"])
            self.assertIn("stimulus_timestamp", results[0].payload)

    def test_start_failure_is_auditable_and_not_silently_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(directory, "P001", "01", "deviceqc", "003")
            protocol = Protocol("deviceqc", "test", "test", "2.0", ())
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="003",
                recorder_factory=FailingRecorder,
                publisher_factory=lambda path: FakePublisher(path, []),
                quality_builder=None,
            )
            with self.assertRaises(RuntimeError):
                session.start()
            context = json.loads(storage.context.read_text(encoding="utf-8"))
            self.assertEqual(
                context["values"]["completion_status"],
                "start_failed",
            )
            self.assertEqual(session.state, SessionState.FAILED)

    def test_publisher_is_closed_on_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(directory, "P001", "01", "deviceqc", "004")
            protocol = Protocol("deviceqc", "test", "test", "2.0", ())
            publishers: list[ClosablePublisher] = []
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="004",
                recorder_factory=FakeRecorder,
                publisher_factory=lambda path: publishers.append(ClosablePublisher(path, [])) or publishers[-1],
                quality_builder=None,
            )
            session.start()
            session.publish("experiment_start")
            session.finalize()
            self.assertTrue(publishers[0].closed)

    def test_publisher_is_closed_on_start_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(directory, "P001", "01", "deviceqc", "005")
            protocol = Protocol("deviceqc", "test", "test", "2.0", ())
            publishers: list[ClosablePublisher] = []
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id="P001",
                session_id="01",
                run_id="005",
                recorder_factory=FailingRecorder,
                publisher_factory=lambda path: publishers.append(ClosablePublisher(path, [])) or publishers[-1],
                quality_builder=None,
            )
            with self.assertRaises(RuntimeError):
                session.start()
            self.assertTrue(publishers[0].closed)


if __name__ == "__main__":
    unittest.main()
