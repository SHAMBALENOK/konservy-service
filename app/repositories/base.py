from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: int) -> Optional[T]:
        pass

    @abstractmethod
    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[T]:
        pass

    @abstractmethod
    async def create(self, obj_in: dict) -> T:
        pass

    @abstractmethod
    async def update(self, id: int, obj_in: dict) -> Optional[T]:
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass