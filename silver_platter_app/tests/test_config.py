import os
import unittest

from silver_platter.config import AppSettings


class ConfigTest(unittest.TestCase):
    def test_defaults_are_mvp_values(self):
        settings = AppSettings.from_env()
        self.assertEqual(settings.app_timezone, "Asia/Seoul")
        self.assertEqual(settings.goldilocks.host, "host.docker.internal")
        self.assertEqual(settings.goldilocks.port, 22581)
        self.assertEqual(settings.goldilocks.schema, "SP")
        self.assertFalse(settings.live_order_enabled)
        self.assertFalse(settings.simulation_order_broker_send)

    def test_env_override(self):
        old = os.environ.get("GOLDILOCKS_PORT")
        os.environ["GOLDILOCKS_PORT"] = "22582"
        try:
            self.assertEqual(AppSettings.from_env().goldilocks.port, 22582)
        finally:
            if old is None:
                os.environ.pop("GOLDILOCKS_PORT", None)
            else:
                os.environ["GOLDILOCKS_PORT"] = old


if __name__ == "__main__":
    unittest.main()
