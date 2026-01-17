"""Diagnostic messages for the text-to-blocks converter.

This module provides error and warning reporting during conversion,
tracking issues like unknown blocks, undefined variables, and unclosed C blocks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DiagnosticLevel(Enum):
    """Severity level for diagnostic messages."""
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


@dataclass
class Diagnostic:
    """A single diagnostic message."""
    level: DiagnosticLevel
    message: str
    sprite: str
    line: Optional[int] = None
    line_text: Optional[str] = None

    def __str__(self) -> str:
        loc = f"Sprite '{self.sprite}'"
        if self.line is not None:
            loc += f" Line {self.line}"
        result = f"{self.level.value}: {self.message}: {loc}"
        if self.line_text:
            result += f"\n  -> {self.line_text}"
        return result


@dataclass
class DiagnosticContext:
    """Context for collecting diagnostics during conversion."""
    sprite_name: str = "Stage"
    current_line: Optional[int] = None
    current_line_text: Optional[str] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)

    def set_location(self, line_number: Optional[int], line_text: Optional[str] = None) -> None:
        """Set the current line context for subsequent diagnostics."""
        self.current_line = line_number
        self.current_line_text = line_text

    def add(
        self,
        level: DiagnosticLevel,
        message: str,
        line: Optional[int] = None,
        line_text: Optional[str] = None,
    ) -> None:
        """Add a diagnostic message."""
        self.diagnostics.append(Diagnostic(
            level=level,
            message=message,
            sprite=self.sprite_name,
            line=line if line is not None else self.current_line,
            line_text=line_text if line_text is not None else self.current_line_text,
        ))

    def error(self, message: str, line: Optional[int] = None, line_text: Optional[str] = None) -> None:
        """Add an error diagnostic."""
        self.add(DiagnosticLevel.ERROR, message, line, line_text)

    def warning(self, message: str, line: Optional[int] = None, line_text: Optional[str] = None) -> None:
        """Add a warning diagnostic."""
        self.add(DiagnosticLevel.WARNING, message, line, line_text)

    def info(self, message: str, line: Optional[int] = None, line_text: Optional[str] = None) -> None:
        """Add an info diagnostic."""
        self.add(DiagnosticLevel.INFO, message, line, line_text)

    def has_errors(self) -> bool:
        """Check if any error diagnostics have been recorded."""
        return any(d.level == DiagnosticLevel.ERROR for d in self.diagnostics)

    def has_warnings(self) -> bool:
        """Check if any warning diagnostics have been recorded."""
        return any(d.level == DiagnosticLevel.WARNING for d in self.diagnostics)

    def get_errors(self) -> List[Diagnostic]:
        """Get all error diagnostics."""
        return [d for d in self.diagnostics if d.level == DiagnosticLevel.ERROR]

    def get_warnings(self) -> List[Diagnostic]:
        """Get all warning diagnostics."""
        return [d for d in self.diagnostics if d.level == DiagnosticLevel.WARNING]

    def clear(self) -> None:
        """Clear all diagnostics."""
        self.diagnostics.clear()

    def print_all(self) -> None:
        """Print all diagnostics to stdout."""
        for diag in self.diagnostics:
            print(diag)

    def summary(self) -> str:
        """Return a summary of diagnostics."""
        errors = len(self.get_errors())
        warnings = len(self.get_warnings())
        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        return ", ".join(parts) if parts else "No issues"


class DiagnosticCollector:
    """Global collector for diagnostics across multiple sprites."""
    
    def __init__(self) -> None:
        self.all_diagnostics: List[Diagnostic] = []

    def add_context_diagnostics(self, ctx: DiagnosticContext) -> None:
        """Add all diagnostics from a context."""
        self.all_diagnostics.extend(ctx.diagnostics)

    def has_errors(self) -> bool:
        """Check if any error diagnostics have been recorded."""
        return any(d.level == DiagnosticLevel.ERROR for d in self.all_diagnostics)

    def has_warnings(self) -> bool:
        """Check if any warning diagnostics have been recorded."""
        return any(d.level == DiagnosticLevel.WARNING for d in self.all_diagnostics)

    def print_all(self) -> None:
        """Print all diagnostics to stdout."""
        for diag in self.all_diagnostics:
            print(diag)

    def summary(self) -> str:
        """Return a summary of diagnostics."""
        errors = sum(1 for d in self.all_diagnostics if d.level == DiagnosticLevel.ERROR)
        warnings = sum(1 for d in self.all_diagnostics if d.level == DiagnosticLevel.WARNING)
        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        return ", ".join(parts) if parts else "No issues"
