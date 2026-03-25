# Testing Guide

## Running Tests

### Using Virtual Environment (Recommended)

Tests should be run using the .venv Python to ensure all dependencies are available:

```powershell
## Run all architecture/adapter/state tests
.\.venv\Scripts\python.exe -m pytest tests/test_architecture_compliance.py tests/test_adapter_contracts.py tests/test_state_management.py -v

## Run all tests in tests directory (PowerShell-compatible)
.\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short

## Run specific test file
.\.venv\Scripts\python.exe -m pytest tests/test_architecture_compliance.py -v

## Run specific test method
.\.venv\Scripts\python.exe -m pytest tests/test_adapter_contracts.py::TestDiscordAdapterContracts::test_discord_tool_implements_interfaces -v
```python

### Alternative: Activate .venv

```powershell
## Activate virtual environment
.\.venv\Scripts\Activate.ps1

## Then run pytest normally
python -m pytest tests/ -v

## Deactivate when done
deactivate
```python

## Test Dependencies

Install test dependencies in .venv:

```powershell
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
```python

Or install individually:

```powershell
.\.venv\Scripts\pip.exe install pytest pytest-asyncio pytest-anyio coloredlogs
```python

## Test Suite Structure

### test_architecture_compliance.py (5 tests)

- `test_no_forbidden_imports_in_core` - Validates core modules don't import Discord
- `test_core_services_layer_separation` - Services layer isolation
- `test_interfaces_are_abstract` - ABC usage verification
- `test_no_circular_imports` - Late import detection
- `test_linting_script_runs` - Programmatic lint execution

### test_adapter_contracts.py (13 tests)

- **Discord Adapter Contracts** (4 tests) - Interface implementations
- **Factory Registration** (4 tests) - ToolFactory & FormatterFactory
- **Interface Definitions** (2 tests) - ABC usage & abstract methods
- **BankCog Adapter** (3 tests) - Location, inheritance, commands

### test_state_management.py (10 tests)

- **Season State** (2 tests) - Structure & identifiers
- **System Configuration** (2 tests) - Config loading & MongoDB
- **Guild Configuration** (2 tests) - Structure & initialization
- **State Transitions** (2 tests) - Transition functions & system operations
- **Database Schemas** (2 tests) - Schema module & guild fields

## Test Results

Expected output (as of January 27, 2026):

```text
27 passed, 1 skipped, 48 warnings in 1.41s
```python

### Expected Skip

- `test_guild_schema_fields` - Skipped (uses dict schema, not class-based)

### Known Warnings

- Pydantic v1→v2 deprecation warnings (tdos_memory package)
- datetime.utcnow() deprecation warnings (to be fixed separately)

## Architecture Exceptions

### Allowed Late Imports with TODO

Files with TODO/FIXME comments can use late imports temporarily during refactoring:

```python
## TODO: Refactor to use service pattern
from abby_core.discord.adapters.delivery import send_announcement_to_guild
```python

The test suite checks up to 3 lines above each import for TODO/FIXME markers.

## Troubleshooting

### ModuleNotFoundError: No module named 'pytest'

Run tests with .venv Python: `.\.venv\Scripts\python.exe -m pytest ...`

### ModuleNotFoundError: No module named 'discord'

Install dependencies: `.\.venv\Scripts\pip.exe install -r requirements.txt`

### ModuleNotFoundError: No module named 'coloredlogs'

Install dev dependencies: `.\.venv\Scripts\pip.exe install -r requirements-dev.txt`

### Import errors from old test files

Some legacy test files have import errors and will be refactored later. Run only the new architecture test files:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_architecture_compliance.py tests/test_adapter_contracts.py tests/test_state_management.py -v
```python

Or exclude problematic files:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_memory_integration.py --ignore=tests/test_memory_unified.py -v
```python

## CI/CD Integration

For automated testing in CI/CD pipelines:

```yaml
## Example GitHub Actions workflow

- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt

- name: Run architecture tests
  run: python -m pytest tests/ -v --tb=short

- name: Verify zero architecture violations
  run: python scripts/lint_layers.py
```python

## Coverage Markers

Tests use custom pytest markers:

- `@pytest.mark.architecture` - Architecture compliance tests
- `@pytest.mark.adapters` - Adapter contract tests
- `@pytest.mark.state` - State management tests
- `@pytest.mark.integration` - Integration tests

Run specific marker:

```powershell
.\.venv\Scripts\python.exe -m pytest -m architecture -v
```python
