"""
File:           types.py
Description:    Provides public types, type aliases, constants, and small classes used by all percy modules.
"""
from __future__ import annotations

from typing import Final, Hashable, TypeVar, Union

# Base types that can store value
Primitives = Union[str, int, float, bool, None]
# Same primitives, as a tuple. Used with `isinstance()`
PRIMITIVES_TUPLE: Final[tuple[type[str], type[int], type[float], type[bool], type[None]]] = (
    str,
    int,
    float,
    bool,
    type(None),
)

# Type that represents a JSON-like type
JsonType = Union[dict[str, "JsonType"], list["JsonType"], Primitives]

# Type that represents a JSON patch payload
JsonPatchType = dict[str, JsonType]

# Types that build up to types used in `jsonschema`s
SchemaPrimitives = Union[str, int, bool, None]
SchemaDetails = Union[dict[str, "SchemaDetails"], list["SchemaDetails"], SchemaPrimitives]
# Type for a schema object used by the `jsonschema` library
SchemaType = dict[str, SchemaDetails]

# Generic, hashable type
H = TypeVar("H", bound=Hashable)


# All sentinel values used in this module should be constructed with this class, for typing purposes.
class SentinelType:
    pass
