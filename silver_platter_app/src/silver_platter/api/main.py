from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel

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
    detect_geopolitical_market_alert,
)
from silver_platter.health import get_health
from silver_platter.ml import FeatureSnapshot, ModelRegistry, predict_many
from silver_platter.ml_ops import (
    WatchlistRegistry,
    create_prediction_job,
    run_prediction_job,
)
from silver_platter.broker import KoreaInvestmentBrokerAdapter, PaperBrokerAdapter
from silver_platter.backtest import (
    BacktestRunConfig,
    ScenarioShock,
    StrategyOrderCandidate,
    apply_scenario_shock,
    run_backtest,
)
from silver_platter.backup import restore_check
from silver_platter.audit import AuditLog
from silver_platter.operations import ComponentStatus, summarize_operations
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
    horizons: List[str] = ["1d", "1w", "1m", "3m"]
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


class MlPredictionJobRequest(BaseModel):
    job_id: str
    snapshot: FeatureSnapshotRequest
    horizons: List[str] = ["1d", "1w", "1m", "3m"]


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
    detail: Dict[str, str] = {}


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
    return {
        "job": job.__dict__,
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

    def strategy(bar: PriceBarInput) -> StrategyOrderCandidate:
        return StrategyOrderCandidate(
            security_id=request.security_id,
            side=request.side,
            market=request.market,
            order_type=request.order_type,
            price=float(bar.close_price or 0.0),
            quantity=request.quantity,
            decision_at=bar.bar_ts,
            avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
        )

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
        "ending_cash_krw": result.ending_cash_krw,
        "realized_pnl_krw": result.realized_pnl_krw,
        "blocked_order_count": result.blocked_order_count,
        "lookahead_violation_count": result.lookahead_violation_count,
        "metrics": result.metrics,
        "order_events": [event.__dict__ for event in result.order_events],
    }


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
