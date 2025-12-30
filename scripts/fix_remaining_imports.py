"""
Fix remaining import issues after reorganization
"""
import os
import re
from pathlib import Path

REPLACEMENTS = [
    # Fix RAG imports
    (r'from rag import', 'from abby_core.rag import'),
    (r'import rag\.', 'import abby_core.rag.'),
    
    # Fix LLM imports  
    (r'from llm import', 'from abby_core.llm import'),
    (r'import llm\.', 'import abby_core.llm.'),
    
    # Fix Twitch imports (now in adapters)
    (r'from Twitch\.', 'from abby_adapters.discord.cogs.Twitch.'),
    (r'import Twitch\.', 'import abby_adapters.discord.cogs.Twitch.'),
    
    # Fix Twitter imports (now in adapters)
    (r'from Twitter\.', 'from abby_adapters.discord.cogs.Twitter.'),
    (r'import Twitter\.', 'import abby_adapters.discord.cogs.Twitter.'),
    
    # Fix utils.audio_layer imports
    (r'from utils import audio_layer', 'from abby_core.utils import audio_layer'),
    
    # Fix main imports (relative import in same package)
    (r'from main import Abby', 'from ...main import Abby'),
    
    # Fix incorrect sys.path manipulation for abby-core (should be abby_core)
    (r"sys\.path\.insert\(0, str\(Path\(__file__\)\.parent\.parent / 'abby-core'\)\)", 
     "# sys.path already configured in launch.py"),
]

def fix_file(file_path):
    """Apply replacements to a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for pattern, replacement in REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Updated {file_path}")
            return True
        return False
    except Exception as e:
        print(f"✗ Error processing {file_path}: {e}")
        return False

def main():
    """Fix all Python files in abby_adapters."""
    root = Path('abby_adapters')
    updated_count = 0
    
    for py_file in root.rglob('*.py'):
        if fix_file(py_file):
            updated_count += 1
    
    print(f"\nUpdated {updated_count} files")

if __name__ == '__main__':
    main()
