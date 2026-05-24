# Silver Platter Trading MVP

This directory contains the implementation workspace for the quant-based stock trading program described in `/home/jhkim5/silver_platter`.

All project artifacts are managed under `/home/jhkim5/silver_platter`. Do not create or modify Silver Platter project files under `/home/jhkim5/work/product`.

## Current Scope

- Wave 0 repository bootstrap
- Wave 1 Goldilocks schema foundation skeleton
- MVP risk rule engine skeleton
- Order preview skeleton
- API, worker, scheduler, and API-bound Web UI with order, operations, backtest, and strategy parameter controls
- Business group assignment, group risk, and normalized volatility comparison helpers
- Trusted headline filtering, headline dedup clustering, headline-to-risk-signal bridge, and geopolitical event alert helper
- Federal Reserve and ECB official RSS headline metadata connector
- OFAC Recent Actions headline metadata connector
- User-designated security ML forecast baseline
- Disclosure impact preview helper
- FIFO realized PnL and overseas stock capital gains tax support estimate helper
- Data provider interface, reference/disclosure/FX ingestion helpers, KRX daily price, CSV and ECOS BOK FX providers, quality manifest, partitioned export helper, and exported snapshot loader/replay runner
- SEC EDGAR and OpenDART disclosure metadata connectors with guarded smoke scripts
- Goldilocks repository writer for provider, security, manifest, quality, price bar, audit, headline, order state, backtest, scenario, restore check, verification gate, and alert delivery rows
- Execution posting, broker reconciliation, order state machine, idempotency, paper/KIS guarded broker boundary with orderability query smoke, kill switch, and event-risk controls
- Watchlist, ML prediction job, prediction actual/error tracking, and volatility/risk index chart helpers
- Backtest/replay lookahead guard, strategy plugin registry, exported snapshot replay runner, paper replay evidence, scenario shock helper, backup manifest/restore-check/status helpers with restore-drill evidence summary, backup execution lock, and backup/restore scheduler helpers with run-once due backup and restore-drill triggering
- API boundary checks for strategy, replay, and headline risk signal input errors
- Audit log, operations summary, provider health/catalog with license-policy detail, and alert delivery helpers
- Verification gate/evidence assessment helper

## Local Commands

```bash
cd /home/jhkim5/silver_platter/silver_platter_app
./scripts/test
./scripts/lint
./scripts/check
./scripts/smoke_api
./scripts/scheduler_smoke
./scripts/guarded_smoke
./scripts/collect_verification_evidence
./scripts/migrate status
./scripts/migrate render
./scripts/migrate plan
./scripts/migrate apply --dry-run
./scripts/migrate apply
./scripts/replay_exported_snapshot --help
./scripts/goldilocks_odbc_smoke
./scripts/goldilocks_repository_smoke
./scripts/kis_orderable_smoke
./scripts/sec_edgar_smoke
./scripts/opendart_smoke
./scripts/krx_kind_smoke
./scripts/krx_price_smoke
./scripts/ecos_fx_smoke
./scripts/official_rss_smoke
./scripts/ofac_recent_actions_smoke
./scripts/provider_smoke
./scripts/alert_webhook_smoke
docker-compose config
npm --prefix web install
npm --prefix web run build
```

For local secrets, create an untracked `.env` and pass it explicitly with `docker-compose --env-file .env ...` or keep secrets in the host environment.
`./scripts/migrate apply` requires a Goldilocks ODBC configuration via `GOLDILOCKS_ODBC_CONNECT_STRING`, `GOLDILOCKS_ODBC_DSN`, or `GOLDILOCKS_ODBC_DRIVER`.
Set `WATCHLIST_STORE_PATH` to persist API watchlist changes to a local JSON file; leave it empty for in-memory development mode.
`./scripts/goldilocks_odbc_smoke` is read-only and skips unless Goldilocks ODBC is configured.
`./scripts/goldilocks_repository_smoke` rolls back provider/license/audit/scenario/restore/headline writer checks and skips unless `GOLDILOCKS_REPOSITORY_SMOKE_WRITE=1` plus Goldilocks ODBC are configured.
`./scripts/goldilocks_backup.sh` uses `BACKUP_BASE_DIR`, `GOLDILOCKS_BACKUP_POLICY`, and `GOLDILOCKS_BACKUP_COMMAND`; it runs the configured command inside a dated backup directory, writes a checksum-backed manifest only when backup files are produced, and skips without creating a fake manifest when no command is configured.
`./scripts/kis_orderable_smoke` is read-only and skips unless KIS query credentials and `KIS_API_BASE_URL` are configured.
`./scripts/sec_edgar_smoke` is read-only and skips unless `SEC_EDGAR_USER_AGENT` is set to a real contact User-Agent.
`./scripts/opendart_smoke` is read-only and skips unless `OPENDART_API_KEY` is configured.
`./scripts/krx_kind_smoke` is read-only and skips unless `KRX_KIND_SMOKE_ENABLED=1` is configured.
`./scripts/krx_price_smoke` is read-only and skips unless `KRX_PRICE_SMOKE_ENABLED=1` is configured.
`./scripts/ecos_fx_smoke` is read-only and skips unless `ECOS_API_KEY` is configured.
`./scripts/official_rss_smoke` is read-only and skips unless `OFFICIAL_RSS_SMOKE_ENABLED=1` is configured.
`./scripts/ofac_recent_actions_smoke` is read-only and skips unless `OFAC_RECENT_ACTIONS_SMOKE_ENABLED=1` is configured.
`./scripts/provider_smoke` runs the guarded SEC EDGAR, OpenDART, KRX KIND, KRX price, ECOS FX, official RSS, and OFAC smoke checks.
`./scripts/alert_webhook_smoke` sends one test alert and skips unless `ALERT_WEBHOOK_URL` is configured.
`./scripts/collect_verification_evidence` writes a local gate evidence JSON bundle under `var/verification/` by default; use `--run-smoke-api` to include API smoke evidence and `--write-goldilocks` to persist assessments/evidence through the configured Goldilocks repository writer.

## MVP Defaults

- DBMS: Goldilocks, external listener at `host.docker.internal:22581`
- Schema: `SP`
- Single security investment amount: KRW 100,000 to KRW 1,000,000,000
- Auto order max amount: KRW 1,000,000,000
- Liquidity hard gate: order amount / 20-trading-day average turnover <= 5%
- Group liquidity hard gate: group daily new orders / group 20-trading-day average turnover <= 5%
- Low liquidity floor: 20-trading-day average turnover under KRW 1,000,000,000
- Low liquidity slippage multiplier: 3x
- Simulation initial cash: KRW 100,000,000
- Overseas capital gains tax support estimate: configurable KRW 2,500,000 deduction, 20% national tax, 2% local income tax

## Safety

Live order sending is disabled by default. Simulation orders must not be sent to the broker adapter.
