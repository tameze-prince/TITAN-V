# TITAN V.

> Moteur « intention → réalité » modulaire : concevoir, valider, exploiter et faire évoluer des produits numériques grâce à une exécution multi-agents contrôlée.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Temporal](https://img.shields.io/badge/Temporal-000000?logo=temporal&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Phase actuelle

**TITAN Core : bootstrap du dépôt.** Le projet est construit comme un monolithe modulaire accompagné de workers isolés.
La spécification produit et d'architecture de référence (décisions, feuille de route, contrats) se trouve dans [`TITAN_Agent.md`](TITAN_Agent.md).

## Stack

| Domaine | Technologies |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Données | PostgreSQL, SQLAlchemy 2 (async), Alembic |
| Orchestration | Temporal (`workers/`) |
| IA et outillage | SDK OpenAI, Model Context Protocol (MCP) |
| Observabilité | OpenTelemetry |
| Qualité | pytest, Ruff, mypy |
| Conteneurs | Docker, Docker Compose |

## Structure

```
TITAN-V/
├── src/titan/        Cœur applicatif (monolithe modulaire)
├── workers/          Workers isolés
├── alembic/          Migrations de base de données
├── tests/            Tests
├── Dockerfile
├── docker-compose.yml
├── TITAN_Agent.md    Spécification maître
└── .env.example      Variables d'environnement
```

## Démarrage rapide

```bash
cp .env.example .env
docker compose up -d

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

## Qualité

```bash
ruff check .
mypy src
pytest
```

## Licence

[MIT](LICENSE) © ZEUFACK TAMEZE Prince