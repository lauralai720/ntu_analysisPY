from dataclasses import dataclass

from datetime import datetime
from typing import Callable, Optional, TypeVar, Generic
from components import Subjects


T = TypeVar("T")

class ResettableLazy(Generic[T]):
    # 所有 ResettableLazy 實例共用同一個重設時間
    reset_request_time: datetime | None = None
    
    def __init__(self, value_factory: Callable[[], T]):
        self._factory = value_factory
        self._last_reset_time: Optional[datetime] = datetime.now()
        self._cached_value: Optional[T] = None # impl
        self._has_value: bool = False

    @property
    def value(self) -> T:
        self._init()
        return self._cached_value
    
    @classmethod
    def request_reset(cls) -> None:
        cls.reset_request_time = datetime.now()

    def _init(self):
        needs_rebuild = (
            self._last_reset_time is None
            or not self._has_value
            or (
                ResettableLazy.reset_request_time is not None
                and self._last_reset_time < ResettableLazy.reset_request_time
            )
        )

        if needs_rebuild:
            self._cached_value = self._factory()
            self._has_value = True
            self._last_reset_time = datetime.now()


@dataclass
class Analysis:
    name : str = ""
    subjects : Subjects = None