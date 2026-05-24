from abc import ABC, abstractmethod
import csv
import gzip
import io
from html.parser import HTMLParser
import json
import os
import time as time_module
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from silver_platter.data_quality import PriceBarInput


@dataclass(frozen=True)
class ProviderMetadata:
    provider_code: str
    provider_type: str
    can_store: bool
    can_display_realtime: bool
    can_redistribute: bool
    priority: int = 100


@dataclass(frozen=True)
class ProviderLicensePolicy:
    provider_code: str
    license_name: str
    can_store: bool
    can_transform: bool
    can_display_realtime: bool
    can_redistribute: bool
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


@dataclass(frozen=True)
class SecurityReference:
    symbol: str
    security_name: str
    market_code: str
    country_code: str
    currency: str
    asset_type: str
    exchange_code: str
    provider_symbol: str
    standard_industry_code: Optional[str] = None
    business_tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DisclosureMetadataInput:
    provider_event_id: str
    security_id: str
    disclosure_type: str
    title: str
    disclosed_at: datetime
    source_url: str
    metadata: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FxRateInput:
    base_currency: str
    quote_currency: str
    rate_date: date
    rate: float
    provider_code: str
    source_priority: int = 100


class MarketDataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        raise NotImplementedError


class ReferenceDataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_securities(self) -> Iterable[SecurityReference]:
        raise NotImplementedError


class DisclosureMetadataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        raise NotImplementedError


class FxRateProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        raise NotImplementedError


class StaticMarketDataProvider(MarketDataProvider):
    def __init__(self, provider_code: str, bars: List[PriceBarInput]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="market_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._bars = bars

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        return [bar for bar in self._bars if bar.security_id == symbol]


class StaticReferenceDataProvider(ReferenceDataProvider):
    def __init__(self, provider_code: str, securities: Sequence[SecurityReference]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="reference_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._securities = list(securities)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_securities(self) -> Iterable[SecurityReference]:
        return list(self._securities)


class StaticDisclosureMetadataProvider(DisclosureMetadataProvider):
    def __init__(
        self, provider_code: str, disclosures: Sequence[DisclosureMetadataInput]
    ):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="disclosure",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._disclosures = list(disclosures)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        return [
            disclosure
            for disclosure in self._disclosures
            if disclosure.security_id == symbol
        ]


class StaticFxRateProvider(FxRateProvider):
    def __init__(self, provider_code: str, rates: Sequence[FxRateInput]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="fx",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._rates = list(rates)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        base = base_currency.strip().upper()
        quote = quote_currency.strip().upper()
        return [
            rate
            for rate in self._rates
            if rate.base_currency.strip().upper() == base
            and rate.quote_currency.strip().upper() == quote
        ]


class CsvFxRateProvider(FxRateProvider):
    def __init__(
        self,
        csv_path: Path,
        provider_code: str = "csv_fx",
        source_priority: int = 50,
    ):
        self.csv_path = csv_path
        self.source_priority = source_priority
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="fx",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=source_priority,
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        base = base_currency.strip().upper()
        quote = quote_currency.strip().upper()
        rows = []
        with self.csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"base_currency", "quote_currency", "rate_date", "rate"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    "FX CSV requires columns: %s" % ", ".join(sorted(required))
                )
            for row in reader:
                if row["base_currency"].strip().upper() != base:
                    continue
                if row["quote_currency"].strip().upper() != quote:
                    continue
                rows.append(
                    FxRateInput(
                        base_currency=base,
                        quote_currency=quote,
                        rate_date=date.fromisoformat(row["rate_date"].strip()),
                        rate=float(row["rate"]),
                        provider_code=self.metadata.provider_code,
                        source_priority=self.source_priority,
                    )
                )
        return sorted(rows, key=lambda item: item.rate_date)


JsonFetcher = Callable[[str, Dict[str, str]], Dict[str, Any]]
DartJsonFetcher = Callable[[str, Dict[str, str], Dict[str, str]], Dict[str, Any]]
HtmlFetcher = Callable[[str, Dict[str, str], Dict[str, str]], str]
KrxCsvFetcher = Callable[[str, str, Dict[str, str], Dict[str, str]], str]


def _default_json_fetcher(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        raw_payload = response.read()
        encoding = response.headers.get("Content-Encoding", "").lower()
    if "gzip" in encoding:
        raw_payload = gzip.decompress(raw_payload)
    elif "deflate" in encoding:
        raw_payload = zlib.decompress(raw_payload)
    payload = raw_payload.decode("utf-8")
    return json.loads(payload)


def _default_json_get_fetcher(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, str],
) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    target = "%s?%s" % (url, query) if query else url
    return _default_json_fetcher(target, headers)


def _ecos_date_token(rate_date: date, cycle: str) -> str:
    normalized = cycle.strip().upper()
    if normalized == "D":
        return rate_date.strftime("%Y%m%d")
    if normalized == "M":
        return rate_date.strftime("%Y%m")
    if normalized == "A":
        return rate_date.strftime("%Y")
    return rate_date.strftime("%Y%m%d")


def _parse_ecos_time(value: str, cycle: str) -> date:
    normalized = cycle.strip().upper()
    if normalized == "D":
        return datetime.strptime(value, "%Y%m%d").date()
    if normalized == "M":
        return datetime.strptime(value, "%Y%m").date().replace(day=1)
    if normalized == "A":
        return date(int(value), 1, 1)
    return datetime.strptime(value, "%Y%m%d").date()


class EcosFxRateProvider(FxRateProvider):
    def __init__(
        self,
        api_key: str,
        start_date: date,
        end_date: date,
        item_code_lookup: Optional[Dict[str, str]] = None,
        stat_code: str = "731Y001",
        cycle: str = "D",
        source_priority: int = 30,
        fetcher: JsonFetcher = _default_json_fetcher,
        base_url: str = "https://ecos.bok.or.kr/api",
    ):
        if not api_key.strip():
            raise ValueError("ECOS API key is required")
        self._metadata = ProviderMetadata(
            provider_code="ecos_bok",
            provider_type="fx",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=source_priority,
        )
        self._api_key = api_key.strip()
        self._start_date = start_date
        self._end_date = end_date
        self._item_code_lookup = {
            key.strip().upper(): value.strip()
            for key, value in (
                item_code_lookup
                or {
                    "USD/KRW": "0000001",
                    "JPY/KRW": "0000002",
                    "EUR/KRW": "0000003",
                }
            ).items()
        }
        self._stat_code = stat_code
        self._cycle = cycle.strip().upper()
        self._source_priority = source_priority
        self._fetcher = fetcher
        self._base_url = base_url.rstrip("/")

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        pair = "%s/%s" % (base_currency.strip().upper(), quote_currency.strip().upper())
        item_code = self._item_code_lookup.get(pair)
        if item_code is None:
            raise ValueError("ECOS FX item code is not configured for %s" % pair)
        start_token = _ecos_date_token(self._start_date, self._cycle)
        end_token = _ecos_date_token(self._end_date, self._cycle)
        url = (
            "%s/StatisticSearch/%s/json/kr/1/100/%s/%s/%s/%s/%s"
            % (
                self._base_url,
                urllib.parse.quote(self._api_key),
                self._stat_code,
                self._cycle,
                start_token,
                end_token,
                item_code,
            )
        )
        payload = self._fetcher(url, {"Accept": "application/json"})
        search = payload.get("StatisticSearch", {})
        if not isinstance(search, dict):
            return []
        result = search.get("RESULT", {})
        if isinstance(result, dict) and str(result.get("CODE", "")).upper() not in {"", "INFO-000"}:
            raise RuntimeError(
                "ECOS FX query failed: %s %s"
                % (result.get("CODE"), result.get("MESSAGE"))
            )
        rows = search.get("row", [])
        if not isinstance(rows, list):
            return []
        rates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get("DATA_VALUE")
            time_value = row.get("TIME")
            if value in {None, ""} or not time_value:
                continue
            rates.append(
                FxRateInput(
                    base_currency=base_currency.strip().upper(),
                    quote_currency=quote_currency.strip().upper(),
                    rate_date=_parse_ecos_time(str(time_value), self._cycle),
                    rate=float(value),
                    provider_code=self.metadata.provider_code,
                    source_priority=self._source_priority,
                )
            )
        return sorted(rates, key=lambda item: item.rate_date)


def _default_html_get_fetcher(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, str],
) -> str:
    query = urllib.parse.urlencode(params)
    target = "%s?%s" % (url, query) if query else url
    request = urllib.request.Request(target, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        raw_payload = response.read()
    return raw_payload.decode("utf-8", errors="replace")


def _decode_text_payload(raw_payload: bytes) -> str:
    for encoding in ("utf-8-sig", "euc-kr", "cp949"):
        try:
            return raw_payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw_payload.decode("utf-8", errors="replace")


def _default_krx_csv_fetcher(
    otp_url: str,
    download_url: str,
    headers: Dict[str, str],
    params: Dict[str, str],
) -> str:
    otp_payload = urllib.parse.urlencode(params).encode("utf-8")
    otp_request = urllib.request.Request(
        otp_url,
        data=otp_payload,
        headers={
            **headers,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(otp_request, timeout=10) as response:
        otp_code = response.read().decode("utf-8").strip()
    if not otp_code:
        raise RuntimeError("KRX OTP generation returned an empty code")
    if otp_code.upper() == "LOGOUT":
        raise RuntimeError(
            "KRX OTP generation returned LOGOUT; the data portal rejected the "
            "session before CSV download"
        )

    download_payload = urllib.parse.urlencode({"code": otp_code}).encode("utf-8")
    download_request = urllib.request.Request(
        download_url,
        data=download_payload,
        headers={
            **headers,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(download_request, timeout=10) as response:
        return _decode_text_payload(response.read())


def _krx_number(value: str) -> float:
    cleaned = value.replace(",", "").strip()
    if cleaned in {"", "-", "N/A"}:
        return 0.0
    return float(cleaned)


def _krx_column(row: Dict[str, str], candidates: Sequence[str]) -> str:
    for candidate in candidates:
        if candidate in row:
            return str(row[candidate]).strip()
    return ""


class KrxDailyPriceProvider(MarketDataProvider):
    def __init__(
        self,
        trade_date: date,
        market_id: str = "ALL",
        fetcher: KrxCsvFetcher = _default_krx_csv_fetcher,
        otp_url: str = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd",
        download_url: str = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd",
    ):
        self._metadata = ProviderMetadata(
            provider_code="krx_data",
            provider_type="market_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=20,
        )
        self._trade_date = trade_date
        self._market_id = market_id.strip().upper()
        self._fetcher = fetcher
        self._otp_url = otp_url
        self._download_url = download_url
        self._cached_bars: Optional[List[PriceBarInput]] = None

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        normalized_symbol = symbol.strip().upper()
        return [
            bar
            for bar in self._load_bars()
            if bar.security_id.strip().upper() == normalized_symbol
        ]

    def _load_bars(self) -> List[PriceBarInput]:
        if self._cached_bars is not None:
            return list(self._cached_bars)
        params = {
            "locale": "ko_KR",
            "mktId": self._market_id,
            "trdDd": self._trade_date.strftime("%Y%m%d"),
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
            "name": "fileDown",
            "url": "dbms/MDC/STAT/standard/MDCSTAT01501",
        }
        csv_payload = self._fetcher(
            self._otp_url,
            self._download_url,
            {
                "Accept": "text/csv,*/*",
                "User-Agent": "Silver Platter KRX daily price collector",
                "Referer": "https://data.krx.co.kr/",
            },
            params,
        )
        reader = csv.DictReader(io.StringIO(csv_payload))
        bars = [self._normalize_row(row) for row in reader if row]
        self._cached_bars = bars
        return list(bars)

    def _normalize_row(self, row: Dict[str, str]) -> PriceBarInput:
        security_id = _krx_column(row, ("종목코드", "단축코드", "ISU_SRT_CD"))
        close_price = _krx_number(_krx_column(row, ("종가", "TDD_CLSPRC")))
        volume = _krx_number(_krx_column(row, ("거래량", "ACC_TRDVOL")))
        turnover = _krx_number(_krx_column(row, ("거래대금", "ACC_TRDVAL")))
        available_at = datetime.combine(self._trade_date, time(16, 0, 0))
        return PriceBarInput(
            security_id=security_id,
            bar_ts=available_at,
            close_price=close_price,
            volume=volume,
            turnover_krw=turnover,
            available_to_model_at=available_at,
        )


class KoreaInvestmentDailyPriceProvider(MarketDataProvider):
    def __init__(
        self,
        credentials: object,
        transport: object,
        start_date: date,
        end_date: date,
        max_bar_count: Optional[int] = None,
        access_token: Optional[str] = None,
        token_cache_path: Optional[str] = None,
    ):
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if max_bar_count is not None and max_bar_count <= 0:
            raise ValueError("max_bar_count must be positive")
        self._metadata = ProviderMetadata(
            provider_code="kis_domestic_daily_price",
            provider_type="market_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=20,
        )
        self._credentials = credentials
        self._transport = transport
        self._start_date = start_date
        self._end_date = end_date
        self._max_bar_count = max_bar_count
        self._access_token = access_token
        self._token_cache_path = (
            Path(token_cache_path).expanduser() if token_cache_path else None
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        provider_symbol = _normalize_kis_domestic_symbol(symbol)
        rows = self._fetch_rows(provider_symbol)
        bars = [
            self._normalize_row(provider_symbol, row)
            for row in rows
            if isinstance(row, dict)
        ]
        bars = sorted(
            {bar.bar_ts: bar for bar in bars}.values(),
            key=lambda item: item.bar_ts,
            reverse=True,
        )
        if self._max_bar_count is not None:
            bars = bars[: self._max_bar_count]
        return sorted(bars, key=lambda item: item.bar_ts)

    def _fetch_rows(self, provider_symbol: str) -> List[Dict[str, object]]:
        if self._max_bar_count is None:
            return self._fetch_rows_for_range(
                provider_symbol,
                self._start_date,
                self._end_date,
            )

        rows: List[Dict[str, object]] = []
        cursor_end = self._end_date
        request_count = 0
        while cursor_end >= self._start_date and len(rows) < self._max_bar_count:
            if request_count:
                time_module.sleep(_kis_request_pause_seconds())
            chunk_start = max(self._start_date, cursor_end - timedelta(days=160))
            chunk_rows = self._fetch_rows_for_range(
                provider_symbol,
                chunk_start,
                cursor_end,
            )
            request_count += 1
            rows.extend(chunk_rows)
            if not chunk_rows:
                cursor_end = chunk_start - timedelta(days=1)
                continue
            dates = [
                date.fromisoformat("%s-%s-%s" % (raw[0:4], raw[4:6], raw[6:8]))
                for raw in (
                    _dict_value(row, ("stck_bsop_date", "STCK_BSOP_DATE"))
                    for row in chunk_rows
                    if isinstance(row, dict)
                )
                if len(raw) == 8
            ]
            cursor_end = (min(dates) if dates else chunk_start) - timedelta(days=1)
        return rows

    def _fetch_rows_for_range(
        self,
        provider_symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, object]]:
        response = self._transport.get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            self._auth_headers("FHKST03010100"),
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": provider_symbol,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        rows = response.get("output2", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

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

    def _normalize_row(self, symbol: str, row: Dict[str, object]) -> PriceBarInput:
        raw_date = _dict_value(row, ("stck_bsop_date", "STCK_BSOP_DATE"))
        if len(raw_date) != 8:
            raise ValueError("KIS daily price row is missing stck_bsop_date")
        market_date = date.fromisoformat(
            "%s-%s-%s" % (raw_date[0:4], raw_date[4:6], raw_date[6:8])
        )
        available_at = datetime.combine(market_date, time(16, 0, 0))
        return PriceBarInput(
            security_id=symbol,
            bar_ts=available_at,
            close_price=_float_or_none(
                _dict_value(row, ("stck_clpr", "STCK_CLPR", "close_price"))
            ),
            volume=_float_or_none(_dict_value(row, ("acml_vol", "ACML_VOL", "volume"))),
            turnover_krw=_float_or_none(
                _dict_value(row, ("acml_tr_pbmn", "ACML_TR_PBMN", "turnover_krw"))
            ),
            available_to_model_at=available_at,
        )


def _normalize_kis_domestic_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".KS") or normalized.endswith(".KQ"):
        normalized = normalized.rsplit(".", 1)[0]
    if not normalized:
        raise ValueError("symbol is required")
    return normalized


def _kis_request_pause_seconds() -> float:
    raw_value = os.getenv("KIS_REQUEST_SLEEP_SECONDS", "1.1").strip()
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 1.1


def _dict_value(row: Dict[str, object], names: Sequence[str]) -> str:
    for name in names:
        value = row.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _float_or_none(value: str) -> Optional[float]:
    if value == "":
        return None
    return float(value.replace(",", ""))


def _sec_column_value(columns: Dict[str, Sequence[Any]], name: str, index: int) -> str:
    values = columns.get(name, [])
    if index >= len(values) or values[index] is None:
        return ""
    return str(values[index])


def _parse_sec_datetime(value: str, fallback_date: str) -> datetime:
    if value:
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
    if fallback_date:
        return datetime.combine(date.fromisoformat(fallback_date), time.min)
    return datetime.utcnow()


def _sec_archive_index_url(cik: str, accession_number: str) -> str:
    cik_for_path = str(int(cik))
    accession_folder = accession_number.replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/%s/%s/%s-index.html"
        % (cik_for_path, accession_folder, accession_number)
    )


class SecEdgarDisclosureProvider(DisclosureMetadataProvider):
    def __init__(
        self,
        user_agent: str,
        cik_lookup: Optional[Dict[str, str]] = None,
        forms: Optional[Sequence[str]] = None,
        fetcher: JsonFetcher = _default_json_fetcher,
        base_url: str = "https://data.sec.gov",
    ):
        if not user_agent.strip():
            raise ValueError("SEC EDGAR access requires a declared User-Agent")
        self._metadata = ProviderMetadata(
            provider_code="sec_edgar",
            provider_type="disclosure",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=30,
        )
        self._user_agent = user_agent.strip()
        self._cik_lookup = {
            key.strip().upper(): value.strip()
            for key, value in (cik_lookup or {}).items()
        }
        self._forms = {form.strip().upper() for form in forms or []}
        self._fetcher = fetcher
        self._base_url = base_url.rstrip("/")

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        cik = self._resolve_cik(symbol)
        url = "%s/submissions/CIK%s.json" % (self._base_url, cik)
        payload = self._fetcher(
            url,
            {
                "User-Agent": self._user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
        )
        recent = payload.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            return []
        return self._normalize_recent_filings(cik, symbol, recent)

    def _resolve_cik(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if normalized in self._cik_lookup:
            normalized = self._cik_lookup[normalized]
        if normalized.startswith("CIK"):
            normalized = normalized[3:]
        if not normalized.isdigit():
            raise ValueError(
                "SEC EDGAR provider requires a numeric CIK or a cik_lookup entry"
            )
        return normalized.zfill(10)

    def _normalize_recent_filings(
        self,
        cik: str,
        requested_symbol: str,
        recent: Dict[str, Sequence[Any]],
    ) -> List[DisclosureMetadataInput]:
        disclosures: List[DisclosureMetadataInput] = []
        accessions = recent.get("accessionNumber", [])
        for index, accession in enumerate(accessions):
            accession_number = str(accession)
            form = _sec_column_value(recent, "form", index).upper()
            if self._forms and form not in self._forms:
                continue
            filing_date = _sec_column_value(recent, "filingDate", index)
            accepted_at = _sec_column_value(recent, "acceptanceDateTime", index)
            primary_document = _sec_column_value(recent, "primaryDocument", index)
            primary_description = _sec_column_value(
                recent,
                "primaryDocDescription",
                index,
            )
            title = " ".join(
                part
                for part in [form, primary_description or primary_document]
                if part
            )
            disclosures.append(
                DisclosureMetadataInput(
                    provider_event_id=accession_number,
                    security_id=requested_symbol.strip().upper(),
                    disclosure_type=form,
                    title=title or form,
                    disclosed_at=_parse_sec_datetime(accepted_at, filing_date),
                    source_url=_sec_archive_index_url(cik, accession_number),
                    metadata=(
                        ("cik", cik),
                        ("accession_number", accession_number),
                        ("filing_date", filing_date),
                        ("report_date", _sec_column_value(recent, "reportDate", index)),
                        ("primary_document", primary_document),
                        ("primary_doc_description", primary_description),
                    ),
                )
            )
        return disclosures


def _parse_dart_date(value: str) -> datetime:
    return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), time.min)


def _dart_disclosure_url(receipt_number: str) -> str:
    return "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=%s" % receipt_number


class OpenDartDisclosureProvider(DisclosureMetadataProvider):
    def __init__(
        self,
        api_key: str,
        corp_code_lookup: Optional[Dict[str, str]] = None,
        begin_date: Optional[date] = None,
        end_date: Optional[date] = None,
        fetcher: DartJsonFetcher = _default_json_get_fetcher,
        base_url: str = "https://opendart.fss.or.kr/api",
    ):
        if not api_key.strip():
            raise ValueError("OpenDART API key is required")
        self._metadata = ProviderMetadata(
            provider_code="opendart",
            provider_type="disclosure",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=10,
        )
        self._api_key = api_key.strip()
        self._corp_code_lookup = {
            key.strip().upper(): value.strip()
            for key, value in (corp_code_lookup or {}).items()
        }
        self._begin_date = begin_date
        self._end_date = end_date
        self._fetcher = fetcher
        self._base_url = base_url.rstrip("/")

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        normalized_symbol = symbol.strip().upper()
        params = {
            "crtfc_key": self._api_key,
            "page_no": "1",
            "page_count": "100",
        }
        corp_code = self._corp_code_lookup.get(normalized_symbol)
        if corp_code:
            params["corp_code"] = corp_code
        if self._begin_date is not None:
            params["bgn_de"] = self._begin_date.strftime("%Y%m%d")
        if self._end_date is not None:
            params["end_de"] = self._end_date.strftime("%Y%m%d")

        payload = self._fetcher(
            "%s/list.json" % self._base_url,
            {"Accept": "application/json"},
            params,
        )
        if str(payload.get("status", "000")) not in {"000", "013"}:
            raise RuntimeError(
                "OpenDART disclosure query failed: %s %s"
                % (payload.get("status"), payload.get("message"))
            )
        rows = payload.get("list", [])
        if not isinstance(rows, list):
            return []
        return [
            self._normalize_disclosure(row, normalized_symbol)
            for row in rows
            if isinstance(row, dict)
        ]

    def _normalize_disclosure(
        self,
        row: Dict[str, Any],
        requested_symbol: str,
    ) -> DisclosureMetadataInput:
        receipt_number = str(row.get("rcept_no", ""))
        report_name = str(row.get("report_nm", ""))
        receipt_date = str(row.get("rcept_dt", ""))
        stock_code = str(row.get("stock_code", "") or requested_symbol)
        return DisclosureMetadataInput(
            provider_event_id=receipt_number,
            security_id=stock_code.strip().upper() or requested_symbol,
            disclosure_type=report_name,
            title=report_name,
            disclosed_at=_parse_dart_date(receipt_date),
            source_url=_dart_disclosure_url(receipt_number),
            metadata=(
                ("corp_code", str(row.get("corp_code", ""))),
                ("corp_name", str(row.get("corp_name", ""))),
                ("stock_code", str(row.get("stock_code", ""))),
                ("corp_cls", str(row.get("corp_cls", ""))),
                ("filer_name", str(row.get("flr_nm", ""))),
                ("remark", str(row.get("rm", ""))),
            ),
        )


class _KindTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: List[List[Dict[str, Any]]] = []
        self._row: Optional[List[Dict[str, Any]]] = None
        self._cell: Optional[Dict[str, Any]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        normalized = tag.lower()
        if normalized == "tr":
            self._row = []
        elif normalized in {"td", "th"} and self._row is not None:
            self._cell = {"text": [], "links": []}
        elif normalized == "a" and self._cell is not None:
            attributes = dict(attrs)
            href = attributes.get("href")
            if href:
                self._cell["links"].append(href)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            text = " ".join(data.split())
            if text:
                self._cell["text"].append(text)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(
                {
                    "text": " ".join(self._cell["text"]).strip(),
                    "links": list(self._cell["links"]),
                }
            )
            self._cell = None
        elif normalized == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _parse_kind_datetime(value: str, fallback_year: Optional[int] = None) -> datetime:
    normalized = " ".join(value.split())
    for fmt in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            pass
    if fallback_year is not None:
        for fmt in ("%m-%d %H:%M", "%m.%d %H:%M", "%m/%d %H:%M"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                return parsed.replace(year=fallback_year)
            except ValueError:
                pass
    raise ValueError("unsupported KIND disclosure datetime: %s" % value)


def _kind_absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


class KrxKindDisclosureProvider(DisclosureMetadataProvider):
    def __init__(
        self,
        begin_date: Optional[date] = None,
        end_date: Optional[date] = None,
        fetcher: HtmlFetcher = _default_html_get_fetcher,
        base_url: str = "https://kind.krx.co.kr/disclosure/searchdisclosurebycorp.do",
        page_size: int = 100,
    ):
        self._metadata = ProviderMetadata(
            provider_code="krx_kind",
            provider_type="disclosure",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
            priority=20,
        )
        self._begin_date = begin_date
        self._end_date = end_date
        self._fetcher = fetcher
        self._base_url = base_url
        self._page_size = page_size

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        normalized_symbol = symbol.strip().upper()
        params = {
            "method": "searchDisclosureByCorpMain",
            "searchCorpName": normalized_symbol,
            "currentPageSize": str(self._page_size),
        }
        if self._begin_date is not None:
            params["fromDate"] = self._begin_date.strftime("%Y-%m-%d")
        if self._end_date is not None:
            params["toDate"] = self._end_date.strftime("%Y-%m-%d")
        html = self._fetcher(
            self._base_url,
            {
                "User-Agent": "Silver Platter KIND metadata collector",
                "Accept": "text/html",
            },
            params,
        )
        return self._parse_html(html, normalized_symbol)

    def _parse_html(
        self,
        html: str,
        requested_symbol: str,
    ) -> List[DisclosureMetadataInput]:
        parser = _KindTableParser()
        parser.feed(html)
        disclosures: List[DisclosureMetadataInput] = []
        fallback_year = (self._end_date or self._begin_date or date.today()).year
        for row in parser.rows:
            cells = [str(cell.get("text", "")).strip() for cell in row]
            if len(cells) < 5 or not cells[0].replace(",", "").isdigit():
                continue
            try:
                disclosed_at = _parse_kind_datetime(cells[1], fallback_year=fallback_year)
            except ValueError:
                continue
            title_links = row[3].get("links", []) if len(row) > 3 else []
            source_url = (
                _kind_absolute_url(self._base_url, str(title_links[0]))
                if title_links
                else self._base_url
            )
            disclosures.append(
                DisclosureMetadataInput(
                    provider_event_id=cells[0].replace(",", ""),
                    security_id=requested_symbol,
                    disclosure_type=cells[3],
                    title=cells[3],
                    disclosed_at=disclosed_at,
                    source_url=source_url,
                    metadata=(
                        ("company_name", cells[2]),
                        ("filer_name", cells[4]),
                        ("source", "KIND"),
                    ),
                )
            )
        return disclosures


def sample_bar(symbol: str, ts: datetime, close: float) -> PriceBarInput:
    return PriceBarInput(
        security_id=symbol,
        bar_ts=ts,
        close_price=close,
        volume=1000,
        turnover_krw=close * 1000,
        available_to_model_at=ts,
    )


def license_policy_from_provider(
    provider: ProviderMetadata,
    license_name: Optional[str] = None,
    can_transform: bool = True,
) -> ProviderLicensePolicy:
    return ProviderLicensePolicy(
        provider_code=provider.provider_code,
        license_name=license_name or "%s_mvp_policy" % provider.provider_code,
        can_store=provider.can_store,
        can_transform=can_transform,
        can_display_realtime=provider.can_display_realtime,
        can_redistribute=provider.can_redistribute,
    )


def default_mvp_provider_catalog() -> List[ProviderMetadata]:
    return [
        ProviderMetadata("krx_free", "reference_data", True, False, False, 10),
        ProviderMetadata("krx_free", "market_data", True, False, False, 20),
        ProviderMetadata("krx_data", "market_data", True, False, False, 20),
        ProviderMetadata("opendart", "disclosure", True, False, False, 10),
        ProviderMetadata("krx_kind", "disclosure", True, False, False, 20),
        ProviderMetadata("sec_edgar", "disclosure", True, False, False, 30),
        ProviderMetadata("ecos_bok", "fx", True, False, False, 30),
        ProviderMetadata("federal_reserve", "headline", True, False, False, 20),
        ProviderMetadata("ecb", "headline", True, False, False, 30),
        ProviderMetadata("ofac", "headline", True, False, False, 10),
        ProviderMetadata("free_fx_placeholder", "fx", True, False, False, 90),
    ]
