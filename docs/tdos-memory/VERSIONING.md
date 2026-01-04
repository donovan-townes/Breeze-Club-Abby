# TDOS Memory Versioning Strategy

This guide explains how to manage TDOS Memory versions as you update it alongside Abby development.

## Version Format

TDOS Memory uses **Semantic Versioning**: `MAJOR.MINOR.PATCH`

- **MAJOR** (1.x.x → 2.x.x): Breaking changes, API changes
- **MINOR** (1.0.x → 1.1.x): New features, backwards compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backwards compatible

**Current version:** `1.0.0` (see `tdos_memory/setup.py`)

## Publication Workflow

### Step 1: Update Version Numbers

Edit these files with your new version (e.g., `1.0.1`):

**File 1: `tdos_memory/setup.py`**

```python
setup(
    name="tdos-memory",
    version="1.0.1",  # ← Update here
    ...
)
```

**File 2: `tdos_memory/pyproject.toml`**

```toml
[project]
version = "1.0.1"  # ← Update here
```

### Step 2: Update Changelog

Edit `tdos_memory/docs/CHANGELOG.md`:

```markdown
## [1.0.1] - 2026-01-03

### Added

- New feature description
- Another new feature

### Fixed

- Bug fix description
- Another bug fix

### Changed

- Breaking API change (if any)

### Dependencies

- Updated dependency X to version Y

---

## [1.0.0] - 2026-01-01

Initial release...
```

### Step 3: Commit Changes

```bash
cd c:\Abby_Discord_Latest

git add tdos_memory/setup.py
git add tdos_memory/pyproject.toml
git add tdos_memory/docs/CHANGELOG.md
git commit -m "chore: bump TDOS Memory to v1.0.1"
```

### Step 4: Create Git Tag

```bash
# Tag for TDOS Memory publication
git tag tdos-memory-v1.0.1

# Push to GitHub
git push origin tdos-memory-v1.0.1
```

**Important:** Tag must follow pattern `tdos-memory-v*` for GitHub Actions to trigger.

### Step 5: Automatic PyPI Publishing

GitHub Actions workflow (`.github/workflows/publish-tdos-memory.yml`) will:

1. Detect the tag
2. Build the package
3. Upload to PyPI
4. Create a GitHub Release

**Status:** Check https://github.com/your-repo/actions to verify.

### Step 6: Update Abby Dependency

Once published to PyPI, update `requirements.txt`:

```diff
- tdos-memory>=1.0.0,<2.0.0
+ tdos-memory>=1.0.1,<2.0.0
```

Alternatively, for flexible minor updates:

```
tdos-memory>=1.0.1,<2.0.0   # Allows 1.0.1, 1.0.2, 1.1.0, etc.
tdos-memory~=1.0.1          # Same as above (shorthand)
tdos-memory==1.0.1          # Exact version (most restrictive)
```

**Recommendation:** Use `>=1.0.1,<2.0.0` to allow bug fixes automatically.

### Step 7: Test New Version

```bash
# Fresh environment
python -m venv test_env
test_env\Scripts\activate

# Install updated requirements
pip install -r requirements.txt

# Verify version
python -c "import tdos_memory; print(f'TDOS Memory {tdos_memory.__version__}')"

# Test Abby still works
python launch.py
```

## Versioning Scenarios

### Scenario 1: Bug Fix (PATCH release)

**When:** Fix a bug, don't change API

**Version bump:** `1.0.0` → `1.0.1`

**Example:**

```python
# Bug: Memory decay calculation was off by 1 day
# Fix: Correct the formula

# tdos_memory/setup.py
version="1.0.1"

# Commit
git tag tdos-memory-v1.0.1

# Update Abby
# requirements.txt: tdos-memory>=1.0.1,<2.0.0
```

### Scenario 2: New Feature (MINOR release)

**When:** Add new function, keep old ones unchanged

**Version bump:** `1.0.0` → `1.1.0`

**Example:**

```python
# New feature: add_memory_note() function for user annotations

# tdos_memory/setup.py
version="1.1.0"

# tdos_memory/docs/CHANGELOG.md
## [1.1.0] - 2026-01-04
### Added
- New add_memory_note() function for user annotations

# Commit
git tag tdos-memory-v1.1.0

# Update Abby
# requirements.txt: tdos-memory>=1.1.0,<2.0.0
```

### Scenario 3: Breaking Change (MAJOR release)

**When:** Change or remove an API that Abby code depends on

**Version bump:** `1.0.0` → `2.0.0`

**Important:** This is a significant event! Requires Abby code updates.

**Example:**

```python
# Breaking change: Rename get_memory_envelope() to get_user_envelope()

# tdos_memory/setup.py
version="2.0.0"

# tdos_memory/docs/CHANGELOG.md
## [2.0.0] - 2026-01-05
### Changed
- BREAKING: Renamed get_memory_envelope() to get_user_envelope()

# Commit
git tag tdos-memory-v2.0.0

# Update ALL Abby code that uses old function
# abby_adapters/discord/cogs/creative/chatbot.py
# - from tdos_memory import get_memory_envelope
# + from tdos_memory import get_user_envelope
# - envelope = get_memory_envelope(...)
# + envelope = get_user_envelope(...)

# Update Abby
# requirements.txt: tdos-memory>=2.0.0,<3.0.0
```

## Version Constraints in requirements.txt

Different ways to specify versions:

```ini
# Latest version (unsafe - could break)
tdos-memory

# Specific version (safe but can't get bug fixes)
tdos-memory==1.0.0

# Minimum version
tdos-memory>=1.0.0

# Range (allows minor/patch updates)
tdos-memory>=1.0.0,<2.0.0

# Shorthand for above
tdos-memory~=1.0.0

# Allow specific patch versions
tdos-memory>=1.0.1,<1.1.0
```

**Recommended for Abby:** `tdos-memory>=1.0.0,<2.0.0`

This allows automatic bug fix updates (1.0.1, 1.0.2) and new features (1.1.0) but prevents breaking changes.

## Release Checklist

Use this checklist for each TDOS Memory release:

- [ ] Code changes tested locally
- [ ] Update version in `setup.py`
- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Commit: `git commit -m "chore: bump to v1.0.1"`
- [ ] Tag: `git tag tdos-memory-v1.0.1`
- [ ] Push tag: `git push origin tdos-memory-v1.0.1`
- [ ] Verify GitHub Actions published to PyPI
- [ ] Verify package on https://pypi.org/project/tdos-memory/
- [ ] Update Abby's `requirements.txt`
- [ ] Test Abby with new version
- [ ] Document changes in INTEGRATION.md if major changes

## Troubleshooting

### GitHub Actions Failed to Publish

**Problem:** Tag pushed but package didn't appear on PyPI

**Solution:**

1. Check GitHub Actions log: https://github.com/your-repo/actions
2. Verify secret `PYPI_API_TOKEN` is set correctly
3. Try manual upload:
   ```bash
   cd tdos_memory
   python -m build
   twine upload dist/*
   ```

### Wrong Version Published

**Problem:** Uploaded 1.0.1 but older 1.0.0 is still showing as latest

**Solution:**

1. PyPI shows latest by upload time, not version number
2. You can't delete/re-upload same version
3. Solution: Release 1.0.2 with fixes

### Requirements.txt Still Uses Old Version

**Problem:** Ran `pip install -r requirements.txt` but got old version

**Solution:**

```bash
# Clear pip cache
pip cache purge

# Reinstall
pip install --upgrade -r requirements.txt

# Verify
python -c "import tdos_memory; print(tdos_memory.__version__)"
```

## Communication with Contributors

When releasing a new TDOS Memory version:

**For PATCH/MINOR releases (backwards compatible):**

- Update `requirements.txt` directly
- Contributors auto-get new version next `pip install -r requirements.txt`
- No code changes needed

**For MAJOR releases (breaking changes):**

- Create GitHub issue explaining changes
- Link to migration guide
- Require code updates in Abby before upgrade
- Example message:

````markdown
## TDOS Memory v2.0.0 Released 🎉

This release includes breaking changes. See [migration guide](docs/tdos-memory/INTEGRATION.md).

**Required action:**
Update your code:

```python
- from tdos_memory import get_memory_envelope
+ from tdos_memory import get_user_envelope
```
````

```

## Resources

- [Semantic Versioning](https://semver.org/)
- [PEP 440 - Python Versioning](https://peps.python.org/pep-0440/)
- [PyPI Package Versioning](https://packaging.python.org/specifications/version-specifiers/)

---

**Keep versions synchronized!** Abby's version should track TDOS Memory updates so contributors have a smooth experience.
```
