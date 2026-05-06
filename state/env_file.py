from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Quote the value if it contains anything that would confuse a naive parser.
# Whitespace, '#' (comment marker), or any of the shell-flavoured chars below.
_NEEDS_QUOTING = re.compile(r"[\s#\"'$`\\]")


def format_value(v: Any) -> str:
    """Convert a Python value into the string form for a `.env` file."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    if not s:
        return ""
    if _NEEDS_QUOTING.search(s):
        # Single-quote and escape inner single quotes.
        escaped = s.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return s


def update_env(env_path: Path, updates: dict[str, Any]) -> list[str]:
    """Update `.env` in place. Returns list of keys that were written.

    Preserves blank lines, comment lines, and any keys not in `updates`.
    Unknown-to-us keys are left alone, so plugin authors who hand-add env
    vars don't lose them when the user saves the Settings form.
    """
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        had_trailing_newline = text.endswith("\n")
    else:
        lines = []
        had_trailing_newline = True

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        eq = line.index("=")
        key = line[:eq].strip()
        if key in updates:
            new_lines.append(f"{key}={format_value(updates[key])}")
            seen.add(key)
        else:
            new_lines.append(line)

    # Append any updates whose key didn't appear in the existing file.
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={format_value(value)}")
            seen.add(key)

    body = "\n".join(new_lines)
    if (had_trailing_newline or new_lines) and not body.endswith("\n"):
        body += "\n"

    env_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(env_path)
    return list(updates.keys())
