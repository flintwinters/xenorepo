"""Local monoapp service supervision tests."""

from pathlib import Path
from unittest.mock import Mock, patch
import unittest

from monotools.orchestration.apps import load_app
from monotools.orchestration.services import ServiceError, ServiceSupervisor


class ServiceSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = load_app(Path("apps/calculator"))
        self.process = Mock()
        self.process.poll.return_value = None
        self.supervisor = ServiceSupervisor((self.definition,), Path.cwd(), launcher=Mock(
            return_value=self.process))

    @patch("monotools.orchestration.services._healthy", return_value=False)
    @patch("monotools.orchestration.services.validate_dist")
    @patch("monotools.orchestration.services.build_app")
    @patch("monotools.orchestration.services.validate_app")
    def test_start_uses_canonical_build_and_owns_process(self, validate, build, dist, healthy) -> None:
        status = self.supervisor.start("calculator")
        self.assertEqual((status.name, status.port, status.running, status.managed),
            ("calculator", 8100, True, True))
        validate.assert_called_once_with(self.definition, Path.cwd())
        build.assert_called_once_with(self.definition, Path.cwd())
        dist.assert_called_once_with(self.definition)

    @patch("monotools.orchestration.services._healthy", return_value=False)
    def test_stop_rejects_unowned_service_and_terminates_owned_service(self, healthy) -> None:
        with self.assertRaisesRegex(ServiceError, "not running under Xenoview"):
            self.supervisor.stop("calculator")
        self.supervisor._processes["calculator"] = self.process
        status = self.supervisor.stop("calculator")
        self.process.terminate.assert_called_once_with()
        self.assertFalse(status.running)

    def test_unknown_app_is_explicit(self) -> None:
        with self.assertRaisesRegex(ServiceError, "unknown monoapp: missing"):
            self.supervisor.start("missing")


if __name__ == "__main__":
    unittest.main()
