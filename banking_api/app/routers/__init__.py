"""Routers package."""

from app.routers.accounts import router as accounts_router
from app.routers.auth import router as auth_router
from app.routers.transactions import router as transactions_router

__all__ = [
    "auth_router",
    "accounts_router",
    "transactions_router",
]
