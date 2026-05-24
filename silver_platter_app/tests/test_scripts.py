import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


class ScriptHelperTests(TestCase):
    def test_load_local_env_parses_simple_assignments_without_executing_values(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "load_local_env"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "# ignored comment",
                        "SEC_EDGAR_USER_AGENT=Silver Platter ops@silverplatter.dev",
                        "export   OPENDART_API_KEY=dart-key",
                        "ECOS_API_KEY=\"ecos-key\"",
                        "ALERT_WEBHOOK_URL='https://alerts.example.test/hook'",
                        "MALICIOUS=$(touch executed)",
                        "SPACED_KEY =ignored",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    (
                        "set -euo pipefail; "
                        ". \"$SCRIPT_PATH\"; "
                        "printf '%s\\n' "
                        "\"$SEC_EDGAR_USER_AGENT\" "
                        "\"$OPENDART_API_KEY\" "
                        "\"$ECOS_API_KEY\" "
                        "\"$ALERT_WEBHOOK_URL\" "
                        "\"$MALICIOUS\" "
                        "\"${SPACED_KEY-unset}\""
                    ),
                ],
                cwd=root,
                env={**os.environ, "SCRIPT_PATH": str(script)},
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                [
                    "Silver Platter ops@silverplatter.dev",
                    "dart-key",
                    "ecos-key",
                    "https://alerts.example.test/hook",
                    "$(touch executed)",
                    "unset",
                ],
                result.stdout.splitlines(),
            )
            self.assertFalse((root / "executed").exists())
