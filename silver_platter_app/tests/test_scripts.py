import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


class ScriptHelperTests(TestCase):
    def _copy_readiness_scripts(self, root: Path) -> None:
        source_root = Path(__file__).resolve().parents[1]
        scripts_dir = root / "scripts"
        scripts_dir.mkdir()
        for name in ["external_smoke_readiness", "load_local_env"]:
            shutil.copyfile(source_root / "scripts" / name, scripts_dir / name)

    def _script_env(self) -> dict:
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}

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

    def test_external_smoke_readiness_reports_missing_external_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_readiness_scripts(root)

            result = subprocess.run(
                ["bash", "scripts/external_smoke_readiness"],
                cwd=root,
                env=self._script_env(),
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("blocked: SEC EDGAR User-Agent", result.stdout)
            self.assertIn("blocked: OpenDART API key", result.stdout)
            self.assertIn("blocked: ECOS API key", result.stdout)
            self.assertIn("skipped: alert webhook URL", result.stdout)
            self.assertIn("external smoke readiness blocked", result.stdout)

    def test_external_smoke_readiness_loads_env_and_reports_ready(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_readiness_scripts(root)
            snapshot = root / "snapshot.jsonl"
            snapshot.write_text("{}", encoding="utf-8")
            (root / ".env").write_text(
                "\n".join(
                    [
                        "SEC_EDGAR_USER_AGENT=Silver Platter ops@silverplatter.dev",
                        "OPENDART_API_KEY=dart-key",
                        "ECOS_API_KEY=ecos-key",
                        "ALERT_WEBHOOK_URL=https://alerts.example.test/hook",
                        "KRX_PRICE_SMOKE_ENABLED=1",
                        "LONG_REPLAY_SNAPSHOT_PATH=%s" % snapshot,
                        "G7_LIVE_SMOKE_APPROVED=1",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", "scripts/external_smoke_readiness"],
                cwd=root,
                env=self._script_env(),
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("ready: SEC EDGAR User-Agent", result.stdout)
            self.assertIn("ready: OpenDART API key", result.stdout)
            self.assertIn("ready: ECOS API key", result.stdout)
            self.assertIn("ready: alert webhook URL", result.stdout)
            self.assertIn("ready: KRX price smoke opt-in", result.stdout)
            self.assertIn("ready: long replay snapshot", result.stdout)
            self.assertIn("ready: G7 live/paper smoke approval", result.stdout)
            self.assertIn("external smoke readiness passed", result.stdout)
