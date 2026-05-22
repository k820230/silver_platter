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


def _write_jsonl(path: Path, records: Sequence[dict]) -> str:
    payload = "\n".join(
        json.dumps(record, sort_keys=True, ensure_ascii=True, default=_json_default)
        for record in records
    )
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_parquet(path: Path, records: Sequence[dict]) -> str:
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    table = pa.Table.from_pylist(list(records))
    pq.write_table(table, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
