from temporalio.client import Client

from titan.config import settings


_client: Client | None = None


async def get_temporal_client() -> Client:
    global _client

    if _client is None:
        _client = await Client.connect(
            settings.temporal_target,
            namespace=settings.temporal_namespace,
        )

    return _client
