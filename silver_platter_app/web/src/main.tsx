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
  security_ids: string[];
  group_ids: string[];
};

type HeadlineRiskResponse = {
  clusters: {
    cluster_id: string;
    provider_count: number;
    headline_count: number;
  }[];
  signals: HeadlineRiskSignal[];
};

type StrategyPlugin = {
  plugin_id: string;
  name: string;
  description: string;
};

type StrategyPluginsResponse = {
  plugins: StrategyPlugin[];
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
  strategyPlugins: StrategyPlugin[];
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
  if (["ok", "pass", "ready", "accepted", "filled"].includes(normalized)) {
    return "ok";
  }
  if (["blocked", "failed", "critical", "rejected", "block"].includes(normalized)) {
    return "critical";
  }
  if (["degraded", "warning", "watch"].includes(normalized)) {
    return "watch";
  }
  return "neutral";
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
    backupStatus,
    strategyPlugins: strategyPlugins.plugins,
    audit,
    gate,
    tax,
    backtest,
    headlineRisk,
  };
}

function App() {
  const [form, setForm] = useState<OrderForm>(DEFAULT_ORDER);
  const [data, setData] = useState<DashboardData>(EMPTY_DASHBOARD);
  const [preview, setPreview] = useState<OrderPreviewResponse | null>(null);
  const [submission, setSubmission] = useState<OrderSubmitResponse | null>(null);
  const [state, setState] = useState<RequestState>("idle");
  const [actionState, setActionState] = useState<RequestState>("idle");
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

  const priceRanges = preview?.price_ranges ?? [];
  const latestPrediction = data.mlJob?.predictions.find((item) => item.horizon === "1w");
  const modelPerformance = data.mlPerformance?.error_summary;
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

      <section className="workbench">
        <article className="order-ticket">
          <header>
            <h1>Order Preview</h1>
            <span>{form.securityId}</span>
          </header>
          <div className="ticket-grid">
            <label>
              Security
              <input
                value={form.securityId}
                onChange={(event) =>
                  setForm((current) => ({ ...current, securityId: event.target.value }))
                }
              />
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
                onChange={(event) =>
                  setForm((current) => ({ ...current, market: event.target.value }))
                }
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
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
