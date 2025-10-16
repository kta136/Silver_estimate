# Security Architecture - Silver Estimation App

## Overview

The application implements a multi-layered security approach combining password authentication, database encryption, and secure key management to protect sensitive business data.

## Authentication System

### 1. Password Management

#### Dual Password System
- **Primary Password**: Application access and database decryption
- **Secondary Password**: Data wipe trigger (emergency recovery). When used, the wipe runs in silent mode—no wipe-related logs are emitted and existing log files are purged alongside the encrypted database.

#### Password Storage
- Passwords never stored in plaintext
- Argon2 hashing algorithm (memory-hard, resistant to GPU attacks)
- Unique salt per password
- Hashes stored in the OS keyring via `silverestimate/security/credential_store.py` (legacy QSettings values are migrated on first launch)

#### Password Flow
```
User Input → Argon2 Hash → Compare with Stored Hash → Grant/Deny Access
                                                   → Derive Encryption Key
```

### 2. First-Run Setup
1. Prompt for primary and secondary passwords
2. Validate passwords are different
3. Generate hashes using Argon2
4. Persist hashed credentials via the credential store (Python `keyring` backend)
5. Create initial database with encryption

### 3. Authentication Process
```python
from silverestimate.security import credential_store

settings = get_app_settings()
main_hash = credential_store.get_password_hash("main", settings=settings, logger=logger)
backup_hash = credential_store.get_password_hash("backup", settings=settings, logger=logger)

if main_hash and backup_hash:
    entered_password = prompt_login()
    if verify_password(main_hash, entered_password):
        return SUCCESS
    if verify_password(backup_hash, entered_password):
        return TRIGGER_WIPE
    return FAILURE

setup_new_passwords()
```

## Database Encryption

### 1. Encryption Algorithm
- **Algorithm**: AES-256-GCM (Authenticated Encryption)
- **Key Size**: 256 bits
- **Nonce Size**: 12 bytes (per encryption operation)
- **Authentication Tag**: Included with ciphertext

### 2. Key Derivation
```python
def derive_key(password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=100000,  # Configurable
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))
```

### 3. Encryption Process
1. Generate random 12-byte nonce
2. Encrypt database content with AES-GCM
3. Store: nonce + ciphertext + tag
4. Save to disk as encrypted file

### 4. Decryption Process
1. Read nonce from file (first 12 bytes)
2. Read ciphertext (remaining bytes)
3. Decrypt using derived key
4. Verify authentication tag
5. Write to temporary file

## Key Management

### 1. Salt Generation and Storage
- **Generation**: `os.urandom(16)` - cryptographically secure
- **Storage**: QSettings with base64 encoding
- **Location**: Platform-specific secure storage
- **Uniqueness**: Per installation

### 2. Key Lifecycle
```
Password + Salt → PBKDF2 → Encryption Key → [Session Use] → Secure Disposal
```

### 3. Session Management
- Keys exist only in memory during runtime
- No key persistence between sessions
- Secure memory cleanup on exit

## Data Protection

### 1. At Rest
- Database file always encrypted on disk
- No plaintext data persistence
- Temporary files securely deleted

### 2. In Transit (Runtime)
- Temporary decrypted file with restricted permissions
- Automatic cleanup on application exit
- Crash-resistant cleanup mechanisms

### 3. Access Control
- Single-user model (current limitation)
- No granular permissions (future enhancement)
- All-or-nothing access model

## Security Mechanisms

### 1. Data Wipe Feature
```python
import logging
import os
from typing import Optional
from silverestimate.security import credential_store
from silverestimate.infrastructure.settings import get_app_settings

def perform_data_wipe(
    db_path: str,
    logger: Optional[logging.Logger] = None,
    *,
    silent: bool = False,
) -> bool:
    # 1. Delete encrypted database file
    if os.path.exists(db_path):
        os.remove(db_path)

    # 2. Remove encryption salt and temp artifacts
    settings = get_app_settings()
    for key in ("security/db_salt", "security/last_temp_db_path"):
        settings.remove(key)

    # 3. Clear password hashes from the secure store
    for kind in ("main", "backup"):
        credential_store.delete_password_hash(
            kind,
            settings=settings,
            logger=None if silent else logger,
        )

    # 4. Silent wipe clears logs without emitting signals
    if silent:
        _clear_log_artifacts()

    return True
```

### 2. Temporary File Security
- Created with restricted permissions
- Stored in system temp directory
- Securely wiped on shutdown (configurable recovery register via `settings.ENABLE_TEMP_DB_RECOVERY`)
- Crash recovery cleanup

### 3. Error Handling
- No sensitive data in error messages
- Secure logging practices
- Graceful degradation on failures

## Threat Model

### 1. Protected Against
- **Unauthorized Access**: Password protection
- **Data Theft**: File-level encryption
- **Memory Dumps**: Limited key lifetime
- **Brute Force**: Argon2 + high iteration count
- **Rainbow Tables**: Unique salts per installation

### 2. Current Limitations
- **Physical Access**: No protection against keyloggers
- **Memory Analysis**: Keys exist in memory during use
- **Multi-user**: No user separation
- **Network Attacks**: Local-only operation

### 3. Future Enhancements
- Hardware security module integration
- Two-factor authentication
- Role-based access control
- Audit logging

## Implementation Details

### 1. Password Hashing
```python
# Using passlib for Argon2
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(stored_hash, provided_password):
    return pwd_context.verify(provided_password, stored_hash)
```

### 2. Database Encryption
```python
class DatabaseManager:
    def _encrypt_db(self):
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)
        
        with open(self.temp_db_path, 'rb') as f_in:
            plaintext = f_in.read()
            
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        with open(self.encrypted_db_path, 'wb') as f_out:
            f_out.write(nonce)
            f_out.write(ciphertext)
```

### 3. Key Derivation
```python
def _derive_key(self, password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))
```

## Security Best Practices

### 1. Development
- Never log passwords or keys
- Use secure random for all crypto operations
- Validate all security-related inputs
- Regular security audits

### 2. Deployment
- Restrict file permissions
- Use secure temp directories
- Enable OS-level security features
- Regular security updates

### 3. Operations
- Regular password rotation
- Backup encryption keys separately
- Monitor for unauthorized access
- Incident response plan

## Compliance Considerations

### 1. Data Protection
- Encryption at rest (compliant)
- Access control (basic)
- Audit logging (future)
- Data retention policies (manual)

### 2. Security Standards
- NIST recommendations for key sizes
- OWASP guidelines for password storage
- Industry best practices for encryption

## Security Maintenance

### 1. Regular Tasks
- Update cryptographic libraries
- Review security logs
- Test backup/restore procedures
- Verify encryption integrity

### 2. Incident Response
- Data breach procedures
- Password reset protocol
- Emergency access methods
- Recovery procedures

### 3. Upgrades
- Key rotation strategy
- Algorithm migration plan
- Backward compatibility
- Security patch management
