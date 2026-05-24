from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.security import (
    PortExposure,
    assess_https_requirement,
    check_backup_access,
    check_writable_directory,
    role_allows,
    validate_external_port_exposure,
)


class SecurityTests(TestCase):
    def test_permission_matrix_allows_role_actions(self):
        self.assertTrue(role_allows("operator", "run_backup"))
        self.assertFalse(role_allows("viewer", "submit_paper_order"))

    def test_writable_directory_and_backup_access_checks(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)

            self.assertEqual("pass", check_writable_directory(path).status)
            self.assertEqual("pass", check_backup_access(path).status)
            self.assertEqual("failed", check_backup_access(path / "missing").status)

    def test_external_port_exposure_and_https_requirement(self):
        self.assertEqual(
            "pass",
            validate_external_port_exposure(
                [PortExposure("127.0.0.1", 8000, "api")]
            ).status,
        )
        self.assertEqual(
            "failed",
            validate_external_port_exposure(
                [PortExposure("0.0.0.0", 8000, "api")]
            ).status,
        )
        self.assertEqual("failed", assess_https_requirement(True, False).status)
        self.assertEqual("pass", assess_https_requirement(False, False).status)
