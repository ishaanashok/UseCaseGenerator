from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from dataset_tool import DEFAULT_DATASET_PATH, build_dataset_profile, build_dataset_toolkit, suggest_use_case_angles
from prompt import SYSTEM_INSTRUCTIONS, build_user_prompt


def _coerce_response_text(content: Any) -> str:
	if content is None:
		return ""
	if isinstance(content, str):
		return content
	try:
		return json.dumps(content, indent=2, ensure_ascii=True, default=str)
	except Exception:
		return str(content)


def _load_local_env_file() -> None:
	path = Path(__file__).resolve().parent / ".env"
	if not path.exists():
		return

	for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		if key and value and key not in os.environ:
			os.environ[key] = value


def _load_environment() -> None:
	load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
	_load_local_env_file()


def build_use_case_agent(dataset_path: str | Path = DEFAULT_DATASET_PATH) -> Agent:
	_load_environment()

	api_key = os.getenv("API_KEY") or os.getenv("OPENROUTER_API_KEY")
	model_id = os.getenv("OPENROUTER_MODEL", "gpt-5.4-mini")
	model = OpenRouter(id=model_id, api_key=api_key, temperature=0.2)
	toolkit = build_dataset_toolkit(dataset_path)

	return Agent(
		name="use_case_generator",
		model=model,
		tools=[toolkit],
		instructions=SYSTEM_INSTRUCTIONS,
		markdown=True,
	)


def generate_use_case(
	domain: str = "",
	department: str = "",
	dataset_path: str | Path = DEFAULT_DATASET_PATH,
	sample_rows: int = 3,
	max_columns: int = 12,
) -> Dict[str, Any]:
	_load_environment()

	dataset_profile = build_dataset_profile(
		dataset_path=dataset_path,
		sample_rows=sample_rows,
		max_columns=max_columns,
	)

	api_key = os.getenv("API_KEY") or os.getenv("OPENROUTER_API_KEY")
	if not api_key:
		fallback_angles = suggest_use_case_angles(dataset_path=dataset_path, domain=domain, department=department)
		fallback_text = (
			"OpenRouter was skipped because no API key was available.\n\n"
			f"Suggested use-case angles: {', '.join(fallback_angles['suggested_angles'])}\n"
			"\nTo run the full generation path, set API_KEY in your environment or .env file."
		)
		return {
			"dataset_profile": dataset_profile,
			"prompt": build_user_prompt(dataset_profile=dataset_profile, domain=domain, department=department),
			"response": None,
			"response_text": fallback_text,
		}

	agent = build_use_case_agent(dataset_path=dataset_path)
	prompt = build_user_prompt(dataset_profile=dataset_profile, domain=domain, department=department)
	response = agent.run(prompt)

	return {
		"dataset_profile": dataset_profile,
		"prompt": prompt,
		"response": response,
		"response_text": _coerce_response_text(getattr(response, "content", None)),
	}
