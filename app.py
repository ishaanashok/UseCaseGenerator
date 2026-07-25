from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from agent import generate_use_case
from dataset_tool import DEFAULT_DATASET_PATH, build_dataset_profile, format_dataset_profile


app = FastAPI(title="AI Use Case Generator")


SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv", ".json", ".sqlite", ".db", ".sqlite3"}


def _strip_code_fences(text: str) -> str:
	lines = text.strip().splitlines()
	if lines and lines[0].lstrip().startswith("```"):
		lines = lines[1:]
	if lines and lines[-1].rstrip().startswith("```"):
		lines = lines[:-1]
	return "\n".join(lines).strip()


def _format_inline_markdown(text: str) -> str:
	formatted = html.escape(text)
	formatted = re.sub(r"`([^`]+)`", r"<code>\1</code>", formatted)
	formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", formatted)
	return formatted


def _clean_item_text(text: str) -> str:
	cleaned = text.strip()
	cleaned = re.sub(r"^[-*]\s+", "", cleaned)
	cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
	return cleaned


def _render_result_html(result_text: str) -> str:
	clean_text = _strip_code_fences(result_text)
	if not clean_text:
		return ""

	sections: list[dict[str, object]] = []
	current_section: dict[str, object] | None = None

	for raw_line in clean_text.splitlines():
		line = raw_line.rstrip()
		stripped = line.strip()
		if not stripped:
			continue

		headline_match = re.match(r"^-\s*\*\*(.+?)\*\*\s*$", line)
		if headline_match:
			current_section = {"title": headline_match.group(1), "items": []}
			sections.append(current_section)
			continue

		if current_section is None:
			current_section = {"title": "Result", "items": []}
			sections.append(current_section)

		items = current_section.setdefault("items", [])
		if isinstance(items, list):
			items.append(stripped)

	section_map = {str(section.get("title", "")).strip().lower(): list(section.get("items", [])) for section in sections}
	result_blocks: list[str] = []

	title_items = section_map.get("title", [])
	use_case_items = section_map.get("use case overview", [])
	if title_items or use_case_items:
		title_text = _clean_item_text(title_items[0]) if title_items else ""
		use_case_text = " ".join(_clean_item_text(item) for item in use_case_items if _clean_item_text(item))
		use_case_html = ""
		if title_text:
			use_case_html += f'<div class="result-usecase-title">{_format_inline_markdown(title_text)}</div>'
		if use_case_text:
			use_case_html += f'<p class="result-paragraph result-usecase-text">{_format_inline_markdown(use_case_text)}</p>'
		result_blocks.append(
			f'<section class="result-section result-usecase"><div class="result-label">Use case</div>{use_case_html}</section>'
		)

	risk_items = section_map.get("risks or assumptions", [])
	if risk_items:
		list_items: list[str] = []
		paragraphs: list[str] = []
		for item in risk_items:
			clean_item = _clean_item_text(item)
			bullet_match = re.match(r"^[-*]\s+(.*)$", clean_item)
			ordered_match = re.match(r"^\d+[.)]\s+(.*)$", clean_item)
			if bullet_match:
				list_items.append(f"<li>{_format_inline_markdown(bullet_match.group(1))}</li>")
			elif ordered_match:
				list_items.append(f"<li>{_format_inline_markdown(ordered_match.group(1))}</li>")
			else:
				paragraphs.append(_format_inline_markdown(clean_item))

		risk_content = ""
		if list_items:
			risk_content += f'<ul class="result-list">{"".join(list_items)}</ul>'
		if paragraphs:
			risk_content += "".join(f"<p class='result-paragraph'>{paragraph}</p>" for paragraph in paragraphs)

		result_blocks.append(
			f'<section class="result-section result-risks"><div class="result-label">Risks or assumptions</div>{risk_content}</section>'
		)

	return "".join(result_blocks)


def _render_page(result_text: str = "", error_text: str = "", domain: str = "") -> str:
	error_block = ""
	if error_text:
		error_block = f'<div class="alert error">{html.escape(error_text)}</div>'

	result_block = _render_result_html(result_text)
	if result_text and not result_block:
		result_block = f'<pre class="result-fallback">{html.escape(result_text)}</pre>'

	domain_value = html.escape(domain)

	return f"""
<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>AI Use Case Generator</title>
	<style>
		:root {{
			color-scheme: light;
			--bg: #f5f1e8;
			--panel: #ffffff;
			--text: #1f2937;
			--muted: #6b7280;
			--accent: #0f766e;
			--accent-2: #eab308;
			--border: #d6d3d1;
			--error: #b91c1c;
			--surface: #fafaf9;
			--surface-2: #f8fafc;
			--shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
		}}
		* {{ box-sizing: border-box; }}
		body {{
			margin: 0;
			font-family: Arial, Helvetica, sans-serif;
			color: var(--text);
			background:
				radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 30%),
				radial-gradient(circle at bottom right, rgba(234, 179, 8, 0.16), transparent 28%),
				var(--bg);
			min-height: 100vh;
		}}
		.wrap {{ max-width: 980px; margin: 0 auto; padding: 56px 20px; }}
		.grid {{ display: grid; gap: 20px; grid-template-columns: 1.05fr 0.95fr; align-items: start; }}
		.card {{ background: var(--panel); border: 1px solid rgba(214, 211, 209, 0.75); border-radius: 20px; box-shadow: var(--shadow); overflow: hidden; }}
		.card-body {{ padding: 24px; }}
		label {{ display: block; font-weight: 700; margin-bottom: 10px; }}
		.field {{ margin-bottom: 18px; }}
		input[type="text"], input[type="file"] {{ width: 100%; padding: 14px 14px; border-radius: 14px; border: 1px solid var(--border); background: #fff; font-size: 1rem; }}
		input[type="file"] {{ padding: 12px; }}
		.hint {{ margin-top: 8px; font-size: 0.93rem; color: var(--muted); }}
		.button {{
			display: inline-flex; align-items: center; justify-content: center; width: 100%;
			border: 0; border-radius: 14px; padding: 14px 18px; font-size: 1rem;
			font-weight: 700; color: white; background: linear-gradient(135deg, var(--accent), #115e59);
			cursor: pointer;
		}}
		.button:hover {{ filter: brightness(1.04); }}
		.alert {{ border-radius: 14px; padding: 14px 16px; margin-bottom: 18px; border: 1px solid transparent; }}
		.alert.error {{ background: #fef2f2; color: var(--error); border-color: #fecaca; }}
		.result-panel {{ padding: 24px; background: linear-gradient(180deg, #fff, var(--surface)); min-height: 420px; }}
		.result-panel h2 {{ margin: 0 0 8px; font-size: 1.1rem; }}
		.result-empty {{ color: var(--muted); font-size: 0.95rem; margin: 0; }}
		.result-section {{
			background: linear-gradient(180deg, #fff, var(--surface-2));
			border: 1px solid rgba(214, 211, 209, 0.75);
			border-radius: 16px;
			padding: 16px 16px 12px;
			margin-top: 14px;
		}}
		.result-label {{
			display: inline-block;
			font-size: 12px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			color: var(--accent);
			margin-bottom: 10px;
		}}
		.result-title .result-title-text {{
			font-size: 1.15rem;
			font-weight: 800;
			line-height: 1.35;
			color: var(--text);
		}}
		.result-usecase-title {{
			font-size: 1.2rem;
			font-weight: 800;
			line-height: 1.35;
			color: var(--text);
			margin-bottom: 10px;
		}}
		.result-usecase-text {{ font-size: 0.98rem; }}
		.result-list {{ margin: 0; padding-left: 20px; color: var(--text); line-height: 1.55; }}
		.result-list li + li {{ margin-top: 8px; }}
		.result-paragraph {{ margin: 0 0 10px; line-height: 1.65; color: var(--text); }}
		.result-paragraph:last-child {{ margin-bottom: 0; }}
		.result-fallback {{
			white-space: pre-wrap; word-break: break-word; margin: 14px 0 0;
			font-family: Consolas, Monaco, 'Courier New', monospace; font-size: 0.93rem;
			line-height: 1.55; background: #111827; color: #f9fafb; padding: 20px;
			border-radius: 16px;
		}}
		@media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} .result-panel {{ min-height: 280px; }} }}
	</style>
</head>
<body>
	<div class="wrap">
		<div class="grid">
			<div class="card">
				<div class="card-body">
					{error_block}
					<form method="post" enctype="multipart/form-data">
						<div class="field">
							<label for="dataset_file">Upload file</label>
							<input id="dataset_file" name="dataset_file" type="file" required>
							<div class="hint">Supported: .xlsx, .xls, .csv, .json, .sqlite, .db, .sqlite3</div>
						</div>
						<div class="field">
							<label for="domain">Domain (optional)</label>
							<input id="domain" name="domain" type="text" value="{domain_value}" placeholder="Example: finance, healthcare, retail">
						</div>
						<button class="button" type="submit">Generate use case</button>
					</form>
				</div>
			</div>

			<div class="card">
				<div class="result-panel">
					<h2>Result</h2>
					{result_block}
				</div>
			</div>
		</div>
	</div>
</body>
</html>
"""


def _save_upload_to_tempfile(upload_file: UploadFile) -> Path:
	suffix = Path(upload_file.filename or "").suffix.lower()
	if suffix not in SUPPORTED_SUFFIXES:
		raise HTTPException(status_code=400, detail="Unsupported file type. Upload an xlsx, csv, json, or sqlite file.")

	temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
	try:
		with temp_file:
			shutil.copyfileobj(upload_file.file, temp_file)
	finally:
		upload_file.file.close()

	return Path(temp_file.name)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
	return HTMLResponse(_render_page())


@app.post("/", response_class=HTMLResponse)
async def generate_from_upload(
	dataset_file: UploadFile = File(...),
	domain: str = Form(""),
) -> HTMLResponse:
	temporary_path = _save_upload_to_tempfile(dataset_file)
	try:
		result = generate_use_case(domain=domain.strip(), dataset_path=temporary_path)
	finally:
		temporary_path.unlink(missing_ok=True)

	return HTMLResponse(_render_page(result_text=result["response_text"], domain=domain))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Generate a business use case from a generic dataset using Agno.")
	parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Path to a generic dataset file: xlsx, csv, json, or sqlite")
	parser.add_argument("--domain", default="", help="Optional business domain")
	parser.add_argument("--department", default="", help="Optional department")
	parser.add_argument("--sample-rows", type=int, default=3, help="Number of sample rows to include per sheet")
	parser.add_argument("--max-columns", type=int, default=12, help="Max columns to include in the prompt summary")
	parser.add_argument("--show-profile", action="store_true", help="Print the dataset profile before generation")
	parser.add_argument("--json", action="store_true", help="Print the final result as JSON")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	dataset_path = Path(args.dataset)

	if args.show_profile:
		profile = build_dataset_profile(dataset_path=dataset_path, sample_rows=args.sample_rows, max_columns=args.max_columns)
		print(format_dataset_profile(profile))
		print()

	result = generate_use_case(
		domain=args.domain,
		department=args.department,
		dataset_path=dataset_path,
		sample_rows=args.sample_rows,
		max_columns=args.max_columns,
	)

	if args.json:
		print(json.dumps({"response_text": result["response_text"], "dataset_profile": result["dataset_profile"]}, indent=2, ensure_ascii=True, default=str))
	else:
		print(result["response_text"])


if __name__ == "__main__":
	main()
