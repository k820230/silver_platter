from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class VolumeLeader:
    rank: int
    market: str
    symbol: str
    name: str
    exchange_code: str
    last_price: Optional[float]
    change_pct: Optional[float]
    volume: float
    turnover: Optional[float]
    source: str

    def as_dict(self) -> dict:
        return {
            "rank": self.rank,
            "market": self.market,
            "symbol": self.symbol,
            "name": self.name,
            "exchange_code": self.exchange_code,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "turnover": self.turnover,
            "source": self.source,
        }


class KoreaInvestmentVolumeRankingProvider:
    def __init__(
        self,
        credentials: object,
        transport: object,
        access_token: Optional[str] = None,
        token_cache_path: Optional[str] = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport
        self._access_token = access_token
        self._token_cache_path = (
            Path(token_cache_path).expanduser() if token_cache_path else None
        )
        self._ranking_request_count = 0

    def domestic_volume_leaders(self, limit: int = 20) -> List[VolumeLeader]:
        response = self._get(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            "FHPST01710000",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "0000000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            },
        )
        rows = response.get("output", [])
        if not isinstance(rows, list):
            rows = []
        leaders = [
            _domestic_volume_leader(row)
            for row in rows
            if isinstance(row, dict)
        ]
        return _ranked(leaders, "KR", limit)

    def us_volume_leaders(
        self,
        limit: int = 20,
        exchanges: Sequence[str] = ("NAS", "NYS", "AMS"),
    ) -> List[VolumeLeader]:
        leaders: List[VolumeLeader] = []
        for exchange in exchanges:
            response = self._get(
                "/uapi/overseas-stock/v1/ranking/trade-vol",
                "HHDFS76310010",
                {
                    "EXCD": exchange,
                    "NDAY": "0",
                    "VOL_RANG": "0",
                    "KEYB": "",
                    "AUTH": "",
                    "PRC1": "",
                    "PRC2": "",
                },
            )
            rows = response.get("output2", [])
            if not isinstance(rows, list):
                rows = []
            leaders.extend(
                _overseas_volume_leader(row)
                for row in rows
                if isinstance(row, dict)
            )
        return _ranked(leaders, "US", limit)

    def _get(self, path: str, tr_id: str, params: Dict[str, str]) -> Dict[str, object]:
        if self._ranking_request_count:
            time.sleep(_kis_request_pause_seconds())
        self._ranking_request_count += 1
        return self._transport.get(path, self._auth_headers(tr_id), params)

    def _auth_headers(self, tr_id: str) -> Dict[str, str]:
        token = self._get_access_token()
        return {
            "content-type": "application/json",
            "authorization": "Bearer %s" % token,
            "appkey": str(getattr(self._credentials, "app_key")),
            "appsecret": str(getattr(self._credentials, "app_secret")),
            "tr_id": tr_id,
            "custtype": str(getattr(self._credentials, "customer_type", "P")),
        }

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        cached_token = self._read_cached_access_token()
        if cached_token:
            self._access_token = cached_token
            return cached_token
        response = self._transport.post(
            "/oauth2/tokenP",
            {"content-type": "application/json"},
            {
                "grant_type": "client_credentials",
                "appkey": str(getattr(self._credentials, "app_key")),
                "appsecret": str(getattr(self._credentials, "app_secret")),
            },
        )
        token = str(response.get("access_token", ""))
        if not token:
            raise RuntimeError("KIS OAuth response did not include access_token")
        self._access_token = token
        self._write_cached_access_token(token, response.get("expires_in"))
        return token

    def _read_cached_access_token(self) -> str:
        if self._token_cache_path is None or not self._token_cache_path.exists():
            return ""
        try:
            payload = json.loads(self._token_cache_path.read_text(encoding="utf-8"))
            token = str(payload.get("access_token", "")).strip()
            expires_at = datetime.fromisoformat(str(payload.get("expires_at", "")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return ""
        if token and expires_at > datetime.utcnow() + timedelta(minutes=1):
            return token
        return ""

    def _write_cached_access_token(self, token: str, expires_in: object) -> None:
        if self._token_cache_path is None:
            return
        try:
            ttl_seconds = max(60, int(expires_in or 0))
        except (TypeError, ValueError):
            ttl_seconds = 86400
        expires_at = datetime.utcnow() + timedelta(seconds=max(1, ttl_seconds - 60))
        try:
            self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_cache_path.write_text(
                json.dumps(
                    {
                        "access_token": token,
                        "expires_at": expires_at.isoformat(),
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            self._token_cache_path.chmod(0o600)
        except OSError:
            return


def _ranked(
    leaders: Iterable[VolumeLeader],
    market: str,
    limit: int,
) -> List[VolumeLeader]:
    ranked = sorted(leaders, key=lambda item: item.volume, reverse=True)[:limit]
    return [
        VolumeLeader(
            rank=index + 1,
            market=market,
            symbol=item.symbol,
            name=item.name,
            exchange_code=item.exchange_code,
            last_price=item.last_price,
            change_pct=item.change_pct,
            volume=item.volume,
            turnover=item.turnover,
            source=item.source,
        )
        for index, item in enumerate(ranked)
    ]


def _kis_request_pause_seconds() -> float:
    raw_value = os.getenv("KIS_REQUEST_SLEEP_SECONDS", "1.1").strip()
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 1.1


def _domestic_volume_leader(row: Dict[str, object]) -> VolumeLeader:
    return VolumeLeader(
        rank=_int_or_zero(_value(row, ("data_rank", "DATA_RANK"))),
        market="KR",
        symbol=_value(row, ("mksc_shrn_iscd", "stck_shrn_iscd", "MKSC_SHRN_ISCD")),
        name=_value(row, ("hts_kor_isnm", "HTS_KOR_ISNM")),
        exchange_code="KR",
        last_price=_float_or_none(_value(row, ("stck_prpr", "STCK_PRPR"))),
        change_pct=_float_or_none(_value(row, ("prdy_ctrt", "PRDY_CTRT"))),
        volume=_float_or_zero(_value(row, ("acml_vol", "ACML_VOL"))),
        turnover=_float_or_none(_value(row, ("acml_tr_pbmn", "ACML_TR_PBMN"))),
        source="kis_domestic_volume_rank",
    )


def _overseas_volume_leader(row: Dict[str, object]) -> VolumeLeader:
    return VolumeLeader(
        rank=_int_or_zero(_value(row, ("rank", "RANK"))),
        market="US",
        symbol=_value(row, ("symb", "SYMB")),
        name=_value(row, ("name", "NAME", "ename", "ENAME")),
        exchange_code=_value(row, ("excd", "EXCD")),
        last_price=_float_or_none(_value(row, ("last", "LAST"))),
        change_pct=_float_or_none(_value(row, ("rate", "RATE"))),
        volume=_float_or_zero(_value(row, ("tvol", "TVOL"))),
        turnover=_float_or_none(_value(row, ("tamt", "TAMT"))),
        source="kis_overseas_trade_vol",
    )


def _value(row: Dict[str, object], names: Sequence[str]) -> str:
    for name in names:
        value = row.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _float_or_none(value: str) -> Optional[float]:
    if value == "":
        return None
    return float(value.replace(",", ""))


def _float_or_zero(value: str) -> float:
    parsed = _float_or_none(value)
    return 0.0 if parsed is None else parsed


def _int_or_zero(value: str) -> int:
    if value == "":
        return 0
    return int(float(value.replace(",", "")))
