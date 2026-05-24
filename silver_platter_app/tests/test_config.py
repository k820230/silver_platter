import os
import unittest
from unittest.mock import patch

from silver_platter.config import AppSettings, sec_edgar_user_agent_has_real_contact


class ConfigTest(unittest.TestCase):
    def test_defaults_are_mvp_values(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = AppSettings.from_env()
        self.assertEqual(settings.app_timezone, "Asia/Seoul")
        self.assertEqual(settings.goldilocks.host, "host.docker.internal")
        self.assertEqual(settings.goldilocks.port, 22581)
        self.assertEqual(settings.goldilocks.schema, "SP")
        self.assertEqual("", settings.alert_webhook_url)
        self.assertIn("Silver Platter", settings.sec_edgar_user_agent)
        self.assertEqual("", settings.opendart_api_key)
        self.assertEqual("", settings.ecos_api_key)
        self.assertFalse(settings.krx_kind_smoke_enabled)
        self.assertFalse(settings.krx_price_smoke_enabled)
        self.assertFalse(settings.kis.configured_for_queries())
        self.assertEqual("demo", settings.kis.trading_env)
        self.assertFalse(settings.live_order_enabled)
        self.assertFalse(settings.simulation_order_broker_send)

    def test_env_override(self):
        with patch.dict(os.environ, {"GOLDILOCKS_PORT": "22582"}, clear=True):
            self.assertEqual(AppSettings.from_env().goldilocks.port, 22582)

    def test_goldilocks_listen_port_fallback(self):
        with patch.dict(os.environ, {"GOLDILOCKS_LISTEN_PORT": "11100"}, clear=True):
            self.assertEqual(AppSettings.from_env().goldilocks.port, 11100)

    def test_sec_edgar_user_agent_contact_validation(self):
        self.assertTrue(
            sec_edgar_user_agent_has_real_contact(
                "Silver Platter ops@silverplatter.dev"
            )
        )
        self.assertFalse(sec_edgar_user_agent_has_real_contact(""))
        self.assertFalse(sec_edgar_user_agent_has_real_contact("Silver Platter"))
        self.assertFalse(
            sec_edgar_user_agent_has_real_contact("Silver Platter admin@example.com")
        )
        self.assertFalse(
            sec_edgar_user_agent_has_real_contact(
                "Silver Platter admin@team.example.org"
            )
        )


if __name__ == "__main__":
    unittest.main()
