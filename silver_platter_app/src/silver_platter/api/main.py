from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from silver_platter.business_groups import (
    VolatilityObservation,
    normalized_group_volatility_changes,
)
from silver_platter.config import AppSettings
from silver_platter.charting import IndexObservation, build_index_chart_series
from silver_platter.data_quality import PriceBarInput, evaluate_price_bars
from silver_platter.disclosures import (
    DisclosureReaction,
    analyze_disclosure_impacts,
    predict_disclosure_impact,
)
from silver_platter.headlines import (
    EventMarketSnapshot,
    Headline,
    deduplicate_headlines,
    detect_geopolitical_market_alert,
)
from silver_platter.health import get_health
from silver_platter.ml import FeatureSnapshot, ModelRegistry, predict_many
from silver_platter.ml_ops import (
    WatchlistRegistry,
    create_prediction_job,
    match_due_prediction_actuals,
    run_prediction_job,
    summarize_prediction_errors,
)
from silver_platter.broker import KoreaInvestmentBrokerAdapter, PaperBrokerAdapter
from silver_platter.risk_controls import headline_clusters_to_event_risk_signals
from silver_platter.backtest import (
    BacktestRunConfig,
    ScenarioShock,
    StrategyOrderCandidate,
    apply_scenario_shock,
    build_paper_replay_evidence,
    run_backtest,
)
from silver_platter.backup import restore_check, summarize_backup_restore_status
from silver_platter.replay import (
    ExportedSnapshotReplayConfig,
    run_exported_snapshot_replay,
)
from silver_platter.strategies import DEFAULT_STRATEGY_REGISTRY, StrategyContext
from silver_platter.audit import AuditLog
from silver_platter.operations import (
    ComponentStatus,
    provider_health_components,
    summarize_operations,
)
from silver_platter.providers import (
    default_mvp_provider_catalog,
    license_policy_from_provider,
)
from silver_platter.verification import (
    DEFAULT_GATE_REQUIREMENTS,
    GateEvidence,
    assess_gate,
)
from silver_platter.order_preview import OrderPreviewInput, create_order_preview
from silver_platter.order_service import OrderSubmissionInput, OrderSubmissionService
from silver_platter.order_state import IdempotencyRegistry
from silver_platter.tax import (
    OverseasRealizedTrade,
    estimate_overseas_capital_gains_tax,
)


app = FastAPI(title="Silver Platter API", version="0.1.0")
ORDER_IDEMPOTENCY = IdempotencyRegistry()
WATCHLISTS = WatchlistRegistry()
AUDIT_LOG = AuditLog()


class OrderPreviewRequest(BaseModel):
    account_id: str
    security_id: str
    side: str
    order_type: str
    market: str
    current_price: float
    quantity: float
    avg_daily_turnover_20d_krw: Optional[float]
    volatility_annualized: float = 0.30
    is_auto_order: bool = False
    fx_rate_krw: float = 1.0
    horizons: List[str] = Field(default_factory=lambda: ["1d", "1w", "1m", "3m"])
    group_day_new_order_amount_krw: Optional[float] = None
    group_avg_daily_turnover_20d_krw: Optional[float] = None


class FeatureSnapshotRequest(BaseModel):
    security_id: str
    as_of: datetime
    last_price: float
    avg_volume_20d: float
    annualized_volatility: float
    risk_score: float
    drift_per_day: float = 0.0


class MlPredictionRequest(BaseModel):
    snapshots: List[FeatureSnapshotRequest]


class WatchlistAddRequest(BaseModel):
    user_id: str
    security_id: str
    note: str = ""


class ActualPriceBarRequest(BaseModel):
    security_id: str
    bar_ts: datetime
    close_price: Optional[float]
    volume: Optional[float]
    turnover_krw: Optional[float]
    available_to_model_at: Optional[datetime]


class MlPredictionJobRequest(BaseModel):
    job_id: str
    snapshot: FeatureSnapshotRequest
    horizons: List[str] = Field(default_factory=lambda: ["1d", "1w", "1m", "3m"])
    actual_bars: List[ActualPriceBarRequest] = Field(default_factory=list)
    observed_at: Optional[datetime] = None


class VolatilityObservationRequest(BaseModel):
    group_id: str
    observation_date: date
    volatility_value: float


class IndexObservationRequest(BaseModel):
    security_id: str
    observed_at: datetime
    volatility_index: float
    risk_score: float


class IndexChartRequest(BaseModel):
    security_id: str
    observations: List[IndexObservationRequest]
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class GroupVolatilityCompareRequest(BaseModel):
    base_date: date
    observations: List[VolatilityObservationRequest]


class EventMarketAlertRequest(BaseModel):
    event_id: str
    observed_at: datetime
    event_tags: Tuple[str, ...]
    five_min_avg_volume: float
    previous_5d_five_min_avg_volume: float
    title: str = ""


class HeadlineRiskSignalItem(BaseModel):
    provider: str
    title: str
    published_at: datetime
    url: str
    security_ids: List[str] = Field(default_factory=list)
    group_ids: List[str] = Field(default_factory=list)
    event_tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class HeadlineRiskSignalsRequest(BaseModel):
    headlines: List[HeadlineRiskSignalItem]


class DisclosureReactionRequest(BaseModel):
    disclosure_type: str
    disclosed_date: date
    reaction_window_days: int
    return_pct: float
    volume_change_pct: float = 0.0


class DisclosureImpactRequest(BaseModel):
    current_price: float
    disclosure_type: str
    reactions: List[DisclosureReactionRequest]


class OverseasRealizedTradeRequest(BaseModel):
    security_id: str
    market: str
    realized_date: date
    realized_pnl_krw: float
    fee_krw: float = 0.0


class OverseasTaxEstimateRequest(BaseModel):
    tax_year: int
    trades: List[OverseasRealizedTradeRequest]


class PriceBarQualityRequest(BaseModel):
    bars: List["PriceBarQualityItem"]


class PriceBarQualityItem(BaseModel):
    security_id: str
    bar_ts: datetime
    close_price: Optional[float]
    volume: Optional[float]
    turnover_krw: Optional[float]
    available_to_model_at: Optional[datetime]


class BacktestRunRequest(BaseModel):
    run_id: str
    strategy_id: str
    from_date: date
    to_date: date
    security_id: str
    market: str = "KR"
    side: str = "buy"
    order_type: str = "limit"
    quantity: float
    avg_daily_turnover_20d_krw: float
    bars: List[PriceBarQualityItem]
    initial_cash_krw: float = 100_000_000.0
    strategy_plugin_id: str = "fixed-close"
    strategy_parameters: Dict[str, Any] = Field(default_factory=dict)


class ExportedSnapshotReplayRequest(BaseModel):
    run_id: str
    strategy_id: str
    from_date: date
    to_date: date
    security_id: str
    snapshot_paths: List[str]
    market: str = "KR"
    side: str = "buy"
    order_type: str = "limit"
    quantity: float = 1.0
    avg_daily_turnover_20d_krw: float = 1_000_000_000.0
    initial_cash_krw: float = 100_000_000.0
    required_min_days: int = 1
    strategy_plugin_id: str = "fixed-close"
    strategy_parameters: Dict[str, Any] = Field(default_factory=dict)


class ScenarioShockRequest(BaseModel):
    scenario_id: str
    name: str
    current_price: float
    fx_rate: float
    avg_daily_turnover_20d_krw: float
    price_shock_pct: float = 0.0
    fx_shock_pct: float = 0.0
    liquidity_multiplier: float = 1.0


class RestoreCheckRequest(BaseModel):
    manifest_path: str


class AuditEventRequest(BaseModel):
    actor_type: str
    action_code: str
    target_type: str
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    detail: Dict[str, str] = Field(default_factory=dict)


class ComponentStatusRequest(BaseModel):
    component: str
    status: str
    detail: str
    checked_at: datetime


class OperationsSummaryRequest(BaseModel):
    components: List[ComponentStatusRequest]


class GateEvidenceRequest(BaseModel):
    requirement_id: str
    status: str
    evidence_uri: str
    checked_at: datetime
    detail: str = ""


class GateAssessmentRequest(BaseModel):
    gate_id: str
    evidence: List[GateEvidenceRequest]


class OrderSubmitRequest(BaseModel):
    order_id: str
    account_id: str
    security_id: str
    side: str
    order_type: str
    market: str
    current_price: float
    quantity: float
    avg_daily_turnover_20d_krw: float
    idempotency_key: str
    broker_code: str = "paper"
    limit_price: Optional[float] = None


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _missing_provider_settings(settings: AppSettings) -> List[str]:
    missing = []
    if not settings.opendart_api_key.strip():
        missing.append("opendart")
    if not settings.ecos_api_key.strip():
        missing.append("ecos_bok")
    user_agent = settings.sec_edgar_user_agent.strip().lower()
    if not user_agent or "example.com" in user_agent:
        missing.append("sec_edgar")
    if not settings.krx_kind_smoke_enabled:
        missing.append("krx_kind")
    if not settings.krx_price_smoke_enabled:
        missing.append("krx_data:market_data")
    return missing


@app.get("/health")
def health() -> Dict[str, Any]:
    return get_health(AppSettings.from_env())


@app.post("/api/orders/preview")
def order_preview(request: OrderPreviewRequest) -> Dict[str, Any]:
    preview_input = OrderPreviewInput(
        account_id=request.account_id,
        security_id=request.security_id,
        side=request.side,
        order_type=request.order_type,
        market=request.market,
        current_price=request.current_price,
        quantity=request.quantity,
        avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
        volatility_annualized=request.volatility_annualized,
        is_auto_order=request.is_auto_order,
        fx_rate_krw=request.fx_rate_krw,
        horizons=request.horizons,
        group_day_new_order_amount_krw=request.group_day_new_order_amount_krw,
        group_avg_daily_turnover_20d_krw=request.group_avg_daily_turnover_20d_krw,
    )
    return create_order_preview(preview_input)


@app.post("/api/orders/submit")
def order_submit(request: OrderSubmitRequest) -> Dict[str, Any]:
    broker = (
        KoreaInvestmentBrokerAdapter(live_order_enabled=False)
        if request.broker_code.strip().lower() in {"kis", "korea_investment"}
        else PaperBrokerAdapter()
    )
    service = OrderSubmissionService(broker, ORDER_IDEMPOTENCY)
    result = service.submit(
        OrderSubmissionInput(
            order_id=request.order_id,
            account_id=request.account_id,
            security_id=request.security_id,
            side=request.side,
            order_type=request.order_type,
            market=request.market,
            current_price=request.current_price,
            quantity=request.quantity,
            avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
            idempotency_key=request.idempotency_key,
            limit_price=request.limit_price,
        )
    )
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "broker_order_id": result.broker_order_id,
        "state": result.state.__dict__,
        "events": [event.__dict__ for event in result.events],
        "preview": result.preview,
    }


@app.post("/api/ml/predictions")
def ml_predictions(request: MlPredictionRequest) -> Dict[str, Any]:
    snapshots = [
        FeatureSnapshot(
            security_id=item.security_id,
            as_of=item.as_of,
            last_price=item.last_price,
            avg_volume_20d=item.avg_volume_20d,
            annualized_volatility=item.annualized_volatility,
            risk_score=item.risk_score,
            drift_per_day=item.drift_per_day,
        )
        for item in request.snapshots
    ]
    predictions = predict_many(ModelRegistry(), snapshots)
    return {
        security_id: [prediction.__dict__ for prediction in values]
        for security_id, values in predictions.items()
    }


@app.post("/api/watchlist/items")
def watchlist_add(request: WatchlistAddRequest) -> Dict[str, Any]:
    item = WATCHLISTS.add(request.user_id, request.security_id, request.note)
    return item.__dict__


@app.delete("/api/watchlist/items/{user_id}/{security_id}")
def watchlist_remove(user_id: str, security_id: str) -> Dict[str, Any]:
    item = WATCHLISTS.remove(user_id, security_id)
    return {"removed": item is not None, "item": None if item is None else item.__dict__}


@app.get("/api/watchlist/items/{user_id}")
def watchlist_list(user_id: str) -> Dict[str, Any]:
    return {"items": [item.__dict__ for item in WATCHLISTS.list_active(user_id)]}


@app.post("/api/ml/jobs/run")
def ml_job_run(request: MlPredictionJobRequest) -> Dict[str, Any]:
    snapshot = FeatureSnapshot(
        security_id=request.snapshot.security_id,
        as_of=request.snapshot.as_of,
        last_price=request.snapshot.last_price,
        avg_volume_20d=request.snapshot.avg_volume_20d,
        annualized_volatility=request.snapshot.annualized_volatility,
        risk_score=request.snapshot.risk_score,
        drift_per_day=request.snapshot.drift_per_day,
    )
    job = create_prediction_job(
        request.job_id,
        request.snapshot.security_id,
        request.horizons,
        request.snapshot.as_of,
    )
    predictions = run_prediction_job(job, snapshot)
    if request.actual_bars:
        observed_at = request.observed_at or max(
            (
                item.available_to_model_at
                for item in request.actual_bars
                if item.available_to_model_at is not None
            ),
            default=datetime.utcnow(),
        )
        predictions = match_due_prediction_actuals(
            predictions,
            [
                PriceBarInput(
                    security_id=item.security_id,
                    bar_ts=item.bar_ts,
                    close_price=item.close_price,
                    volume=item.volume,
                    turnover_krw=item.turnover_krw,
                    available_to_model_at=item.available_to_model_at,
                )
                for item in request.actual_bars
            ],
            observed_at,
        )
    return {
        "job": job.__dict__,
        "error_summary": summarize_prediction_errors(predictions, job.security_id).__dict__,
        "predictions": [
            {
                **prediction.__dict__,
                "interval": prediction.interval.__dict__,
            }
            for prediction in predictions
        ],
    }


@app.post("/api/indices/chart")
def index_chart(request: IndexChartRequest) -> Dict[str, Any]:
    series = build_index_chart_series(
        [
            IndexObservation(
                security_id=item.security_id,
                observed_at=item.observed_at,
                volatility_index=item.volatility_index,
                risk_score=item.risk_score,
            )
            for item in request.observations
        ],
        request.security_id,
        request.start_at,
        request.end_at,
    )
    return series.as_dict()


@app.post("/api/groups/volatility/compare")
def group_volatility_compare(
    request: GroupVolatilityCompareRequest,
) -> Dict[str, Any]:
    normalized = normalized_group_volatility_changes(
        [
            VolatilityObservation(
                group_id=item.group_id,
                observation_date=item.observation_date,
                volatility_value=item.volatility_value,
            )
            for item in request.observations
        ],
        request.base_date,
    )
    return {
        group_id: [point.__dict__ for point in points]
        for group_id, points in normalized.items()
    }


@app.post("/api/events/geopolitical-alert")
def geopolitical_alert(request: EventMarketAlertRequest) -> Dict[str, Any]:
    alert = detect_geopolitical_market_alert(
        EventMarketSnapshot(
            event_id=request.event_id,
            observed_at=request.observed_at,
            event_tags=request.event_tags,
            five_min_avg_volume=request.five_min_avg_volume,
            previous_5d_five_min_avg_volume=request.previous_5d_five_min_avg_volume,
            title=request.title,
        )
    )
    return {"alert": None if alert is None else alert.as_dict()}


@app.post("/api/headlines/risk-signals")
def headline_risk_signals(request: HeadlineRiskSignalsRequest) -> Dict[str, Any]:
    clusters = deduplicate_headlines(
        [
            Headline(
                provider=item.provider,
                title=item.title,
                published_at=item.published_at,
                url=item.url,
                security_ids=tuple(item.security_ids),
                group_ids=tuple(item.group_ids),
                event_tags=tuple(item.event_tags),
                metadata=item.metadata,
            )
            for item in request.headlines
        ]
    )
    signals = headline_clusters_to_event_risk_signals(clusters)
    return {
        "clusters": [cluster.as_dict() for cluster in clusters],
        "signals": [
            {
                "event_id": signal.event_id,
                "event_type": signal.event_type,
                "severity": signal.severity,
                "observed_at": signal.observed_at.isoformat(),
                "security_ids": sorted(signal.security_ids),
                "group_ids": sorted(signal.group_ids),
                "expires_at": None
                if signal.expires_at is None
                else signal.expires_at.isoformat(),
            }
            for signal in signals
        ],
    }


@app.post("/api/disclosures/impact-preview")
def disclosure_impact_preview(request: DisclosureImpactRequest) -> Dict[str, Any]:
    pattern = analyze_disclosure_impacts(
        [
            DisclosureReaction(
                disclosure_type=item.disclosure_type,
                disclosed_date=item.disclosed_date,
                reaction_window_days=item.reaction_window_days,
                return_pct=item.return_pct,
                volume_change_pct=item.volume_change_pct,
            )
            for item in request.reactions
        ],
        request.disclosure_type,
    )
    prediction = predict_disclosure_impact(request.current_price, pattern)
    return {
        "pattern": pattern.__dict__,
        "prediction": prediction.__dict__,
    }


@app.post("/api/tax/overseas-capital-gains")
def overseas_capital_gains_tax(
    request: OverseasTaxEstimateRequest,
) -> Dict[str, Any]:
    estimate = estimate_overseas_capital_gains_tax(
        [
            OverseasRealizedTrade(
                security_id=item.security_id,
                market=item.market,
                realized_date=item.realized_date,
                realized_pnl_krw=item.realized_pnl_krw,
                fee_krw=item.fee_krw,
            )
            for item in request.trades
        ],
        request.tax_year,
    )
    return estimate.as_dict()


@app.post("/api/data/price-bars/quality")
def price_bar_quality(request: PriceBarQualityRequest) -> Dict[str, Any]:
    result = evaluate_price_bars(
        [
            PriceBarInput(
                security_id=item.security_id,
                bar_ts=item.bar_ts,
                close_price=item.close_price,
                volume=item.volume,
                turnover_krw=item.turnover_krw,
                available_to_model_at=item.available_to_model_at,
            )
            for item in request.bars
        ]
    )
    return result.as_dict()


@app.post("/api/backtests/run")
def backtest_run(request: BacktestRunRequest) -> Dict[str, Any]:
    bars = [
        PriceBarInput(
            security_id=item.security_id,
            bar_ts=item.bar_ts,
            close_price=item.close_price,
            volume=item.volume,
            turnover_krw=item.turnover_krw,
            available_to_model_at=item.available_to_model_at,
        )
        for item in request.bars
    ]

    try:
        strategy = DEFAULT_STRATEGY_REGISTRY.build(
            request.strategy_plugin_id,
            StrategyContext(
                strategy_id=request.strategy_id,
                security_id=request.security_id,
                market=request.market,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
                parameters=request.strategy_parameters,
            ),
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    result = run_backtest(
        BacktestRunConfig(
            run_id=request.run_id,
            strategy_id=request.strategy_id,
            from_date=request.from_date,
            to_date=request.to_date,
            initial_cash_krw=request.initial_cash_krw,
        ),
        bars,
        strategy,
    )
    return {
        "run_id": result.run_id,
        "status": result.status,
        "strategy_plugin_id": request.strategy_plugin_id,
        "ending_cash_krw": result.ending_cash_krw,
        "realized_pnl_krw": result.realized_pnl_krw,
        "blocked_order_count": result.blocked_order_count,
        "lookahead_violation_count": result.lookahead_violation_count,
        "metrics": result.metrics,
        "paper_replay_evidence": build_paper_replay_evidence(result).as_dict(),
        "order_events": [event.__dict__ for event in result.order_events],
    }


@app.post("/api/backtests/replay-exported-snapshot")
def backtest_replay_exported_snapshot(
    request: ExportedSnapshotReplayRequest,
) -> Dict[str, Any]:
    try:
        result = run_exported_snapshot_replay(
            ExportedSnapshotReplayConfig(
                run_id=request.run_id,
                strategy_id=request.strategy_id,
                from_date=request.from_date,
                to_date=request.to_date,
                security_id=request.security_id,
                snapshot_paths=[Path(path) for path in request.snapshot_paths],
                market=request.market,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
                initial_cash_krw=request.initial_cash_krw,
                required_min_days=request.required_min_days,
                strategy_plugin_id=request.strategy_plugin_id,
                strategy_parameters=request.strategy_parameters,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return result.as_dict()


@app.get("/api/backtests/strategy-plugins")
def backtest_strategy_plugins() -> Dict[str, Any]:
    return {"plugins": [plugin.as_dict() for plugin in DEFAULT_STRATEGY_REGISTRY.list_plugins()]}


@app.post("/api/scenarios/shock")
def scenario_shock(request: ScenarioShockRequest) -> Dict[str, Any]:
    result = apply_scenario_shock(
        request.current_price,
        request.fx_rate,
        request.avg_daily_turnover_20d_krw,
        ScenarioShock(
            scenario_id=request.scenario_id,
            name=request.name,
            price_shock_pct=request.price_shock_pct,
            fx_shock_pct=request.fx_shock_pct,
            liquidity_multiplier=request.liquidity_multiplier,
        ),
    )
    return result.__dict__


@app.post("/api/operations/restore-check")
def operations_restore_check(request: RestoreCheckRequest) -> Dict[str, Any]:
    result = restore_check(Path(request.manifest_path))
    return result.__dict__


@app.get("/api/operations/backup-status")
def operations_backup_status(
    backup_base_dir: Optional[str] = None,
    max_backup_age_days: int = 8,
) -> Dict[str, Any]:
    if max_backup_age_days < 1:
        raise HTTPException(400, "max_backup_age_days must be at least 1")
    settings = AppSettings.from_env()
    base_dir = Path(backup_base_dir or settings.backup_base_dir)
    return summarize_backup_restore_status(
        base_dir,
        max_backup_age_days=max_backup_age_days,
    ).as_dict()


@app.post("/api/audit/events")
def audit_event_append(request: AuditEventRequest) -> Dict[str, Any]:
    event = AUDIT_LOG.append(
        actor_type=request.actor_type,
        actor_id=request.actor_id,
        action_code=request.action_code,
        target_type=request.target_type,
        target_id=request.target_id,
        detail=request.detail,
    )
    return event.as_dict()


@app.get("/api/audit/events")
def audit_event_list(
    action_code: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "events": [
            event.as_dict()
            for event in AUDIT_LOG.query(action_code, target_type, target_id)
        ]
    }


@app.post("/api/operations/summary")
def operations_summary(request: OperationsSummaryRequest) -> Dict[str, Any]:
    summary = summarize_operations(
        [
            ComponentStatus(
                component=item.component,
                status=item.status,
                detail=item.detail,
                checked_at=item.checked_at,
            )
            for item in request.components
        ]
    )
    return summary.as_dict()


@app.get("/api/operations/provider-health")
def operations_provider_health() -> Dict[str, Any]:
    settings = AppSettings.from_env()
    summary = summarize_operations(
        provider_health_components(
            default_mvp_provider_catalog(),
            missing_credentials=_missing_provider_settings(settings),
        )
    )
    return summary.as_dict()


@app.get("/api/providers/catalog")
def provider_catalog() -> Dict[str, Any]:
    providers = []
    for provider in default_mvp_provider_catalog():
        policy = license_policy_from_provider(provider)
        providers.append(
            {
                "provider_code": provider.provider_code,
                "provider_type": provider.provider_type,
                "priority": provider.priority,
                "license_policy": {
                    "license_name": policy.license_name,
                    "can_store": policy.can_store,
                    "can_transform": policy.can_transform,
                    "can_display_realtime": policy.can_display_realtime,
                    "can_redistribute": policy.can_redistribute,
                },
            }
        )
    return {"providers": providers}


@app.post("/api/verification/gates/assess")
def verification_gate_assess(request: GateAssessmentRequest) -> Dict[str, Any]:
    assessment = assess_gate(
        request.gate_id,
        DEFAULT_GATE_REQUIREMENTS,
        [
            GateEvidence(
                requirement_id=item.requirement_id,
                status=item.status,
                evidence_uri=item.evidence_uri,
                checked_at=item.checked_at,
                detail=item.detail,
            )
            for item in request.evidence
        ],
    )
    return assessment.as_dict()
