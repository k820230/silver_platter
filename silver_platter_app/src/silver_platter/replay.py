from dataclasses import dataclass, replace
from datetime import date
import argparse
import json
from pathlib import Path
from typing import List, Optional, Sequence

from silver_platter.backtest import (
    BacktestResult,
    BacktestRunConfig,
    PaperReplayEvidence,
    build_paper_replay_evidence,
    run_backtest,
)
from silver_platter.exports import load_price_bars_from_paths
from silver_platter.strategies import DEFAULT_STRATEGY_REGISTRY, StrategyContext


@dataclass(frozen=True)
class ExportedSnapshotReplayConfig:
    run_id: str
    strategy_id: str
    from_date: date
    to_date: date
    security_id: str
    snapshot_paths: List[Path]
    market: str = "KR"
    side: str = "buy"
    order_type: str = "limit"
    quantity: float = 1.0
    avg_daily_turnover_20d_krw: float = 1_000_000_000.0
    initial_cash_krw: float = 100_000_000.0
    required_min_days: int = 1
    strategy_plugin_id: str = "fixed-close"
    strategy_parameters: Optional[dict] = None
    replay_seed: str = ""


@dataclass(frozen=True)
class ExportedSnapshotReplayResult:
    config: ExportedSnapshotReplayConfig
    loaded_bar_count: int
    replay_bar_count: int
    source_paths: List[str]
    backtest: BacktestResult
    paper_replay_evidence: PaperReplayEvidence

    def as_dict(self) -> dict:
        return {
            "run_id": self.backtest.run_id,
            "status": self.backtest.status,
            "strategy_id": self.config.strategy_id,
            "strategy_plugin_id": self.config.strategy_plugin_id,
            "security_id": self.config.security_id,
            "from_date": self.config.from_date.isoformat(),
            "to_date": self.config.to_date.isoformat(),
            "loaded_bar_count": self.loaded_bar_count,
            "replay_bar_count": self.replay_bar_count,
            "source_paths": self.source_paths,
            "strategy_parameters": self.config.strategy_parameters or {},
            "replay_seed": self.backtest.replay_seed,
            "ending_cash_krw": self.backtest.ending_cash_krw,
            "realized_pnl_krw": self.backtest.realized_pnl_krw,
            "blocked_order_count": self.backtest.blocked_order_count,
            "lookahead_violation_count": self.backtest.lookahead_violation_count,
            "metrics": self.backtest.metrics,
            "paper_replay_evidence": self.paper_replay_evidence.as_dict(),
            "order_events": [
                {
                    "candidate": event.candidate.__dict__,
                    "accepted": event.accepted,
                    "reason": event.reason,
                    "realized_pnl_krw": event.realized_pnl_krw,
                }
                for event in self.backtest.order_events
            ],
        }


def run_exported_snapshot_replay(
    config: ExportedSnapshotReplayConfig,
) -> ExportedSnapshotReplayResult:
    bars = load_price_bars_from_paths(config.snapshot_paths)
    replay_bars = [bar for bar in bars if bar.security_id == config.security_id]
    if not replay_bars:
        raise ValueError("no bars found for security_id: %s" % config.security_id)
    strategy = DEFAULT_STRATEGY_REGISTRY.build(
        config.strategy_plugin_id,
        StrategyContext(
            strategy_id=config.strategy_id,
            security_id=config.security_id,
            market=config.market,
            side=config.side,
            order_type=config.order_type,
            quantity=config.quantity,
            avg_daily_turnover_20d_krw=config.avg_daily_turnover_20d_krw,
            parameters=config.strategy_parameters or {},
        ),
    )

    backtest = run_backtest(
        BacktestRunConfig(
            run_id=config.run_id,
            strategy_id=config.strategy_id,
            from_date=config.from_date,
            to_date=config.to_date,
            initial_cash_krw=config.initial_cash_krw,
            replay_seed=config.replay_seed,
        ),
        replay_bars,
        strategy,
    )
    metrics = dict(backtest.metrics)
    metrics["loaded_bar_count"] = float(len(bars))
    metrics["replay_bar_count"] = float(len(replay_bars))
    backtest = replace(backtest, metrics=metrics)

    return ExportedSnapshotReplayResult(
        config=config,
        loaded_bar_count=len(bars),
        replay_bar_count=len(replay_bars),
        source_paths=[str(path) for path in config.snapshot_paths],
        backtest=backtest,
        paper_replay_evidence=build_paper_replay_evidence(
            backtest,
            required_min_days=config.required_min_days,
        ),
    )


def _json_default(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a backtest from exported price bar snapshot files")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--security-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--market", default="KR")
    parser.add_argument("--side", default="buy")
    parser.add_argument("--order-type", default="limit")
    parser.add_argument("--quantity", type=float, default=1.0)
    parser.add_argument("--avg-daily-turnover-20d-krw", type=float, default=1_000_000_000.0)
    parser.add_argument("--initial-cash-krw", type=float, default=100_000_000.0)
    parser.add_argument("--required-min-days", type=int, default=1)
    parser.add_argument("--strategy-plugin-id", default="fixed-close")
    parser.add_argument("--strategy-parameter", action="append", default=[])
    parser.add_argument("--replay-seed", default="")
    return parser.parse_args(argv)


def _parse_strategy_parameters(raw_items: Sequence[str]) -> dict:
    parameters = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError("strategy parameter must use key=value: %s" % item)
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("strategy parameter key is required")
        try:
            value = float(raw_value)
        except ValueError:
            value = raw_value
        parameters[key] = value
    return parameters


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    strategy_parameters = _parse_strategy_parameters(args.strategy_parameter)
    result = run_exported_snapshot_replay(
        ExportedSnapshotReplayConfig(
            run_id=args.run_id,
            strategy_id=args.strategy_id,
            from_date=date.fromisoformat(args.from_date),
            to_date=date.fromisoformat(args.to_date),
            security_id=args.security_id,
            snapshot_paths=[Path(item) for item in args.snapshot_path],
            market=args.market,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            avg_daily_turnover_20d_krw=args.avg_daily_turnover_20d_krw,
            initial_cash_krw=args.initial_cash_krw,
            required_min_days=args.required_min_days,
            strategy_plugin_id=args.strategy_plugin_id,
            strategy_parameters=strategy_parameters,
            replay_seed=args.replay_seed,
        )
    )
    print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=True, default=_json_default))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
