import React, { useCallback, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Database,
  LineChart,
  Play,
  ReceiptText,
  RefreshCw,
  Send,
  ServerCog,
  ShieldCheck,
  TestTube2,
} from "lucide-react";
import "./styles.css";

type RequestState = "idle" | "loading" | "ready" | "error";

type ComponentHealth = {
  status: string;
  detail: string;
};

type HealthResponse = {
  status: string;
  components: Record<string, ComponentHealth>;
};

type PriceRange = {
  horizon: string;
  lower: number;
  median: number;
  upper: number;
  expected_pnl_lower_krw: number;
  expected_pnl_upper_krw: number;
};

type HorizonProjection = {
  horizon: string;
  days: number;
  expected_price: number;
  expected_profit_krw: number;
  expected_profit_pct: number;
};

type InvestmentProjection = {
  side: string;
  entry_price: number;
  break_even_price: number;
  target_profit_pct: number;
  target_price: number;
  expected_return_annualized_pct: number;
  expected_profit_krw: number;
  expected_profit_pct: number;
  best_horizon: string;
  estimated_days_to_break_even: number | null;
  estimated_days_to_target_profit: number | null;
  estimated_holding_days: number | null;
  risk_score: number;
  risk_level: string;
  guidance: {
    action: string;
    level: string;
    summary: string;
    actions: string[];
  };
  horizon_projections: HorizonProjection[];
};

type RiskIssue = {
  code: string;
  severity: string;
  message: string;
};

type OrderPreviewResponse = {
  security_id: string;
  side: string;
  order_type: string;
  market: string;
  order_amount_krw: number;
  expected_slippage_krw: number;
  price_ranges: PriceRange[];
  investment_projection: InvestmentProjection;
  risk_check: {
    status: string;
    issues: RiskIssue[];
  };
};

type OrderSubmitResponse = {
  accepted: boolean;
  reason: string;
  broker_order_id: string | null;
  state: {
    status: string;
  };
  preview: OrderPreviewResponse;
};

type PredictionInterval = {
  horizon: string;
  price_lower: number;
  price_mid: number;
  price_upper: number;
  volume_lower: number;
  volume_mid: number;
  volume_upper: number;
  volatility_mid: number;
  risk_score: number;
};

type StoredPrediction = {
  prediction_id: string;
  horizon: string;
  target_at: string;
  interval: PredictionInterval;
  actual_price: number | null;
  absolute_error: number | null;
  pct_error: number | null;
};

type MlJobResponse = {
  job: {
    job_id: string;
    security_id: string;
    status: string;
  };
  error_summary: {
    security_id: string;
    sample_count: number;
    mean_absolute_error: number;
    mean_absolute_pct_error: number;
  };
  predictions: StoredPrediction[];
};

type IndexChartPoint = {
  observed_at: string;
  volatility_index: number;
  risk_score: number;
};

type IndexChartResponse = {
  security_id: string;
  points: IndexChartPoint[];
};

type GroupVolatilityPoint = {
  group_id: string;
  observation_date: string;
  volatility_value: number;
  change_pct_from_base: number;
};

type GroupVolatilityResponse = Record<string, GroupVolatilityPoint[]>;

type OperationsSummaryResponse = {
  status: string;
  open_issue_count: number;
  components: {
    component: string;
    status: string;
    detail: string;
    checked_at: string;
  }[];
};

type ProviderCatalogItem = {
  provider_code: string;
  provider_type: string;
  priority: number;
  license_policy: {
    license_name: string;
    can_store: boolean;
    can_transform: boolean;
    can_display_realtime: boolean;
    can_redistribute: boolean;
  };
};

type ProviderCatalogResponse = {
  providers: ProviderCatalogItem[];
};

type BackupStatusResponse = {
  status: string;
  backup_base_dir: string;
  latest_manifest_path: string | null;
  latest_backup_date: string | null;
  backup_status: string;
  restore_status: string;
  latest_restore_drill_path: string | null;
  restore_drill_status: string;
  restore_drill_checked_at: string | null;
  lock_held: boolean;
  issue_count: number;
  issues: string[];
};

type AuditEvent = {
  event_id: string;
  occurred_at: string;
  actor_type: string;
  action_code: string;
  target_type: string;
  target_id: string | null;
};

type AuditEventsResponse = {
  events: AuditEvent[];
};

type GateAssessmentResponse = {
  gate_id: string;
  status: string;
  passed_count: number;
  total_count: number;
};

type OverseasTaxResponse = {
  taxable_gain_krw: number;
  estimated_tax_krw: number;
};

type BacktestResponse = {
  status: string;
  strategy_plugin_id: string;
  ending_cash_krw: number;
  realized_pnl_krw: number;
  blocked_order_count: number;
  lookahead_violation_count: number;
};

type HeadlineRiskSignal = {
  event_id: string;
  event_type: string;
  severity: string;
  observed_at: string;
  security_ids: string[];
  group_ids: string[];
  expires_at: string | null;
};

type HeadlineRiskCluster = {
  cluster_id: string;
  representative: {
    provider: string;
    title: string;
    published_at: string;
    url: string;
    event_tags: string[];
  };
  provider_count: number;
  source_urls: string[];
  headline_count: number;
};

type HeadlineRiskResponse = {
  clusters: HeadlineRiskCluster[];
  signals: HeadlineRiskSignal[];
};

type HistoryPrefetchResult = {
  security_id: string;
  market_code: string;
  provider_code: string;
  status: string;
  is_new_security: boolean;
  bar_count: number;
  existing_bar_count: number;
  quality_status: string;
  storage_uri: string;
  detail: string;
};

type SecuritySearchResponse = {
  security: {
    security_id: string;
    provider_symbol: string;
    market_code: string;
    currency: string;
    exchange_code: string;
  };
  history_prefetch: HistoryPrefetchResult;
};

type StrategyPlugin = {
  plugin_id: string;
  name: string;
  description: string;
};

type StrategyPluginsResponse = {
  plugins: StrategyPlugin[];
};

type VolumeLeader = {
  rank: number;
  market: string;
  symbol: string;
  name: string;
  exchange_code: string;
  last_price: number | null;
  change_pct: number | null;
  volume: number;
  turnover: number | null;
  source: string;
};

type VolumeLeaderMarket = {
  market: string;
  status: string;
  source: string;
  detail: string;
  items: VolumeLeader[];
};

type VolumeLeadersResponse = {
  generated_at: string;
  limit: number;
  markets: VolumeLeaderMarket[];
};

type PriceHistorySecurity = {
  security_db_id: number;
  security_id: string;
  security_name: string;
  market: string;
  exchange_code: string;
  provider_code: string;
  provider_name: string;
  bar_interval: string;
  bar_count: number;
  first_bar_ts: string;
  latest_bar_ts: string;
  latest_close_price: number | null;
  latest_volume: number | null;
};

type PriceHistorySecuritiesResponse = {
  items: PriceHistorySecurity[];
};

type PriceHistoryRiskPoint = {
  bar_ts: string;
  close_price: number;
  volume: number | null;
  return_pct: number | null;
  rolling_volatility_pct: number;
  volume_ratio: number | null;
  lower_bound: number;
  upper_bound: number;
  risk_score: number;
  risk_status: string;
};

type PriceHistoryRiskChartResponse = {
  security_id: string;
  market: string;
  risk_range: HistoryRiskRange;
  bar_interval: string;
  point_count: number;
  current_price: number | null;
  current_volume: number | null;
  latest_bar_ts: string | null;
  latest_risk: PriceHistoryRiskPoint | null;
  points: PriceHistoryRiskPoint[];
  summary: string;
  evidence: string[];
  reasoning: string;
};

type DashboardData = {
  health: HealthResponse | null;
  mlJob: MlJobResponse | null;
  mlPerformance: MlJobResponse | null;
  indexChart: IndexChartResponse | null;
  groupVolatility: GroupVolatilityResponse | null;
  operations: OperationsSummaryResponse | null;
  providerHealth: OperationsSummaryResponse | null;
  providerCatalog: ProviderCatalogResponse | null;
  backupStatus: BackupStatusResponse | null;
  audit: AuditEventsResponse | null;
  gate: GateAssessmentResponse | null;
  tax: OverseasTaxResponse | null;
  backtest: BacktestResponse | null;
  headlineRisk: HeadlineRiskResponse | null;
  volumeLeaders: VolumeLeadersResponse | null;
  historySecurities: PriceHistorySecuritiesResponse | null;
  strategyPlugins: StrategyPlugin[];
};

type RecentPreviewSecurity = {
  securityId: string;
  market: string;
  price: number | null;
};

type OrderForm = {
  securityId: string;
  side: string;
  price: string;
  quantity: string;
  orderType: string;
  market: string;
  strategyPluginId: string;
  strategyMinReturnPct: string;
};

const DEFAULT_ORDER: OrderForm = {
  securityId: "005930.KS",
  side: "buy",
  price: "80100",
  quantity: "120",
  orderType: "limit",
  market: "KR",
  strategyPluginId: "fixed-close",
  strategyMinReturnPct: "0.01",
};

const DASHBOARD_POLL_INTERVAL_MS = 60_000;
const RECENT_PREVIEW_SECURITIES_KEY = "silver-platter:recent-preview-securities";
const RECENT_PREVIEW_SECURITIES_LIMIT = 20;
const HISTORY_RISK_RANGES = ["1w", "1d", "1h", "5m"] as const;
type HistoryRiskRange = (typeof HISTORY_RISK_RANGES)[number];
type AppTab = "dashboard" | "history-risk";

const EMPTY_DASHBOARD: DashboardData = {
  health: null,
  mlJob: null,
  mlPerformance: null,
  indexChart: null,
  groupVolatility: null,
  operations: null,
  providerHealth: null,
  providerCatalog: null,
  backupStatus: null,
  audit: null,
  gate: null,
  tax: null,
  backtest: null,
  headlineRisk: null,
  volumeLeaders: null,
  historySecurities: null,
  strategyPlugins: [],
};

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} 응답 오류 (${response.status})`);
  }
  return (await response.json()) as T;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path} 응답 오류 (${response.status})`);
  }
  return (await response.json()) as T;
}

function toNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatKrw(value: number): string {
  return `${Math.round(value).toLocaleString("ko-KR")} KRW`;
}

function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 1,
    notation: "compact",
  }).format(value);
}

function formatMaybeNumber(value: number | null | undefined, digits = 0): string {
  return value == null ? "확인 불가" : formatNumber(value, digits);
}

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${formatNumber(value, 1)}%`;
}

function formatErrorPct(value: number): string {
  return `${formatNumber(value * 100, 2)}%`;
}

function formatDays(value: number | null | undefined): string {
  if (value == null) {
    return "도달 전";
  }
  if (value === 0) {
    return "즉시";
  }
  return `${value.toLocaleString("ko-KR")}일`;
}

function statusLabel(value: string | undefined): string {
  if (!value) {
    return "확인 불가";
  }
  const normalized = value.toLowerCase();
  const labels: Record<string, string> = {
    accepted: "접수",
    avoid: "진입 보류",
    block: "차단",
    blocked: "차단",
    critical: "위험",
    degraded: "주의",
    error: "오류",
    failed: "실패",
    filled: "체결",
    high: "높음",
    idle: "대기",
    loading: "로딩 중",
    low: "낮음",
    moderate: "보통",
    no_data: "데이터 없음",
    ok: "정상",
    pass: "통과",
    proceed: "진행",
    ready: "준비됨",
    reduce: "축소",
    rejected: "거절",
    skipped_disabled: "비활성화로 건너뜀",
    skipped_existing_history: "기존 이력 사용",
    skipped_provider_unconfigured: "공급자 미설정",
    skipped_unconfigured: "미설정",
    skipped_unsupported_market: "미지원 시장",
    stage: "분할 진입",
    stored: "저장됨",
    submitted: "제출됨",
    warning: "경고",
    watch: "관찰",
  };
  return labels[normalized] ?? value.replace(/_/g, " ");
}

function yesNo(value: boolean): string {
  return value ? "가능" : "불가";
}

function providerLicenseSummary(
  provider: ProviderCatalogItem | undefined,
  fallback: string,
): string {
  if (!provider) {
    return fallback;
  }
  const policy = provider.license_policy;
  return `${policy.license_name} | 저장 ${yesNo(policy.can_store)} | 변환 ${yesNo(
    policy.can_transform,
  )} | 실시간 표시 ${yesNo(policy.can_display_realtime)} | 재배포 ${yesNo(
    policy.can_redistribute,
  )} | 우선순위 ${provider.priority}`;
}

function backupStatusDetail(status: BackupStatusResponse): string {
  const parts = status.latest_backup_date
    ? [
        `백업 ${statusLabel(status.backup_status)}`,
        `복구 ${statusLabel(status.restore_status)}`,
        `훈련 ${statusLabel(status.restore_drill_status)}`,
        `기준일 ${status.latest_backup_date}`,
      ]
    : ["백업 매니페스트 없음", `훈련 ${statusLabel(status.restore_drill_status)}`];
  if (status.restore_drill_checked_at) {
    parts.push(`훈련 점검 ${status.restore_drill_checked_at}`);
  }
  if (status.lock_held) {
    parts.push("잠금 유지 중");
  }
  if (status.issue_count) {
    parts.push(`이슈 ${status.issue_count}건`);
    parts.push(status.issues.slice(0, 2).join("; "));
  }
  return parts.filter(Boolean).join(" | ");
}

function statusTone(value: string | undefined): string {
  const normalized = (value ?? "").toLowerCase();
  if (
    [
      "ok",
      "pass",
      "ready",
      "accepted",
      "filled",
      "stored",
      "low",
      "proceed",
      "skipped_existing_history",
    ].includes(normalized)
  ) {
    return "ok";
  }
  if (["blocked", "failed", "critical", "rejected", "block", "avoid", "high"].includes(normalized)) {
    return "critical";
  }
  if (
    [
      "degraded",
      "warning",
      "watch",
      "no_data",
      "moderate",
      "reduce",
      "skipped_disabled",
      "skipped_unconfigured",
      "skipped_provider_unconfigured",
      "skipped_unsupported_market",
      "stage",
    ].includes(normalized)
  ) {
    return "watch";
  }
  return "neutral";
}

function rangeLabel(value: HistoryRiskRange): string {
  const labels: Record<HistoryRiskRange, string> = {
    "1w": "1주",
    "1d": "1일",
    "1h": "1시간",
    "5m": "5분",
  };
  return labels[value];
}

function horizonLabel(value: string): string {
  const labels: Record<string, string> = {
    "1d": "1일",
    "1w": "1주",
    "1m": "1개월",
    "3m": "3개월",
  };
  return labels[value.toLowerCase()] ?? value.toUpperCase();
}

function sideLabel(value: string): string {
  const labels: Record<string, string> = {
    buy: "매수",
    sell: "매도",
  };
  return labels[value.toLowerCase()] ?? statusLabel(value);
}

function orderTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    limit: "지정가",
    market: "시장가",
  };
  return labels[value.toLowerCase()] ?? statusLabel(value);
}

function marketLabel(value: string): string {
  const labels: Record<string, string> = {
    KR: "국내",
    US: "미국",
  };
  return labels[value.toUpperCase()] ?? value;
}

function strategyLabel(plugin: Pick<StrategyPlugin, "plugin_id" | "name"> | null | undefined): string {
  if (!plugin) {
    return "전략 확인 불가";
  }
  const labels: Record<string, string> = {
    "fixed-close": "고정 종가 리플레이",
    "momentum-threshold": "모멘텀 기준 전략",
  };
  return labels[plugin.plugin_id] ?? plugin.name;
}

function componentLabel(value: string): string {
  const labels: Record<string, string> = {
    api: "API",
    backup_restore: "백업/복구",
    goldilocks: "Goldilocks",
    order_state: "주문 상태",
  };
  return labels[value] ?? value.replace(/_/g, " ");
}

function groupLabel(value: string): string {
  const labels: Record<string, string> = {
    "Cloud AI": "클라우드 AI",
    "EV Battery": "전기차 배터리",
    Semiconductor: "반도체",
  };
  return labels[value] ?? value;
}

function providerLabel(value: string): string {
  const labels: Record<string, string> = {
    ecb: "ECB",
    federal_reserve: "연준",
    headline: "뉴스",
  };
  return labels[value] ?? value;
}

function providerComponentLabel(value: string): string {
  const stripped = value.replace(/^provider:/, "");
  const [providerCode, providerType] = stripped.split(":");
  const providerLabels: Record<string, string> = {
    csv_fx: "CSV 환율",
    ecos_bok: "ECOS 한국은행",
    kis_domestic_daily_price: "KIS 국내 일봉",
    krx_data: "KRX 데이터",
    krx_kind: "KRX KIND",
    opendart: "OpenDART",
    sec_edgar: "SEC EDGAR",
  };
  const typeLabels: Record<string, string> = {
    disclosure: "공시",
    fx: "환율",
    macro: "거시",
    price: "가격",
    reference: "종목",
  };
  const providerName = providerLabels[providerCode] ?? providerCode;
  return providerType ? `${providerName} (${typeLabels[providerType] ?? providerType})` : providerName;
}

function riskTagLabel(value: string): string {
  const labels: Record<string, string> = {
    geopolitical: "국제 정세",
    sanction: "제재",
  };
  return labels[value] ?? value;
}

function operationDetailLabel(value: string): string {
  const labels: Record<string, string> = {
    "health route responsive": "헬스 체크 응답 정상",
    "paper submission enabled": "모의 주문 제출 활성화",
  };
  return labels[value] ?? value;
}

function marketDetailLabel(value: string): string {
  const labels: Record<string, string> = {
    "KIS query credentials are not configured": "KIS 조회용 인증 정보가 설정되지 않았습니다",
  };
  return labels[value] ?? value;
}

function auditActionLabel(value: string): string {
  const labels: Record<string, string> = {
    ORDER_SUBMIT: "주문 제출",
  };
  return labels[value] ?? value.replace(/_/g, " ");
}

function targetTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    order: "주문",
  };
  return labels[value] ?? value;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "확인 불가";
  }
  return new Date(value).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function historyPrefetchLabel(result: HistoryPrefetchResult | null, state: RequestState): string {
  if (state === "loading") {
    return "과거 데이터 수집 중";
  }
  if (state === "error") {
    return "과거 데이터 수집 실패";
  }
  if (!result) {
    return "과거 데이터 대기";
  }
  if (result.status === "stored") {
    return `과거 데이터 ${result.bar_count.toLocaleString("ko-KR")}개 저장`;
  }
  if (result.status === "skipped_existing_history") {
    return `기존 과거 데이터 ${result.existing_bar_count.toLocaleString("ko-KR")}개 사용`;
  }
  return `과거 데이터 ${statusLabel(result.status)}`;
}

function loadRecentPreviewSecurities(): RecentPreviewSecurity[] {
  try {
    const payload = window.localStorage.getItem(RECENT_PREVIEW_SECURITIES_KEY);
    if (!payload) {
      return [];
    }
    const parsed = JSON.parse(payload) as RecentPreviewSecurity[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item) => item && item.securityId && item.market)
      .map((item) => ({
        securityId: item.securityId,
        market: item.market,
        price: typeof item.price === "number" && Number.isFinite(item.price) ? item.price : null,
      }))
      .slice(0, RECENT_PREVIEW_SECURITIES_LIMIT);
  } catch {
    return [];
  }
}

function saveRecentPreviewSecurities(items: RecentPreviewSecurity[]): void {
  try {
    window.localStorage.setItem(
      RECENT_PREVIEW_SECURITIES_KEY,
      JSON.stringify(items.slice(0, RECENT_PREVIEW_SECURITIES_LIMIT)),
    );
  } catch {
    return;
  }
}

function nextRecentPreviewSecurities(
  current: RecentPreviewSecurity[],
  form: OrderForm,
): RecentPreviewSecurity[] {
  const securityId = (form.securityId.trim() || DEFAULT_ORDER.securityId).toUpperCase();
  const market = (form.market || DEFAULT_ORDER.market).toUpperCase();
  const price = toNumber(form.price, 0);
  const deduped = current.filter(
    (item) =>
      item.securityId.toUpperCase() !== securityId || item.market.toUpperCase() !== market,
  );
  return [
    { securityId, market, price: price > 0 ? price : null },
    ...deduped,
  ].slice(0, RECENT_PREVIEW_SECURITIES_LIMIT);
}

function orderPayload(form: OrderForm) {
  return {
    account_id: "demo-account",
    security_id: form.securityId.trim() || DEFAULT_ORDER.securityId,
    side: form.side,
    order_type: form.orderType,
    market: form.market,
    current_price: toNumber(form.price, 0),
    quantity: toNumber(form.quantity, 0),
    avg_daily_turnover_20d_krw: 5_000_000_000,
    volatility_annualized: 0.3,
    target_profit_pct: Math.max(0, toNumber(form.strategyMinReturnPct, 0.01)),
    expected_return_annualized: 0.08,
    horizons: ["1d", "1w", "1m", "3m"],
    group_day_new_order_amount_krw: 600_000_000,
    group_avg_daily_turnover_20d_krw: 20_000_000_000,
  };
}

function mlSnapshot(form: OrderForm, asOf: string) {
  return {
    security_id: form.securityId.trim() || DEFAULT_ORDER.securityId,
    as_of: asOf,
    last_price: toNumber(form.price, 0),
    avg_volume_20d: 42_500_000,
    annualized_volatility: 0.3,
    risk_score: 37.6,
    drift_per_day: 0.0006,
  };
}

function sampleIndexObservations(securityId: string, asOf: string) {
  const observedAt = new Date(asOf);
  return [4, 3, 2, 1, 0].map((daysAgo, index) => {
    const timestamp = new Date(observedAt);
    timestamp.setUTCDate(observedAt.getUTCDate() - daysAgo);
    return {
      security_id: securityId,
      observed_at: timestamp.toISOString(),
      volatility_index: 27.8 + index * 1.4,
      risk_score: 31 + index * 1.65,
    };
  });
}

function sampleBacktestBars(securityId: string) {
  return [
    ["2026-05-20T09:00:00", 79_200],
    ["2026-05-21T09:00:00", 79_700],
    ["2026-05-22T09:00:00", 80_100],
  ].map(([barTs, closePrice]) => ({
    security_id: securityId,
    bar_ts: barTs,
    close_price: closePrice,
    volume: 1_200_000,
    turnover_krw: 96_120_000_000,
    available_to_model_at: barTs,
  }));
}

function sampleMlActualBars(securityId: string, asOf: Date, basePrice: number) {
  const horizons = [
    ["1d", 1, 1.006],
    ["1w", 5, 1.018],
    ["1m", 21, 0.982],
    ["3m", 63, 1.041],
  ] as const;
  return horizons.map(([, days, priceMultiplier]) => {
    const barTs = new Date(asOf);
    barTs.setUTCDate(asOf.getUTCDate() + days);
    barTs.setUTCHours(15, 0, 0, 0);
    const availableAt = new Date(barTs);
    availableAt.setUTCHours(16, 0, 0, 0);
    return {
      security_id: securityId,
      bar_ts: barTs.toISOString(),
      close_price: Math.max(1, Math.round(basePrice * priceMultiplier * 100) / 100),
      volume: 1_100_000,
      turnover_krw: 88_000_000_000,
      available_to_model_at: availableAt.toISOString(),
    };
  });
}

function strategyParameters(form: OrderForm): Record<string, number> {
  if (form.strategyPluginId !== "momentum-threshold") {
    return {};
  }
  return {
    min_return_pct: toNumber(form.strategyMinReturnPct, 0.01),
  };
}

async function loadDashboardData(form: OrderForm): Promise<DashboardData> {
  const asOf = new Date().toISOString();
  const securityId = form.securityId.trim() || DEFAULT_ORDER.securityId;
  const basePrice = toNumber(form.price, 0);
  const performanceAsOf = new Date(asOf);
  performanceAsOf.setUTCDate(performanceAsOf.getUTCDate() - 70);
  const healthPromise = apiGet<HealthResponse>("/health");
  const mlPromise = apiPost<MlJobResponse>("/api/ml/jobs/run", {
    job_id: `web-${Date.now()}`,
    snapshot: mlSnapshot(form, asOf),
    horizons: ["1d", "1w", "1m", "3m"],
  });
  const mlPerformancePromise = apiPost<MlJobResponse>("/api/ml/jobs/run", {
    job_id: `web-perf-${Date.now()}`,
    snapshot: mlSnapshot(form, performanceAsOf.toISOString()),
    horizons: ["1d", "1w", "1m", "3m"],
    actual_bars: sampleMlActualBars(securityId, performanceAsOf, basePrice),
    observed_at: asOf,
  });
  const indexPromise = apiPost<IndexChartResponse>("/api/indices/chart", {
    security_id: securityId,
    observations: sampleIndexObservations(securityId, asOf),
  });
  const groupPromise = apiPost<GroupVolatilityResponse>("/api/groups/volatility/compare", {
    base_date: "2026-05-20",
    observations: [
      { group_id: "Semiconductor", observation_date: "2026-05-20", volatility_value: 0.24 },
      { group_id: "Semiconductor", observation_date: "2026-05-22", volatility_value: 0.27 },
      { group_id: "EV Battery", observation_date: "2026-05-20", volatility_value: 0.31 },
      { group_id: "EV Battery", observation_date: "2026-05-22", volatility_value: 0.335 },
      { group_id: "Cloud AI", observation_date: "2026-05-20", volatility_value: 0.28 },
      { group_id: "Cloud AI", observation_date: "2026-05-22", volatility_value: 0.332 },
    ],
  });
  const operationsPromise = apiPost<OperationsSummaryResponse>("/api/operations/summary", {
    components: [
      {
        component: "api",
        status: "ok",
        detail: "health route responsive",
        checked_at: asOf,
      },
      {
        component: "order_state",
        status: "ready",
        detail: "paper submission enabled",
        checked_at: asOf,
      },
    ],
  });
  const providerHealthPromise = apiGet<OperationsSummaryResponse>(
    "/api/operations/provider-health",
  );
  const providerCatalogPromise = apiGet<ProviderCatalogResponse>("/api/providers/catalog");
  const volumeLeadersPromise = apiGet<VolumeLeadersResponse>(
    "/api/markets/volume-leaders?limit=20",
  );
  const historySecuritiesPromise = apiGet<PriceHistorySecuritiesResponse>(
    "/api/history/securities?limit=100",
  ).catch(() => ({ items: [] }));
  const backupStatusPromise = apiGet<BackupStatusResponse>("/api/operations/backup-status");
  const strategyPluginsPromise = apiGet<StrategyPluginsResponse>("/api/backtests/strategy-plugins");
  const auditPromise = apiGet<AuditEventsResponse>("/api/audit/events");
  const gatePromise = apiPost<GateAssessmentResponse>("/api/verification/gates/assess", {
    gate_id: "G2",
    evidence: [
      {
        requirement_id: "api_health",
        status: "pass",
        evidence_uri: "GET /health",
        checked_at: asOf,
        detail: "dashboard refresh completed",
      },
      {
        requirement_id: "web_health",
        status: "pass",
        evidence_uri: "web build",
        checked_at: asOf,
        detail: "vite build artifact exists",
      },
      {
        requirement_id: "compose_config",
        status: "pass",
        evidence_uri: "docker compose config",
        checked_at: asOf,
        detail: "local check script covers compose render",
      },
    ],
  });
  const taxPromise = apiPost<OverseasTaxResponse>("/api/tax/overseas-capital-gains", {
    tax_year: 2026,
    trades: [
      {
        security_id: "AAPL",
        market: "US",
        realized_date: "2026-05-22",
        realized_pnl_krw: 4_500_000,
        fee_krw: 60_000,
      },
    ],
  });
  const backtestPromise = apiPost<BacktestResponse>("/api/backtests/run", {
    run_id: `web-bt-${Date.now()}`,
    strategy_id: "web-preview",
    from_date: "2026-05-20",
    to_date: "2026-05-22",
    security_id: securityId,
    market: form.market,
    side: form.side,
    order_type: form.orderType,
    quantity: Math.max(1, toNumber(form.quantity, 1) / 40),
    avg_daily_turnover_20d_krw: 5_000_000_000,
    strategy_plugin_id: form.strategyPluginId,
    strategy_parameters: strategyParameters(form),
    bars: sampleBacktestBars(securityId),
  });
  const headlineRiskPromise = apiPost<HeadlineRiskResponse>("/api/headlines/risk-signals", {
    headlines: [
      {
        provider: "federal_reserve",
        title: "제재 충격이 반도체 수출에 영향",
        published_at: asOf,
        url: "https://www.federalreserve.gov/feeds/press_all.xml",
        security_ids: [securityId],
        group_ids: ["Semiconductor"],
        event_tags: ["geopolitical", "sanction"],
      },
      {
        provider: "ecb",
        title: "제재 충격이 반도체 수출에 영향",
        published_at: asOf,
        url: "https://www.ecb.europa.eu/rss/press.html",
        group_ids: ["Semiconductor"],
        event_tags: ["geopolitical", "sanction"],
      },
    ],
  });

  const [
    health,
    mlJob,
    mlPerformance,
    indexChart,
    groupVolatility,
    operations,
    providerHealth,
    providerCatalog,
    volumeLeaders,
    historySecurities,
    backupStatus,
    strategyPlugins,
    audit,
    gate,
    tax,
    backtest,
    headlineRisk,
  ] = await Promise.all([
    healthPromise,
    mlPromise,
    mlPerformancePromise,
    indexPromise,
    groupPromise,
    operationsPromise,
    providerHealthPromise,
    providerCatalogPromise,
    volumeLeadersPromise,
    historySecuritiesPromise,
    backupStatusPromise,
    strategyPluginsPromise,
    auditPromise,
    gatePromise,
    taxPromise,
    backtestPromise,
    headlineRiskPromise,
  ]);

  return {
    health,
    mlJob,
    mlPerformance,
    indexChart,
    groupVolatility,
    operations,
    providerHealth,
    providerCatalog,
    volumeLeaders,
    historySecurities,
    backupStatus,
    strategyPlugins: strategyPlugins.plugins,
    audit,
    gate,
    tax,
    backtest,
    headlineRisk,
  };
}

type GeoRiskEvent = {
  eventId: string;
  observedAt: string;
  severity: string;
  title: string;
  provider: string;
  providerCount: number;
  headlineCount: number;
  eventTags: string[];
  sourceUrls: string[];
  pointIndex: number;
};

function scaleValue(value: number, min: number, max: number, low: number, high: number): number {
  if (max <= min) {
    return (low + high) / 2;
  }
  return low + ((value - min) / (max - min)) * (high - low);
}

function svgPath(points: { x: number; y: number }[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
}

function closestPointIndex(points: PriceHistoryRiskPoint[], timestamp: string): number {
  if (!points.length) {
    return 0;
  }
  const target = new Date(timestamp).getTime();
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  points.forEach((point, index) => {
    const distance = Math.abs(new Date(point.bar_ts).getTime() - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function riskColor(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "critical" || normalized === "block") {
    return "#b85b3f";
  }
  if (normalized === "watch" || normalized === "warning") {
    return "#b58a28";
  }
  return "#39705f";
}

function buildGeoRiskEvents(
  headlineRisk: HeadlineRiskResponse | null,
  chart: PriceHistoryRiskChartResponse | null,
): GeoRiskEvent[] {
  if (!headlineRisk || !chart) {
    return [];
  }
  const clusters = new Map(
    headlineRisk.clusters.map((cluster) => [cluster.cluster_id, cluster]),
  );
  return headlineRisk.signals
    .map((signal) => {
      const cluster = clusters.get(signal.event_id);
      const representative = cluster?.representative;
      return {
        eventId: signal.event_id,
        observedAt: signal.observed_at,
        severity: signal.severity,
        title: representative?.title ?? statusLabel(signal.event_type),
        provider: representative?.provider ?? "headline",
        providerCount: cluster?.provider_count ?? 1,
        headlineCount: cluster?.headline_count ?? 1,
        eventTags: representative?.event_tags ?? [signal.event_type],
        sourceUrls: cluster?.source_urls ?? [],
        pointIndex: closestPointIndex(chart.points, signal.observed_at),
      };
    })
    .sort((left, right) => left.pointIndex - right.pointIndex);
}

function PriceRiskChart({
  chart,
}: {
  chart: PriceHistoryRiskChartResponse | null;
}) {
  if (!chart || !chart.points.length) {
    return <div className="empty-row">저장된 과거 데이터가 선택되지 않았습니다</div>;
  }

  const width = 720;
  const height = 320;
  const left = 54;
  const right = 26;
  const top = 22;
  const priceBottom = 218;
  const volumeTop = 242;
  const volumeBottom = 292;
  const xAt = (index: number) =>
    scaleValue(index, 0, Math.max(1, chart.points.length - 1), left, width - right);
  const priceValues = chart.points.flatMap((point) => [
    point.close_price,
    point.lower_bound,
    point.upper_bound,
  ]);
  const priceMin = Math.min(...priceValues);
  const priceMax = Math.max(...priceValues);
  const pricePadding = Math.max(1, (priceMax - priceMin) * 0.08);
  const yAt = (value: number) =>
    scaleValue(value, priceMin - pricePadding, priceMax + pricePadding, priceBottom, top);
  const maxVolume = Math.max(
    1,
    ...chart.points.map((point) => point.volume ?? 0),
  );
  const upperPoints = chart.points.map((point, index) => ({
    x: xAt(index),
    y: yAt(point.upper_bound),
  }));
  const lowerPoints = chart.points.map((point, index) => ({
    x: xAt(index),
    y: yAt(point.lower_bound),
  }));
  const pricePoints = chart.points.map((point, index) => ({
    x: xAt(index),
    y: yAt(point.close_price),
  }));
  const bandPath = `${svgPath(upperPoints)} ${svgPath([...lowerPoints].reverse()).replace(/^M/, "L")} Z`;
  const latest = chart.latest_risk;
  const latestIndex = chart.points.length - 1;

  return (
    <svg className="risk-svg" role="img" aria-label="가격 리스크 차트" viewBox={`0 0 ${width} ${height}`}>
      <rect x="0" y="0" width={width} height={height} rx="8" />
      <line x1={left} y1={priceBottom} x2={width - right} y2={priceBottom} className="axis-line" />
      <line x1={left} y1={volumeBottom} x2={width - right} y2={volumeBottom} className="axis-line" />
      <path d={bandPath} className="risk-band" />
      <path d={svgPath(upperPoints)} className="risk-bound upper" />
      <path d={svgPath(lowerPoints)} className="risk-bound lower" />
      {chart.points.map((point, index) => {
        const x = xAt(index);
        const volumeHeight = ((point.volume ?? 0) / maxVolume) * (volumeBottom - volumeTop);
        return (
          <rect
            className="volume-bar"
            height={volumeHeight}
            key={`volume-${point.bar_ts}`}
            width={Math.max(2, (width - left - right) / chart.points.length - 2)}
            x={x - 2}
            y={volumeBottom - volumeHeight}
          />
        );
      })}
      <path d={svgPath(pricePoints)} className="price-line" />
      {chart.points.map((point, index) => (
        <circle
          className="risk-point"
          cx={xAt(index)}
          cy={yAt(point.close_price)}
          fill={riskColor(point.risk_status)}
          key={`risk-${point.bar_ts}`}
          r={index === latestIndex ? 4 : 2.6}
        />
      ))}
      {latest ? (
        <line
          className="current-price-line"
          x1={left}
          x2={width - right}
          y1={yAt(latest.close_price)}
          y2={yAt(latest.close_price)}
        />
      ) : null}
      <text className="axis-label" x={left} y={16}>
        {formatMaybeNumber(priceMax, 0)}
      </text>
      <text className="axis-label" x={left} y={priceBottom + 16}>
        {formatMaybeNumber(priceMin, 0)}
      </text>
      <text className="axis-label" x={left} y={height - 12}>
        {formatTimestamp(chart.points[0]?.bar_ts)}
      </text>
      <text className="axis-label end" x={width - right} y={height - 12}>
        {formatTimestamp(chart.latest_bar_ts)}
      </text>
    </svg>
  );
}

function GeopoliticalRiskChart({
  chart,
  events,
}: {
  chart: PriceHistoryRiskChartResponse | null;
  events: GeoRiskEvent[];
}) {
  if (!chart || !chart.points.length) {
    return <div className="empty-row">저장된 과거 데이터가 선택되지 않았습니다</div>;
  }

  const width = 720;
  const height = 260;
  const left = 54;
  const right = 26;
  const top = 24;
  const bottom = 214;
  const xAt = (index: number) =>
    scaleValue(index, 0, Math.max(1, chart.points.length - 1), left, width - right);
  const eventByIndex = new Map<number, number>();
  events.forEach((event) => {
    const score = event.severity === "critical" ? 90 : event.severity === "warning" ? 58 : 34;
    eventByIndex.set(event.pointIndex, Math.max(eventByIndex.get(event.pointIndex) ?? 16, score));
  });
  const riskPoints = chart.points.map((_, index) => ({
    x: xAt(index),
    y: scaleValue(eventByIndex.get(index) ?? 16, 0, 100, bottom, top),
  }));

  return (
    <svg className="risk-svg geo" role="img" aria-label="국제 정세 리스크 차트" viewBox={`0 0 ${width} ${height}`}>
      <rect x="0" y="0" width={width} height={height} rx="8" />
      <line x1={left} y1={bottom} x2={width - right} y2={bottom} className="axis-line" />
      <line x1={left} y1={scaleValue(70, 0, 100, bottom, top)} x2={width - right} y2={scaleValue(70, 0, 100, bottom, top)} className="risk-threshold" />
      <path d={svgPath(riskPoints)} className="geo-line" />
      {events.map((event) => {
        const x = xAt(event.pointIndex);
        const y = scaleValue(event.severity === "critical" ? 90 : 58, 0, 100, bottom, top);
        return (
          <g key={event.eventId}>
            <line className="event-marker-line" x1={x} x2={x} y1={top} y2={bottom} />
            <circle className={`event-marker ${event.severity}`} cx={x} cy={y} r="6" />
          </g>
        );
      })}
      <text className="axis-label" x={left} y={16}>
        리스크 100
      </text>
      <text className="axis-label" x={left} y={height - 12}>
        {formatTimestamp(chart.points[0]?.bar_ts)}
      </text>
      <text className="axis-label end" x={width - right} y={height - 12}>
        {formatTimestamp(chart.latest_bar_ts)}
      </text>
    </svg>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard");
  const [form, setForm] = useState<OrderForm>(DEFAULT_ORDER);
  const [data, setData] = useState<DashboardData>(EMPTY_DASHBOARD);
  const [preview, setPreview] = useState<OrderPreviewResponse | null>(null);
  const [submission, setSubmission] = useState<OrderSubmitResponse | null>(null);
  const [historyPrefetch, setHistoryPrefetch] = useState<HistoryPrefetchResult | null>(null);
  const [historyRiskRange, setHistoryRiskRange] = useState<HistoryRiskRange>("1w");
  const [selectedHistorySecurity, setSelectedHistorySecurity] =
    useState<PriceHistorySecurity | null>(null);
  const [historyRiskChart, setHistoryRiskChart] =
    useState<PriceHistoryRiskChartResponse | null>(null);
  const [recentPreviewSecurities, setRecentPreviewSecurities] = useState<
    RecentPreviewSecurity[]
  >(() => loadRecentPreviewSecurities());
  const [state, setState] = useState<RequestState>("idle");
  const [actionState, setActionState] = useState<RequestState>("idle");
  const [historyState, setHistoryState] = useState<RequestState>("idle");
  const [historyRiskState, setHistoryRiskState] = useState<RequestState>("idle");
  const [error, setError] = useState<string>("");

  const refresh = useCallback(async (nextForm: OrderForm = form) => {
    setState("loading");
    setError("");
    try {
      const [dashboard, nextPreview] = await Promise.all([
        loadDashboardData(nextForm),
        apiPost<OrderPreviewResponse>("/api/orders/preview", orderPayload(nextForm)),
      ]);
      setData(dashboard);
      setPreview(nextPreview);
      setRecentPreviewSecurities((current) => {
        const next = nextRecentPreviewSecurities(current, nextForm);
        saveRecentPreviewSecurities(next);
        return next;
      });
      setState("ready");
    } catch (exc) {
      setState("error");
      setError(exc instanceof Error ? exc.message : "대시보드 새로고침 실패");
    }
  }, [form]);

  useEffect(() => {
    void refresh(DEFAULT_ORDER);
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refresh();
    }, DASHBOARD_POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [refresh]);

  useEffect(() => {
    const firstSecurity = data.historySecurities?.items[0] ?? null;
    if (!selectedHistorySecurity && firstSecurity) {
      setSelectedHistorySecurity(firstSecurity);
    }
  }, [data.historySecurities, selectedHistorySecurity]);

  const loadHistoryRiskChart = useCallback(
    async (security: PriceHistorySecurity, range: HistoryRiskRange) => {
      setHistoryRiskState("loading");
      try {
        const chart = await apiGet<PriceHistoryRiskChartResponse>(
          `/api/history/risk-chart?security_id=${encodeURIComponent(
            security.security_id,
          )}&market=${encodeURIComponent(security.market)}&risk_range=${range}&limit=160`,
        );
        setHistoryRiskChart(chart);
        setHistoryRiskState("ready");
      } catch (exc) {
        setHistoryRiskChart(null);
        setHistoryRiskState("error");
      }
    },
    [],
  );

  useEffect(() => {
    if (selectedHistorySecurity) {
      void loadHistoryRiskChart(selectedHistorySecurity, historyRiskRange);
    }
  }, [
    historyRiskRange,
    loadHistoryRiskChart,
    selectedHistorySecurity?.market,
    selectedHistorySecurity?.security_id,
  ]);

  const selectHistorySecurity = (security: PriceHistorySecurity) => {
    const latestPrice = security.latest_close_price;
    const nextForm = {
      ...form,
      securityId: security.security_id,
      market: security.market,
      price: latestPrice && latestPrice > 0 ? String(latestPrice) : form.price,
    };
    setSelectedHistorySecurity(security);
    setForm(nextForm);
    void refresh(nextForm);
  };

  const submitPaperOrder = async () => {
    setActionState("loading");
    setError("");
    const timestamp = Date.now();
    try {
      const result = await apiPost<OrderSubmitResponse>("/api/orders/submit", {
        ...orderPayload(form),
        order_id: `web-order-${timestamp}`,
        idempotency_key: `web-order-${timestamp}`,
        broker_code: "paper",
        limit_price: toNumber(form.price, 0),
      });
      await apiPost<AuditEvent>("/api/audit/events", {
        actor_type: "system",
        actor_id: "web-dashboard",
        action_code: "ORDER_SUBMIT",
        target_type: "order",
        target_id: `web-order-${timestamp}`,
        detail: {
          security_id: form.securityId,
          accepted: String(result.accepted),
          state: result.state.status,
        },
      });
      setSubmission(result);
      setPreview(result.preview);
      setData((current) => ({
        ...current,
        audit: null,
      }));
      const audit = await apiGet<AuditEventsResponse>("/api/audit/events");
      setData((current) => ({ ...current, audit }));
      setActionState("ready");
    } catch (exc) {
      setActionState("error");
      setError(exc instanceof Error ? exc.message : "주문 제출 실패");
    }
  };

  const prepareSecurityHistory = async () => {
    setHistoryState("loading");
    setError("");
    try {
      const result = await apiPost<SecuritySearchResponse>("/api/securities/search", {
        security_id: form.securityId.trim() || DEFAULT_ORDER.securityId,
        market: form.market,
        prefetch_history: true,
      });
      setHistoryPrefetch(result.history_prefetch);
      setRecentPreviewSecurities((current) => {
        const next = nextRecentPreviewSecurities(current, form);
        saveRecentPreviewSecurities(next);
        return next;
      });
      setHistoryState("ready");
    } catch (exc) {
      setHistoryState("error");
      setError(exc instanceof Error ? exc.message : "과거 데이터 사전 수집 실패");
    }
  };

  const applySecurityToPreview = (
    securityId: string,
    market: string,
    price: number | null = null,
  ) => {
    const nextForm = {
      ...form,
      securityId,
      market,
      price: price && price > 0 ? String(price) : form.price,
    };
    setHistoryPrefetch(null);
    setHistoryState("idle");
    setForm(nextForm);
    void refresh(nextForm);
  };

  const priceRanges = preview?.price_ranges ?? [];
  const investmentProjection = preview?.investment_projection ?? null;
  const latestPrediction = data.mlJob?.predictions.find((item) => item.horizon === "1w");
  const modelPerformance = data.mlPerformance?.error_summary;
  const mlIssue =
    data.mlJob && data.mlJob.predictions.length === 0
      ? "예측 결과 없음"
      : data.mlJob
        ? ""
        : "예측 대기 중";
  const latestIndex = data.indexChart?.points.at(-1);
  const selectedStrategy =
    data.strategyPlugins.find((plugin) => plugin.plugin_id === form.strategyPluginId) ?? null;
  const groupRows = useMemo(() => {
    return Object.entries(data.groupVolatility ?? {}).map(([name, points]) => {
      const latest = points.at(-1);
      const change = latest?.change_pct_from_base ?? 0;
      return {
        name,
        change,
        risk: Math.abs(change) >= 15 ? "caution" : Math.abs(change) >= 8 ? "watch" : "normal",
      };
    });
  }, [data.groupVolatility]);
  const auditRows = (data.audit?.events ?? []).slice(-5).reverse();
  const fifoRows = submission
    ? [
        {
          id: submission.broker_order_id ?? submission.state.status,
          side: submission.preview.side,
          quantity: toNumber(form.quantity, 0),
          amount: submission.preview.order_amount_krw,
        },
      ]
    : [];
  const providerCatalogByComponent = useMemo(() => {
    return new Map(
      (data.providerCatalog?.providers ?? []).map((provider) => [
        `provider:${provider.provider_code}:${provider.provider_type}`,
        provider,
      ]),
    );
  }, [data.providerCatalog]);
  const healthStatus = data.health?.status;
  const riskStatus = preview?.risk_check.status;
  const headlineSignal = data.headlineRisk?.signals[0] ?? null;
  const headlineRiskStatus = headlineSignal?.severity;
  const operationsStatus =
    data.backupStatus?.status === "critical" || data.backupStatus?.status === "degraded"
      ? data.backupStatus.status
      : data.providerHealth?.status === "critical" || data.providerHealth?.status === "degraded"
        ? data.providerHealth.status
        : data.operations?.status;
  const gateStatus = data.gate?.status;
  const volumeMarkets = data.volumeLeaders?.markets ?? [];
  const historySecurities = data.historySecurities?.items ?? [];
  const geoRiskEvents = buildGeoRiskEvents(data.headlineRisk, historyRiskChart);
  const latestHistoryRisk = historyRiskChart?.latest_risk ?? null;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <strong>Silver Platter</strong>
          <span>{state === "loading" ? "새로고침 중" : "모의 운용"}</span>
        </div>
        <button
          type="button"
          className="icon-button"
          title="대시보드 새로고침"
          onClick={() => refresh()}
          disabled={state === "loading"}
        >
          <RefreshCw size={18} />
        </button>
      </header>

      {error ? (
        <section className="status-strip critical" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </section>
      ) : null}

      <section className="top-insights" aria-label="시장 바로가기">
        <article className="volume-leader-panel">
          <header>
            <div>
              <h2>거래량 상위 20</h2>
              <span>
                {data.volumeLeaders
                  ? new Date(data.volumeLeaders.generated_at).toLocaleTimeString("ko-KR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "불러오는 중"}
              </span>
            </div>
            <BarChart3 size={18} />
          </header>
          <div className="volume-market-grid">
            {volumeMarkets.map((market) => (
              <section className="volume-market" key={market.market}>
                <header>
                  <strong>{marketLabel(market.market)}</strong>
                  <span>{statusLabel(market.status)}</span>
                </header>
                <div className="volume-list">
                  {market.items.length ? (
                    market.items.slice(0, 20).map((item) => (
                      <button
                        type="button"
                        className="volume-row"
                        key={`${market.market}-${item.symbol}-${item.exchange_code}`}
                        onClick={() =>
                          applySecurityToPreview(item.symbol, market.market, item.last_price)
                        }
                        title={`${item.symbol}을 주문 미리보기에 설정`}
                      >
                        <span>{item.rank}</span>
                        <strong>{item.symbol}</strong>
                        <em>{item.name || item.exchange_code}</em>
                        <span>{formatCompactNumber(item.volume)}</span>
                      </button>
                    ))
                  ) : (
                    <p>{market.detail ? marketDetailLabel(market.detail) : statusLabel(market.status)}</p>
                  )}
                </div>
              </section>
            ))}
          </div>
        </article>

        <article className="recent-security-panel">
          <header>
            <h2>최근 조회 종목</h2>
            <span>{recentPreviewSecurities.length}/20</span>
          </header>
          <div className="recent-security-list">
            {recentPreviewSecurities.length ? (
              recentPreviewSecurities.map((item) => (
                <button
                  type="button"
                  key={`${item.market}-${item.securityId}`}
                  className="recent-security-button"
                  onClick={() => applySecurityToPreview(item.securityId, item.market, item.price)}
                  title={`${item.securityId}을 주문 미리보기에 설정`}
                >
                  <strong>{item.securityId}</strong>
                  <span>{marketLabel(item.market)}</span>
                  {item.price ? <em>{formatNumber(item.price, 2)}</em> : null}
                </button>
              ))
            ) : (
              <p>최근 조회한 종목이 없습니다</p>
            )}
          </div>
        </article>
      </section>

      <nav className="app-tabs" aria-label="대시보드 화면">
        <button
          type="button"
          className={activeTab === "dashboard" ? "active" : ""}
          onClick={() => setActiveTab("dashboard")}
        >
          대시보드
        </button>
        <button
          type="button"
          className={activeTab === "history-risk" ? "active" : ""}
          onClick={() => setActiveTab("history-risk")}
        >
          과거 리스크
        </button>
      </nav>

      <section className="metric-grid" aria-label="상태 지표">
        <article className={`metric-card ${statusTone(riskStatus)}`}>
          <ShieldCheck size={18} />
          <span>리스크 게이트</span>
          <strong>{statusLabel(riskStatus)}</strong>
        </article>
        <article className={`metric-card ${statusTone(healthStatus)}`}>
          <Database size={18} />
          <span>Goldilocks</span>
          <strong>{statusLabel(data.health?.components.goldilocks?.status)}</strong>
        </article>
        <article className={`metric-card ${statusTone(gateStatus)}`}>
          <Activity size={18} />
          <span>검증</span>
          <strong>
            {data.gate ? `${data.gate.passed_count}/${data.gate.total_count}` : "확인 불가"}
          </strong>
        </article>
        <article className="metric-card neutral">
          <ReceiptText size={18} />
          <span>세금 추정</span>
          <strong>{data.tax ? formatKrw(data.tax.estimated_tax_krw) : "확인 불가"}</strong>
        </article>
        <article className={`metric-card ${statusTone(data.backtest?.status)}`}>
          <TestTube2 size={18} />
          <span>백테스트</span>
          <strong>{data.backtest ? statusLabel(data.backtest.status) : "확인 불가"}</strong>
        </article>
        <article className={`metric-card ${statusTone(headlineRiskStatus)}`}>
          <AlertTriangle size={18} />
          <span>뉴스 리스크</span>
          <strong>{headlineSignal ? statusLabel(headlineSignal.severity) : "확인 불가"}</strong>
        </article>
        <article className={`metric-card ${statusTone(operationsStatus)}`}>
          <ServerCog size={18} />
          <span>운영 상태</span>
          <strong>{statusLabel(operationsStatus)}</strong>
        </article>
      </section>

      {activeTab === "history-risk" ? (
        <section className="history-risk-workspace">
          <aside className="history-selector-panel">
            <header>
              <h2>DB 과거 데이터</h2>
              <span>{historySecurities.length}</span>
            </header>
            <div className="history-security-list">
              {historySecurities.length ? (
                historySecurities.map((security) => (
                  <button
                    type="button"
                    className={
                      selectedHistorySecurity?.market === security.market &&
                      selectedHistorySecurity?.security_id === security.security_id
                        ? "history-security-button active"
                        : "history-security-button"
                    }
                    key={`${security.market}-${security.security_id}-${security.provider_code}`}
                    onClick={() => selectHistorySecurity(security)}
                  >
                    <strong>{security.security_id}</strong>
                    <span>{marketLabel(security.market)}</span>
                    <em>{security.security_name}</em>
                    <small>
                      {security.latest_close_price
                        ? `${formatNumber(security.latest_close_price, 2)} | `
                        : ""}
                      {security.bar_count.toLocaleString("ko-KR")}개
                    </small>
                  </button>
                ))
              ) : (
                <p>저장된 DB 과거 데이터가 없습니다</p>
              )}
            </div>
          </aside>

          <section className="history-graph-stack">
            <article className="risk-chart-card">
              <header>
                <div>
                  <h2>가격 리스크</h2>
                  <span>
                    {selectedHistorySecurity
                      ? `${marketLabel(selectedHistorySecurity.market)}/${selectedHistorySecurity.security_id}`
                      : "선택 없음"}
                  </span>
                </div>
                <div className="range-toggle" role="group" aria-label="리스크 범위">
                  {HISTORY_RISK_RANGES.map((range) => (
                    <button
                      type="button"
                      className={historyRiskRange === range ? "active" : ""}
                      key={range}
                      onClick={() => setHistoryRiskRange(range)}
                    >
                      {rangeLabel(range)}
                    </button>
                  ))}
                </div>
              </header>

              <div className="history-risk-stats">
                <span>현재가</span>
                <strong>{formatMaybeNumber(historyRiskChart?.current_price, 2)}</strong>
                <span>거래량</span>
                <strong>{formatMaybeNumber(historyRiskChart?.current_volume, 0)}</strong>
                <span>리스크</span>
                <strong className={statusTone(latestHistoryRisk?.risk_status)}>
                  {latestHistoryRisk
                    ? `${statusLabel(latestHistoryRisk.risk_status)} ${formatNumber(
                        latestHistoryRisk.risk_score,
                        1,
                      )}`
                    : statusLabel(historyRiskState)}
                </strong>
                <span>최근 시점</span>
                <strong>{formatTimestamp(historyRiskChart?.latest_bar_ts)}</strong>
              </div>

              <PriceRiskChart chart={historyRiskChart} />

              {historyRiskChart ? (
                <div className="risk-point-list" role="table" aria-label="최근 리스크 포인트">
                  <div className="risk-point-row head">
                    <span>시각</span>
                    <span>종가</span>
                    <span>리스크</span>
                    <span>상태</span>
                  </div>
                  {historyRiskChart.points.slice(-6).map((point) => (
                    <div className="risk-point-row" key={point.bar_ts}>
                      <span>{formatTimestamp(point.bar_ts)}</span>
                      <strong>{formatNumber(point.close_price, 2)}</strong>
                      <strong>{formatNumber(point.risk_score, 1)}</strong>
                      <span className={statusTone(point.risk_status)}>
                        {statusLabel(point.risk_status)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}

              <section className="risk-analysis">
                <header>
                  <strong>리스크 요약</strong>
                  <span>{statusLabel(historyRiskState)}</span>
                </header>
                <p>{historyRiskChart?.summary ?? "저장된 과거 리스크 분석을 불러오지 못했습니다."}</p>
                <div className="evidence-grid">
                  <div>
                    <strong>근거</strong>
                    <ul>
                      {(historyRiskChart?.evidence ?? ["불러온 근거가 없습니다."]).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <strong>판단 이유</strong>
                    <p>{historyRiskChart?.reasoning ?? "불러온 판단 이유가 없습니다."}</p>
                  </div>
                </div>
              </section>
            </article>

            <article className="risk-chart-card">
              <header>
                <div>
                  <h2>국제 정세 리스크</h2>
                  <span>{rangeLabel(historyRiskRange)} 기준</span>
                </div>
                <AlertTriangle size={18} />
              </header>

              <GeopoliticalRiskChart chart={historyRiskChart} events={geoRiskEvents} />

              <section className="geo-event-panel">
                <header>
                  <strong>이벤트 상세</strong>
                  <span>{geoRiskEvents.length}</span>
                </header>
                <div className="geo-event-list">
                  {geoRiskEvents.length ? (
                    geoRiskEvents.map((event) => (
                      <article className="geo-event-row" key={event.eventId}>
                        <div>
                          <strong>{event.title}</strong>
                          <span>
                            {providerLabel(event.provider)} | {formatTimestamp(event.observedAt)} |{" "}
                            {statusLabel(event.severity)}
                          </span>
                        </div>
                        <p>
                          {event.providerCount}개 공급자와 {event.headlineCount}개 헤드라인이{" "}
                          {event.eventTags.map(riskTagLabel).join(", ")} 리스크 주제와 일치했습니다.
                        </p>
                      </article>
                    ))
                  ) : (
                    <p>선택한 범위에 국제 정세 이벤트가 없습니다</p>
                  )}
                </div>
              </section>
            </article>
          </section>
        </section>
      ) : (
      <section className="workbench">
        <article className="order-ticket">
          <header>
            <h1>주문 미리보기</h1>
            <span>{form.securityId}</span>
          </header>
          <div className="ticket-grid">
            <label>
              종목
              <div className="inline-input-action">
                <input
                  value={form.securityId}
                  onChange={(event) => {
                    setHistoryPrefetch(null);
                    setHistoryState("idle");
                    setForm((current) => ({ ...current, securityId: event.target.value }));
                  }}
                />
                <button
                  type="button"
                  className="icon-button inline-icon-button"
                  title="과거 데이터 준비"
                  aria-label="과거 데이터 준비"
                  onClick={prepareSecurityHistory}
                  disabled={historyState === "loading"}
                >
                  <Database size={16} />
                </button>
              </div>
            </label>
            <label>
              매매 구분
              <select
                value={form.side}
                onChange={(event) => setForm((current) => ({ ...current, side: event.target.value }))}
              >
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </label>
            <label>
              가격
              <input
                value={form.price}
                inputMode="decimal"
                onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              />
            </label>
            <label>
              수량
              <input
                value={form.quantity}
                inputMode="numeric"
                onChange={(event) =>
                  setForm((current) => ({ ...current, quantity: event.target.value }))
                }
              />
            </label>
            <label>
              주문 유형
              <select
                value={form.orderType}
                onChange={(event) =>
                  setForm((current) => ({ ...current, orderType: event.target.value }))
                }
              >
                <option value="limit">지정가</option>
                <option value="market">시장가</option>
              </select>
            </label>
            <label>
              시장
              <select
                value={form.market}
                onChange={(event) => {
                  setHistoryPrefetch(null);
                  setHistoryState("idle");
                  setForm((current) => ({ ...current, market: event.target.value }));
                }}
              >
                <option value="KR">국내</option>
                <option value="US">미국</option>
              </select>
            </label>
            <label>
              전략
              <select
                value={form.strategyPluginId}
                onChange={(event) =>
                  setForm((current) => ({ ...current, strategyPluginId: event.target.value }))
                }
              >
                {(data.strategyPlugins.length ? data.strategyPlugins : [{ plugin_id: "fixed-close", name: "Fixed close replay", description: "" }]).map(
                  (plugin) => (
                    <option value={plugin.plugin_id} key={plugin.plugin_id}>
                      {strategyLabel(plugin)}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              최소 수익률
              <input
                value={form.strategyMinReturnPct}
                inputMode="decimal"
                onChange={(event) =>
                  setForm((current) => ({ ...current, strategyMinReturnPct: event.target.value }))
                }
              />
            </label>
          </div>

          <div className="ticket-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => refresh()}
              disabled={state === "loading"}
            >
              <Play size={16} />
              미리보기
            </button>
            <button
              type="button"
              className="text-button primary"
              onClick={submitPaperOrder}
              disabled={actionState === "loading"}
            >
              <Send size={16} />
              모의 제출
            </button>
          </div>

          {historyState !== "idle" || historyPrefetch ? (
            <div
              className={`history-strip ${statusTone(
                historyState === "error" ? "failed" : historyPrefetch?.status,
              )}`}
            >
              <Database size={16} />
              <span>{historyPrefetchLabel(historyPrefetch, historyState)}</span>
            </div>
          ) : null}

          <div className="decision-band">
            <span>주문 금액</span>
            <strong>{preview ? formatKrw(preview.order_amount_krw) : "확인 불가"}</strong>
            <span>슬리피지</span>
            <strong>{preview ? formatKrw(preview.expected_slippage_krw) : "확인 불가"}</strong>
            <span>주문 상태</span>
            <strong>{submission ? statusLabel(submission.state.status) : "미제출"}</strong>
            <span>주문 유형</span>
            <strong>{orderTypeLabel(form.orderType)}</strong>
            <span>전략</span>
            <strong>{selectedStrategy ? strategyLabel(selectedStrategy) : statusLabel(data.backtest?.strategy_plugin_id)}</strong>
            <span>최소 수익률</span>
            <strong>{formatPct(toNumber(form.strategyMinReturnPct, 0.01) * 100)}</strong>
          </div>

          {investmentProjection ? (
            <section className="investment-projection">
              <header>
                <div>
                  <h2>거래 전망</h2>
                  <span>
                    리스크 {statusLabel(investmentProjection.risk_level)} |{" "}
                    {formatNumber(investmentProjection.risk_score, 1)}
                  </span>
                </div>
                <strong className={statusTone(investmentProjection.guidance.level)}>
                  {statusLabel(investmentProjection.guidance.action)}
                </strong>
              </header>
              <div className="projection-grid">
                <span>예상 손익</span>
                <strong>{formatKrw(investmentProjection.expected_profit_krw)}</strong>
                <span>최적 기간</span>
                <strong>{horizonLabel(investmentProjection.best_horizon)}</strong>
                <span>손익분기</span>
                <strong>
                  {formatNumber(investmentProjection.break_even_price, 2)} |{" "}
                  {formatDays(investmentProjection.estimated_days_to_break_even)}
                </strong>
                <span>목표가</span>
                <strong>
                  {formatNumber(investmentProjection.target_price, 2)} |{" "}
                  {formatDays(investmentProjection.estimated_days_to_target_profit)}
                </strong>
                <span>예상 보유</span>
                <strong>{formatDays(investmentProjection.estimated_holding_days)}</strong>
                <span>수익률</span>
                <strong>{formatPct(investmentProjection.expected_profit_pct)}</strong>
              </div>
              <p>{investmentProjection.guidance.summary}</p>
              <div className="guidance-actions">
                {investmentProjection.guidance.actions.map((action) => (
                  <span key={action}>{action}</span>
                ))}
              </div>
              <div className="projection-horizons" role="table" aria-label="기간별 예상 손익">
                {investmentProjection.horizon_projections.map((projection) => (
                  <div key={projection.horizon}>
                    <span>{horizonLabel(projection.horizon)}</span>
                    <strong>{formatKrw(projection.expected_profit_krw)}</strong>
                    <em>{formatNumber(projection.expected_price, 2)}</em>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="range-table" role="table" aria-label="예측 가격 범위">
            <div className="range-row range-head" role="row">
              <span>기간</span>
              <span>하단</span>
              <span>중앙</span>
              <span>상단</span>
            </div>
            {priceRanges.map((range) => (
              <div className="range-row" role="row" key={range.horizon}>
                <span>{horizonLabel(range.horizon)}</span>
                <span>{formatNumber(range.lower, 0)}</span>
                <span>{formatNumber(range.median, 0)}</span>
                <span>{formatNumber(range.upper, 0)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="chart-panel">
          <header>
            <h2>그룹 변동성</h2>
            <BarChart3 size={18} />
          </header>
          <div className="bar-list">
            {groupRows.map((group) => (
              <div className="bar-row" key={group.name}>
                <span>{groupLabel(group.name)}</span>
                <div className="bar-track">
                  <div
                    className={`bar-fill ${group.risk}`}
                    style={{ width: `${Math.min(100, Math.abs(group.change) * 4)}%` }}
                  />
                </div>
                <strong>{formatPct(group.change)}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="chart-panel">
          <header>
            <h2>ML 예측</h2>
            <LineChart size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>가격</dt>
              <dd>
                {latestPrediction
                  ? `${formatNumber(latestPrediction.interval.price_lower, 0)} - ${formatNumber(
                      latestPrediction.interval.price_upper,
                      0,
                    )}`
                  : "확인 불가"}
              </dd>
            </div>
            <div>
              <dt>거래량</dt>
              <dd>
                {latestPrediction
                  ? `${formatNumber(latestPrediction.interval.volume_lower / 1_000_000, 1)}M - ${formatNumber(
                      latestPrediction.interval.volume_upper / 1_000_000,
                      1,
                    )}M`
                  : "확인 불가"}
              </dd>
            </div>
            <div>
              <dt>변동성</dt>
              <dd>
                {latestPrediction ? `${formatNumber(latestPrediction.interval.volatility_mid * 100, 1)}%` : "확인 불가"}
              </dd>
            </div>
            <div>
              <dt>리스크</dt>
              <dd>{latestPrediction ? formatNumber(latestPrediction.interval.risk_score, 1) : "확인 불가"}</dd>
            </div>
            <div>
              <dt>MAE</dt>
              <dd>{data.mlJob ? formatNumber(data.mlJob.error_summary.mean_absolute_error, 2) : "확인 불가"}</dd>
            </div>
          </dl>
        </article>

        <article className="chart-panel">
          <header>
            <h2>모델 성능</h2>
            <Activity size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>샘플</dt>
              <dd>{modelPerformance ? modelPerformance.sample_count : "확인 불가"}</dd>
            </div>
            <div>
              <dt>MAE</dt>
              <dd>
                {modelPerformance
                  ? formatNumber(modelPerformance.mean_absolute_error, 2)
                  : "확인 불가"}
              </dd>
            </div>
            <div>
              <dt>MAPE</dt>
              <dd>
                {modelPerformance
                  ? formatErrorPct(modelPerformance.mean_absolute_pct_error)
                  : "확인 불가"}
              </dd>
            </div>
            <div>
              <dt>종목</dt>
              <dd>{modelPerformance?.security_id ?? form.securityId}</dd>
            </div>
          </dl>
        </article>

        <article className="wide-panel">
          <header>
            <h2>종목 ML</h2>
            <LineChart size={18} />
          </header>
          <div className="index-strip">
            <span>상태</span>
            <strong className={mlIssue ? "critical" : statusTone(data.mlJob?.job.status)}>
              {mlIssue || statusLabel(data.mlJob?.job.status)}
            </strong>
            <span>예측</span>
            <strong>{data.mlJob ? data.mlJob.predictions.length : "확인 불가"}</strong>
            <span>샘플</span>
            <strong>{modelPerformance ? modelPerformance.sample_count : "확인 불가"}</strong>
          </div>
          <div className="range-table" role="table" aria-label="종목 ML 예측">
            <div className="range-row range-head" role="row">
              <span>기간</span>
              <span>목표일</span>
              <span>중앙값</span>
              <span>리스크</span>
            </div>
            {(data.mlJob?.predictions ?? []).map((prediction) => (
              <div className="range-row" role="row" key={prediction.prediction_id}>
                <span>{horizonLabel(prediction.horizon)}</span>
                <span>{new Date(prediction.target_at).toLocaleDateString("ko-KR")}</span>
                <span>{formatNumber(prediction.interval.price_mid, 0)}</span>
                <span>{formatNumber(prediction.interval.risk_score, 1)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>리스크 지수</h2>
            <LineChart size={18} />
          </header>
          <div className="index-strip">
            <span>변동성</span>
            <strong>{latestIndex ? formatNumber(latestIndex.volatility_index, 1) : "확인 불가"}</strong>
            <span>리스크</span>
            <strong>{latestIndex ? formatNumber(latestIndex.risk_score, 1) : "확인 불가"}</strong>
            <span>룩어헤드</span>
            <strong>{data.backtest ? data.backtest.lookahead_violation_count : "확인 불가"}</strong>
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>뉴스 리스크</h2>
            <AlertTriangle size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>신호</dt>
              <dd>{data.headlineRisk ? data.headlineRisk.signals.length : "확인 불가"}</dd>
            </div>
            <div>
              <dt>클러스터</dt>
              <dd>{data.headlineRisk ? data.headlineRisk.clusters.length : "확인 불가"}</dd>
            </div>
            <div>
              <dt>영향 종목</dt>
              <dd>{headlineSignal ? headlineSignal.security_ids.join(", ") : "확인 불가"}</dd>
            </div>
            <div>
              <dt>그룹</dt>
              <dd>{headlineSignal ? headlineSignal.group_ids.map(groupLabel).join(", ") : "확인 불가"}</dd>
            </div>
          </dl>
        </article>

        <article className="wide-panel">
          <header>
            <h2>운영 상태</h2>
            <ServerCog size={18} />
          </header>
          <div className="ops-grid">
            {(data.operations?.components ?? []).map((item) => (
              <div className="ops-row" key={item.component}>
                <span>{componentLabel(item.component)}</span>
                <strong className={statusTone(item.status)}>{statusLabel(item.status)}</strong>
                <em>{operationDetailLabel(item.detail)}</em>
              </div>
            ))}
            {data.backupStatus ? (
              <div className="ops-row">
                <span>백업/복구</span>
                <strong className={statusTone(data.backupStatus.status)}>{statusLabel(data.backupStatus.status)}</strong>
                <em>{backupStatusDetail(data.backupStatus)}</em>
              </div>
            ) : null}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>데이터 공급자 상태</h2>
            <Database size={18} />
          </header>
          <div className="ops-grid">
            {(data.providerHealth?.components ?? []).map((item) => (
              <div className="ops-row provider-row" key={item.component}>
                <span>{providerComponentLabel(item.component)}</span>
                <strong className={statusTone(item.status)}>{statusLabel(item.status)}</strong>
                <em>
                  {providerLicenseSummary(
                    providerCatalogByComponent.get(item.component),
                    item.detail,
                  )}
                </em>
              </div>
            ))}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>감사 로그</h2>
            <ClipboardList size={18} />
          </header>
          <div className="audit-list">
            {auditRows.length ? (
              auditRows.map((event) => (
                <div className="audit-row" key={event.event_id}>
                  <span>{new Date(event.occurred_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}</span>
                  <strong>{auditActionLabel(event.action_code)}</strong>
                  <em>{event.target_id ?? targetTypeLabel(event.target_type)}</em>
                </div>
              ))
            ) : (
              <div className="empty-row">감사 이벤트가 없습니다</div>
            )}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>FIFO 원장</h2>
            <ReceiptText size={18} />
          </header>
          <div className="audit-list">
            {fifoRows.length ? (
              fifoRows.map((row) => (
                <div className="audit-row" key={row.id}>
                  <span>{sideLabel(row.side)}</span>
                  <strong>{formatNumber(row.quantity, 2)}</strong>
                  <em>{formatKrw(row.amount)}</em>
                </div>
              ))
            ) : (
              <div className="empty-row">FIFO 이벤트가 없습니다</div>
            )}
          </div>
        </article>
      </section>
      )}
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
