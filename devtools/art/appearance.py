"""Appearance-only import boundaries for the approved cosmetic derivatives.

Copyright 2026 Rusty Shackleford and nfx. SPDX-License-Identifier: AGPL-3.0-or-later.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import cast


def _numbers(value: object, size: int) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"expected {size} UV coordinates")
    values = cast(list[object], value)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError("UV coordinates must be numbers")
    result = [float(cast(float, v)) for v in values]
    if not all(math.isfinite(v) for v in result):
        raise ValueError("UV coordinates must be finite")
    return result


def uv_bounds(value: object) -> tuple[float, float, float, float]:
    """Return a face's UV bounds for either a cube or a polygon.

    requires: value is Blockbench cube UVs or a mesh corner-to-UV mapping.
    effects: returns ordered minimum/maximum texture coordinates without mutation.
    throws: ValueError for malformed, empty or nonfinite coordinates.
    """
    if isinstance(value, dict):
        if not value:
            raise ValueError("a face must have UV corners")
        points = [_numbers(v, 2) for v in cast(dict[str, object], value).values()]
        return (
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        )
    u, v, U, V = _numbers(value, 4)
    return min(u, U), min(v, V), max(u, U), max(v, V)


def shift_uv(
    value: object, du: float, dv: float
) -> list[float] | dict[str, list[float]]:
    """Translate UVs while preserving their orientation and vertex keys.

    requires: value satisfies uv_bounds; offsets are finite.
    effects: returns translated coordinates without modifying value.
    throws: ValueError for malformed input or nonfinite offsets.
    """
    uv_bounds(value)
    if not math.isfinite(du) or not math.isfinite(dv):
        raise ValueError("UV offsets must be finite")
    if isinstance(value, dict):
        result: dict[str, list[float]] = {}
        for key, point in cast(dict[str, object], value).items():
            u, v = _numbers(point, 2)
            result[key] = [round(u + du, 4), round(v + dv, 4)]
        return result
    u, v, U, V = _numbers(value, 4)
    return [round(u + du, 4), round(v + dv, 4), round(U + du, 4), round(V + dv, 4)]


def require_appearance_only(profile: Path, reference: Path) -> bytes:
    """Check the explicit import mode and the released gameplay contract.

    requires: paths point to the live and frozen released profile.
    effects: returns the live bytes; never writes either profile.
    throws: SystemExit for a wrong invocation or gameplay changes; OSError on unreadable files.
    """
    if sys.argv[1:] != ["--appearance-only"]:
        raise SystemExit(
            "Use --appearance-only. Cosmetic imports must not regenerate gameplay profiles."
        )
    before = profile.read_bytes()
    if json.loads(before) != json.loads(reference.read_bytes()):
        raise SystemExit(
            "Gameplay profile differs from the released contract; review it separately before importing art."
        )
    return before
