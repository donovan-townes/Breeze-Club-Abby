# TDOS Memory Troubleshooting Guide

Common issues when using TDOS Memory with Abby and their solutions.

## Installation Issues

### Issue 1: `ModuleNotFoundError: No module named 'tdos_memory'`

**Symptoms:**

```
ImportError: No module named 'tdos_memory'
```

**Causes:**

- TDOS Memory not installed
- Wrong virtual environment active
- Installation failed silently

**Solutions:**

1. **Verify Installation**

   ```bash
   pip list | grep tdos-memory
   ```

   If not listed, it's not installed.

2. **Install Missing Package**

   ```bash
   pip install tdos-memory>=1.0.0
   ```

3. **Install from requirements.txt**

   ```bash
   pip install -r requirements.txt
   ```

4. **Check Virtual Environment**

   ```bash
   which python  # On Windows: where python
   ```

   Should show path inside your venv folder.

5. **Force Reinstall**
   ```bash
   pip uninstall tdos-memory -y
   pip install --no-cache-dir tdos-memory
   ```

---

### Issue 2: `ImportError: cannot import name 'get_memory_envelope'`

**Symptoms:**

```
ImportError: cannot import name 'get_memory_envelope' from 'tdos_memory'
```

**Causes:**

- Installed an incompatible version (pre-1.0.0)
- Function name changed in your TDOS Memory version
- Syntax error in your import statement

**Solutions:**

1. **Check Installed Version**

   ```bash
   python -c "import tdos_memory; print(tdos_memory.__version__)"
   ```

2. **Verify Correct Import**

   ```python
   # Should work
   from tdos_memory import get_memory_envelope

   # Check what's available
   import tdos_memory
   print(dir(tdos_memory))  # See all exported functions
   ```

3. **Update to Latest**

   ```bash
   pip install --upgrade tdos-memory
   ```

4. **Check CHANGELOG**
   See `tdos_memory/docs/CHANGELOG.md` for API changes

---

### Issue 3: Dependency Installation Hangs

**Symptoms:**

```
Installing collected packages: tdos-memory
⠸  Installing tdos-memory... (takes forever)
```

**Causes:**

- Network issue
- PyPI server slow
- Large package being compiled

**Solutions:**

1. **Cancel and Retry**

   ```bash
   Ctrl+C  # Cancel
   pip install --no-cache-dir tdos-memory
   ```

2. **Use Different PyPI Mirror** (if PyPI is down)

   ```bash
   pip install -i https://mirrors.aliyun.com/pypi/simple/ tdos-memory
   ```

3. **Check Network**
   ```bash
   ping pypi.org
   ```

---

## MongoDB Connection Issues

### Issue 4: `ServerSelectionTimeoutError: No servers found`

**Symptoms:**

```
pymongo.errors.ServerSelectionTimeoutError: No servers found in replica set
```

**Causes:**

- MongoDB not running
- Wrong connection string
- Firewall blocking connection
- MongoDB Atlas IP whitelist issue

**Solutions:**

1. **Verify MongoDB is Running**

   ```bash
   # If using MongoDB Atlas
   ping cluster0.mongodb.net

   # If using local MongoDB
   mongosh  # or mongo command
   ```

2. **Check Connection String**

   ```bash
   # In your .env file
   MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority

   # Verify string is correct (no typos in password)
   ```

3. **MongoDB Atlas IP Whitelist**

   - Go to https://cloud.mongodb.com
   - Cluster → Network Access
   - Add your IP address to whitelist (or 0.0.0.0/0 for all)

4. **Test Connection**

   ```python
   from abby_core.database.mongodb import connect_to_mongodb

   try:
       client = connect_to_mongodb()
       client.admin.command('ping')
       print("✓ MongoDB connected")
   except Exception as e:
       print(f"✗ MongoDB error: {e}")
   ```

5. **Check Credentials**

   ```bash
   # MongoDB Atlas: Username should include special characters encoded
   # Example: user@email.com → user%40email.com (@ becomes %40)

   MONGODB_URI=mongodb+srv://user%40email.com:password@cluster.mongodb.net/
   ```

---

### Issue 5: `OperationFailure: authentication failed`

**Symptoms:**

```
pymongo.errors.OperationFailure: authentication failed
```

**Causes:**

- Wrong MongoDB password
- Wrong username
- User doesn't have access to database
- Credentials not properly encoded in URL

**Solutions:**

1. **Verify Credentials**

   ```bash
   # Test with mongosh
   mongosh "mongodb+srv://username:password@cluster.mongodb.net"
   ```

   If this fails, credentials are wrong.

2. **Encode Special Characters**

   - `@` → `%40`
   - `:` → `%3A`
   - `#` → `%23`

   Example:

   ```
   Password: my@pass:123
   Encoded: my%40pass%3A123
   ```

3. **Check Permissions**

   - User might need `readWrite` role
   - Go to MongoDB Atlas → Security → Database Users
   - Verify user has access to your database

4. **Reset Password**
   - MongoDB Atlas → Security → Database Users
   - Edit user → Edit Password
   - Use new password in MONGODB_URI

---

## Memory Operation Issues

### Issue 6: Memory Envelope Always Empty

**Symptoms:**

```python
envelope = get_memory_envelope("user123", "guild456", "discord")
print(len(envelope.facts))  # Output: 0 (always empty)
```

**Causes:**

- Facts not saved to MongoDB
- Wrong user_id/guild_id
- MongoDB collection empty
- Cache not refreshed

**Solutions:**

1. **Verify Facts Exist in MongoDB**

   ```bash
   mongosh
   > use abby_db
   > db.user_memory.findOne({user_id: "user123"})
   ```

2. **Check User ID Format**

   ```python
   # Discord user IDs should be strings
   user_id = str(ctx.author.id)  # Not just ctx.author.id

   # Should be like: "123456789012345678"
   ```

3. **Save Facts First**

   ```python
   from tdos_memory import add_memorable_fact

   # Save a fact
   await add_memorable_fact(
       user_id="user123",
       guild_id="guild456",
       fact="User likes pizza",
       confidence=0.9,
       source="test"
   )

   # Now retrieve
   envelope = get_memory_envelope("user123", "guild456", "discord")
   print(len(envelope.facts))  # Should be > 0
   ```

4. **Invalidate Cache**

   ```python
   from tdos_memory import invalidate_cache

   # After saving facts, clear cache
   await invalidate_cache(user_id="user123", guild_id="guild456")

   # Next call will fetch fresh data
   envelope = get_memory_envelope("user123", "guild456", "discord")
   ```

5. **Check Collection Names**

   ```python
   # Verify your MongoMemoryStore is using correct collection names
   self.memory_store = MongoMemoryStore(
       storage_client=mongo_client,
       profile_collection="discord_profiles",     # Default
       session_collection="chat_sessions",        # Default
       narrative_collection="shared_narratives"   # Default
   )

   # These should match what you're checking in MongoDB
   ```

---

### Issue 7: Changes Not Persisted

**Symptoms:**

```python
await add_memorable_fact(..., fact="Important info")
# App restarts or moved to another server
envelope = get_memory_envelope(...)
print(envelope.facts)  # Fact is missing!
```

**Causes:**

- Database not actually saving data
- Wrong MongoDB database
- Data written to wrong collection
- MongoDB connection lost

**Solutions:**

1. **Verify Data Saved**

   ```bash
   mongosh
   > use abby_db
   > db.discord_profiles.countDocuments()  # Should be > 0
   > db.discord_profiles.find().limit(1)   # See sample document
   ```

2. **Check Database Name**

   ```python
   # In launch.py or your initialization
   # Check that MONGODB_URI points to correct database

   MONGODB_URI=mongodb+srv://.../?retryWrites=true&w=majority

   # To specify database: add /abby_db
   MONGODB_URI=mongodb+srv://...@cluster.mongodb.net/abby_db
   ```

3. **Verify Write Concern**

   ```python
   # Make sure writes are being acknowledged
   client = connect_to_mongodb()

   # Check write concern
   print(client.write_concern)  # Should show w=1 or higher
   ```

4. **Test Connection Persistence**
   ```python
   async def test_persistence():
       # Write
       await add_memorable_fact(
           user_id="test_user",
           guild_id="test_guild",
           fact="Test fact",
           confidence=1.0,
           source="test"
       )

       # Disconnect and reconnect
       # (simulate connection reset)

       # Read
       envelope = get_memory_envelope("test_user", "test_guild", "discord")
       assert len(envelope.facts) > 0
   ```

---

### Issue 8: `RuntimeError: Event loop is closed`

**Symptoms:**

```
RuntimeError: Event loop is closed
```

**Causes:**

- Trying to use async function in non-async context
- Event loop not properly initialized
- Memory service called before bot is ready

**Solutions:**

1. **Use in Async Context Only**

   ```python
   # WRONG - not in async function
   async def setup(bot):
       facts = add_memorable_fact(...)  # Missing await!

   # CORRECT
   async def setup(bot):
       await add_memorable_fact(...)    # With await
   ```

2. **Wait for Bot Ready**

   ```python
   class MyCog(commands.Cog):
       @commands.Cog.listener()
       async def on_ready(self):
           # Now safe to use memory
           await self.initialize_memory()
   ```

3. **Use Memory Service Instead of Direct Calls**
   ```python
   # Better - uses managed event loop
   facts = await self.memory_service.get_user_facts(user_id, guild_id)
   ```

---

## Performance Issues

### Issue 9: Memory Retrieval is Slow

**Symptoms:**

```python
# Takes 5+ seconds
envelope = get_memory_envelope(user_id, guild_id, source_id)
```

**Causes:**

- Large number of facts (thousands)
- MongoDB queries not indexed
- Network latency to MongoDB
- Memory decay calculations expensive

**Solutions:**

1. **Create Indexes** (run once)

   ```python
   from tdos_memory.storage import MongoMemoryStore

   memory_store.create_indexes()  # Creates optimal indexes
   ```

2. **Use Pagination**

   ```python
   # Instead of loading all facts
   facts = await memory_service.get_user_facts(
       user_id, guild_id,
       skip=0,
       limit=100  # Only load 100 at a time
   )
   ```

3. **Load Recent Facts Only**

   ```python
   # Instead of all historical facts
   recent_facts = await memory_service.get_recent_facts(
       user_id, guild_id,
       days=30  # Last 30 days only
   )
   ```

4. **Cache Results**

   ```python
   # Cache envelope for session duration
   cache = {}

   def get_cached_envelope(user_id, guild_id):
       key = f"{user_id}:{guild_id}"
       if key not in cache:
           cache[key] = get_memory_envelope(user_id, guild_id, "discord")
       return cache[key]
   ```

5. **Check MongoDB Connection**

   ```bash
   # If using MongoDB Atlas, check network latency
   ping cluster0.mongodb.net

   # Should be < 100ms
   ```

---

### Issue 10: Memory Decay Not Working

**Symptoms:**

```python
# Old facts should have lower confidence but don't
envelope = get_memory_envelope(user_id, guild_id, source_id)
for fact in envelope.facts:
    print(fact.confidence)  # All ~1.0, not decaying
```

**Causes:**

- Decay task not running
- Decay threshold not met (facts too recent)
- Decay factor misconfigured

**Solutions:**

1. **Manually Run Decay**

   ```python
   from tdos_memory import apply_decay

   # Force decay on old facts
   decayed = await apply_decay(
       days_old_threshold=1,  # Decay facts older than 1 day
       decay_factor=0.95      # 95% retention per day
   )

   print(f"Decayed {decayed} facts")
   ```

2. **Schedule Periodic Decay** (in a background task)

   ```python
   from discord.ext import tasks

   @tasks.loop(hours=1)  # Run every hour
   async def apply_memory_decay():
       await apply_decay(days_old_threshold=1, decay_factor=0.95)

   @apply_memory_decay.before_loop
   async def before_decay():
       await self.bot.wait_until_ready()
   ```

3. **Verify Decay Settings**

   ```python
   # Check if threshold is too high

   # This won't decay facts less than 30 days old
   await apply_decay(days_old_threshold=30)

   # Better - decay facts daily
   await apply_decay(days_old_threshold=1)
   ```

4. **Check Timestamps**

   ```bash
   mongosh
   > db.discord_profiles.findOne()

   # Look for created_at/updated_at timestamps
   # Should show when facts were created
   ```

---

## LLM Integration Issues

### Issue 11: Memory Format Causes LLM Errors

**Symptoms:**

```python
memory_context = format_envelope_for_llm(envelope)
prompt = f"Context: {memory_context}\n\nUser: {user_input}"

# LLM errors or generates bad response
response = await llm.generate(prompt)
```

**Causes:**

- Formatted string has special characters breaking prompt
- Context too long (token limit exceeded)
- Formatting incompatible with LLM

**Solutions:**

1. **Check Formatted Output**

   ```python
   envelope = get_memory_envelope(user_id, guild_id, "discord")
   context = format_envelope_for_llm(envelope)
   print(context)  # See what's being injected
   ```

2. **Limit Context Length**

   ```python
   memory_context = format_envelope_for_llm(
       envelope,
       max_tokens=500  # Limit to 500 tokens
   )
   ```

3. **Test Prompt Separately**

   ```python
   # Test with just memory context
   test_prompt = f"Context: {memory_context}"
   response = await llm.generate(test_prompt)

   # If this works, issue is with user_input
   ```

4. **Sanitize User Input**

   ```python
   # Remove characters that might break prompt
   user_input = user_input.replace('"', '\\"').replace('\n', ' ')
   ```

5. **Add Prompt Boundaries**
   ```python
   prompt = f"""
   <context>
   {memory_context}
   </context>
   ```

<user_message>
{user_input}
</user_message>

Your response:
"""

````

---

## Debugging Tips

### Enable Debug Logging

```python
import logging

# Enable detailed TDOS Memory logging
logging.getLogger('tdos_memory').setLevel(logging.DEBUG)

# Also enable MongoDB logging
logging.getLogger('pymongo').setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(handler)
````

### Inspect Memory Database

```bash
# Connect to MongoDB
mongosh

# See collections
> db.getCollectionNames()

# See how many memory profiles
> db.discord_profiles.countDocuments()

# See sample data
> db.discord_profiles.findOne({user_id: "YOUR_USER_ID"})

# Delete test data
> db.discord_profiles.deleteOne({user_id: "test_user"})
```

### Get Help

If you're stuck:

1. Check [TDOS Memory Troubleshooting](../../tdos_memory/docs/TROUBLESHOOTING.md)
2. Check [TDOS Memory docs](../../tdos_memory/docs/README.md)
3. Check [INTEGRATION.md](INTEGRATION.md) for usage examples
4. Open an issue on GitHub

---

**Still having issues?** Open a GitHub issue with:

- Error message (full traceback)
- What you were trying to do
- Your Python/TDOS Memory versions
- Relevant code snippet
