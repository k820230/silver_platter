import json
from datetime import datetime
from typing import Dict, Optional

from silver_platter.alerts import AlertDeliveryResult
from silver_platter.audit import AuditEvent
from silver_platter.backtest import (
    BacktestOrderEvent,
    BacktestResult,
    BacktestRunConfig,
    ScenarioResult,
    ScenarioShock,
)
from silver_platter.backup import RestoreCheckResult
from silver_platter.charting import IndexChartSeries
from silver_platter.data_pipeline import PriceBarIngestionResult, RawDataManifest
from silver_platter.data_quality import DataQualityResult, PriceBarInput
from silver_platter.headlines import Headline, HeadlineDedupCluster
from silver_platter.ml_ops import ModelErrorSummary, WatchlistItem
from silver_platter.order_state import OrderStateEvent
from silver_platter.providers import ProviderLicensePolicy, ProviderMetadata, SecurityReference
from silver_platter.risk_controls import EventRiskSignal
from silver_platter.verification import GateAssessment, GateEvidence


class GoldilocksRepository:
    def __init__(self, connection: object):
        self.connection = connection

    def commit(self) -> None:
        self.connection.commit()

    def upsert_provider(
        self,
        provider: ProviderMetadata,
        provider_name: Optional[str] = None,
        base_url: Optional[str] = None,
        auth_type: Optional[str] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.data_provider (
                provider_code,
                provider_name,
                provider_type,
                base_url,
                auth_type
            )
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM SP.data_provider WHERE provider_code = ?
            )
            """,
            (
                provider.provider_code,
                provider_name or provider.provider_code,
                provider.provider_type,
                base_url,
                auth_type,
                provider.provider_code,
            ),
        )

    def upsert_security_reference(self, security: SecurityReference) -> None:
        self._execute(
            """
            INSERT INTO SP.security_master (
                symbol,
                security_name,
                market_code,
                country_code,
                currency,
                asset_type,
                exchange_code
            )
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM SP.security_master
                WHERE market_code = ? AND symbol = ?
            )
            """,
            (
                security.symbol,
                security.security_name,
                security.market_code,
                security.country_code,
                security.currency,
                security.asset_type,
                security.exchange_code,
                security.market_code,
                security.symbol,
            ),
        )

    def insert_data_license(
        self,
        provider_id: int,
        policy: ProviderLicensePolicy,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.data_license (
                provider_id,
                license_name,
                can_store,
                can_transform,
                can_display_realtime,
                can_redistribute,
                effective_from,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_id,
                policy.license_name,
                policy.can_store,
                policy.can_transform,
                policy.can_display_realtime,
                policy.can_redistribute,
                policy.effective_from,
                policy.effective_to,
            ),
        )

    def insert_provider_symbol_map(
        self,
        provider_id: int,
        security_id: int,
        provider_symbol: str,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.provider_symbol_map (
                provider_id,
                security_id,
                provider_symbol,
                valid_from,
                valid_to
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                provider_id,
                security_id,
                provider_symbol,
                valid_from,
                valid_to,
            ),
        )

    def insert_raw_manifest(
        self,
        provider_id: int,
        manifest: RawDataManifest,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.raw_data_manifest (
                provider_id,
                dataset_name,
                source_uri,
                storage_uri,
                content_sha256,
                loaded_at,
                quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_id,
                manifest.dataset_name,
                manifest.source_uri,
                manifest.storage_uri,
                manifest.content_sha256,
                manifest.loaded_at,
                manifest.quality_status,
            ),
        )

    def insert_data_quality_run(
        self,
        dataset_name: str,
        result: DataQualityResult,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        started = started_at or datetime.utcnow()
        completed = completed_at or started
        self._execute(
            """
            INSERT INTO SP.data_quality_run (
                dataset_name,
                started_at,
                completed_at,
                quality_status,
                issue_count,
                detail
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_name,
                started,
                completed,
                result.status,
                len(result.issues),
                json.dumps(result.as_dict(), ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_price_bar(
        self,
        provider_id: int,
        security_id: int,
        bar: PriceBarInput,
        bar_interval: str = "1d",
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.price_bar (
                security_id,
                provider_id,
                bar_interval,
                market_date,
                bar_ts,
                close_price,
                volume,
                turnover_krw,
                available_to_model_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                security_id,
                provider_id,
                bar_interval,
                bar.bar_ts.date(),
                bar.bar_ts,
                bar.close_price,
                bar.volume,
                bar.turnover_krw,
                bar.available_to_model_at,
            ),
        )

    def write_price_bar_ingestion(
        self,
        provider_id: int,
        security_id: int,
        result: PriceBarIngestionResult,
        bar_interval: str = "1d",
    ) -> None:
        self.insert_raw_manifest(provider_id, result.manifest)
        self.insert_data_quality_run(result.dataset_name, result.quality)
        for bar in result.bars:
            self.insert_price_bar(provider_id, security_id, bar, bar_interval)

    def insert_user_watchlist_item(
        self,
        item: WatchlistItem,
        security_id: int,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.user_watchlist (
                user_id,
                security_id,
                note,
                created_at,
                deactivated_at,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item.user_id,
                security_id,
                item.note,
                item.created_at,
                None if item.is_active else datetime.utcnow(),
                item.is_active,
            ),
        )

    def deactivate_user_watchlist_item(
        self,
        user_id: str,
        security_id: int,
        deactivated_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            UPDATE SP.user_watchlist
            SET is_active = FALSE,
                deactivated_at = ?
            WHERE user_id = ?
              AND security_id = ?
              AND is_active = TRUE
            """,
            (
                deactivated_at or datetime.utcnow(),
                user_id,
                security_id,
            ),
        )

    def insert_model_error_summary(
        self,
        security_id: int,
        model_version: str,
        horizon: str,
        summary: ModelErrorSummary,
        calculated_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.ml_model_performance_summary (
                security_id,
                model_version,
                horizon,
                sample_count,
                mean_absolute_error,
                mean_absolute_pct_error,
                calculated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                security_id,
                model_version,
                horizon,
                summary.sample_count,
                summary.mean_absolute_error,
                summary.mean_absolute_pct_error,
                calculated_at or datetime.utcnow(),
            ),
        )

    def insert_index_chart_snapshot(
        self,
        security_id: int,
        series: IndexChartSeries,
        chart_type: str = "volatility_risk",
        generated_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.index_chart_snapshot (
                security_id,
                chart_type,
                start_at,
                end_at,
                generated_at,
                point_count,
                payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                security_id,
                chart_type,
                series.start_at,
                series.end_at,
                generated_at or datetime.utcnow(),
                len(series.points),
                json.dumps(series.as_dict(), ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_audit_event(self, event: AuditEvent) -> None:
        self._execute(
            """
            INSERT INTO SP.audit_log (
                actor_type,
                actor_id,
                action_code,
                target_type,
                target_id,
                occurred_at,
                detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.actor_type,
                event.actor_id,
                event.action_code,
                event.target_type,
                event.target_id,
                event.occurred_at,
                json.dumps(event.detail, ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_order_state_event(
        self,
        order_request_id: int,
        event: OrderStateEvent,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.order_state_event (
                order_request_id,
                from_status,
                to_status,
                occurred_at,
                filled_quantity_delta,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_request_id,
                event.from_state,
                event.to_state,
                event.occurred_at,
                event.filled_quantity_delta,
                event.reason,
            ),
        )

    def insert_order_idempotency_key(
        self,
        idempotency_key: str,
        order_request_id: int,
        reserved_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.order_idempotency_key (
                idempotency_key,
                order_request_id,
                reserved_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                idempotency_key,
                order_request_id,
                reserved_at or datetime.utcnow(),
                expires_at,
            ),
        )

    def insert_backtest_run(
        self,
        config: BacktestRunConfig,
        result: Optional[BacktestResult] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        summary = {}
        if result is not None:
            summary = {
                "ending_cash_krw": result.ending_cash_krw,
                "realized_pnl_krw": result.realized_pnl_krw,
                "blocked_order_count": result.blocked_order_count,
                "lookahead_violation_count": result.lookahead_violation_count,
                "metrics": result.metrics,
            }
        self._execute(
            """
            INSERT INTO SP.backtest_run (
                run_code,
                strategy_id,
                market_scope,
                from_date,
                to_date,
                initial_cash_krw,
                status,
                started_at,
                completed_at,
                result_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config.run_id,
                config.strategy_id,
                config.market_scope,
                config.from_date,
                config.to_date,
                config.initial_cash_krw,
                result.status if result is not None else "queued",
                started_at,
                completed_at,
                json.dumps(summary, ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_backtest_order_event(
        self,
        backtest_run_id: int,
        event: BacktestOrderEvent,
        security_id: Optional[int] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.backtest_order_event (
                backtest_run_id,
                security_id,
                side,
                order_type,
                order_price,
                quantity,
                decision_at,
                accepted,
                reason,
                realized_pnl_krw
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                backtest_run_id,
                security_id,
                event.candidate.side,
                event.candidate.order_type,
                event.candidate.price,
                event.candidate.quantity,
                event.candidate.decision_at,
                event.accepted,
                event.reason,
                event.realized_pnl_krw,
            ),
        )

    def insert_backtest_metric(
        self,
        backtest_run_id: int,
        metric_code: str,
        metric_value: float,
        calculated_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.backtest_metric (
                backtest_run_id,
                metric_code,
                metric_value,
                calculated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                backtest_run_id,
                metric_code,
                metric_value,
                calculated_at or datetime.utcnow(),
            ),
        )

    def write_backtest_result(
        self,
        backtest_run_id: int,
        result: BacktestResult,
        security_id_map: Optional[Dict[str, int]] = None,
    ) -> None:
        security_ids = security_id_map or {}
        for event in result.order_events:
            self.insert_backtest_order_event(
                backtest_run_id,
                event,
                security_ids.get(event.candidate.security_id),
            )
        for metric_code, metric_value in sorted(result.metrics.items()):
            self.insert_backtest_metric(backtest_run_id, metric_code, metric_value)

    def insert_scenario_result(
        self,
        shock: ScenarioShock,
        result: ScenarioResult,
        created_at: Optional[datetime] = None,
        detail: Optional[Dict[str, object]] = None,
    ) -> None:
        payload = detail or {
            "price_shock_pct": shock.price_shock_pct,
            "fx_shock_pct": shock.fx_shock_pct,
            "liquidity_multiplier": shock.liquidity_multiplier,
        }
        self._execute(
            """
            INSERT INTO SP.scenario_result (
                scenario_code,
                scenario_name,
                shocked_price,
                shocked_fx_rate,
                shocked_turnover_krw,
                created_at,
                detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.scenario_id,
                shock.name,
                result.shocked_price,
                result.shocked_fx_rate,
                result.shocked_turnover_krw,
                created_at or datetime.utcnow(),
                json.dumps(payload, ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_restore_check_run(
        self,
        result: RestoreCheckResult,
        backup_run_id: Optional[int] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.restore_check_run (
                backup_run_id,
                manifest_path,
                checked_at,
                status,
                issue_count,
                issues
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                backup_run_id,
                result.manifest_path,
                result.checked_at,
                result.status,
                result.issue_count,
                json.dumps(result.issues, ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_gate_assessment(
        self,
        assessment: GateAssessment,
        assessed_at: Optional[datetime] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.verification_gate_assessment (
                gate_id,
                status,
                passed_count,
                total_count,
                assessed_at,
                detail
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.gate_id,
                assessment.status,
                assessment.passed_count,
                assessment.total_count,
                assessed_at or datetime.utcnow(),
                json.dumps(assessment.as_dict(), ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_gate_evidence(
        self,
        gate_id: str,
        evidence: GateEvidence,
        gate_assessment_id: Optional[int] = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO SP.verification_gate_evidence (
                verification_gate_assessment_id,
                gate_id,
                requirement_id,
                status,
                evidence_uri,
                checked_at,
                detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gate_assessment_id,
                gate_id,
                evidence.requirement_id,
                evidence.status,
                evidence.evidence_uri,
                evidence.checked_at,
                evidence.detail,
            ),
        )

    def insert_alert_delivery_result(self, result: AlertDeliveryResult) -> None:
        self._execute(
            """
            INSERT INTO SP.alert_delivery_run (
                provider_code,
                alert_id,
                status,
                delivered_at,
                error_message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                result.provider_code,
                result.alert_id,
                result.status,
                result.delivered_at,
                result.error_message,
            ),
        )

    def insert_headline_event(self, headline: Headline) -> None:
        self._execute(
            """
            INSERT INTO SP.headline_event (
                provider_code,
                provider_raw_ref,
                headline,
                published_at,
                source_url,
                security_ids,
                group_ids,
                event_tags,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                headline.provider,
                headline.metadata.get("raw_ref", headline.url),
                headline.title,
                headline.published_at,
                headline.url,
                json.dumps(list(headline.security_ids), ensure_ascii=True, sort_keys=True),
                json.dumps(list(headline.group_ids), ensure_ascii=True, sort_keys=True),
                json.dumps(list(headline.event_tags), ensure_ascii=True, sort_keys=True),
                json.dumps(headline.metadata, ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_headline_dedup_cluster(self, cluster: HeadlineDedupCluster) -> None:
        self._execute(
            """
            INSERT INTO SP.headline_dedup_cluster (
                cluster_code,
                representative_provider_code,
                representative_headline,
                representative_published_at,
                provider_count,
                headline_count,
                source_urls
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cluster.cluster_id,
                cluster.representative.provider,
                cluster.representative.title,
                cluster.representative.published_at,
                cluster.provider_count,
                len(cluster.headlines),
                json.dumps(list(cluster.source_urls), ensure_ascii=True, sort_keys=True),
            ),
        )

    def insert_headline_risk_signal(self, signal: EventRiskSignal) -> None:
        self._execute(
            """
            INSERT INTO SP.headline_risk_signal (
                cluster_code,
                event_type,
                severity,
                observed_at,
                expires_at,
                security_ids,
                group_ids
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.event_id,
                signal.event_type,
                signal.severity,
                signal.observed_at,
                signal.expires_at,
                json.dumps(sorted(signal.security_ids), ensure_ascii=True, sort_keys=True),
                json.dumps(sorted(signal.group_ids), ensure_ascii=True, sort_keys=True),
            ),
        )

    def _execute(self, sql: str, params: tuple) -> object:
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        return cursor
