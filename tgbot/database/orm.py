from contextlib import asynccontextmanager
import logging
from typing import (
    Any,
    AsyncGenerator,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar

from tgbot.database.database import Base
from .models import User


T = TypeVar("T", bound=Base)
session_context = ContextVar("session", default=None)


class CRUDBase(Generic[T]):
    """
    Base class for CRUD operations on database models.
    Provides common methods for creating, reading, updating, and deleting records.
    """

    def __init__(
        self,
        model: Type[T],
        session_factory: sessionmaker,
    ):
        """
        Initialize the CRUD repository with a model and session factory.

        Args:
            model: SQLAlchemy model class to operate on
            session_factory: Async session factory for database operations
        """
        self.model = model
        self.session_factory = session_factory

    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get the current session or create a new one.

        Yields:
            Active database session
        """
        existing_session = session_context.get()
        if existing_session is not None:
            yield existing_session
        else:
            async with self.session_factory() as session:
                token = session_context.set(session)
                try:
                    async with session.begin():
                        yield session
                finally:
                    session_context.reset(token)

    async def create(self, **kwargs) -> T:
        """
        Create a new record in the database.

        Args:
            **kwargs: Fields and values for the new record

        Returns:
            The created object instance
        """
        async with self._get_session() as session:
            obj = self.model(**kwargs)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            # This will ensure the object has all generated values (like id)

        return obj

    async def get(self, id: int) -> Optional[T]:
        """
        Retrieve a record by its ID.

        Args:
            id: The primary key of the record

        Returns:
            The found object or None if not found
        """
        async with self._get_session() as session:
            result = await session.get(self.model, id)
            logging.info(result)
            return result

    async def get_all(
        self, page: Optional[int] = None, size: Optional[int] = None, **kwargs
    ) -> List[T]:
        """
        Retrieve all records matching the given filters with pagination.

        Args:
            page: Page number for pagination (1-indexed)
            size: Number of records per page
            **kwargs: Fields and values to filter by

        Returns:
            List of matching objects
        """
        async with self._get_session() as session:
            filters = []
            for key, value in kwargs.items():
                if isinstance(value, (tuple, list)):
                    filters.append(getattr(self.model, key).in_(value))
                else:
                    filters.append(getattr(self.model, key) == value)

            query = (
                select(self.model).filter(and_(*filters)).order_by(desc(self.model.id))
            )

            if page is not None and size is not None and page > 0 and size > 0:
                query = query.offset((page - 1) * size).limit(size)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update a record by its ID.

        Args:
            id: The primary key of the record to update
            **kwargs: Fields and values to update

        Returns:
            The updated object or None if not found
        """
        async with self._get_session() as session:
            obj = await session.get(self.model, id)
            if not obj:
                return None

            for key, value in kwargs.items():
                setattr(obj, key, value)

            await session.flush()
            return obj

    async def update_all(
        self, filters: Dict[str, Any], values: Dict[str, Any]
    ) -> List[T]:
        """
        Update multiple records matching the given filters.

        Args:
            filters: Dictionary of field-value pairs to filter records
            values: Dictionary of field-value pairs to update

        Returns:
            List of updated objects
        """
        async with self._get_session() as session:
            query = select(self.model).filter_by(**filters)
            result = await session.execute(query)
            objs = list(result.scalars().all())

            for obj in objs:
                for key, value in values.items():
                    setattr(obj, key, value)

            await session.flush()
            return objs

    async def delete(self, id: int) -> bool:
        """
        Delete a record by its ID.

        Args:
            id: The primary key of the record to delete

        Returns:
            True if successful, False if record not found
        """
        async with self._get_session() as session:
            obj = await session.get(self.model, id)
            if not obj:
                return False

            await session.delete(obj)
            return True

    async def count(self, **kwargs) -> int:
        """
        Count records matching the given filters.

        Args:
            **kwargs: Fields and values to filter by

        Returns:
            Count of matching records
        """
        async with self._get_session() as session:
            query = select(func.count()).select_from(self.model)

            if kwargs:
                filters = []
                for key, value in kwargs.items():
                    if isinstance(value, (tuple, list)):
                        filters.append(getattr(self.model, key).in_(value))
                    else:
                        filters.append(getattr(self.model, key) == value)
                query = query.filter(and_(*filters))

            result = await session.execute(query)
            return result.scalar() or 0


class UsersRepo(CRUDBase["User"]):
    """
    Repository for user-related database operations.
    Extends the basic CRUD operations with user-specific functionality.
    """

    def __init__(self, session_factory: sessionmaker):
        """
        Initialize the users repository.

        Args:
            session_factory: Async session factory for database operations
        """
        super().__init__(User, session_factory)


class AsyncORM:
    """
    Static class to manage all repository instances.
    Provides centralized access to all database models.
    """

    _initialized: ClassVar[bool] = False

    _session_factory: sessionmaker = None

    # Repository instances
    users: UsersRepo = None

    @classmethod
    def set_session_factory(cls, session_factory: sessionmaker) -> None:
        """
        Set the session factory for all repositories.

        Args:
            session_factory: Async session factory for database operations
        """
        cls._session_factory = session_factory

    @classmethod
    def init_models(cls) -> None:
        """
        Initialize all repository instances.
        Must be called after set_session_factory.
        """
        if cls._session_factory is None:
            raise ValueError("Session factory not set. Call set_session_factory first.")

        cls.users = UsersRepo(cls._session_factory)

        cls._initialized = True

    @classmethod
    @asynccontextmanager
    async def transaction(cls) -> AsyncGenerator["AsyncORM", None]:
        """
        Creates transaction, that available for all repos
        """
        if not cls._initialized:
            raise RuntimeError(
                "AsyncORMWithTransactions not initialized. Call initialize() first."
            )

        existing_session = session_context.get()
        if existing_session is not None:
            yield cls
            return

        async with cls._session_factory() as session:
            token = session_context.set(session)
            try:
                async with session.begin():
                    yield cls
            finally:
                session_context.reset(token)
