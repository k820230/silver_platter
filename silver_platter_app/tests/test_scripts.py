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

    def _copy_scripts(self, root: Path, names: list) -> None:
        source_root = Path(__file__).resolve().parents[1]
        scripts_dir = root / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        for name in names:
            target = scripts_dir / name
            shutil.copyfile(source_root / "scripts" / name, target)
            target.chmod(0o755)

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
            self.assertIn("blocked: Goldilocks ODBC history prefetch storage", result.stdout)
            self.assertIn("blocked: G7 approval evidence", result.stdout)
            self.assertIn("external smoke readiness blocked", result.stdout)

    def test_external_smoke_readiness_loads_env_and_reports_ready(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_readiness_scripts(root)
            snapshot = root / "snapshot.jsonl"
            snapshot.write_text("{}", encoding="utf-8")
            g7_evidence = root / "g7-evidence.json"
            g7_evidence.write_text("{}", encoding="utf-8")
            (root / ".env").write_text(
                "\n".join(
                    [
                        "SEC_EDGAR_USER_AGENT=Silver Platter ops@silverplatter.dev",
                        "OPENDART_API_KEY=dart-key",
                        "ECOS_API_KEY=ecos-key",
                        "ALERT_WEBHOOK_URL=https://alerts.example.test/hook",
                        "GOLDILOCKS_ODBC_DSN=sp_test",
                        "KRX_PRICE_SMOKE_ENABLED=1",
                        "LONG_REPLAY_SNAPSHOT_PATH=%s" % snapshot,
                        "G7_APPROVAL_EVIDENCE_PATH=%s" % g7_evidence,
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
            self.assertIn("ready: Goldilocks ODBC history prefetch storage", result.stdout)
            self.assertIn("ready: KRX price smoke opt-in", result.stdout)
            self.assertIn("ready: long replay snapshot", result.stdout)
            self.assertIn("ready: G7 approval evidence", result.stdout)
            self.assertIn("ready: G7 live/paper smoke approval", result.stdout)
            self.assertIn("external smoke readiness passed", result.stdout)

    def test_prepare_long_replay_snapshot_writes_replayable_jsonl(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_long_replay_snapshot"
        replay_script = Path(__file__).resolve().parents[1] / "scripts" / "replay_exported_snapshot"
        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "long_replay_sample.jsonl"
            result = subprocess.run(
                [str(script)],
                cwd=Path(__file__).resolve().parents[1],
                env={
                    **os.environ,
                    "LONG_REPLAY_SNAPSHOT_PATH": str(snapshot),
                    "PYTHONPATH": "src",
                },
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(snapshot.exists())
            self.assertIn("LONG_REPLAY_SNAPSHOT_PATH=%s" % snapshot, result.stdout)

            replay = subprocess.run(
                [
                    str(replay_script),
                    "--run-id",
                    "test-long-replay",
                    "--strategy-id",
                    "test",
                    "--from-date",
                    "2026-01-02",
                    "--to-date",
                    "2026-05-22",
                    "--security-id",
                    "005930",
                    "--snapshot-path",
                    str(snapshot),
                    "--required-min-days",
                    "30",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONPATH": "src"},
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn('"loaded_bar_count": 101', replay.stdout)
            self.assertIn('"status": "completed"', replay.stdout)
            self.assertIn('"status": "pass"', replay.stdout)

    def test_krx_price_smoke_preserves_explicit_disabled_env(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_scripts(root, ["krx_price_smoke", "load_local_env"])
            (root / ".env").write_text("KRX_PRICE_SMOKE_ENABLED=1\n", encoding="utf-8")

            result = subprocess.run(
                ["bash", "scripts/krx_price_smoke"],
                cwd=root,
                env={**self._script_env(), "KRX_PRICE_SMOKE_ENABLED": "0"},
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("KRX price smoke skipped", result.stdout)

    def test_collect_g7_approval_evidence_writes_pass_bundle_without_approval(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "collect_g7_approval_evidence"
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "g7-evidence.json"
            result = subprocess.run(
                [str(script), "--output", str(output), "--fail-on-blocked"],
                cwd=Path(__file__).resolve().parents[1],
                env={
                    **os.environ,
                    "LIVE_ORDER_ENABLED": "false",
                    "G7_LIVE_SMOKE_APPROVED": "0",
                    "PYTHONPATH": "src",
                },
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(output.exists())
            payload = output.read_text(encoding="utf-8")
            self.assertIn('"gate_id": "G7"', payload)
            self.assertIn('"status": "pass"', payload)
            self.assertIn("approval_flag=G7_LIVE_SMOKE_APPROVED remains manual", result.stdout)
