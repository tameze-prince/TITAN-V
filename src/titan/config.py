from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://titan:titan@localhost:5432/titan"
    temporal_target: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "titan-core"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "titan"
    otel_endpoint: str = "http://localhost:4317"
    model_provider: str = "local"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    openai_base_url: str | None = None
    agent_execution_timeout_seconds: int = 120
    general_agent_max_concurrency: int = 4
    engineering_agent_max_concurrency: int = 2
    sandbox_image: str = "python:3.13-slim"
    sandbox_network: str = "none"
    sandbox_memory: str = "512m"
    sandbox_cpus: str = "1.0"
    sandbox_pids_limit: int = 128
    sandbox_timeout_seconds: int = 60
    workspace_root: str = ".titan/workspaces"
    model_max_input_tokens: int = 64_000
    model_max_output_tokens: int = 16_000
    model_max_cost: float = 0.0
    orchestration_max_cost: float = 0.0
    recovery_auto_enabled: bool = False
    operator_auth_required: bool = False
    operator_auth_mode: str = "static"
    operator_api_token: str | None = None
    operator_subject: str = "local-development-operator"
    operator_role: str = "operator"
    oidc_issuer_url: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_roles_claim: str = "roles"
    oidc_admin_roles: str = "admin,titan-admin"
    oidc_operator_roles: str = "operator,titan-operator"
    oidc_viewer_roles: str = "viewer,titan-viewer"
    oidc_required_scope: str | None = None
    oidc_clock_skew_seconds: int = 30
    oidc_jwks_cache_seconds: int = 300
    oidc_request_timeout_seconds: float = 5.0
    oidc_require_https: bool = True
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_authorization_endpoint: str | None = None
    oidc_token_endpoint: str | None = None
    oidc_userinfo_endpoint: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_scopes: str = "openid profile email"
    operator_session_cookie_name: str = "titan_session"
    oidc_state_cookie_name: str = "titan_oidc_state"
    operator_session_ttl_seconds: int = 28_800
    operator_session_rotation_seconds: int = 3_600
    operator_session_cookie_secure: bool = True
    operator_session_cookie_samesite: str = "lax"
    oidc_auth_state_ttl_seconds: int = 600
    human_approval_timeout_seconds: int = 86_400
    resource_rbac_required: bool = False
    resource_rbac_admin_bypass: bool = True
    delegation_max_ttl_seconds: int = 86_400
    policy_escalation_enabled: bool = True
    recovery_max_attempts: int = 2
    recovery_min_autonomy_level: int = 3
    recovery_max_auto_risk_level: str = "R1"
    repair_max_attempts: int = 2
    quality_gate_min_score: float = 1.0
    quality_gate_evaluator_version: str = "1.0"
    quality_profile_name: str = "default-quality"
    quality_evaluator_kind: str = "RULE_BASED"
    quality_evaluator_model: str | None = None
    openai_input_cost_per_1k: float = 0.0
    openai_output_cost_per_1k: float = 0.0

    model_config = SettingsConfigDict(
        env_prefix="TITAN_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
