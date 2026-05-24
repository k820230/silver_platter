from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Dict, Optional, Protocol
import urllib.parse
import urllib.request


@dataclass(frozen=True)
class BrokerOrderRequest:
    order_id: str
    account_id: str
    security_id: str
    side: str
    order_type: str
    quantity: float
    limit_price: Optional[float] = None
    market: str = "KR"
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class BrokerOrderAck:
    accepted: bool
    broker_order_id: Optional[str]
    status: str
    reason: str
    submitted_at: datetime
    broker_send_attempted: bool


@dataclass(frozen=True)
class KoreaInvestmentCredentials:
    app_key: str
    app_secret: str
    account_number: str
    account_product_code: str = "01"
    customer_type: str = "P"
    trading_env: str = "demo"


@dataclass(frozen=True)
class KoreaInvestmentOrderableResult:
    security_id: str
    order_price: str
    order_division: str
    nrcvb_buy_amount_krw: float
    nrcvb_buy_quantity: float
    max_buy_amount_krw: float
    max_buy_quantity: float
    raw: Dict[str, Any]


@dataclass(frozen=True)
class MarketTradingWindow:
    market: str
    timezone: str
    open_time: str
    close_time: str


MARKET_TRADING_WINDOWS: Dict[str, MarketTradingWindow] = {
    "KR": MarketTradingWindow("KR", "Asia/Seoul", "09:00", "15:30"),
    "KRX": MarketTradingWindow("KRX", "Asia/Seoul", "09:00", "15:30"),
    "US": MarketTradingWindow("US", "America/New_York", "09:30", "16:00"),
}


class KoreaInvestmentTransport(Protocol):
    def get(
        self,
        path: str,
        headers: Dict[str, str],
        params: Dict[str, str],
    ) -> Dict[str, Any]:
        ...

    def post(
        self,
        path: str,
        headers: Dict[str, str],
        body: Dict[str, str],
    ) -> Dict[str, Any]:
        ...


class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        return BrokerOrderAck(
            accepted=True,
            broker_order_id="paper-%s" % request.order_id,
            status="accepted",
            reason="paper order accepted without live broker transmission",
            submitted_at=datetime.utcnow(),
            broker_send_attempted=False,
        )


class KoreaInvestmentHttpTransport:
    def __init__(self, base_url: str):
        if not base_url.strip():
            raise ValueError("KIS_API_BASE_URL is required")
        self.base_url = base_url.rstrip("/")

    def get(
        self,
        path: str,
        headers: Dict[str, str],
        params: Dict[str, str],
    ) -> Dict[str, Any]:
        query = urllib.parse.urlencode(params)
        suffix = "%s?%s" % (path, query) if query else path
        return self._request("GET", suffix, headers, None)

    def post(
        self,
        path: str,
        headers: Dict[str, str],
        body: Dict[str, str],
    ) -> Dict[str, Any]:
        return self._request("POST", path, headers, body)

    def _request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=True, sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            "%s%s" % (self.base_url, path),
            data=payload,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
        if not response_body:
            return {}
        return json.loads(response_body)


class KoreaInvestmentBrokerAdapter(BrokerAdapter):
    def __init__(
        self,
        live_order_enabled: bool = False,
        credentials: Optional[KoreaInvestmentCredentials] = None,
        transport: Optional[KoreaInvestmentTransport] = None,
    ):
        self.live_order_enabled = live_order_enabled
        self.credentials = credentials
        self.transport = transport
        self._access_token: Optional[str] = None

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        if not self.live_order_enabled:
            return BrokerOrderAck(
                accepted=False,
                broker_order_id=None,
                status="rejected",
                reason="live Korea Investment order sending is disabled",
                submitted_at=datetime.utcnow(),
                broker_send_attempted=False,
            )
        if self.credentials is None or self.transport is None:
            return BrokerOrderAck(
                accepted=False,
                broker_order_id=None,
                status="rejected",
                reason="Korea Investment credentials and transport are required",
                submitted_at=datetime.utcnow(),
                broker_send_attempted=False,
            )
        if request.market.strip().upper() != "KR":
            return BrokerOrderAck(
                accepted=False,
                broker_order_id=None,
                status="rejected",
                reason="Korea Investment live adapter currently supports KR domestic stock orders only",
                submitted_at=datetime.utcnow(),
                broker_send_attempted=False,
            )
        response = self._send_domestic_cash_order(request)
        accepted = str(response.get("rt_cd", "")) == "0"
        output = response.get("output", {})
        broker_order_id = None
        if isinstance(output, dict):
            broker_order_id = output.get("ODNO") or output.get("odno")
            org_no = output.get("KRX_FWDG_ORD_ORGNO") or output.get("krx_fwdg_ord_orgno")
            if org_no and broker_order_id:
                broker_order_id = "%s-%s" % (org_no, broker_order_id)
        return BrokerOrderAck(
            accepted=accepted,
            broker_order_id=broker_order_id if accepted else None,
            status="accepted" if accepted else "rejected",
            reason=str(response.get("msg1", "Korea Investment order response")),
            submitted_at=datetime.utcnow(),
            broker_send_attempted=True,
        )

    def inquire_domestic_orderable(
        self,
        security_id: str,
        order_price: float,
        order_type: str = "market",
    ) -> KoreaInvestmentOrderableResult:
        if self.credentials is None or self.transport is None:
            raise ValueError("Korea Investment credentials and transport are required")
        token = self._get_access_token()
        order_division = "01" if order_type.strip().lower() == "market" else "00"
        params = {
            "CANO": self.credentials.account_number,
            "ACNT_PRDT_CD": self.credentials.account_product_code,
            "PDNO": security_id,
            "ORD_UNPR": _format_kis_number(order_price),
            "ORD_DVSN": order_division,
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N",
        }
        response = self.transport.get(
            "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
            self._auth_headers(token, _kis_orderable_tr_id(self.credentials.trading_env)),
            params,
        )
        output = response.get("output", {})
        if not isinstance(output, dict):
            output = {}
        return KoreaInvestmentOrderableResult(
            security_id=security_id,
            order_price=params["ORD_UNPR"],
            order_division=order_division,
            nrcvb_buy_amount_krw=_to_float(output.get("nrcvb_buy_amt")),
            nrcvb_buy_quantity=_to_float(output.get("nrcvb_buy_qty")),
            max_buy_amount_krw=_to_float(output.get("max_buy_amt")),
            max_buy_quantity=_to_float(output.get("max_buy_qty")),
            raw=response,
        )

    def _send_domestic_cash_order(self, request: BrokerOrderRequest) -> Dict[str, Any]:
        token = self._get_access_token()
        assert self.credentials is not None
        assert self.transport is not None
        tr_id = _kis_order_cash_tr_id(
            self.credentials.trading_env,
            request.side.strip().lower(),
        )
        order_division = "01" if request.order_type.strip().lower() == "market" else "00"
        body = {
            "CANO": self.credentials.account_number,
            "ACNT_PRDT_CD": self.credentials.account_product_code,
            "PDNO": request.security_id,
            "ORD_DVSN": order_division,
            "ORD_QTY": _format_kis_number(request.quantity),
            "ORD_UNPR": _format_kis_number(request.limit_price or 0),
            "EXCG_ID_DVSN_CD": "KRX",
            "SLL_TYPE": "",
            "CNDT_PRIC": "",
        }
        headers = self._auth_headers(token, tr_id)
        return self.transport.post(
            "/uapi/domestic-stock/v1/trading/order-cash",
            headers,
            body,
        )

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        assert self.credentials is not None
        assert self.transport is not None
        response = self.transport.post(
            "/oauth2/tokenP",
            {"content-type": "application/json"},
            {
                "grant_type": "client_credentials",
                "appkey": self.credentials.app_key,
                "appsecret": self.credentials.app_secret,
            },
        )
        token = str(response.get("access_token", ""))
        if not token:
            raise RuntimeError("Korea Investment OAuth response did not include access_token")
        self._access_token = token
        return token

    def _auth_headers(self, token: str, tr_id: str) -> Dict[str, str]:
        assert self.credentials is not None
        return {
            "content-type": "application/json",
            "authorization": "Bearer %s" % token,
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret,
            "tr_id": tr_id,
            "custtype": self.credentials.customer_type,
        }


def _format_kis_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _kis_order_cash_tr_id(trading_env: str, side: str) -> str:
    env = trading_env.strip().lower()
    if env not in {"real", "demo"}:
        raise ValueError("trading_env must be 'real' or 'demo'")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    if env == "real":
        return "TTTC0012U" if side == "buy" else "TTTC0011U"
    return "VTTC0012U" if side == "buy" else "VTTC0011U"


def _kis_orderable_tr_id(trading_env: str) -> str:
    env = trading_env.strip().lower()
    if env == "real":
        return "TTTC8908R"
    if env == "demo":
        return "VTTC8908R"
    raise ValueError("trading_env must be 'real' or 'demo'")


def _to_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(str(value).replace(",", ""))


def is_regular_order_time(market: str, now: datetime) -> bool:
    normalized_market = market.strip().upper()
    window = MARKET_TRADING_WINDOWS.get(normalized_market)
    if window is None:
        return False
    if now.weekday() >= 5:
        return False
    current = now.strftime("%H:%M")
    return window.open_time <= current <= window.close_time
