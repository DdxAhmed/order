"""Safe platform catalog used by inventory management and UI selectors.

Ubisoft and Rockstar are intentionally inventory-only in this release.  The
catalog does not declare an email adapter and must never be used to parse or
deliver authentication material.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlatformDefinition:
    code: str
    label: str
    inventory_management: bool = True
    legacy_customer_access: bool = False
    email_metadata_only: bool = True


PLATFORM_CATALOG: tuple[PlatformDefinition, ...] = (
    PlatformDefinition("steam", "Steam", legacy_customer_access=True),
    PlatformDefinition("ubisoft", "Ubisoft"),
    PlatformDefinition("rockstar", "Rockstar Games"),
)

PLATFORM_BY_CODE = {item.code: item for item in PLATFORM_CATALOG}
SUPPORTED_PLATFORM_CODES = frozenset(PLATFORM_BY_CODE)
INVENTORY_PLATFORM_CODES = frozenset(
    item.code for item in PLATFORM_CATALOG if item.inventory_management
)


def platform_definition(code: str) -> PlatformDefinition | None:
    return PLATFORM_BY_CODE.get(code.strip().casefold())


def is_supported_platform(code: str) -> bool:
    return platform_definition(code) is not None

