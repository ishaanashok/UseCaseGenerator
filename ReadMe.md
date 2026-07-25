## AI Use Case Generator

This project reads a generic tabular dataset, summarizes its structure, and uses Agno + OpenRouter to generate one practical business use case.

It now includes a very small web UI where you upload a file and optionally enter a domain. The app analyzes the uploaded dataset and returns one generated use case.

### What was created

- `dataset_tool.py` loads Excel, CSV, JSON, or SQLite sources, builds a compact dataset profile, formats that profile for prompting, and exposes those helpers as an Agno toolkit.
- `prompt.py` defines the agent instructions and the prompt template that combines dataset context with optional user inputs.
- `agent.py` builds the Agno agent and runs the generation pipeline.
- `app.py` is a small CLI entry point for running the pipeline.

### How to use it

1. Make sure `.env` contains `API_KEY` for OpenRouter.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the web app locally:

```bash
uvicorn app:app --reload
```

4. Open the local URL, upload a file, and optionally type a domain.

5. If you want the old CLI flow, run:

```bash
python app.py --domain finance --department accounts-payable --show-profile
```

6. If you want the output as JSON:

```bash
python app.py --domain finance --department procurement --json
```

### What the pipeline does

1. Reads the Excel workbook.
2. Summarizes sheet names, columns, row counts, and sample rows.
3. Combines that summary with the optional domain and department.
4. Sends the combined context to an Agno agent backed by Gemini.
5. Prints one tailored use case.

### Notes

- You can change the model with `OPENROUTER_MODEL` in `.env` if needed.
- You can point to a different data source with `--dataset path/to/file.xlsx`, `path/to/file.csv`, `path/to/file.json`, or `path/to/file.sqlite`.
- For Vercel, set `API_KEY` in the project environment variables and deploy this repo as a Python app. The root `app.py` exposes the FastAPI `app` entrypoint.
