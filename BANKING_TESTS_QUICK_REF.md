# Banking Integration Test Quick Reference

## What Was Built

A comprehensive test suite for Phase 2 banking features (Issues #3-#6):
- Slash commands: `/bank balance`, `/bank deposit`, `/bank withdraw`, `/bank history`, `/bank init`, `/bank pay`
- Interest accrual: 0.1% daily, prorated every 10 minutes, logged as transactions
- Wallet transfers: `/pay @user amount` with validation and dual logging
- Guild scoping: All operations isolated per guild
- Transaction logging: All operations recorded with type, amount, timestamp, balance_after, description

## Test Files Overview

### test_banking_integration.py
**Core operations** - 14 test classes validating the happy path
- Deposit/withdraw fund movements
- Transfer (pay) operations with dual logging
- Interest calculations and thresholds
- Transaction history retrieval
- Guild scoping and isolation
- Canonical field names (wallet_balance, bank_balance)

**Run:**
```bash
pytest tests/test_banking_integration.py -v
```

### test_banking_edge_cases.py
**Edge cases & validation** - 14 test classes validating error handling
- Self-pay prevention
- Insufficient funds detection
- Bot-pay prevention
- Zero and negative amount validation
- Large amount handling
- Boundary conditions (interest min balance)
- Auto-profile creation for transfers
- Concurrency and atomicity

**Run:**
```bash
pytest tests/test_banking_edge_cases.py -v
```

### test_banking_history.py
**History & formatting** - 11 test classes validating transaction history
- History retrieval and filtering by user/guild
- Transaction type mapping (deposit, withdraw, transfer, interest, init)
- Description formatting for each type
- Amount and balance tracking
- Timestamp recording
- Display formatting (emoji, currency, etc.)
- Multi-guild isolation

**Run:**
```bash
pytest tests/test_banking_history.py -v
```

## Running Tests

### All banking tests
```bash
cd c:\Abby_Discord_Latest
pytest tests/test_banking*.py -v
```

### With coverage report
```bash
pytest tests/test_banking*.py --cov=abby_core.economy --cov=abby_core.database --cov-report=html
```

### Specific test class
```bash
pytest tests/test_banking_integration.py::TestDepositWithdraw -v
pytest tests/test_banking_edge_cases.py::TestSelfTransferValidation -v
pytest tests/test_banking_history.py::TestTransactionTypes -v
```

## Test Coverage Summary

| Operation | Tests | Coverage |
|-----------|-------|----------|
| Deposit | 12 | wallet→bank, logging, validation |
| Withdraw | 11 | bank→wallet, logging, validation |
| Transfer (Pay) | 18 | dual update, dual logging, edge cases |
| Interest | 11 | calculation, min balance, logging |
| History | 20 | retrieval, filtering, formatting |
| Guild Scoping | 4 | isolation, no cross-guild pollution |
| Canonical Fields | 2 | wallet_balance, bank_balance |
| Currency | 11 | 100 BC = $1.00, rounding |
| Edge Cases | 30+ | zero amounts, bots, atomicity, etc. |

## Key Test Patterns

### Mocking MongoDB
```python
@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(mongo, "connect_to_mongodb", lambda: client)
    return client
```

### Testing Update Operations
```python
mongo.update_balance("user-1", wallet_delta=-100, bank_delta=100, guild_id="guild-1")
assert economy_col.update_calls[-1][1]["$inc"]["wallet_balance"] == -100
assert economy_col.update_calls[-1][1]["$inc"]["bank_balance"] == 100
```

### Testing Logging
```python
mongo.log_transaction("user-1", "guild-1", "deposit", 100, 600)
txn = txn_col.insert_calls[0]
assert txn["type"] == "deposit"
assert txn["amount"] == 100
```

### Testing Guild Isolation
```python
mongo.update_balance("user-1", wallet_delta=-100, guild_id="guild-1")
mongo.update_balance("user-1", wallet_delta=-200, guild_id="guild-2")
# Verify separate operations with different guild_ids
```

## Known Test Limitations

1. **Discord Cog Commands**: Slash command decorators tested manually in dev environment, not via pytest
2. **Timestamps**: Tests don't verify exact timestamp values; integration tests would
3. **Interest Rounding**: Default 0.1% rate rounds to 0 for most balances; tests verify the calculation logic

## Adding New Tests

When adding new banking features:

1. **Find the right file:**
   - Core operation → `test_banking_integration.py`
   - Edge case or validation → `test_banking_edge_cases.py`
   - History/formatting → `test_banking_history.py`

2. **Create test class and methods:**
```python
class TestMyFeature:
    def test_my_operation(self, fake_client):
        # Setup
        collection = fake_client.db.collections["economy"]
        
        # Execute
        mongo.my_operation("user-1", guild_id="guild-1")
        
        # Assert
        assert len(collection.operations) == 1
```

3. **Run tests to validate:**
```bash
pytest tests/test_banking_integration.py::TestMyFeature -v
```

## Next Steps

1. Run full test suite to ensure all pass
2. Measure coverage: `pytest --cov=abby_core.economy tests/test_banking*.py`
3. Fix any failures (likely mock-related)
4. When satisfied, move to Issue #20 (Peer tipping with `/tip` command)

## Related Documentation

- [docs/BANKING_TEST_SUITE.md](docs/BANKING_TEST_SUITE.md) - Detailed test inventory
- [ISSUES.md](ISSUES.md) - Issue #6 status
- [docs/CONTRIBUTING.md](docs/contributing/README.md) - Contribution guidelines
