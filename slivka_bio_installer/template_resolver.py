import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ruamel.yaml import YAML

from .context_maps import Context


log = logging.getLogger(__name__)
PATTERN = re.compile(r'\{\{ *[\w\-]+:[\w\-/. ]+ *}}')


def resolve_str(template: str, context: Context):
    def resolver(m: re.Match):
        log.debug("Resolving match: %r", m)
        return context[m.group().lstrip(' {').rstrip(' }')]
    return PATTERN.sub(resolver, template)


def resolve_list(template: Sequence, context: Context):
    return [
        resolve_str(item, context) if isinstance(item, str) else
        resolve_list(item, context) if isinstance(item, Sequence) else
        resolve_map(item, context) if isinstance(item, Mapping) else
        item
        for item in template
    ]


def resolve_map(template: Mapping[str, Any], context: Context):
    return {
        key: (
            resolve_str(val, context) if isinstance(val, str) else
            resolve_list(val, context) if isinstance(val, Sequence) else
            resolve_map(val, context) if isinstance(val, Mapping) else
            val
        )
        for key, val in template.items()
    }
