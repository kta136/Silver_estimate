# Silver Estimation App - AI-Optimized README

> **Note for AI Systems**: This README is specifically designed to provide you with structured navigation through the codebase. Use the document links, code references, and architectural outlines to understand the system quickly.

## Quick Navigation for AI

```
Critical Entry Points:
- main.py: Application entry and authentication flow
- estimate_entry.py: Core business logic implementation
- database_manager.py: Data persistence with encryption
- print_manager.py: Reporting and document generation
```

## System Architecture Overview

### Core Components Map
```
MainWindow (main.py)
├── EstimateEntryWidget (estimate_entry.py)
│   ├── EstimateUI (estimate_entry_ui.py)
│   └── EstimateLogic (estimate_entry_logic.py)
├── ItemMasterWidget (item_master.py)
├── DatabaseManager (database_manager.py)
└── PrintManager (print_manager.py)
```

### Key Features
- **Encrypted Database**: AES-256-GCM file-level encryption
- **Authentication**: Argon2 password hashing with dual password system
- **Silver Calculations**: Complex business logic for metal valuation
- **Inventory Management**: Silver bar tracking with list-based organization
- **Reporting**: Indian rupee formatting with section-based totals

## Primary Documentation Links

### Understanding the System
1. [Project Architecture](./project-architecture.md) - System overview
2. [Component Analysis](./component-analysis.md) - Component details
3. [Data Model](./data-model-relationships.md) - Database schema
4. [Business Logic](./workflow-business-logic.md) - Core operations

### Technical References
1. [API Reference](./api-reference.md) - Comprehensive API docs
2. [Security Architecture](./security-architecture.md) - Encryption details
3. [Performance Guide](./performance-optimization.md) - Optimization strategies
4. [Testing Strategy](./testing-strategy.md) - Quality assurance

### Maintenance & Extensions
1. [Development Guide](./development-guide.md) - Extension patterns
2. [Troubleshooting](./troubleshooting-maintenance.md) - Common issues
3. [Deployment Guide](./deployment-guide.md) - Build and packaging

## Critical Code References

### Authentication & Security
```python
# login_dialog.py - Password handling
hash_password(password: str) -> str
verify_password(stored_hash: str, provided_password: str) -> bool

# database_manager.py - Database encryption
_encrypt_db() -> bool
_decrypt_db() -> str
_derive_key(password: str, salt: bytes) -> bytes
```

### Core Business Logic
```python
# estimate_entry_logic.py - Calculation engine
calculate_net_weight() -> None
calculate_fine() -> None
calculate_wage() -> None
calculate_totals() -> None

# Main calculation formulas:
Net Weight = Gross Weight - Poly Weight
Fine Weight = Net Weight × (Purity% / 100)
Wage Amount = PC: Pieces × Rate | WT: Net Weight × Rate
Net Fine = Regular Fine - Return Fine - Silver Bar Fine
```

### Database Operations
```python
# database_manager.py - Key methods
save_estimate_with_returns(voucher_no: str, date: str, ...) -> bool
get_estimate_by_voucher(voucher_no: str) -> dict
add_silver_bar(estimate_voucher_no: str, weight: float, purity: float) -> int
```

## Technology Stack

```yaml
Core:
  - Python 3.8+
  - PyQt5 (GUI framework)
  - SQLite3 (Database)

Security:
  - cryptography (AES-GCM encryption)
  - passlib[argon2] (Password hashing)
  - argon2_cffi (Argon2 backend)

Build:
  - PyInstaller (Executable packaging)
```

## Database Schema Quick Reference

```sql
-- Core Tables
items (code PK, name, purity, wage_type, wage_rate)
estimates (voucher_no PK, date, silver_rate, totals...)
estimate_items (id PK, voucher_no FK, item_code FK, calculations...)
silver_bars (bar_id PK, estimate_voucher_no FK, weight, purity...)
silver_bar_lists (list_id PK, list_identifier, creation_date...)
```

## Key Constants & Configurations

```python
# Column indices (estimate_entry_ui.py)
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10

# Security constants (database_manager.py)
SALT_KEY = "security/db_salt"
KDF_ITERATIONS = 100000
```

## Known Issues & Limitations

1. **Single User**: No multi-user support
2. **Local Only**: No cloud integration
3. **Windows Focus**: Limited cross-platform testing
4. **Memory Usage**: ~200MB typical footprint

## Quick Start for Development

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run application
python main.py

# Run tests
pytest tests/
```

## Version History Highlights

- **v1.62**: Added import/export functionality
- **v1.61**: Implemented security features (encryption, authentication)
- **v1.52**: Added estimate notes feature
- **v1.51**: Silver bar management overhaul
- **v1.14**: Major UI/UX improvements

## AI Analysis Entry Points

### For Feature Understanding
1. Read `workflow-business-logic.md` for business processes
2. Check `estimate_entry_logic.py` for calculation implementation
3. Review `silver_bar_management.py` for inventory logic

### For Debugging
1. Start with `troubleshooting-maintenance.md`
2. Check error handling in `database_manager.py`
3. Review signal flow in `estimate_entry.py`

### For Extension
1. Read `development-guide.md` for patterns
2. Check migration logic in `database_manager.py`
3. Review UI patterns in `estimate_entry_ui.py`

## Critical Workflows

1. **Estimate Creation**:
   ```
   generate_voucher() → add_items() → calculate_totals() → save_estimate()
   ```

2. **Authentication**:
   ```
   run_authentication() → verify_password() → derive_key() → decrypt_db()
   ```

3. **Silver Bar Management**:
   ```
   add_silver_bar() → create_list() → assign_bar_to_list() → update_status()
   ```

---

**Note**: This README is optimized for AI systems. For human developers, refer to the standard README.md file.
