from typing import Optional
from loguru import logger

async def try_register_with_lds(server, lds_endpoint: Optional[str]):
    """Best-effort: registra no LDS se um endpoint for informado.
    Em muitos ambientes, não há LDS; então apenas loga caso falhe.
    """
    if not lds_endpoint:
        logger.info("LDS: endpoint não informado; ignorando registro.")
        return
    try:
        await server.register_to_discovery(lds_endpoint)
        logger.info("LDS: registro solicitado em {}", lds_endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LDS: falha ao registrar: {}", exc)