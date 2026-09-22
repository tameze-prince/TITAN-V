from titan.persistence import models
from titan.persistence.base import Base


def test_core_tables_are_registered() -> None:
    expected = {
        "agents",
        "projects",
        "tasks",
        "task_dependencies",
        "workflows",
        "artifacts",
        "events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_project_autonomy_constraint_exists() -> None:
    constraints = {constraint.name for constraint in models.ProjectModel.__table__.constraints}
    assert "ck_projects_autonomy_level_range" in constraints or "autonomy_level_range" in constraints
