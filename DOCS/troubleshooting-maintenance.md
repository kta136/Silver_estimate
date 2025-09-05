# Troubleshooting & Maintenance Guide

## Common Issues and Solutions

### 1. Database Issues

#### "Database decryption failed" Error
**Symptoms**: Application won't start, shows decryption error
**Causes**: Incorrect password, corrupted file, missing salt
**Solutions**:
1. Verify correct password is being used
2. Check if `security/db_salt` exists in QSettings
3. Examine `database/estimation.db` file size (should be > 12 bytes)
4. Use data wipe feature if recovery impossible

#### Schema Version Mismatch
**Symptoms**: Missing columns, SQL errors
**Solutions**:
1. Check `schema_version` table manually
2. Run migration manually: `self._migrate_to_version_X()`
3. Backup data and reinitialize if needed

#### Transaction Deadlocks
**Symptoms**: Application hangs during save
**Solutions**:
1. Add timeout to transactions
2. Ensure proper commit/rollback in all paths
3. Check for nested transactions

### 2. UI Issues

#### Table Not Updating
**Symptoms**: Cell values don't refresh
**Solutions**:
```python
# Force table refresh
self.table.blockSignals(True)
try:
    # Update operations
    self.table.viewport().update()
finally:
    self.table.blockSignals(False)
```

#### Focus Problems
**Symptoms**: Cursor jumps to wrong cell
**Solutions**:
1. Check signal handlers for recursive calls
2. Use QTimer.singleShot for deferred focus
3. Verify cell editability flags

#### Print Preview Issues
**Symptoms**: Incorrect formatting, missing data
**Solutions**:
1. Verify font settings loaded correctly
2. Check margin settings in QSettings
3. Debug HTML generation in PrintManager

### 3. Performance Issues

#### Slow Table Loading
**Symptoms**: Delay when loading large estimates
**Solutions**:
1. Batch row insertion
2. Defer signal connections
3. Use SQLite transactions

#### Memory Leaks
**Symptoms**: Increasing memory usage over time
**Solutions**:
1. Ensure dialogs are destroyed properly
2. Clean up temporary files
3. Release references to large objects

### 4. Import/Export Problems

#### File Encoding Errors
**Symptoms**: Import fails with unicode errors
**Solutions**:
```python
encodings_to_try = ['utf-8', 'cp1252', 'latin-1']
for enc in encodings_to_try:
    try:
        with open(file_path, 'r', encoding=enc) as f:
            content = f.read()
        break
    except UnicodeDecodeError:
        continue
```

#### Delimiter Detection Failures
**Symptoms**: Import shows jumbled data
**Solutions**:
1. Allow manual delimiter selection
2. Implement column preview
3. Add validation for parsed data

## Maintenance Tasks

### 1. Regular Database Maintenance

#### Backup Procedure
```python
import shutil
import datetime

def backup_database():
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'backups/estimation_{timestamp}.db'
    shutil.copy2('database/estimation.db', backup_path)
```

#### Database Optimization
```sql
-- Run periodically
VACUUM;
ANALYZE;
REINDEX;
```

#### Integrity Checks
```python
def check_database_integrity(self):
    self.cursor.execute('PRAGMA integrity_check')
    result = self.cursor.fetchone()
    return result[0] == 'ok'
```

### 2. Security Maintenance

#### Password Rotation
1. Update password hash in QSettings
2. Re-encrypt database with new key
3. Test login with new credentials

#### Salt Management
```python
def rotate_salt(self):
    # Generate new salt
    new_salt = os.urandom(16)
    
    # Decrypt with old key
    self._decrypt_db()
    
    # Update salt in settings
    settings.setValue("security/db_salt", base64.b64encode(new_salt))
    
    # Derive new key and re-encrypt
    self.key = self._derive_key(password, new_salt)
    self._encrypt_db()
```

### 3. Performance Monitoring

#### Query Performance
```python
def log_slow_queries(self, query, params, threshold=0.1):
    start = time.time()
    self.cursor.execute(query, params)
    duration = time.time() - start
    
    if duration > threshold:
        logging.warning(f"Slow query ({duration:.3f}s): {query}")
```

#### Memory Usage
```python
import psutil

def monitor_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"Memory usage: {memory_info.rss / 1024 / 1024:.1f} MB")
```

### 4. Update Management

#### Version Checking
```python
def check_for_updates():
    current_version = "1.62"
    # Implement version check logic
    # Check against remote server or GitHub
```

#### Automated Migrations
```python
def auto_migrate_database(self):
    current_version = self._check_schema_version()
    target_version = self.LATEST_SCHEMA_VERSION
    
    while current_version < target_version:
        migration_method = f"_migrate_to_version_{current_version + 1}"
        if hasattr(self, migration_method):
            getattr(self, migration_method)()
            current_version += 1
        else:
            raise Exception(f"Migration method {migration_method} not found")
```

## Diagnostic Tools

### 1. Logging System

The Silver Estimation App includes a comprehensive logging system that is invaluable for troubleshooting. Here's how to use it effectively:

#### Configuring Logging Settings

```python
# Via environment variable
# Windows
set SILVER_APP_DEBUG=true
python main.py

# Linux/macOS
SILVER_APP_DEBUG=true python main.py

# Via settings dialog
# Tools → Settings → Logging
```

#### Log Level Configuration

The application allows you to selectively enable or disable specific log levels:

- **Normal Logs (INFO)**: Day-to-day application events
- **Critical Logs (ERROR/CRITICAL)**: Error conditions and critical issues
- **Debug Logs**: Detailed diagnostic information (only when Debug Mode is enabled)

To configure log levels:
1. Go to Tools → Settings → Logging → Log Levels
2. Check/uncheck the desired log levels
3. Click Apply to save changes

#### Automatic Log Cleanup

To manage disk space and prevent log files from growing too large:

1. Go to Tools → Settings → Logging → Automatic Log Cleanup
2. Enable "Automatically Delete Old Logs"
3. Set the retention period (1-365 days)
4. Click Apply to save changes

You can also manually clean up logs by clicking the "Clean Up Logs Now" button.

#### Log File Locations

```
logs/
├── silver_app.log         # Main application log (INFO and above) - if enabled
├── silver_app_error.log   # Error log (ERROR and CRITICAL only) - if enabled
├── silver_app_debug.log   # Debug log (all messages when debug enabled) - if enabled
└── archived/              # Directory for rotated logs
```

#### Common Log Analysis Techniques

```bash
# Find all errors for a specific user session
grep "user_id=123" logs/silver_app*.log

# View all database errors
grep -A 10 "Database error" logs/silver_app_error.log

# Track a specific estimate through the system
grep "voucher_no=EST1234" logs/silver_app_debug.log

# Find slow database operations
grep "Slow query" logs/silver_app.log
```

#### Interpreting Log Patterns

| Log Pattern | Potential Issue | Troubleshooting Steps |
|-------------|----------------|----------------------|
| Multiple "Database error" entries | Database corruption or connection issues | Check database integrity, verify encryption key |
| "Authentication failed" followed by app crash | Password or salt issues | Check QSettings for missing salt, verify password hashing |
| Repeated "Slow query detected" | Database performance issues | Add indexes, optimize queries, check for large result sets |
| UI exceptions with "wrapped C/C++ object deleted" | Widget lifecycle issues | Check for premature widget destruction, verify parent-child relationships |

For more detailed information on using the logging system, refer to the [Logging Guide](../logging_guide.md).

### 2. Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Debug database queries
self.db.set_trace_callback(print)
```

### 2. Health Check Script
```python
def system_health_check():
    checks = {
        'database_exists': os.path.exists('database/estimation.db'),
        'database_readable': os.access('database/estimation.db', os.R_OK),
        'settings_accessible': bool(QSettings("YourCompany", "SilverEstimateApp").value("security/db_salt")),
        'temp_dir_writable': os.access(tempfile.gettempdir(), os.W_OK)
    }
    
    for check, result in checks.items():
        print(f"{check}: {'✓' if result else '✗'}")
```

### 3. Error Recovery Tools

#### Database Recovery
```python
def attempt_database_recovery(self):
    try:
        # Try to decrypt with error handling
        self._decrypt_db()
        # Check basic structure
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = self.cursor.fetchall()
        
        # Verify core tables exist
        required_tables = ['items', 'estimates', 'estimate_items', 'silver_bars']
        missing_tables = [t for t in required_tables if t not in [row[0] for row in tables]]
        
        if missing_tables:
            print(f"Missing tables: {missing_tables}")
            self.setup_database()  # Recreate missing tables
            
        return True
    except Exception as e:
        print(f"Recovery failed: {e}")
        return False
```

#### Settings Recovery
```python
def reset_application_settings():
    settings = QSettings("YourCompany", "SilverEstimateApp")
    # Backup current settings
    backup_file = f"settings_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.ini"
    settings.sync()
    
    # Clear all settings
    settings.clear()
    
    # Restore defaults
    settings.setValue("ui/table_font_size", 9)
    settings.setValue("print/margins", "10,5,10,5")
    settings.setValue("print/preview_zoom", 1.25)
    settings.sync()
```

## Common Error Messages

### 1. Application Errors

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "Database decryption failed" | Wrong password, corrupted file | Verify password, check file integrity |
| "No such column" | Schema mismatch | Run database migration |
| "Foreign key constraint failed" | Referential integrity violation | Check dependent records before deletion |
| "Table already exists" | Duplicate migration | Check schema_version table |

### 2. User Interface Errors

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "AttributeError: object has no attribute" | Missing UI component | Check UI initialization order |
| "RuntimeError: wrapped C/C++ object deleted" | Widget destroyed prematurely | Maintain proper parent-child relationships |
| "QTimer can only be used with threads started with QThread" | Timer created in wrong thread | Use QTimer.singleShot or create in main thread |

### 3. Data Processing Errors

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "ValueError: invalid literal for float()" | Non-numeric input | Validate input with QDoubleValidator |
| "sqlite3.IntegrityError: UNIQUE constraint failed" | Duplicate primary key | Check for existing records before insert |
| "UnicodeDecodeError" | File encoding mismatch | Try multiple encodings during import |

## Maintenance Checklist

### Daily Tasks
- [ ] Check application logs for errors
- [ ] Verify database backup completed
- [ ] Monitor disk space usage
- [ ] Verify automatic log cleanup is running (check logs/silver_app.log for cleanup messages)

### Weekly Tasks
- [ ] Run database integrity check
- [ ] Review error logs for patterns
- [ ] Test backup restoration
- [ ] Verify log levels are appropriately configured for the environment

### Monthly Tasks
- [ ] Optimize database (VACUUM)
- [ ] Review log retention settings
- [ ] Update documentation
- [ ] Review security settings
- [ ] Check disk space usage by log files

### Quarterly Tasks
- [ ] Rotate passwords
- [ ] Update salt
- [ ] Performance profiling
- [ ] Security audit

## Emergency Procedures

### 1. Data Recovery
1. Stop all write operations
2. Create backup of current state
3. Attempt recovery from most recent backup
4. If failed, use data wipe and restore from older backup

### 2. Security Breach
1. Change all passwords immediately
2. Rotate encryption salt
3. Review access logs
4. Re-encrypt all sensitive data

### 3. Performance Crisis
1. Identify bottleneck (CPU, I/O, Memory)
2. Disable non-essential features
3. Optimize queries and indexes
4. Consider data archiving