"""Registry for explicitly implemented, non-sensitive merchant services.

An empty registry is intentional. A database `service_key` alone is not a
service implementation and must never grant access to authentication codes,
credentials, or any other sensitive material.
"""

from __future__ import annotations


def registered_service_keys() -> tuple[str, ...]:
    """Return production-ready service keys with a reviewed handler.

    No such handler exists in this application at present.
    """
    return ()


def is_registered_non_sensitive_service(service_key: str) -> bool:
    return service_key in registered_service_keys()
