from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from silver_platter.data_quality import PriceBarInput


@dataclass(frozen=True)
class ExportedFile:
    path: str
    partition_date: date
    row_count: int
    format: str
    content_sha256: str


@dataclass(frozen=True)
class PartitionedExportResult:
    dataset_name: str
    provider_code: str
    row_count: int
    requested_format: str
    written_format: str
    files: List[ExportedFile]

    def as_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "provider_code": self.provider_code,
            "row_count": self.row_count,
            "requested_format": self.requested_format,
            "written_format": self.written_format,
            "files": [
                {
                    "path": item.path,
                    "partition_date": item.partition_date.isoformat(),
                    "row_count": item.row_count,
                    "format": item.format,
                    "content_sha256": item.content_sha256,
                }
                for item in self.files
            ],
        }


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _price_bar_record(bar: PriceBarInput) -> dict:
    record = asdict(bar)
    return {
        key: value.isoformat() if isinstance(value, (datetime, date)) else value
        for key, value in record.items()
    }


def _datetime_or_none(value: object) -> datetime:
    if value is None:
        raise ValueError("datetime value is required")
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _optional_datetime(value: object) -> datetime:
    return _datetime_or_none(value)


def _price_bar_from_record(record: dict) -> PriceBarInput:
    return PriceBarInput(
        security_id=str(record["security_id"]),
        bar_ts=_datetime_or_none(record["bar_ts"]),
        close_price=None if record.get("close_price") is None else float(record["close_price"]),
        volume=None if record.get("volume") is None else float(record["volume"]),
        turnover_krw=None
        if record.get("turnover_krw") is None
        else float(record["turnover_krw"]),
        available_to_model_at=None
        if record.get("available_to_model_at") is None
        else _optional_datetime(record["available_to_model_at"]),
    )


def _write_jsonl(path: Path, records: Sequence[dict]) -> str:
    payload = "\n".join(
        json.dumps(record, sort_keys=True, ensure_ascii=True, default=_json_default)
        for record in records
    )
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> List[PriceBarInput]:
    bars = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        bars.append(_price_bar_from_record(json.loads(line)))
    return bars


def _write_parquet(path: Path, records: Sequence[dict]) -> str:
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    table = pa.Table.from_pylist(list(records))
    pq.write_table(table, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_parquet(path: Path) -> List[PriceBarInput]:
    import pyarrow.parquet as pq  # type: ignore

    table = pq.read_table(path)
    return [_price_bar_from_record(record) for record in table.to_pylist()]


def _path_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in {"jsonl", "parquet"}:
        raise ValueError("unsupported export file extension: %s" % path)
    return suffix


def _read_price_bars_by_format(path: Path, file_format: str) -> List[PriceBarInput]:
    if file_format == "jsonl":
        return _read_jsonl(path)
    if file_format == "parquet":
        return _read_parquet(path)
    raise ValueError("unsupported export format: %s" % file_format)


def export_price_bars_partitioned(
    bars: Iterable[PriceBarInput],
    base_dir: Path,
    provider_code: str,
    dataset_name: str = "price_bar",
    prefer_parquet: bool = True,
) -> PartitionedExportResult:
    rows = list(bars)
    if not rows:
        raise ValueError("at least one price bar is required for export")

    partitions: Dict[date, List[dict]] = {}
    for bar in rows:
        partition_date = bar.bar_ts.date()
        partitions.setdefault(partition_date, []).append(_price_bar_record(bar))

    written_format = "parquet" if prefer_parquet else "jsonl"
    if prefer_parquet:
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            written_format = "jsonl"

    files: List[ExportedFile] = []
    for partition_date, records in sorted(partitions.items(), key=lambda item: item[0]):
        target_dir = (
            base_dir
            / dataset_name
            / ("provider=%s" % provider_code)
            / ("date=%s" % partition_date.isoformat())
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = "parquet" if written_format == "parquet" else "jsonl"
        target_path = target_dir / ("part-00000.%s" % suffix)
        if written_format == "parquet":
            digest = _write_parquet(target_path, records)
        else:
            digest = _write_jsonl(target_path, records)
        files.append(
            ExportedFile(
                path=str(target_path),
                partition_date=partition_date,
                row_count=len(records),
                format=written_format,
                content_sha256=digest,
            )
        )

    return PartitionedExportResult(
        dataset_name=dataset_name,
        provider_code=provider_code,
        row_count=len(rows),
        requested_format="parquet" if prefer_parquet else "jsonl",
        written_format=written_format,
        files=files,
    )


def load_price_bars_from_exported_files(
    files: Iterable[ExportedFile],
) -> List[PriceBarInput]:
    bars: List[PriceBarInput] = []
    for exported_file in sorted(files, key=lambda item: item.path):
        path = Path(exported_file.path)
        bars.extend(_read_price_bars_by_format(path, exported_file.format))
    return sorted(bars, key=lambda item: (item.security_id, item.bar_ts))


def load_price_bars_from_paths(paths: Iterable[Path]) -> List[PriceBarInput]:
    discovered: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            discovered.extend(
                sorted(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() in {".jsonl", ".parquet"}
                )
            )
        else:
            if not path.exists():
                raise FileNotFoundError(str(path))
            discovered.append(path)

    if not discovered:
        raise ValueError("no exported snapshot files found")

    bars: List[PriceBarInput] = []
    for path in sorted(discovered):
        bars.extend(_read_price_bars_by_format(path, _path_format(path)))
    return sorted(bars, key=lambda item: (item.security_id, item.bar_ts))
