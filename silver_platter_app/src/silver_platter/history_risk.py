from dataclasses import dataclass
from math import sqrt
from statistics import fmean, pstdev
from typing import Iterable, List, Optional

from silver_platter.data_quality import PriceBarInput


RISK_RANGE_HORIZON_YEARS = {
    "1w": 5.0 / 252.0,
    "1d": 1.0 / 252.0,
    "1h": 1.0 / (252.0 * 6.5),
    "5m": 5.0 / (252.0 * 6.5 * 60.0),
}


@dataclass(frozen=True)
class PriceHistoryRiskPoint:
    bar_ts: str
    close_price: float
    volume: Optional[float]
    return_pct: Optional[float]
    rolling_volatility_pct: float
    volume_ratio: Optional[float]
    lower_bound: float
    upper_bound: float
    risk_score: float
    risk_status: str

    def as_dict(self) -> dict:
        return {
            "bar_ts": self.bar_ts,
            "close_price": self.close_price,
            "volume": self.volume,
            "return_pct": self.return_pct,
            "rolling_volatility_pct": self.rolling_volatility_pct,
            "volume_ratio": self.volume_ratio,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "risk_score": self.risk_score,
            "risk_status": self.risk_status,
        }


def build_price_history_risk_chart(
    security_id: str,
    market: str,
    bars: Iterable[PriceBarInput],
    selected_range: str = "1w",
    limit: int = 160,
) -> dict:
    if limit <= 0:
        raise ValueError("limit must be positive")
    normalized_range = selected_range.strip().lower()
    if normalized_range not in RISK_RANGE_HORIZON_YEARS:
        raise ValueError("risk_range must be one of 1w, 1d, 1h, 5m")

    clean_bars = _dedupe_sorted_bars(
        bar
        for bar in bars
        if bar.close_price is not None and float(bar.close_price) > 0
    )
    selected_bars = clean_bars[-limit:]
    points = _risk_points(selected_bars, normalized_range)
    latest = points[-1] if points else None
    latest_volume_avg = _average_latest_volume(selected_bars, 20)

    return {
        "security_id": security_id,
        "market": market,
        "risk_range": normalized_range,
        "bar_interval": "1d",
        "point_count": len(points),
        "current_price": latest.close_price if latest else None,
        "current_volume": latest.volume if latest else None,
        "latest_bar_ts": latest.bar_ts if latest else None,
        "latest_risk": latest.as_dict() if latest else None,
        "points": [point.as_dict() for point in points],
        "summary": _summary(security_id, market, normalized_range, latest),
        "evidence": _evidence(selected_bars, normalized_range, latest, latest_volume_avg),
        "reasoning": _reasoning(normalized_range),
    }


def _dedupe_sorted_bars(bars: Iterable[PriceBarInput]) -> List[PriceBarInput]:
    by_ts = {bar.bar_ts: bar for bar in sorted(bars, key=lambda item: item.bar_ts)}
    return [by_ts[key] for key in sorted(by_ts)]


def _risk_points(
    bars: List[PriceBarInput],
    selected_range: str,
) -> List[PriceHistoryRiskPoint]:
    closes = [float(bar.close_price or 0.0) for bar in bars]
    returns: List[Optional[float]] = [None]
    for previous, current in zip(closes, closes[1:]):
        returns.append((current / previous) - 1.0 if previous > 0 else None)

    points: List[PriceHistoryRiskPoint] = []
    for index, bar in enumerate(bars):
        close_price = closes[index]
        returns_window = [
            value
            for value in returns[max(1, index - 19) : index + 1]
            if value is not None
        ]
        daily_volatility = _rolling_volatility(returns_window)
        lower, upper = _risk_bounds(close_price, daily_volatility, selected_range)
        volume_ratio = _volume_ratio(bars, index, 20)
        score = _risk_score(close_price, lower, daily_volatility, volume_ratio)
        points.append(
            PriceHistoryRiskPoint(
                bar_ts=bar.bar_ts.isoformat(),
                close_price=round(close_price, 4),
                volume=None if bar.volume is None else round(float(bar.volume), 4),
                return_pct=None
                if returns[index] is None
                else round(float(returns[index]) * 100.0, 4),
                rolling_volatility_pct=round(daily_volatility * 100.0, 4),
                volume_ratio=None if volume_ratio is None else round(volume_ratio, 4),
                lower_bound=round(lower, 4),
                upper_bound=round(upper, 4),
                risk_score=round(score, 2),
                risk_status=_risk_status(score),
            )
        )
    return points


def _rolling_volatility(returns_window: List[float]) -> float:
    if len(returns_window) >= 2:
        return pstdev(returns_window)
    if returns_window:
        return abs(returns_window[-1])
    return 0.0


def _risk_bounds(
    close_price: float,
    daily_volatility: float,
    selected_range: str,
) -> tuple:
    annualized_volatility = daily_volatility * sqrt(252.0)
    horizon_sigma = annualized_volatility * sqrt(RISK_RANGE_HORIZON_YEARS[selected_range])
    z_score = 1.65
    lower = close_price * (1.0 - z_score * horizon_sigma)
    upper = close_price * (1.0 + z_score * horizon_sigma)
    return max(0.0, lower), max(0.0, upper)


def _volume_ratio(
    bars: List[PriceBarInput],
    index: int,
    window: int,
) -> Optional[float]:
    current_volume = bars[index].volume
    if current_volume is None:
        return None
    volumes = [
        float(bar.volume)
        for bar in bars[max(0, index - window + 1) : index + 1]
        if bar.volume is not None and float(bar.volume) > 0
    ]
    if not volumes:
        return None
    average_volume = fmean(volumes)
    if average_volume <= 0:
        return None
    return float(current_volume) / average_volume


def _average_latest_volume(bars: List[PriceBarInput], window: int) -> Optional[float]:
    volumes = [
        float(bar.volume)
        for bar in bars[-window:]
        if bar.volume is not None and float(bar.volume) > 0
    ]
    if not volumes:
        return None
    return fmean(volumes)


def _risk_score(
    close_price: float,
    lower_bound: float,
    daily_volatility: float,
    volume_ratio: Optional[float],
) -> float:
    downside_pct = ((close_price - lower_bound) / close_price) * 100.0
    volatility_component = min(45.0, daily_volatility * 100.0 * 9.0)
    downside_component = min(40.0, downside_pct * 6.0)
    volume_component = 0.0
    if volume_ratio is not None and volume_ratio > 1.0:
        volume_component = min(15.0, (volume_ratio - 1.0) * 6.0)
    return min(100.0, volatility_component + downside_component + volume_component)


def _risk_status(score: float) -> str:
    if score >= 70.0:
        return "critical"
    if score >= 40.0:
        return "watch"
    return "ok"


def _summary(
    security_id: str,
    market: str,
    selected_range: str,
    latest: Optional[PriceHistoryRiskPoint],
) -> str:
    if latest is None:
        return "%s/%s 저장 가격 데이터가 없어 리스크 그래프를 만들 수 없습니다." % (
            market,
            security_id,
        )
    downside_pct = (
        (latest.close_price - latest.lower_bound) / latest.close_price
    ) * 100.0
    upside_pct = ((latest.upper_bound - latest.close_price) / latest.close_price) * 100.0
    return (
        "%s/%s 현재가는 %.4f이고 %s 기준 리스크 범위는 %.4f~%.4f입니다. "
        "하방 폭은 %.2f%%, 상방 폭은 %.2f%%이며 최신 리스크 상태는 %s입니다."
        % (
            market,
            security_id,
            latest.close_price,
            selected_range.upper(),
            latest.lower_bound,
            latest.upper_bound,
            downside_pct,
            upside_pct,
            latest.risk_status.upper(),
        )
    )


def _evidence(
    bars: List[PriceBarInput],
    selected_range: str,
    latest: Optional[PriceHistoryRiskPoint],
    latest_volume_avg: Optional[float],
) -> List[str]:
    if latest is None:
        return ["저장된 유효 종가 데이터가 없습니다."]
    volume_detail = "거래량 데이터가 없습니다."
    if latest.volume is not None and latest_volume_avg:
        volume_detail = "현재 거래량 %.0f, 최근 20개 평균 거래량 %.0f입니다." % (
            latest.volume,
            latest_volume_avg,
        )
    return [
        "%s개의 저장 가격봉을 시간순으로 정렬하고 동일 시각 데이터는 최신 행만 사용했습니다."
        % len(bars),
        "각 시점은 직전 최대 20개 수익률의 표준편차로 변동성을 계산했습니다.",
        "%s 리스크 범위는 연율화 변동성을 선택 범위로 환산한 뒤 1.65 표준편차 밴드로 산출했습니다."
        % selected_range.upper(),
        "최신 수익률은 %s이고 최근 일간 변동성은 %.2f%%입니다."
        % (
            "없음" if latest.return_pct is None else "%.2f%%" % latest.return_pct,
            latest.rolling_volatility_pct,
        ),
        volume_detail,
    ]


def _reasoning(selected_range: str) -> str:
    return (
        "가격 리스크는 주문 판단 시점에서 과거에 이미 관측된 종가와 거래량만 사용합니다. "
        "최근 변동성이 커지면 현재가 주변의 상하단 밴드가 넓어지고, 거래량이 평소보다 급증하면 "
        "리스크 점수에 유동성/이벤트 가능성 가중치가 더해집니다. %s 선택은 같은 저장 가격 이력을 "
        "더 짧거나 긴 판단 범위로 환산해 밴드 폭을 조절합니다."
        % selected_range.upper()
    )
