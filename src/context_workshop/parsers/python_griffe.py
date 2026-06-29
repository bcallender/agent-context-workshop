"""Python symbol extraction — Griffe-backed, emits unified Symbol rows.

Ported from the original dict-returning python_symbols.py. Now emits Symbol
objects (Task 1 contract) instead of plain dicts, and resolves re-exports via
griffe.Alias so canonical definition paths are available (Rung 1).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import griffe

from context_workshop.parsers.schema import Symbol


def load_python_package(
    package: str,
    *,
    search_paths: Iterable[str | Path] | None = None,
    resolve: bool = True,
) -> griffe.Module:
    """Load a package with Griffe; resolve aliases so re-exports carry targets."""
    loader = griffe.GriffeLoader(search_paths=[str(p) for p in search_paths or []])
    module = loader.load(package)
    if resolve:
        loader.resolve_aliases(implicit=False, external=False)
    return module


def extract_python_symbols(
    module: griffe.Module,
    *,
    parent_path: str = "",
    public_only: bool = False,
) -> list[Symbol]:
    """Extract module/class/function/method/attribute rows from a Griffe module tree."""
    elements: list[Symbol] = []
    current_path = f"{parent_path}.{module.name}" if parent_path else module.name

    def include(member: Any) -> bool:
        return not public_only or bool(getattr(member, "is_public", False))

    if include(module):
        elements.append(
            Symbol(
                language="python",
                extractor="griffe",
                rung="resolution",
                kind="module",
                name=module.name,
                qualified_name=current_path,
                docstring=module.docstring.value if module.docstring else None,
                filepath=str(module.filepath) if module.filepath else None,
                is_public=module.is_public,
                line_start=module.lineno,
                line_end=module.endlineno,
                visibility=None,
                is_reexport=False,
                exported_path=current_path,
                canonical_path=current_path,
            )
        )

    for member in module.members.values():
        if isinstance(member, griffe.Module):
            elements.extend(
                extract_python_symbols(member, parent_path=current_path, public_only=public_only)
            )
        elif isinstance(member, griffe.Class):
            if include(member):
                elements.append(
                    Symbol(
                        language="python",
                        extractor="griffe",
                        rung="resolution",
                        kind="class",
                        name=member.name,
                        qualified_name=f"{current_path}.{member.name}",
                        docstring=member.docstring.value if member.docstring else None,
                        filepath=str(member.filepath)
                        if getattr(member, "filepath", None)
                        else None,
                        bases=[str(base) for base in member.bases],
                        is_public=member.is_public,
                        line_start=member.lineno,
                        line_end=member.endlineno,
                        visibility=None,
                        is_reexport=False,
                        exported_path=f"{current_path}.{member.name}",
                        canonical_path=f"{current_path}.{member.name}",
                    )
                )
            for child in member.members.values():
                if isinstance(child, griffe.Function) and include(child):
                    elements.append(
                        Symbol(
                            language="python",
                            extractor="griffe",
                            rung="resolution",
                            kind="method",
                            name=child.name,
                            qualified_name=f"{current_path}.{member.name}.{child.name}",
                            parent=member.name,
                            docstring=child.docstring.value if child.docstring else None,
                            filepath=str(child.filepath)
                            if getattr(child, "filepath", None)
                            else None,
                            is_public=child.is_public,
                            parameters=[param.name for param in child.parameters],
                            signature=str(child.returns) if child.returns else None,
                            line_start=child.lineno,
                            line_end=child.endlineno,
                            visibility=None,
                            is_reexport=False,
                            exported_path=f"{current_path}.{member.name}.{child.name}",
                            canonical_path=f"{current_path}.{member.name}.{child.name}",
                        )
                    )
        elif isinstance(member, griffe.Function):
            if include(member):
                elements.append(
                    Symbol(
                        language="python",
                        extractor="griffe",
                        rung="resolution",
                        kind="function",
                        name=member.name,
                        qualified_name=f"{current_path}.{member.name}",
                        docstring=member.docstring.value if member.docstring else None,
                        filepath=str(member.filepath)
                        if getattr(member, "filepath", None)
                        else None,
                        is_public=member.is_public,
                        parameters=[param.name for param in member.parameters],
                        signature=str(member.returns) if member.returns else None,
                        line_start=member.lineno,
                        line_end=member.endlineno,
                        visibility=None,
                        is_reexport=False,
                        exported_path=f"{current_path}.{member.name}",
                        canonical_path=f"{current_path}.{member.name}",
                    )
                )
        elif isinstance(member, griffe.Attribute):
            if include(member):
                elements.append(
                    Symbol(
                        language="python",
                        extractor="griffe",
                        rung="resolution",
                        kind="attribute",
                        name=member.name,
                        qualified_name=f"{current_path}.{member.name}",
                        docstring=member.docstring.value if member.docstring else None,
                        filepath=str(member.filepath)
                        if getattr(member, "filepath", None)
                        else None,
                        is_public=member.is_public,
                        line_start=member.lineno,
                        line_end=member.endlineno,
                        visibility=None,
                        is_reexport=False,
                        exported_path=f"{current_path}.{member.name}",
                        canonical_path=f"{current_path}.{member.name}",
                    )
                )
        elif isinstance(member, griffe.Alias):
            if include(member):
                target_path = getattr(member, "target_path", None)
                canonical, t_file, t_l0, t_l1 = target_path, None, None, None
                try:
                    t = member.final_target
                    canonical = t.canonical_path
                    t_file = str(t.filepath) if getattr(t, "filepath", None) else None
                    t_l0, t_l1 = t.lineno, t.endlineno
                except Exception:
                    canonical = None  # unresolvable alias: honest about failure
                elements.append(
                    Symbol(
                        language="python",
                        extractor="griffe",
                        rung="resolution",
                        kind="reexport",
                        name=member.name,
                        qualified_name=f"{current_path}.{member.name}",
                        is_reexport=True,
                        exported_path=f"{current_path}.{member.name}",
                        canonical_path=canonical,
                        filepath=t_file,
                        line_start=t_l0,
                        line_end=t_l1,
                        is_public=bool(getattr(member, "is_public", False)),
                    )
                )

    return elements
