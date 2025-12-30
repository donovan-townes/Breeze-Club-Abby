"""
Script to update all imports after reorganization.
Converts old import paths to new abby-core structure.
"""
import os
import re
from pathlib import Path

# Define replacement patterns
REPLACEMENTS = [
    # Utils imports
    (r'from utils\.', 'from abby_core.utils.'),
    (r'import utils\.', 'import abby_core.utils.'),
    
    # Economy imports  
    (r'from Exp\.xp_handler', 'from abby_core.economy.xp_handler'),
    (r'from Banking\.', 'from abby_core.economy.'),
    (r'import Exp\.xp_handler', 'import abby_core.economy.xp_handler'),
    
    # LLM imports
    (r'from abby-core\.llm', 'from abby_core.llm'),
    
    # RAG imports
    (r'from abby-core\.rag', 'from abby_core.rag'),
]

def update_file(filepath):
    """Update imports in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for pattern, replacement in REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
    return False

def main():
    """Update all Python files in adapter."""
    root = Path('abby-adapters/discord')
    if not root.exists():
        print("Error: abby-adapters/discord not found")
        return
    
    updated = []
    for pyfile in root.rglob('*.py'):
        if update_file(pyfile):
            updated.append(str(pyfile))
            print(f"✓ Updated {pyfile}")
    
    print(f"\nUpdated {len(updated)} files")
    
    # Also update core files that might have cross-references
    core_root = Path('abby-core')
    for pyfile in core_root.rglob('*.py'):
        if update_file(pyfile):
            print(f"✓ Updated {pyfile}")

if __name__ == '__main__':
    main()
