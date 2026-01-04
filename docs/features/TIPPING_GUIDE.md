# Tipping System Guide

## Overview

The Breeze Coin tipping system allows users to show appreciation by sending tips to other community members. The system includes daily budgets and anti-abuse controls to maintain a healthy economy.

## Features

### Daily Budget System

- **Daily Limit**: Each user can tip up to **1,000 Breeze Coins per day**
- **24-Hour Reset**: Budget resets automatically 24 hours after first use
- **Per-Guild**: Budget is tracked separately for each Discord server
- **Real-time Tracking**: See your remaining budget after each tip

### Anti-Abuse Controls

- ✅ Cannot tip yourself
- ✅ Cannot tip bots
- ✅ Must have sufficient wallet balance
- ✅ Daily budget prevents excessive tipping
- ✅ All tips are logged in transaction history

### Transaction Logging

- All tips are logged with type `"tip"` in the database
- Both sender and recipient transaction histories are updated
- Optional reason field for context
- Timestamps for all transactions

## Using the `/tip` Command

### Basic Syntax

```
/tip @user amount [reason] [public]
```

### Parameters

- **@user** (required): The user to tip
- **amount** (required): Number of Breeze Coins to tip (must be positive)
- **reason** (optional): A message explaining why you're tipping
- **public** (optional): Whether to show a public thank-you (default: true)

### Examples

#### Simple Tip

```
/tip @Alice 100
```

Sends 100 BC to Alice with a public confirmation.

#### Tip with Reason

```
/tip @Bob 50 reason:"Great job on the project!"
```

Sends 50 BC to Bob with a thank-you message.

#### Private Tip

```
/tip @Charlie 200 reason:"Thanks for the help" public:false
```

Sends 200 BC to Charlie privately (only you see the confirmation).

#### Large Tip

```
/tip @Diana 500 reason:"Outstanding contribution to the community ⭐"
```

Sends a larger tip with an appreciative message.

## Budget Management

### Checking Your Budget

After each tip, you'll see your remaining budget in the confirmation message:

```
✅ Tip Sent!
From: @YourName
To: @RecipientName
Amount: 100 BC
Your New Balance: 400 BC
Tip Budget Remaining: 900 BC
```

### Budget Reset

- Budget resets **24 hours** after your first tip of the day
- Example: First tip at 2:00 PM Monday → Budget resets at 2:00 PM Tuesday
- You'll automatically receive a fresh 1,000 BC budget

### Budget Exhaustion

If you try to tip more than your remaining budget:

```
⚠️ Insufficient tipping budget. You have 50 BC remaining today.
Daily limit: 1,000 BC (resets every 24 hours)
```

## Validation Rules

### Amount Validation

- ✅ Must be a positive number
- ❌ Cannot tip 0 BC
- ❌ Cannot tip negative amounts
- ✅ Cannot exceed your wallet balance
- ✅ Cannot exceed your daily tipping budget

### Recipient Validation

- ❌ Cannot tip yourself
- ❌ Cannot tip bots
- ✅ Can tip any human Discord member
- ✅ Recipient profile auto-created if needed

### Wallet Requirements

- Must have initialized your bank profile (`/bank init`)
- Must have sufficient Breeze Coins in your **wallet** (not bank)
- Tips come from your wallet, not your bank account

## Confirmation Messages

### Public Tips (default)

Everyone in the channel sees:

```embed
💸 Tip Sent!
From: @Sender
To: @Recipient
Amount: 100 BC
Reason: Great work on the project!
Your New Balance: 400 BC
Tip Budget Remaining: 900 BC

Thank you for spreading kindness! ✨
```

### Private Tips

Only you see the confirmation (ephemeral message):

```embed
💸 Tip Sent!
From: @You
To: @Recipient
Amount: 200 BC
Reason: Thanks for your help
Your New Balance: 300 BC
Tip Budget Remaining: 800 BC

Thank you for spreading kindness! ✨
```

## Transaction History

### Viewing Your Tips

Use `/bank history` to see all transactions, including tips:

```
Recent Transactions
━━━━━━━━━━━━━━━━━━━━
🔄 Tip
   Amount: -100 BC
   Balance After: 400 BC
   Note: Tipped 100 BC to @Alice: Great work!
   Date: 2024-01-15 14:30:22
```

### Transaction Types

Tips are logged as `"tip"` type transactions:

- **Sender**: `-amount BC` (deducted from wallet)
- **Recipient**: `+amount BC` (added to wallet)
- **Note**: Includes recipient/sender name and optional reason

## Best Practices

### When to Tip

- 🎉 Recognize exceptional contributions
- 💡 Reward helpful advice or assistance
- 🎨 Appreciate creative work or content
- 📚 Thank someone for teaching/mentoring
- 🤝 Celebrate collaborative achievements

### Budget Strategy

- **Small Tips (10-50 BC)**: Quick thank-yous for minor helps
- **Medium Tips (50-200 BC)**: Significant contributions
- **Large Tips (200-500 BC)**: Exceptional work or major help
- **Save Budget**: Keep some budget for unexpected opportunities

### Etiquette

- ✅ Include a reason to make tips meaningful
- ✅ Use public tips to recognize work publicly
- ✅ Use private tips for sensitive situations
- ❌ Don't pressure others to tip you back
- ❌ Don't use tips as payment for services

## Technical Details

### Database Fields

The economy schema includes:

```python
tip_budget_used: int       # Amount of daily budget used
tip_budget_reset: datetime # Last time budget was reset
```

### Budget Functions

- `get_tip_budget_remaining()`: Calculate available budget
- `reset_tip_budget_if_needed()`: Auto-reset after 24 hours
- `increment_tip_budget_used()`: Track budget usage

### Guild Scoping

- All tips are scoped to the current Discord server
- Budget is per-server (tipping in Server A doesn't affect Server B budget)
- Transaction history is per-server

## Error Messages

### Insufficient Budget

```
⚠️ Insufficient tipping budget. You have 50 BC remaining today.
Daily limit: 1,000 BC (resets every 24 hours)
```

**Solution**: Wait for budget reset or tip a smaller amount.

### Insufficient Funds

```
⚠️ Insufficient funds. You have 80 BC in your wallet.
```

**Solution**: Deposit more coins or tip a smaller amount.

### No Profile

```
⚠️ Your profile not found. Initialize with `/bank init` first.
```

**Solution**: Run `/bank init` to create your economy profile.

### Self-Tip

```
⚠️ You cannot tip yourself.
```

**Solution**: Tip someone else instead!

### Bot Recipient

```
⚠️ You cannot tip bots.
```

**Solution**: Only tip human Discord members.

### Invalid Amount

```
⚠️ Tip amount must be positive.
```

**Solution**: Enter a positive number (e.g., 50, 100, 500).

## Moderation

### Admin Override

_(Feature planned for future release)_

- Admins can reset user budgets
- Admins can refund tips
- Admins can adjust daily limits

### Abuse Prevention

Current anti-abuse measures:

- Daily budget limits (1,000 BC)
- Cannot self-tip or tip bots
- All transactions logged permanently
- Guild-scoped isolation

## FAQ

### Can I tip more than 1,000 BC per day?

No, the daily limit is 1,000 BC. This prevents economy inflation and abuse.

### When does my budget reset?

24 hours after your first tip. Check your confirmation message for remaining budget.

### Can I tip someone in a different server?

No, tips are server-specific. Each server has its own economy.

### What if the recipient doesn't have a profile?

The system automatically creates a profile for them when you send the tip.

### Can I get my tip back?

No, tips are final. Double-check before sending.

### Do tips come from my wallet or bank?

Tips come from your **wallet**. Use `/bank withdraw` to move coins from bank to wallet.

### Can I see who tipped me?

Yes, check `/bank history` to see all tips received.

### What's the difference between `/pay` and `/tip`?

- `/pay`: General money transfer (no budget limit)
- `/tip`: Recognition/appreciation (1,000 BC daily budget)

## See Also

- [Banking System Guide](../features/README.md) - Learn about wallets and banks
- [Economy Commands](../getting-started/README.md) - All economy commands
- [ISSUES.md](../ISSUES.md) - Issue #20 specification

---

**Need help?** Ask in your server's support channel or check the main documentation.
