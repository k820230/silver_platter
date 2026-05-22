import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  LineChart,
  ReceiptText,
  ShieldCheck,
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
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
