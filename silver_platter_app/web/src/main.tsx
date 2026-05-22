import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Database,
  LineChart,
  ReceiptText,
  ServerCog,
  ShieldCheck,
  TestTube2,
} from "lucide-react";
import "./styles.css";

const groupVolatility = [
  { name: "Semiconductor", change: "+12.4%", risk: "watch" },
  { name: "EV Battery", change: "+8.1%", risk: "normal" },
  { name: "Cloud AI", change: "+18.7%", risk: "caution" },
];

const priceRanges = [
  { horizon: "1D", low: "78,400", mid: "80,100", high: "81,900" },
  { horizon: "1W", low: "75,600", mid: "80,100", high: "84,700" },
  { horizon: "1M", low: "70,200", mid: "80,100", high: "90,500" },
  { horizon: "3M", low: "62,900", mid: "80,100", high: "98,400" },
];

const operations = [
  { name: "Provider Quality", status: "OK", detail: "34 checks" },
  { name: "Order State", status: "Ready", detail: "8 transitions" },
  { name: "Backtest", status: "OK", detail: "No lookahead" },
  { name: "Backup", status: "Watch", detail: "Manifest only" },
];

const auditEvents = [
  { time: "09:00", action: "ORDER_PREVIEW", target: "005930.KS" },
  { time: "09:04", action: "RISK_CHECK", target: "pass" },
  { time: "09:11", action: "BACKTEST_RUN", target: "bt-1" },
];

function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <strong>Silver Platter</strong>
          <span>Simulation</span>
        </div>
        <button type="button" className="icon-button" title="System health">
          <Activity size={18} />
        </button>
      </header>

      <section className="metric-grid" aria-label="Status metrics">
        <article className="metric-card">
          <ShieldCheck size={18} />
          <span>Risk Gate</span>
          <strong>Pass</strong>
        </article>
        <article className="metric-card">
          <Database size={18} />
          <span>Goldilocks</span>
          <strong>Ready</strong>
        </article>
        <article className="metric-card">
          <AlertTriangle size={18} />
          <span>Event Alert</span>
          <strong>Watch</strong>
        </article>
        <article className="metric-card">
          <ReceiptText size={18} />
          <span>Tax Estimate</span>
          <strong>440,000 KRW</strong>
        </article>
        <article className="metric-card">
          <TestTube2 size={18} />
          <span>Backtest</span>
          <strong>54 Tests</strong>
        </article>
        <article className="metric-card">
          <ServerCog size={18} />
          <span>Operations</span>
          <strong>Degraded</strong>
        </article>
      </section>

      <section className="workbench">
        <article className="order-ticket">
          <header>
            <h1>Order Preview</h1>
            <span>005930.KS</span>
          </header>
          <div className="ticket-grid">
            <label>
              Side
              <select defaultValue="buy">
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </label>
            <label>
              Price
              <input defaultValue="80100" inputMode="decimal" />
            </label>
            <label>
              Quantity
              <input defaultValue="120" inputMode="numeric" />
            </label>
            <label>
              Type
              <select defaultValue="limit">
                <option value="limit">Limit</option>
                <option value="market">Market</option>
              </select>
            </label>
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
                <span>{range.horizon}</span>
                <span>{range.low}</span>
                <span>{range.mid}</span>
                <span>{range.high}</span>
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
            {groupVolatility.map((group) => (
              <div className="bar-row" key={group.name}>
                <span>{group.name}</span>
                <div className="bar-track">
                  <div
                    className={`bar-fill ${group.risk}`}
                    style={{ width: group.change.replace("+", "") }}
                  />
                </div>
                <strong>{group.change}</strong>
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
              <dd>75,600 - 84,700</dd>
            </div>
            <div>
              <dt>Volume</dt>
              <dd>42.5M - 57.5M</dd>
            </div>
            <div>
              <dt>Volatility</dt>
              <dd>29.4%</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>37.6</dd>
            </div>
          </dl>
        </article>

        <article className="wide-panel">
          <header>
            <h2>Operations</h2>
            <ServerCog size={18} />
          </header>
          <div className="ops-grid">
            {operations.map((item) => (
              <div className="ops-row" key={item.name}>
                <span>{item.name}</span>
                <strong>{item.status}</strong>
                <em>{item.detail}</em>
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
            {auditEvents.map((event) => (
              <div className="audit-row" key={`${event.time}-${event.action}`}>
                <span>{event.time}</span>
                <strong>{event.action}</strong>
                <em>{event.target}</em>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
