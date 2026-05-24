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
    throw new Error(`${path} returned ${response.status}`);
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
    throw new Error(`${path} returned ${response.status}`);
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
  return value.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
    notation: "compact",
  }).format(value);
}

function formatMaybeNumber(value: number | null | undefined, digits = 0): string {
  return value == null ? "Unknown" : formatNumber(value, digits);
}

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${formatNumber(value, 1)}%`;
}

function formatErrorPct(value: number): string {
  return `${formatNumber(value * 100, 2)}%`;
}

function statusLabel(value: string | undefined): string {
  if (!value) {
    return "Unknown";
  }
  return value.replace(/_/g, " ").toUpperCase();
}

function yesNo(value: boolean): string {
  return value ? "yes" : "no";
}

function providerLicenseSummary(
  provider: ProviderCatalogItem | undefined,
  fallback: string,
): string {
  if (!provider) {
    return fallback;
  }
  const policy = provider.license_policy;
  return `${policy.license_name} store ${yesNo(policy.can_store)} transform ${yesNo(policy.can_transform)} realtime ${yesNo(policy.can_display_realtime)} redistribute ${yesNo(policy.can_redistribute)} priority ${provider.priority}`;
}

function backupStatusDetail(status: BackupStatusResponse): string {
  const parts = status.latest_backup_date
    ? [
        `backup ${status.backup_status}`,
        `restore ${status.restore_status}`,
        `drill ${status.restore_drill_status}`,
        `date ${status.latest_backup_date}`,
      ]
    : ["no backup manifest", `drill ${status.restore_drill_status}`];
  if (status.restore_drill_checked_at) {
    parts.push(`drill checked ${status.restore_drill_checked_at}`);
  }
  if (status.lock_held) {
    parts.push("lock held");
  }
  if (status.issue_count) {
    parts.push(`${status.issue_count} issue${status.issue_count === 1 ? "" : "s"}`);
    parts.push(status.issues.slice(0, 2).join("; "));
  }
  return parts.filter(Boolean).join(" | ");
}

function statusTone(value: string | undefined): string {
  const normalized = (value ?? "").toLowerCase();
  if (
    ["ok", "pass", "ready", "accepted", "filled", "stored", "skipped_existing_history"].includes(
      normalized,
    )
  ) {
    return "ok";
  }
  if (["blocked", "failed", "critical", "rejected", "block"].includes(normalized)) {
    return "critical";
  }
  if (
    [
      "degraded",
      "warning",
      "watch",
      "no_data",
      "skipped_disabled",
      "skipped_unconfigured",
      "skipped_provider_unconfigured",
      "skipped_unsupported_market",
    ].includes(normalized)
  ) {
    return "watch";
  }
  return "neutral";
}

function rangeLabel(value: HistoryRiskRange): string {
  return value.toUpperCase();
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
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
    return "History loading";
  }
  if (state === "error") {
    return "History failed";
  }
  if (!result) {
    return "History idle";
  }
  if (result.status === "stored") {
    return `History stored ${result.bar_count.toLocaleString("en-US")} bars`;
  }
  if (result.status === "skipped_existing_history") {
    return `History ready ${result.existing_bar_count.toLocaleString("en-US")} bars`;
  }
  return `History ${statusLabel(result.status)}`;
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
  const deduped = current.filter(
    (item) =>
      item.securityId.toUpperCase() !== securityId || item.market.toUpperCase() !== market,
  );
  return [{ securityId, market }, ...deduped].slice(0, RECENT_PREVIEW_SECURITIES_LIMIT);
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
        title: "Sanction shock affects chip exports",
        published_at: asOf,
        url: "https://www.federalreserve.gov/feeds/press_all.xml",
        security_ids: [securityId],
        group_ids: ["Semiconductor"],
        event_tags: ["geopolitical", "sanction"],
      },
      {
        provider: "ecb",
        title: "Sanction shock affects chip exports",
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
    return <div className="empty-row">No stored history selected</div>;
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
    <svg className="risk-svg" role="img" aria-label="Price risk chart" viewBox={`0 0 ${width} ${height}`}>
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
    return <div className="empty-row">No stored history selected</div>;
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
    <svg className="risk-svg geo" role="img" aria-label="Geopolitical risk chart" viewBox={`0 0 ${width} ${height}`}>
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
        Risk 100
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
      setError(exc instanceof Error ? exc.message : "dashboard refresh failed");
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
    const nextForm = {
      ...form,
      securityId: security.security_id,
      market: security.market,
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
      setError(exc instanceof Error ? exc.message : "order submission failed");
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
      setError(exc instanceof Error ? exc.message : "history prefetch failed");
    }
  };

  const applySecurityToPreview = (securityId: string, market: string) => {
    setHistoryPrefetch(null);
    setHistoryState("idle");
    setForm((current) => ({
      ...current,
      securityId,
      market,
    }));
  };

  const priceRanges = preview?.price_ranges ?? [];
  const latestPrediction = data.mlJob?.predictions.find((item) => item.horizon === "1w");
  const modelPerformance = data.mlPerformance?.error_summary;
  const mlIssue =
    data.mlJob && data.mlJob.predictions.length === 0
      ? "No predictions returned"
      : data.mlJob
        ? ""
        : "Awaiting forecast";
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
          <span>{state === "loading" ? "Refreshing" : "Simulation"}</span>
        </div>
        <button
          type="button"
          className="icon-button"
          title="Refresh dashboard"
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

      <section className="top-insights" aria-label="Market shortcuts">
        <article className="volume-leader-panel">
          <header>
            <div>
              <h2>Volume Top 20</h2>
              <span>
                {data.volumeLeaders
                  ? new Date(data.volumeLeaders.generated_at).toLocaleTimeString("ko-KR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "Loading"}
              </span>
            </div>
            <BarChart3 size={18} />
          </header>
          <div className="volume-market-grid">
            {volumeMarkets.map((market) => (
              <section className="volume-market" key={market.market}>
                <header>
                  <strong>{market.market}</strong>
                  <span>{statusLabel(market.status)}</span>
                </header>
                <div className="volume-list">
                  {market.items.length ? (
                    market.items.slice(0, 20).map((item) => (
                      <button
                        type="button"
                        className="volume-row"
                        key={`${market.market}-${item.symbol}-${item.exchange_code}`}
                        onClick={() => applySecurityToPreview(item.symbol, market.market)}
                        title={`Set ${item.symbol} in Order Preview`}
                      >
                        <span>{item.rank}</span>
                        <strong>{item.symbol}</strong>
                        <em>{item.name || item.exchange_code}</em>
                        <span>{formatCompactNumber(item.volume)}</span>
                      </button>
                    ))
                  ) : (
                    <p>{market.detail || statusLabel(market.status)}</p>
                  )}
                </div>
              </section>
            ))}
          </div>
        </article>

        <article className="recent-security-panel">
          <header>
            <h2>Recent Preview</h2>
            <span>{recentPreviewSecurities.length}/20</span>
          </header>
          <div className="recent-security-list">
            {recentPreviewSecurities.length ? (
              recentPreviewSecurities.map((item) => (
                <button
                  type="button"
                  key={`${item.market}-${item.securityId}`}
                  className="recent-security-button"
                  onClick={() => applySecurityToPreview(item.securityId, item.market)}
                  title={`Set ${item.securityId} in Order Preview`}
                >
                  <strong>{item.securityId}</strong>
                  <span>{item.market}</span>
                </button>
              ))
            ) : (
              <p>No previews yet</p>
            )}
          </div>
        </article>
      </section>

      <nav className="app-tabs" aria-label="Dashboard views">
        <button
          type="button"
          className={activeTab === "dashboard" ? "active" : ""}
          onClick={() => setActiveTab("dashboard")}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={activeTab === "history-risk" ? "active" : ""}
          onClick={() => setActiveTab("history-risk")}
        >
          History Risk
        </button>
      </nav>

      <section className="metric-grid" aria-label="Status metrics">
        <article className={`metric-card ${statusTone(riskStatus)}`}>
          <ShieldCheck size={18} />
          <span>Risk Gate</span>
          <strong>{statusLabel(riskStatus)}</strong>
        </article>
        <article className={`metric-card ${statusTone(healthStatus)}`}>
          <Database size={18} />
          <span>Goldilocks</span>
          <strong>{statusLabel(data.health?.components.goldilocks?.status)}</strong>
        </article>
        <article className={`metric-card ${statusTone(gateStatus)}`}>
          <Activity size={18} />
          <span>Verification</span>
          <strong>
            {data.gate ? `${data.gate.passed_count}/${data.gate.total_count}` : "Unknown"}
          </strong>
        </article>
        <article className="metric-card neutral">
          <ReceiptText size={18} />
          <span>Tax Estimate</span>
          <strong>{data.tax ? formatKrw(data.tax.estimated_tax_krw) : "Unknown"}</strong>
        </article>
        <article className={`metric-card ${statusTone(data.backtest?.status)}`}>
          <TestTube2 size={18} />
          <span>Backtest</span>
          <strong>{data.backtest ? statusLabel(data.backtest.status) : "Unknown"}</strong>
        </article>
        <article className={`metric-card ${statusTone(headlineRiskStatus)}`}>
          <AlertTriangle size={18} />
          <span>Headline Risk</span>
          <strong>{headlineSignal ? statusLabel(headlineSignal.severity) : "Unknown"}</strong>
        </article>
        <article className={`metric-card ${statusTone(operationsStatus)}`}>
          <ServerCog size={18} />
          <span>Operations</span>
          <strong>{statusLabel(operationsStatus)}</strong>
        </article>
      </section>

      {activeTab === "history-risk" ? (
        <section className="history-risk-workspace">
          <aside className="history-selector-panel">
            <header>
              <h2>DB History</h2>
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
                    <span>{security.market}</span>
                    <em>{security.security_name}</em>
                    <small>{security.bar_count.toLocaleString("en-US")} bars</small>
                  </button>
                ))
              ) : (
                <p>No stored DB history</p>
              )}
            </div>
          </aside>

          <section className="history-graph-stack">
            <article className="risk-chart-card">
              <header>
                <div>
                  <h2>Price Risk</h2>
                  <span>
                    {selectedHistorySecurity
                      ? `${selectedHistorySecurity.market}/${selectedHistorySecurity.security_id}`
                      : "No selection"}
                  </span>
                </div>
                <div className="range-toggle" role="group" aria-label="Risk range">
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
                <span>Current</span>
                <strong>{formatMaybeNumber(historyRiskChart?.current_price, 2)}</strong>
                <span>Volume</span>
                <strong>{formatMaybeNumber(historyRiskChart?.current_volume, 0)}</strong>
                <span>Risk</span>
                <strong className={statusTone(latestHistoryRisk?.risk_status)}>
                  {latestHistoryRisk
                    ? `${statusLabel(latestHistoryRisk.risk_status)} ${formatNumber(
                        latestHistoryRisk.risk_score,
                        1,
                      )}`
                    : statusLabel(historyRiskState)}
                </strong>
                <span>Latest</span>
                <strong>{formatTimestamp(historyRiskChart?.latest_bar_ts)}</strong>
              </div>

              <PriceRiskChart chart={historyRiskChart} />

              <section className="risk-analysis">
                <header>
                  <strong>Risk Summary</strong>
                  <span>{statusLabel(historyRiskState)}</span>
                </header>
                <p>{historyRiskChart?.summary ?? "Stored history risk is not loaded."}</p>
                <div className="evidence-grid">
                  <div>
                    <strong>Evidence</strong>
                    <ul>
                      {(historyRiskChart?.evidence ?? ["No evidence loaded."]).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <strong>Reasoning</strong>
                    <p>{historyRiskChart?.reasoning ?? "No reasoning loaded."}</p>
                  </div>
                </div>
              </section>
            </article>

            <article className="risk-chart-card">
              <header>
                <div>
                  <h2>Geopolitical Risk</h2>
                  <span>{rangeLabel(historyRiskRange)} aligned</span>
                </div>
                <AlertTriangle size={18} />
              </header>

              <GeopoliticalRiskChart chart={historyRiskChart} events={geoRiskEvents} />

              <section className="geo-event-panel">
                <header>
                  <strong>Event Details</strong>
                  <span>{geoRiskEvents.length}</span>
                </header>
                <div className="geo-event-list">
                  {geoRiskEvents.length ? (
                    geoRiskEvents.map((event) => (
                      <article className="geo-event-row" key={event.eventId}>
                        <div>
                          <strong>{event.title}</strong>
                          <span>
                            {event.provider} | {formatTimestamp(event.observedAt)} |{" "}
                            {statusLabel(event.severity)}
                          </span>
                        </div>
                        <p>
                          {event.providerCount} providers and {event.headlineCount} headlines
                          matched {event.eventTags.join(", ")} risk themes.
                        </p>
                      </article>
                    ))
                  ) : (
                    <p>No geopolitical events in the selected range</p>
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
            <h1>Order Preview</h1>
            <span>{form.securityId}</span>
          </header>
          <div className="ticket-grid">
            <label>
              Security
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
                  title="Prepare history"
                  aria-label="Prepare history"
                  onClick={prepareSecurityHistory}
                  disabled={historyState === "loading"}
                >
                  <Database size={16} />
                </button>
              </div>
            </label>
            <label>
              Side
              <select
                value={form.side}
                onChange={(event) => setForm((current) => ({ ...current, side: event.target.value }))}
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </label>
            <label>
              Price
              <input
                value={form.price}
                inputMode="decimal"
                onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              />
            </label>
            <label>
              Quantity
              <input
                value={form.quantity}
                inputMode="numeric"
                onChange={(event) =>
                  setForm((current) => ({ ...current, quantity: event.target.value }))
                }
              />
            </label>
            <label>
              Type
              <select
                value={form.orderType}
                onChange={(event) =>
                  setForm((current) => ({ ...current, orderType: event.target.value }))
                }
              >
                <option value="limit">Limit</option>
                <option value="market">Market</option>
              </select>
            </label>
            <label>
              Market
              <select
                value={form.market}
                onChange={(event) => {
                  setHistoryPrefetch(null);
                  setHistoryState("idle");
                  setForm((current) => ({ ...current, market: event.target.value }));
                }}
              >
                <option value="KR">KR</option>
                <option value="US">US</option>
              </select>
            </label>
            <label>
              Strategy
              <select
                value={form.strategyPluginId}
                onChange={(event) =>
                  setForm((current) => ({ ...current, strategyPluginId: event.target.value }))
                }
              >
                {(data.strategyPlugins.length ? data.strategyPlugins : [{ plugin_id: "fixed-close", name: "Fixed close replay", description: "" }]).map(
                  (plugin) => (
                    <option value={plugin.plugin_id} key={plugin.plugin_id}>
                      {plugin.name}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              Min Return
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
              Preview
            </button>
            <button
              type="button"
              className="text-button primary"
              onClick={submitPaperOrder}
              disabled={actionState === "loading"}
            >
              <Send size={16} />
              Paper Submit
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
            <span>Amount</span>
            <strong>{preview ? formatKrw(preview.order_amount_krw) : "Unknown"}</strong>
            <span>Slippage</span>
            <strong>{preview ? formatKrw(preview.expected_slippage_krw) : "Unknown"}</strong>
            <span>Order State</span>
            <strong>{submission ? statusLabel(submission.state.status) : "Not submitted"}</strong>
            <span>Strategy</span>
            <strong>{selectedStrategy?.name ?? statusLabel(data.backtest?.strategy_plugin_id)}</strong>
            <span>Min Return</span>
            <strong>{formatPct(toNumber(form.strategyMinReturnPct, 0.01) * 100)}</strong>
          </div>

          <div className="range-table" role="table" aria-label="Predicted price ranges">
            <div className="range-row range-head" role="row">
              <span>Horizon</span>
              <span>Low</span>
              <span>Mid</span>
              <span>High</span>
            </div>
            {priceRanges.map((range) => (
              <div className="range-row" role="row" key={range.horizon}>
                <span>{range.horizon.toUpperCase()}</span>
                <span>{formatNumber(range.lower, 0)}</span>
                <span>{formatNumber(range.median, 0)}</span>
                <span>{formatNumber(range.upper, 0)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="chart-panel">
          <header>
            <h2>Group Volatility</h2>
            <BarChart3 size={18} />
          </header>
          <div className="bar-list">
            {groupRows.map((group) => (
              <div className="bar-row" key={group.name}>
                <span>{group.name}</span>
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
            <h2>ML Forecast</h2>
            <LineChart size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>Price</dt>
              <dd>
                {latestPrediction
                  ? `${formatNumber(latestPrediction.interval.price_lower, 0)} - ${formatNumber(
                      latestPrediction.interval.price_upper,
                      0,
                    )}`
                  : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Volume</dt>
              <dd>
                {latestPrediction
                  ? `${formatNumber(latestPrediction.interval.volume_lower / 1_000_000, 1)}M - ${formatNumber(
                      latestPrediction.interval.volume_upper / 1_000_000,
                      1,
                    )}M`
                  : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Volatility</dt>
              <dd>
                {latestPrediction ? `${formatNumber(latestPrediction.interval.volatility_mid * 100, 1)}%` : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>{latestPrediction ? formatNumber(latestPrediction.interval.risk_score, 1) : "Unknown"}</dd>
            </div>
            <div>
              <dt>MAE</dt>
              <dd>{data.mlJob ? formatNumber(data.mlJob.error_summary.mean_absolute_error, 2) : "Unknown"}</dd>
            </div>
          </dl>
        </article>

        <article className="chart-panel">
          <header>
            <h2>Model Performance</h2>
            <Activity size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>Samples</dt>
              <dd>{modelPerformance ? modelPerformance.sample_count : "Unknown"}</dd>
            </div>
            <div>
              <dt>MAE</dt>
              <dd>
                {modelPerformance
                  ? formatNumber(modelPerformance.mean_absolute_error, 2)
                  : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>MAPE</dt>
              <dd>
                {modelPerformance
                  ? formatErrorPct(modelPerformance.mean_absolute_pct_error)
                  : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Security</dt>
              <dd>{modelPerformance?.security_id ?? form.securityId}</dd>
            </div>
          </dl>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Security ML</h2>
            <LineChart size={18} />
          </header>
          <div className="index-strip">
            <span>Status</span>
            <strong className={mlIssue ? "critical" : statusTone(data.mlJob?.job.status)}>
              {mlIssue || statusLabel(data.mlJob?.job.status)}
            </strong>
            <span>Predictions</span>
            <strong>{data.mlJob ? data.mlJob.predictions.length : "Unknown"}</strong>
            <span>Samples</span>
            <strong>{modelPerformance ? modelPerformance.sample_count : "Unknown"}</strong>
          </div>
          <div className="range-table" role="table" aria-label="Security ML predictions">
            <div className="range-row range-head" role="row">
              <span>Horizon</span>
              <span>Target</span>
              <span>Mid</span>
              <span>Risk</span>
            </div>
            {(data.mlJob?.predictions ?? []).map((prediction) => (
              <div className="range-row" role="row" key={prediction.prediction_id}>
                <span>{prediction.horizon.toUpperCase()}</span>
                <span>{new Date(prediction.target_at).toLocaleDateString("en-US")}</span>
                <span>{formatNumber(prediction.interval.price_mid, 0)}</span>
                <span>{formatNumber(prediction.interval.risk_score, 1)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Risk Index</h2>
            <LineChart size={18} />
          </header>
          <div className="index-strip">
            <span>Volatility</span>
            <strong>{latestIndex ? formatNumber(latestIndex.volatility_index, 1) : "Unknown"}</strong>
            <span>Risk</span>
            <strong>{latestIndex ? formatNumber(latestIndex.risk_score, 1) : "Unknown"}</strong>
            <span>Lookahead</span>
            <strong>{data.backtest ? data.backtest.lookahead_violation_count : "Unknown"}</strong>
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Headline Risk</h2>
            <AlertTriangle size={18} />
          </header>
          <dl className="forecast-list">
            <div>
              <dt>Signals</dt>
              <dd>{data.headlineRisk ? data.headlineRisk.signals.length : "Unknown"}</dd>
            </div>
            <div>
              <dt>Clusters</dt>
              <dd>{data.headlineRisk ? data.headlineRisk.clusters.length : "Unknown"}</dd>
            </div>
            <div>
              <dt>Affected</dt>
              <dd>{headlineSignal ? headlineSignal.security_ids.join(", ") : "Unknown"}</dd>
            </div>
            <div>
              <dt>Groups</dt>
              <dd>{headlineSignal ? headlineSignal.group_ids.join(", ") : "Unknown"}</dd>
            </div>
          </dl>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Operations</h2>
            <ServerCog size={18} />
          </header>
          <div className="ops-grid">
            {(data.operations?.components ?? []).map((item) => (
              <div className="ops-row" key={item.component}>
                <span>{item.component}</span>
                <strong className={statusTone(item.status)}>{statusLabel(item.status)}</strong>
                <em>{item.detail}</em>
              </div>
            ))}
            {data.backupStatus ? (
              <div className="ops-row">
                <span>backup_restore</span>
                <strong className={statusTone(data.backupStatus.status)}>{statusLabel(data.backupStatus.status)}</strong>
                <em>{backupStatusDetail(data.backupStatus)}</em>
              </div>
            ) : null}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Provider Health</h2>
            <Database size={18} />
          </header>
          <div className="ops-grid">
            {(data.providerHealth?.components ?? []).map((item) => (
              <div className="ops-row provider-row" key={item.component}>
                <span>{item.component.replace("provider:", "")}</span>
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
            <h2>Audit</h2>
            <ClipboardList size={18} />
          </header>
          <div className="audit-list">
            {auditRows.length ? (
              auditRows.map((event) => (
                <div className="audit-row" key={event.event_id}>
                  <span>{new Date(event.occurred_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</span>
                  <strong>{event.action_code}</strong>
                  <em>{event.target_id ?? event.target_type}</em>
                </div>
              ))
            ) : (
              <div className="empty-row">No audit events</div>
            )}
          </div>
        </article>

        <article className="wide-panel">
          <header>
            <h2>FIFO Ledger</h2>
            <ReceiptText size={18} />
          </header>
          <div className="audit-list">
            {fifoRows.length ? (
              fifoRows.map((row) => (
                <div className="audit-row" key={row.id}>
                  <span>{row.side.toUpperCase()}</span>
                  <strong>{formatNumber(row.quantity, 2)}</strong>
                  <em>{formatKrw(row.amount)}</em>
                </div>
              ))
            ) : (
              <div className="empty-row">No FIFO events</div>
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
