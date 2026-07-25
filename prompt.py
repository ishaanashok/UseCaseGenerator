from __future__ import annotations

from typing import Any, Dict

from dataset_tool import format_dataset_profile


SYSTEM_INSTRUCTIONS = """You generate one practical business use case from a generic dataset.
Use the dataset summary and optional user context together. If the user gives a domain or department, prefer that context.
If the dataset points to a specific business function, anchor the idea there. Do not invent tables or fields that are not in the dataset.
Write a concise but actionable use case with implementation-friendly detail."""


def build_user_prompt(
	dataset_profile: Dict[str, Any],
	domain: str = "",
	department: str = "",
) -> str:
	context_lines = []
	context_lines.append(f"Domain: {domain or 'not provided'}")
	context_lines.append(f"Department: {department or 'not provided'}")
	context_lines.append("")
	context_lines.append("Dataset summary:")
	context_lines.append(format_dataset_profile(dataset_profile))
	context_lines.append("")
	context_lines.append("Dataset type:")
	context_lines.append(str(dataset_profile.get("dataset_kind", "unknown")))
	context_lines.append("")
	context_lines.append("Task:")
	context_lines.append("Generate exactly one use case that fits this dataset and user context.")
	context_lines.append("Return the result in this structure:")
	context_lines.append("- Title")
	context_lines.append("- Use case overview")
	context_lines.append("- Why this dataset fits")
	context_lines.append("- Suggested inputs")
	context_lines.append("- Suggested pipeline")
	context_lines.append("- Expected output")
	context_lines.append("- Business value")
	context_lines.append("- Risks or assumptions")
	context_lines.append("")
	context_lines.append("Keep it realistic, specific, and based on the actual dataset content.")
	return "\n".join(context_lines)
