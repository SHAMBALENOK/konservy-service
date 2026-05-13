"""
Generic repository pattern for database operations.
Provides base CRUD operations with async SQLAlchemy 2.0.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing base CRUD operations.
    
    All methods are async and use SQLAlchemy 2.0 syntax.
    """

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get a single record by internal ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_uuid(
        self, uuid_field_name: str = "account_id", **kwargs: Any
    ) -> ModelType | None:
        """Get a single record by UUID field."""
        filters = {getattr(self.model, uuid_field_name): kwargs.get(uuid_field_name)}
        result = await self.session.execute(
            select(self.model).filter_by(**filters)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any | None = None,
    ) -> list[ModelType]:
        """Get all records with pagination."""
        query = select(self.model).offset(skip).limit(limit)

        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.id.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count total records with optional filters."""
        query = select(func.count()).select_from(self.model)

        if filters:
            query = query.filter_by(**filters)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def create(self, attributes: dict[str, Any]) -> ModelType:
        """Create a new record."""
        obj = self.model(**attributes)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(
        self,
        db_obj: ModelType,
        attributes: dict[str, Any],
    ) -> ModelType:
        """Update an existing record."""
        for field, value in attributes.items():
            if hasattr(db_obj, field) and value is not None:
                setattr(db_obj, field, value)

        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj: ModelType) -> None:
        """Delete a record."""
        await self.session.delete(db_obj)
        await self.session.flush()

    async def exists(self, filters: dict[str, Any]) -> bool:
        """Check if record exists with given filters."""
        query = select(self.model).filter_by(**filters)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def find_one(self, filters: dict[str, Any]) -> ModelType | None:
        """Find a single record by filters."""
        query = select(self.model).filter_by(**filters)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_many(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Find multiple records by filters with pagination."""
        query = select(self.model)

        if filters:
            query = query.filter_by(**filters)

        query = query.offset(skip).limit(limit).order_by(self.model.id.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
