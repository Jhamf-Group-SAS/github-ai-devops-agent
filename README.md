# GitHub AI DevOps Agent

Multi-tenant SaaS platform powered by a GitHub App and AI agents for automated auditing, fixing, testing, and deploying projects.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

API available at `http://localhost:8000`  
Docs at `http://localhost:8000/docs` (development mode only)

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

uvicorn api.main:app --reload
```

## Tests

```bash
pytest
```

## Architecture

See [GitHub_AI_DevOps_Agent_Master_Plan.md](./GitHub_AI_DevOps_Agent_Master_Plan.md) for the full roadmap.
