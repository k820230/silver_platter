from datetime import datetime
from unittest import TestCase

from silver_platter.operations import (
    ComponentStatus,
    provider_health_components,
    summarize_operations,
)
from silver_platter.providers import ProviderLicensePolicy, ProviderMetadata


class OperationsTests(TestCase):
    def test_operations_summary_degraded_for_component_warning(self):
        summary = summarize_operations(
            [
                ComponentStatus("api", "ok", "ready", datetime(2026, 5, 22, 9, 0, 0)),
                ComponentStatus("backup", "failed", "checksum mismatch", datetime(2026, 5, 22, 9, 0, 0)),
            ],
            generated_at=datetime(2026, 5, 22, 9, 1, 0),
        )

        self.assertEqual("critical", summary.status)
        self.assertEqual(1, summary.open_issue_count)
        self.assertEqual("api", summary.as_dict()["components"][0]["component"])

    def test_provider_health_components_map_catalog_to_operations_statuses(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)
        components = provider_health_components(
            [
                ProviderMetadata("krx_data", "market_data", True, False, False, 20),
                ProviderMetadata("opendart", "disclosure", True, False, False, 10),
                ProviderMetadata("blocked_vendor", "market_data", False, False, False, 90),
            ],
            missing_credentials={"opendart"},
            failed_providers={"krx_data:market_data"},
            checked_at=checked_at,
        )

        statuses = {component.component: component.status for component in components}
        self.assertEqual("failed", statuses["provider:krx_data:market_data"])
        self.assertEqual("degraded", statuses["provider:opendart:disclosure"])
        self.assertEqual("block", statuses["provider:blocked_vendor:market_data"])
        self.assertEqual("critical", summarize_operations(components).status)
        krx_detail = {
            component.component: component.detail for component in components
        }["provider:krx_data:market_data"]
        self.assertIn("license=krx_data_mvp_policy", krx_detail)
        self.assertIn("redistribute=False", krx_detail)

    def test_provider_health_components_block_when_license_disallows_transform(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)
        components = provider_health_components(
            [ProviderMetadata("vendor", "headline", True, False, False, 20)],
            missing_credentials={"vendor"},
            license_policies=[
                ProviderLicensePolicy(
                    "vendor",
                    "vendor_view_only",
                    can_store=True,
                    can_transform=False,
                    can_display_realtime=False,
                    can_redistribute=False,
                )
            ],
            checked_at=checked_at,
        )

        self.assertEqual("block", components[0].status)
        self.assertIn("license blocks storage or transformation", components[0].detail)
        self.assertIn("license=vendor_view_only", components[0].detail)
