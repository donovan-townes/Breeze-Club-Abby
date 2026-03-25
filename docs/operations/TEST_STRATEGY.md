# Test Strategy and Infrastructure

Comprehensive testing approach for Abby: unit vs. integration tests, fixtures, markers, CI/CD integration, and test quality maintenance for 50-year deployments.

**Last Updated:** January 31, 2026  
**Framework:** pytest with async support  
**Coverage Target:** 70%+ (critical paths 90%+)  
**CI/CD:** GitHub Actions (on every PR)

---

## Executive Summary

Abby implements **three-layer testing** for 50-year reliability:

1. **Unit Tests** — Test logic in isolation (mock all I/O)
2. **Integration Tests** — Test component interaction (use test database)
3. **Contract Tests** — Validate adapter implementations match interfaces

---

## Test Environment Setup

### Install Dependencies

```bash
## Add to requirements-dev.txt
pytest==7.4.0
pytest-asyncio==0.21.0
mongomock==4.1.2
python-dotenv==1.0.0
```python

### Run Tests

```bash
## Run all tests
pytest tests/ -v

## Run specific test file
pytest tests/test_state_management.py -v

## Run specific test by name
pytest tests/test_metrics_service.py::test_record_transition -v

## Run with coverage
pytest tests/ --cov=abby_core --cov-report=html
```python

---

## Test Markers

Tests are categorized with pytest markers for selective execution:

```python
import pytest

@pytest.mark.architecture
def test_platform_state_schema():
    """Architecture tests validate domain models."""
    pass

@pytest.mark.adapters
def test_discord_adapter_contracts():
    """Adapter tests validate platform-specific implementations."""
    pass

@pytest.mark.state
def test_state_transition_valid():
    """State tests validate FSM logic."""
    pass

@pytest.mark.integration
def test_end_to_end_conversation():
    """Integration tests validate full workflows."""
    pass
```python

### Run by Marker

```bash
## Run only architecture tests
pytest -m architecture -v

## Run all except integration tests (fast feedback)
pytest -m "not integration" -v

## Run integration tests only (slow, scheduled in CI)
pytest -m integration -v
```python

### Marker Definitions

```python
## tests/conftest.py
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "architecture: tests for core architecture"
    )
    config.addinivalue_line(
        "markers", "adapters: tests for platform adapters"
    )
    config.addinivalue_line(
        "markers", "state: tests for state management"
    )
    config.addinivalue_line(
        "markers", "integration: end-to-end tests"
    )
```python

---

## Fixtures

Reusable test infrastructure:

```python
## tests/conftest.py
import pytest
from mongomock import MongoClient
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_db():
    """Provide in-memory MongoDB for tests."""
    client = MongoClient()
    db = client["test_db"]
    yield db
    # Cleanup: mongomock auto-cleans on client close

@pytest.fixture
def reset_global_metrics():
    """Reset global metrics before each test."""
    from abby_core.services.metrics_service import MetricsService
    MetricsService._instance = None
    yield
    MetricsService._instance = None

@pytest.fixture
def clean_state_collections(mock_db):
    """Clear all state collections before test."""
    collections = [
        "platform_state", "lifecycle_state", "gameplay_state",
        "configuration_state", "generation_state"
    ]
    for name in collections:
        mock_db[name].delete_many({})
    yield mock_db

@pytest.fixture
async def mock_bot():
    """Mock Discord bot for adapter tests."""
    bot = AsyncMock()
    bot.user = MagicMock(id=111222333)
    bot.get_guild = MagicMock(return_value=MagicMock(
        id=123456789,
        name="Test Guild",
        member_count=50
    ))
    return bot
```python

### Using Fixtures

```python
@pytest.mark.state
def test_state_transition(clean_state_collections):
    """Test uses fixture to ensure clean state."""
    db = clean_state_collections
    
    # Test logic
    db.platform_state.insert_one({"guild_id": "123", "status": "ready"})
    result = db.platform_state.find_one({"guild_id": "123"})
    
    assert result["status"] == "ready"
```python

### Fixture Composition

```python
@pytest.fixture
async def full_test_context(clean_state_collections, mock_bot, reset_global_metrics):
    """Combine multiple fixtures for complex tests."""
    return {
        "db": clean_state_collections,
        "bot": mock_bot,
        "metrics": reset_global_metrics
    }

@pytest.mark.integration
async def test_full_generation_flow(full_test_context):
    """Test with all fixtures pre-configured."""
    db = full_test_context["db"]
    bot = full_test_context["bot"]
    
    # Full end-to-end test with mocked bot
    result = await generate_response(guild_id="123", user_id="456")
    assert result.status == "success"
```python

---

## Unit Tests (Isolated Logic)

### State Management

```python
## tests/test_state_management.py
import pytest
from abby_core.system.state_management import StateTransitionValidator

@pytest.mark.state
def test_valid_state_transition():
    """Test valid state transition is allowed."""
    validator = StateTransitionValidator()
    
    is_valid = validator.validate_transition(
        from_state="WAITING_FOR_INPUT",
        to_state="GENERATING_RESPONSE",
        effects=[]
    )
    
    assert is_valid is True

@pytest.mark.state
def test_invalid_state_transition():
    """Test invalid transition is blocked."""
    validator = StateTransitionValidator()
    
    with pytest.raises(ValueError):
        validator.validate_transition(
            from_state="WAITING_FOR_INPUT",
            to_state="WAITING_FOR_INPUT",  # Invalid: same state
            effects=[]
        )
```python

### Metrics Collection

```python
## tests/test_metrics_service.py
@pytest.mark.architecture
async def test_record_transition(reset_global_metrics, mock_db):
    """Test transition recording."""
    from abby_core.services.metrics_service import MetricsService
    
    metrics = MetricsService(db=mock_db)
    
    await metrics.record_transition(
        user_id="123",
        guild_id="456",
        from_state="WAITING",
        to_state="GENERATING",
        duration_ms=1500
    )
    
    # Verify recorded
    records = mock_db.metrics.find_one({
        "user_id": "123",
        "operation": "transition"
    })
    
    assert records["duration_ms"] == 1500
```python

### Adapter Contracts

```python
## tests/test_adapter_contracts.py
@pytest.mark.adapters
def test_discord_adapter_implements_interface():
    """Verify adapter implements IServerInfoTool."""
    from abby_core.interfaces.tools import IServerInfoTool
    from abby_core.discord.adapters import DiscordServerInfoTool
    
    assert issubclass(DiscordServerInfoTool, IServerInfoTool)
    
    # Verify methods
    tool = DiscordServerInfoTool(bot=MagicMock())
    assert hasattr(tool, "get_server_info")
    assert callable(tool.get_server_info)
```python

---

## Integration Tests (Full Workflow)

### End-to-End Conversation

```python
## tests/test_end_to_end_conversation.py
@pytest.mark.integration
async def test_full_conversation_flow(clean_state_collections, mock_bot):
    """Test user message → intent → generation → response."""
    from abby_core.services.conversation_service import ConversationService
    from abby_core.services.generation_service import GenerationService
    
    db = clean_state_collections
    
    # Simulate user message
    user_input = "Hello Abby!"
    
    # Process through conversation FSM
    conversation = ConversationService(db=db, bot=mock_bot)
    result = await conversation.handle_message(
        user_id="123",
        guild_id="456",
        content=user_input
    )
    
    # Verify state progression
    assert result.status == "success"
    assert result.response is not None
    
    # Verify metrics recorded
    metrics = db.metrics.find_one({"user_id": "123"})
    assert metrics["event"] == "message_processed"
```python

### State Machine Transitions

```python
## tests/test_conversation_fsm.py
@pytest.mark.state
async def test_state_machine_progression(clean_state_collections):
    """Test FSM progresses through valid states."""
    from abby_core.system.conversation_fsm import ConversationFSM
    
    fsm = ConversationFSM(db=clean_state_collections)
    
    # Initial state
    initial = await fsm.get_state("user_123", "guild_456")
    assert initial == "WAITING_FOR_INPUT"
    
    # Transition 1
    await fsm.transition("user_123", "guild_456", "GENERATING_RESPONSE")
    assert await fsm.get_state("user_123", "guild_456") == "GENERATING_RESPONSE"
    
    # Transition 2
    await fsm.transition("user_123", "guild_456", "RESPONDING")
    assert await fsm.get_state("user_123", "guild_456") == "RESPONDING"
    
    # Back to initial
    await fsm.transition("user_123", "guild_456", "WAITING_FOR_INPUT")
    assert await fsm.get_state("user_123", "guild_456") == "WAITING_FOR_INPUT"
```python

### DLQ Integration

```python
## tests/test_dlq_integration.py
@pytest.mark.integration
async def test_failed_operation_retry(clean_state_collections):
    """Test operation failure handling and retry."""
    from abby_core.services.dlq_service import DLQService
    
    dlq = DLQService(db=clean_state_collections)
    
    # Simulate failed operation
    await dlq.enqueue_failed_operation(
        operation_id="op_123",
        error_category="state_transition",
        error_message="Invalid state",
        metadata={"user_id": "456"}
    )
    
    # Verify in DLQ
    pending = clean_state_collections.dlq.find_one({"operation_id": "op_123"})
    assert pending["status"] == "PENDING"
    assert pending["retry_count"] == 0
    
    # Simulate retry
    await dlq.retry_operation("op_123")
    
    # Verify retry_count incremented
    updated = clean_state_collections.dlq.find_one({"operation_id": "op_123"})
    assert updated["retry_count"] == 1
```python

---

## Mocking Patterns

### Mocking Discord Bot

```python
from unittest.mock import MagicMock, AsyncMock

## Create mock bot
bot = MagicMock()
bot.user = MagicMock(id=111)

## Mock guild retrieval
guild = MagicMock()
guild.id = 123
guild.name = "Test Guild"
guild.get_member = MagicMock(return_value=MagicMock(
    display_name="Test User"
))

bot.get_guild = MagicMock(return_value=guild)

## Use in test
from abby_core.discord.adapters import DiscordServerInfoTool
tool = DiscordServerInfoTool(bot=bot)

info = await tool.get_server_info("123")
assert info.name == "Test Guild"
```python

### Mocking External APIs

```python
from unittest.mock import patch, AsyncMock

## Mock OpenAI API call
@patch("openai.ChatCompletion.acreate")
async def test_generation_with_mock_llm(mock_create):
    """Test generation without calling real LLM."""
    
    # Configure mock
    mock_create.return_value = AsyncMock(
        choices=[AsyncMock(
            message=AsyncMock(content="Generated response")
        )]
    )
    
    # Run test
    from abby_core.services.generation_service import GenerationService
    gen = GenerationService()
    
    response = await gen.generate("Hello")
    assert response == "Generated response"
    
    # Verify API was called with correct params
    mock_create.assert_called_once()
```python

### Mocking Database

```python
import mongomock

## Use mongomock instead of MongoDB
mock_client = mongomock.MongoClient()
mock_db = mock_client["test"]

## Insert test data
mock_db.users.insert_one({"user_id": "123", "xp": 100})

## Query
user = mock_db.users.find_one({"user_id": "123"})
assert user["xp"] == 100
```python

---

## Async Test Support

### Async Fixtures

```python
@pytest.fixture
async def async_mock_service():
    """Fixture providing async operations."""
    service = AsyncMock()
    service.process = AsyncMock(return_value="success")
    return service

@pytest.mark.asyncio
async def test_async_operation(async_mock_service):
    """Test async operations."""
    result = await async_mock_service.process("input")
    assert result == "success"
```python

### Mark Async Tests

```python
@pytest.mark.asyncio
async def test_async_state_transition():
    """Mark test as async for pytest-asyncio."""
    state = StateManager()
    result = await state.transition("WAITING", "GENERATING")
    assert result is True
```python

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
## .github/workflows/tests.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]
    
    steps:

    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
    
    - name: Run tests (fast path)
      run: |
        pytest -m "not integration" -v
    
    - name: Run coverage
      run: |
        pytest --cov=abby_core tests/
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```python

### Test Execution Strategy

```bash
## Fast feedback (< 2 min) - runs on every commit
pytest -m "not integration" -v

## Full suite (10-30 min) - scheduled nightly
pytest tests/ -v --cov

## Before release - full suite + performance benchmarks
pytest tests/ -v --benchmark
```python

---

## Test Quality Maintenance

### Coverage Expectations

| Component | Target | Current |
| ----------- | -------- | --------- |
| **State Management** | 90%+ | 92% |
| **Metrics Service** | 85%+ | 87% |
| **Adapters** | 85%+ | 84% |
| **Economy/XP** | 80%+ | 82% |
| **Overall** | 70%+ | 78% |

### Coverage Gaps

Identify and fix gaps:

```bash
## Generate coverage report
pytest --cov=abby_core --cov-report=html tests/

## Open report
open htmlcov/index.html

## Find untested lines
grep class="nc" htmlcov/*.html
```python

### Annual Test Reviews

- [ ] Update fixtures for new features
- [ ] Review test execution time (> 30s → optimize)
- [ ] Audit mock objects for realism
- [ ] Check for flaky tests (random failures)
- [ ] Update CI/CD to new Python versions

---

## Common Test Patterns

### Testing Error Cases

```python
@pytest.mark.state
def test_invalid_xp_delta_rejected():
    """Test negative XP delta is rejected."""
    from abby_core.services.xp_service import XPService
    
    service = XPService(db=MagicMock())
    
    with pytest.raises(ValueError):
        service.validate_xp_delta(-100)  # Negative not allowed
```python

### Testing Idempotency

```python
@pytest.mark.architecture
async def test_scheduler_job_idempotent(clean_state_collections):
    """Test scheduler job can safely run multiple times."""
    from abby_core.services.scheduler import xp_streaming_handler
    
    db = clean_state_collections
    db.xp_updates.insert_one({"user_id": "123", "xp_delta": 50})
    
    # Run twice
    await xp_streaming_handler(db)
    await xp_streaming_handler(db)
    
    # Should only process once
    user = db.users.find_one({"user_id": "123"})
    assert user["xp"] == 50  # Not 100
```python

### Testing Concurrent Operations

```python
@pytest.mark.architecture
async def test_concurrent_state_transitions(clean_state_collections):
    """Test concurrent transitions don't cause corruption."""
    import asyncio
    from abby_core.system.state_management import StateTransitionValidator
    
    validator = StateTransitionValidator()
    
    # Run 100 transitions concurrently
    tasks = [
        validator.validate_transition(
            "WAITING", "GENERATING", []
        )
        for _ in range(100)
    ]
    
    results = await asyncio.gather(*tasks)
    assert all(results)  # All should succeed
```python

---

## 50-Year Test Strategy

### Annual Audits

- [ ] Review test coverage (70%+ minimum)
- [ ] Audit fixture definitions (still relevant?)
- [ ] Check for deprecated test patterns
- [ ] Verify CI/CD still compatible with latest Python

### 5-Year Reviews

- [ ] Migrate to new testing framework (if better available)
- [ ] Redesign performance benchmarks
- [ ] Add integration tests for new features
- [ ] Plan test infrastructure scaling

### 10-Year Reviews

- [ ] Full testing architecture redesign
- [ ] Evaluate AI-assisted test generation
- [ ] Plan for quantum-resistant cryptography testing
- [ ] Multi-region integration testing

---

## Related Documents

- [ADAPTER_CONTRACTS.md](../architecture/ADAPTER_CONTRACTS.md) — Contract testing patterns
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Debug failed tests
