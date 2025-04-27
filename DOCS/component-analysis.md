# Component Analysis - Silver Estimation App

## 1. Database Layer

### DatabaseManager (database_manager.py)

#### Responsibilities
- Database encryption/decryption
- Schema management and versioning
- CRUD operations for all entities
- Transaction management
- Temporary file handling

#### Key Methods
```python
# Encryption
- _encrypt_db(): Encrypts database to file
- _decrypt_db(): Decrypts to temporary file
- _derive_key(): Creates encryption key from password

# Schema Management
- setup_database(): Initializes/updates schema
- _check_schema_version(): Version control
- _update_schema_version(): Migration tracking

# Data Operations
- save_estimate_with_returns(): Complex save with multiple item types
- add_silver_bar(): Links bars to estimates
- delete_single_estimate(): Cascading deletion
```

#### Schema Structure
- **items**: Product catalog (code, name, purity, wage_type, wage_rate)
- **estimates**: Header records (voucher_no, date, silver_rate, totals)
- **estimate_items**: Line items with type flags
- **silver_bars**: Inventory tracking with estimate linkage
- **silver_bar_lists**: Grouping mechanism for bars
- **bar_transfers**: Movement history
- **schema_version**: Migration tracking

## 2. UI Components

### EstimateEntryWidget (estimate_entry.py)

#### Architecture
- Combines UI layout (EstimateUI) with business logic (EstimateLogic)
- Uses NumericDelegate for input validation
- Implements keyboard navigation

#### Key Features
- Multi-mode entry (Regular/Return/Silver Bar)
- Real-time calculations
- Cell navigation optimization
- Last balance tracking
- Print preview integration

### ItemMasterWidget (item_master.py)

#### Features
- Item CRUD operations
- Live search filtering
- Validation (purity limits, wage rates)
- Duplicate prevention
- Batch operations prevention

### SilverBarDialog (silver_bar_management.py)

#### Version 2.0 Features
- List-based bar organization
- Weight-based searching
- Transfer tracking
- Note management
- Print capabilities

## 3. Security Components

### LoginDialog (login_dialog.py)

#### Features
- Argon2 password hashing
- Dual password system
- First-run setup
- Data wipe functionality
- Reset/recovery options

### Encryption System

#### Implementation
- AES-GCM with 256-bit keys
- PBKDF2HMAC key derivation
- Random salt generation
- Nonce handling per encryption

## 4. Utility Components

### PrintManager (print_manager.py)

#### Capabilities
- Manual text formatting
- Indian rupee formatting
- Fixed-width layout
- Section-based totals
- HTML table generation for inventory

### Import/Export System

#### ItemImportManager
- Configurable parsing
- Delimiter detection
- Q-type conversion
- Adjustment factors
- Duplicate handling

#### ItemExportManager
- Pipe-delimited format
- Header consistency
- Batch processing

## 5. Dialog Components

### SettingsDialog
- Centralized configuration
- QTabWidget organization
- Print settings
- Security management
- Data operations

### CustomFontDialog
- Decimal font sizes
- Bold support
- Preview functionality
- Min/max constraints

## Component Interaction Patterns

### Data Flow
1. User input → UI widget
2. Validation via delegates
3. Logic processing
4. Database operations
5. Encryption/decryption
6. Storage/retrieval

### Event Handling
- Signal/slot connections
- Event filtering for navigation
- Cell change handlers
- Mode toggles

### State Management
- QSettings for persistence
- Mode flags (return/silver bar)
- Transaction control
- Session tracking
