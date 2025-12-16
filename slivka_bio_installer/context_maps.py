import logging
from collections.abc import Mapping, Iterable
from typing import Protocol, Any


log = logging.getLogger(__name__)


class Context(Protocol):
    def __getitem__(self: 'Context', key: str) -> Any: ...


class ChainContextMap(Context):
    def __init__(self, *contexts: Context):
        self._contexts = list(contexts)

    def __getitem__(self, item):
        log.debug("Accessing key: '%s'", item)
        for context in self._contexts:
            log.debug("Trying %s", context)
            try:
                value = context[item]
                log.debug("Found ChainContextMap[%s] = %s", item, value)
                return value
            except KeyError:
                pass
        else:
            raise KeyError(item)

    def prepend(self, context):
        self._contexts.insert(0, context)

    def append(self, context):
        self._contexts.append(context)


class SimpleContextMap(Context):
    def __init__(
            self,
            mapping: Iterable[tuple[str, Any]],
            prefix: str = None
    ):
        if prefix is not None:
            self._mapping = {
                f"{prefix}:{key}": val for key, val in mapping
            }
        else:
            self._mapping = dict(mapping)

    def __getitem__(self, item: str):
        return self._mapping[item]

    def __repr__(self):
        return str(self._mapping)
