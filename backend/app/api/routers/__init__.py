from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.accounts import router as accounts_router
from app.api.routers.audit import router as audit_router
from app.api.routers.auth import router as auth_router
from app.api.routers.customer import router as customer_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.import_csv import router as import_router
from app.api.routers.mailboxes import router as mailboxes_router
from app.api.routers.orders import router as orders_router
from app.api.routers.platforms import router as platforms_router
from app.api.routers.salla_admin import router as salla_admin_router
from app.api.routers.salla_public import router as salla_public_router
from app.api.routers.customers import router as customers_router

api_router = APIRouter(prefix="/api/v1")

# Admin routers
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(accounts_router)
api_router.include_router(orders_router)
api_router.include_router(customers_router)
api_router.include_router(mailboxes_router)
api_router.include_router(platforms_router)
api_router.include_router(import_router)
api_router.include_router(salla_admin_router)
api_router.include_router(audit_router)

# Customer & public routers
api_router.include_router(customer_router)
api_router.include_router(salla_public_router)
