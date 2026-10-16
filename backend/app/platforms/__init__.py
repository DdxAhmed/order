from app.platforms.catalog import (
    INVENTORY_PLATFORM_CODES,
    PLATFORM_BY_CODE,
    PLATFORM_CATALOG,
    SUPPORTED_PLATFORM_CODES,
    PlatformDefinition,
    is_supported_platform,
    platform_definition,
)
from app.platforms.steam import SteamMailAdapter

__all__ = [
    "INVENTORY_PLATFORM_CODES",
    "PLATFORM_BY_CODE",
    "PLATFORM_CATALOG",
    "SUPPORTED_PLATFORM_CODES",
    "PlatformDefinition",
    "SteamMailAdapter",
    "is_supported_platform",
    "platform_definition",
]
