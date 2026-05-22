# Silver Platter Trading MVP

This directory contains the implementation workspace for the quant-based stock trading program described in `/home/jhkim5/silver_platter`.

All project artifacts are managed under `/home/jhkim5/silver_platter`. Do not create or modify Silver Platter project files under `/home/jhkim5/work/product`.

## Current Scope

- Wave 0 repository bootstrap
- Wave 1 Goldilocks schema foundation skeleton
- MVP risk rule engine skeleton
- Order preview skeleton
- API, worker, scheduler, and Web UI startup skeletons
- Business group assignment, group risk, and normalized volatility comparison helpers
- Trusted headline filtering and geopolitical event alert helper
- User-designated security ML forecast baseline
- Disclosure impact preview helper
- FIFO realized PnL and overseas stock capital gains tax support estimate helper
- Data provider interface, reference/disclosure/FX ingestion helpers, quality manifest, and partitioned export helper

## Local Commands

```bash
cd /home/jhkim5/silver_platter/silver_platter_app
./scripts/test
./scripts/lint
./scripts/check
./scripts/migrate status
./scripts/migrate render
docker-compose config
npm --prefix web install
npm --prefix web run build
```

For local secrets, create an untracked `.env` and pass it explicitly with `docker-compose --env-file .env ...` or keep secrets in the host environment.

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
