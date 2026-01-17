"""ParsedNode class for representing parsed Scratch blocks."""

from typing import Any, Dict, List, Optional


class ParsedNode:
    """Represents a parsed Scratch block before emission to JSON."""

    def __init__(
        self,
        opcode: str,
        inputs: Optional[Dict[str, Any]] = None,
        fields: Optional[Dict[str, Any]] = None,
        mutation: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.opcode = opcode
        self.inputs = inputs or {}
        self.fields = fields or {}
        self.mutation = mutation or {}
        self.children: List[ParsedNode] = []
        self.children2: List[ParsedNode] = []
        self.procedure_info: Optional[Dict[str, Any]] = None
