"""
File:           selector_parser.py
Description:    TODO
"""

from __future__ import annotations

from typing import Final

from conda_recipe_manager.parser._is_modifiable import IsModifiable
from conda_recipe_manager.parser.enums import LogicOp, Platform, SchemaVersion

# A selector is comprised of known operators and special types, or (in V0 recipes) arbitrary Python strings
SelectorValue = LogicOp | Platform | str


class SelectorNode:
    """
    Represents a node in a selector parse tree
    """

    def __init__(self, value: str):
        """
        Constructs a selector node
        :param value: Selector value stored in the node
        """

        # Enumerate special/known selector types
        def _init_value() -> SelectorValue:
            lower_val: Final[str] = value.lower()
            if lower_val in Platform:
                return Platform(lower_val)
            if lower_val in LogicOp:
                return LogicOp(lower_val)
            return value

        self._value: Final[SelectorValue] = _init_value()
        self._children: list[SelectorNode] = []

    def __str__(self) -> str:
        """
        Returns a debug string representation of a node
        :returns: Node's debug string
        """
        return f"Value: {self._value} | Children #: {len(self._children)}"

    def __repr__(self) -> str:
        """
        Returns a common string representation of a node
        :returns: Node's value
        """
        return str(self._value)

    def is_op(self) -> bool:
        """
        Indicates if the node represents an operation
        :returns: True if the node represents an operation
        """
        return self._value in LogicOp

    def is_platform(self) -> bool:
        """
        Indicates if the node represents a build platform
        :returns: True if the node represents a build platform
        """
        return self._value in Platform


class SelectorParser(IsModifiable):
    """
    Parses a selector statement
    """

    def _process_postfix_stack(stack: list[SelectorNode]) -> SelectorNode:
        """
        Recursively processes the postfix stack of nodes, building a tree
        :returns: Current node in the tree
        """
        cur = stack.pop()
        match cur._value:
            case LogicOp.NOT:
                cur._children = [SelectorParser._process_postfix_stack(stack)]
            case LogicOp.AND | LogicOp.OR:
                r = SelectorParser._process_postfix_stack(stack)
                l = SelectorParser._process_postfix_stack(stack)
                cur._children = [l, r]
        return cur

    def _parse_selector_tree(tokens: list[str]) -> SelectorNode:
        """
        Constructs a selector parse tree
        :param tokens: Selector tokens to process
        :returns: The root of the parse tree
        """

        # Shunting yard
        op_stack: list[SelectorNode] = []
        postfix_stack: list[SelectorNode] = []
        while tokens:
            node = SelectorNode(tokens.pop(0))
            if node.is_op():
                op_stack.append(node)
                continue
            postfix_stack.append(node)

        while op_stack:
            postfix_stack.append(op_stack.pop())

        root = SelectorParser._process_postfix_stack(postfix_stack)

        return root

    def __init__(self, content: str, schema_version: SchemaVersion):
        """
        Constructs and parses a selector string
        :param content: Selector string to parse
        :param schema_version: Schema the recipe uses
        """
        super().__init__()
        self._schema_version: Final[SchemaVersion] = schema_version

        # Sanitizes content string
        def _init_content() -> str:
            if self._schema_version == SchemaVersion.V0 and content and content[0] == "[" and content[-1] == "]":
                return content[1:-1]
            return content

        self._content: Final[str] = _init_content()

        self._root = SelectorParser._parse_selector_tree(self._content.split())

    def get_selected_platforms() -> set[Platform]:
        """
        Returns the set of platforms selected by this selector
        """
        # TODO complete
        return set()
