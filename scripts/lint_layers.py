#!/usr/bin/env python3
"""Enforce architecture layer boundaries.

Checks:
- No discord imports in core/{services,economy,llm,personality,rag,system}
- No adapter imports in core/
- No sys.path hacks in core
"""

import re
import sys
from pathlib import Path

CORE_MODULES = [
    "services", "economy", "llm", "personality", "rag", "system",
    "interfaces", "config", "database", "observability"
]

FORBIDDEN_IMPORTS_IN_CORE = [
    r"import discord",
    r"from discord",
    r"from abby_core\.discord",
    r"from fastapi",
    r"from click",
    r"from slack_sdk",
]

FORBIDDEN_PATTERNS = [
    r"sys\.path\.insert",
    r"sys\.path\.append",
]

def lint_file(path: Path) -> list:
    """Check a file for violations. Returns list of error messages."""
    errors = []
    
    # Exclude cogs/, adapters/, core/ - they're allowed to import discord
    # Also exclude discord/config.py (platform initialization)
    path_str = str(path).replace("\\", "/")
    if ("/discord/cogs/" in path_str or "/discord/adapters/" in path_str or 
        "/discord/core/" in path_str or path_str.endswith("/discord/config.py")):
        return errors
    
    # Check if file is in a core module
    parts = path.parts
    is_in_core = any(p == "abby_core" for p in parts) and any(
        m in str(path) for m in CORE_MODULES
    )
    
    if not is_in_core:
        return errors
    
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return [f"{path}: Failed to read: {e}"]
    
    lines = content.split("\n")
    
    for i, line in enumerate(lines, start=1):
        # Skip comments
        if line.strip().startswith("#"):
            continue
        
        # Allow late imports with TODO/FIXME comment above (temporary exception for refactoring)
        has_todo_exception = False
        if i > 1:
            # Check up to 3 lines above for TODO or FIXME
            for check_idx in range(max(0, i - 4), i):
                if "TODO" in lines[check_idx] or "FIXME" in lines[check_idx]:
                    has_todo_exception = True
                    break
        
        if has_todo_exception:
            continue
        
        # Check forbidden imports
        for pattern in FORBIDDEN_IMPORTS_IN_CORE:
            if re.search(pattern, line):
                errors.append(
                    f"{path}:{i}: Forbidden import in core module: {line.strip()}"
                )
        
        # Check sys.path hacks
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                errors.append(
                    f"{path}:{i}: sys.path manipulation in core: {line.strip()}"
                )
    
    return errors

def main():
    """Lint all Python files in abby_core."""
    root = Path("abby_core")
    errors = []
    
    for py_file in root.rglob("*.py"):
        errors.extend(lint_file(py_file))
    
    if errors:
        print("❌ Architecture violations found:\n")
        for error in errors:
            print(f"  {error}")
        return 1
    else:
        print("✅ No architecture violations")
        return 0

if __name__ == "__main__":
    sys.exit(main())
