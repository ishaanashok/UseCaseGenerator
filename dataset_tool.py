from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from agno.agent import Toolkit


DEFAULT_DATASET_PATH = Path("data/AP_Finance_Data.xlsx")


def _source_kind(dataset_path: str | Path) -> str:
	path = Path(dataset_path)
	extension = path.suffix.lower()
	if extension in {".xlsx", ".xls"}:
		return "excel"
	if extension == ".csv":
		return "csv"
	if extension == ".json":
		return "json"
	if extension in {".sqlite", ".db", ".sqlite3"}:
		return "sqlite"
	return "unknown"


def _to_serializable(value: Any) -> Any:
	if value is None:
		return None
	if isinstance(value, (datetime, date)):
		return value.isoformat()
	if isinstance(value, pd.Timestamp):
		return value.to_pydatetime().isoformat()

	try:
		if pd.isna(value):
			return None
	except Exception:
		pass

	if hasattr(value, "item") and not isinstance(value, (str, bytes, dict, list, tuple, set)):
		try:
			value = value.item()
		except Exception:
			pass

	if isinstance(value, (datetime, date)):
		return value.isoformat()

	return value


def _normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	normalized_records: List[Dict[str, Any]] = []
	for record in records:
		normalized_records.append({key: _to_serializable(value) for key, value in record.items()})
	return normalized_records


def load_dataset(dataset_path: str | Path = DEFAULT_DATASET_PATH) -> Dict[str, pd.DataFrame]:
	path = Path(dataset_path)
	if not path.exists():
		raise FileNotFoundError(f"Dataset not found: {path}")

	kind = _source_kind(path)
	if kind == "excel":
		return pd.read_excel(path, sheet_name=None, engine="openpyxl")
	if kind == "csv":
		return {path.stem: pd.read_csv(path)}
	if kind == "json":
		frame = pd.read_json(path)
		return {path.stem: frame}
	if kind == "sqlite":
		connection = sqlite3.connect(path)
		try:
			table_names = pd.read_sql_query(
				"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
				connection,
			)["name"].tolist()
			if not table_names:
				raise ValueError(f"No tables found in SQLite database: {path}")
			return {table_name: pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection) for table_name in table_names}
		finally:
			connection.close()

	raise ValueError(f"Unsupported dataset type for {path}. Use xlsx, csv, json, or sqlite.")


def build_dataset_profile(
	dataset_path: str | Path = DEFAULT_DATASET_PATH,
	sample_rows: int = 3,
	max_columns: int = 12,
) -> Dict[str, Any]:
	sheets = load_dataset(dataset_path)
	path = Path(dataset_path)

	profile: Dict[str, Any] = {
		"dataset_name": path.name,
		"dataset_path": str(path),
		"dataset_kind": _source_kind(path),
		"sheet_count": len(sheets),
		"sheets": [],
	}

	for sheet_name, frame in sheets.items():
		preview_columns = [str(column) for column in list(frame.columns)[:max_columns]]
		sample_records = _normalize_records(frame.head(sample_rows).to_dict(orient="records"))

		profile["sheets"].append(
			{
				"sheet_name": sheet_name,
				"row_count": int(len(frame)),
				"column_count": int(len(frame.columns)),
				"columns": [str(column) for column in frame.columns],
				"preview_columns": preview_columns,
				"sample_rows": sample_records,
			}
		)

	return profile


def format_dataset_profile(profile: Dict[str, Any]) -> str:
	lines: List[str] = []
	lines.append(f"Dataset: {profile['dataset_name']}")
	lines.append(f"Path: {profile['dataset_path']}")
	lines.append(f"Type: {profile.get('dataset_kind', 'unknown')}")
	lines.append(f"Sheets: {profile['sheet_count']}")

	for sheet in profile.get("sheets", []):
		lines.append("")
		lines.append(f"Sheet: {sheet['sheet_name']}")
		lines.append(f"Rows: {sheet['row_count']}")
		lines.append(f"Columns: {sheet['column_count']}")
		lines.append(f"Column names: {', '.join(sheet['columns'])}")
		lines.append("Sample rows:")
		for index, row in enumerate(sheet.get("sample_rows", []), start=1):
			lines.append(f"  {index}. {json.dumps(row, ensure_ascii=True)}")

	return "\n".join(lines)


def suggest_use_case_angles(
	dataset_path: str | Path = DEFAULT_DATASET_PATH,
	domain: str = "",
	department: str = "",
) -> Dict[str, Any]:
	profile = build_dataset_profile(dataset_path=dataset_path, sample_rows=2)
	sheet_names = {sheet["sheet_name"].lower() for sheet in profile["sheets"]}
	column_names = {
		str(column).lower()
		for sheet in profile["sheets"]
		for column in sheet.get("columns", [])
	}

	suggested_angles: List[str] = []
	if {"vendors", "invoices", "payments"}.issubset(sheet_names):
		suggested_angles.append("accounts payable automation and vendor payment intelligence")
	if "cost_centers" in sheet_names or "cost center" in " ".join(column_names):
		suggested_angles.append("budget tracking and cost center spend control")
	if {"payment_status", "invoice_status"}.issubset(column_names):
		suggested_angles.append("payment exception and overdue invoice monitoring")

	if domain or department:
		suggested_angles.insert(0, f"tailored use case for domain='{domain or 'unspecified'}' and department='{department or 'unspecified'}'")

	if not suggested_angles:
		suggested_angles.append("generic workflow automation and reporting")

	return {
		"domain": domain,
		"department": department,
		"dataset_name": profile["dataset_name"],
		"dataset_kind": profile.get("dataset_kind", "unknown"),
		"suggested_angles": suggested_angles,
	}


def get_dataset_profile(
	dataset_path: str = str(DEFAULT_DATASET_PATH),
	sample_rows: int = 3,
	max_columns: int = 12,
) -> Dict[str, Any]:
	return build_dataset_profile(dataset_path=dataset_path, sample_rows=sample_rows, max_columns=max_columns)


def get_sheet_preview(
	sheet_name: str,
	dataset_path: str = str(DEFAULT_DATASET_PATH),
	sample_rows: int = 5,
) -> Dict[str, Any]:
	sheets = load_dataset(dataset_path)
	if sheet_name not in sheets:
		available = ", ".join(sheets.keys())
		raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {available}")

	frame = sheets[sheet_name]
	return {
		"sheet_name": sheet_name,
		"row_count": int(len(frame)),
		"column_count": int(len(frame.columns)),
		"columns": [str(column) for column in frame.columns],
		"sample_rows": _normalize_records(frame.head(sample_rows).to_dict(orient="records")),
	}


def build_dataset_toolkit(dataset_path: str | Path = DEFAULT_DATASET_PATH) -> Toolkit:
	default_dataset_path = str(dataset_path)

	def toolkit_get_dataset_profile(sample_rows: int = 3, max_columns: int = 12) -> Dict[str, Any]:
		return get_dataset_profile(dataset_path=default_dataset_path, sample_rows=sample_rows, max_columns=max_columns)

	def toolkit_get_sheet_preview(sheet_name: str, sample_rows: int = 5) -> Dict[str, Any]:
		return get_sheet_preview(sheet_name=sheet_name, dataset_path=default_dataset_path, sample_rows=sample_rows)

	def toolkit_suggest_use_case_angles(domain: str = "", department: str = "") -> Dict[str, Any]:
		return suggest_use_case_angles(dataset_path=default_dataset_path, domain=domain, department=department)

	def toolkit_format_dataset_profile(sample_rows: int = 3, max_columns: int = 12) -> str:
		profile = get_dataset_profile(
			dataset_path=default_dataset_path,
			sample_rows=sample_rows,
			max_columns=max_columns,
		)
		return format_dataset_profile(profile)

	return Toolkit(
		name="dataset_toolkit",
		tools=[
			toolkit_get_dataset_profile,
			toolkit_get_sheet_preview,
			toolkit_suggest_use_case_angles,
			toolkit_format_dataset_profile,
		],
	)
