from fastapi import FastAPI
from pydantic import BaseModel

from titan import __version__


class ProjectCreate(BaseModel):
    name: str


app = FastAPI(title="TITAN V.", version=__version__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/api/v1/projects", status_code=201)
async def create_project(payload: ProjectCreate) -> dict[str, str]:
    # Persistence is intentionally introduced in the next bootstrap step.
    return {"id": "pending", "name": payload.name}
