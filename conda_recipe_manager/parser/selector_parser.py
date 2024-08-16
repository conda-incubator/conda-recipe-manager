"""
:Description: Custom parser for selector recipe selector syntax. This parser does not evaluate Python code directly,
                and should therefore not be affected by the execution vulnerability in the V0 recipe format.
"""

from __future__ import annotations

from typing import Final, Optional

from conda_recipe_manager.parser._is_modifiable import IsModifiable
from conda_recipe_manager.parser.enums import ALL_LOGIC_OPS, LogicOp, SchemaVersion
from conda_recipe_manager.parser.platform_types import (
    ALL_ARCHITECTURES,
    ALL_OPERATING_SYSTEMS,
    ALL_PLATFORMS,
    Arch,
    OperatingSystem,
    Platform,
    PlatformQualifiers,
    get_platforms_by_arch,
    get_platforms_by_os,
)

# A selector is comprised of known operators and special types, or (in V0 recipes) arbitrary Python strings
SelectorValue = LogicOp | PlatformQualifiers | str


class _SelectorNode:
    """
    Represents a node in a selector parse tree. This class should not be used outside of this module.
    """

    def __init__(self, value: str):
        """
        Constructs a selector node
        :param value: Selector value stored in the node
        """

        # Enumerate special/known selector types
        def _init_value() -> SelectorValue:
            lower_val: Final[str] = value.lower()
            if lower_val in ALL_PLATFORMS:
                return Platform(lower_val)
            if lower_val in ALL_OPERATING_SYSTEMS:
                return OperatingSystem(lower_val)
            if lower_val in ALL_ARCHITECTURES:
                return Arch(lower_val)
            if lower_val in ALL_LOGIC_OPS:
                return LogicOp(lower_val)
            return value

        self.value: Final[SelectorValue] = _init_value()
        # Left and right nodes
        self.l_node: Optional[_SelectorNode] = None
        self.r_node: Optional[_SelectorNode] = None

    def __str__(self) -> str:
        """
        Returns a debug string representation of a sub-tree rooted at this node.
        :returns: Node's debug string
        """
        l_str: Final[str] = "" if self.l_node is None else f" L {self.l_node}"
        r_str: Final[str] = "" if self.r_node is None else f" R {self.r_node}"
        return f"{self.value}{l_str}{r_str}"

    def __repr__(self) -> str:
        """
        Returns a common string representation of a node
        :returns: Node's value
        """
        return str(self.value)

    def is_logical_op(self) -> bool:
        """
        Indicates if the node represents an operation
        :returns: True if the node represents an operation
        """
        return self.value in ALL_LOGIC_OPS


class SelectorParser(IsModifiable):
    """
    Parses a selector statement
    """

    @staticmethod
    def _process_postfix_stack(stack: list[_SelectorNode]) -> Optional[_SelectorNode]:
        """
        Recursively processes the postfix stack of nodes, building a tree
        :returns: Current node in the tree
        """
        if not stack:
            return None
        cur = stack.pop()
        match cur.value:
            case LogicOp.NOT:
                cur.l_node = SelectorParser._process_postfix_stack(stack)
            case LogicOp.AND | LogicOp.OR:
                cur.r_node = SelectorParser._process_postfix_stack(stack)
                cur.l_node = SelectorParser._process_postfix_stack(stack)
        return cur

    @staticmethod
    def _parse_selector_tree(tokens: list[str]) -> Optional[_SelectorNode]:
        """
        Constructs a selector parse tree
        :param tokens: Selector tokens to process
        :returns: The root of the parse tree
        """

        # Shunting yard
        op_stack: list[_SelectorNode] = []
        postfix_stack: list[_SelectorNode] = []
        while tokens:
            node = _SelectorNode(tokens.pop(0))
            if node.is_logical_op():
                # `NOT` has the highest precedence. For example:
                #   - `not osx and win` is interpreted as `(not osx) and win`
                #   - In Python, `not True or True` is interpreted as `(not True) or True`, returning `True`
                if node.value != LogicOp.NOT:
                    while op_stack and op_stack[-1].value == LogicOp.NOT:
                        postfix_stack.append(op_stack.pop())
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

    def __str__(self) -> str:
        """
        Returns a debug string representation of the parser.
        :returns: Parser's debug string
        """
        return f"Schema: V{self._schema_version} | Tree: {self._root}"

    def get_selected_platforms(self) -> set[Platform]:
        """
        Returns the set of platforms selected by this selector
        """

        # Recursive helper function that performs a post-order traversal
        def _eval_node(node: Optional[_SelectorNode]) -> set[Platform]:
            # Typeguard base-case
            if node is None:
                return set()

            match node.value:
                case Platform():
                    return {node.value}
                case Arch():
                    return get_platforms_by_arch(node.value)
                case OperatingSystem():
                    return get_platforms_by_os(node.value)
                case LogicOp():
                    match node.value:
                        case LogicOp.NOT:
                            return ALL_PLATFORMS - _eval_node(node.l_node)
                        case LogicOp.AND:
                            return _eval_node(node.l_node) & _eval_node(node.r_node)
                        case LogicOp.OR:
                            return _eval_node(node.l_node) | _eval_node(node.r_node)
                case _:
                    return set()

        return _eval_node(self._root)
