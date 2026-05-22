from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel

from silver_platter.business_groups import (
    VolatilityObservation,
    normalized_group_volatility_changes,
)
from silver_platter.config import AppSettings
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
from silver_platter.order_preview import OrderPreviewInput, create_order_preview
from silver_platter.tax import (
    OverseasRealizedTrade,
    estimate_overseas_capital_gains_tax,
)


app = FastAPI(title="Silver Platter API", version="0.1.0")


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


class VolatilityObservationRequest(BaseModel):
    group_id: str
    observation_date: date
    volatility_value: float


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
