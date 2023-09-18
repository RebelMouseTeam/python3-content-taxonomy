from abc import ABCMeta
from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic
from typing import Iterable
from typing import Iterator
from typing import TypeVar

Case = TypeVar('Case')
Scalar = TypeVar('Scalar')
Filter = TypeVar('Filter')


@dataclass(frozen=True)
class Operator(Generic[Case], metaclass=ABCMeta):
    pass


@dataclass(frozen=True)
class Argument(Generic[Scalar], metaclass=ABCMeta):
    pass


@dataclass(frozen=True)
class Reference:
    alias: str


class IResolver(metaclass=ABCMeta):
    @abstractmethod
    def dereference_filters(self, operators_: Iterable['Operator[Filter]'], arguments_: 'IResolver.IArguments') -> Iterator[Filter]:
        pass

    class IArguments(metaclass=ABCMeta):
        @abstractmethod
        def get_argument(self, alias: str) -> 'Argument':
            pass

        @abstractmethod
        def get_value(self, alias: str, index: int) -> Scalar:
            pass
