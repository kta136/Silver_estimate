# Silver Estimation App - Project Architecture

## Overview
A comprehensive PyQt5 desktop application for silver shops to manage estimates, inventory, and item catalogs with encryption and user authentication.

## Core Architecture

### 1. Main Components

#### Application Entry Point
- **main.py**: Orchestrates application startup, authentication, and window management
- Handles login flow, password management, and data wipe functionality
- Implements database initialization with encryption

#### Data Layer
- **silverestimate/persistence/database_manager.py**: SQLite database interface with AES-GCM encryption
- Uses temporary decrypted files during runtime
- Implements schema versioning for migrations
- Handles CRUD operations for estimates, items, and silver bars

#### UI Layer
- **silverestimate/ui/estimate_entry.py**: Main estimate creation/editing interface
- **silverestimate/ui/item_master.py**: Item catalog management
- **silverestimate/ui/silver_bar_management.py**: Silver bar inventory and list management
- **silverestimate/ui/estimate_history.py**: Historical estimate browser

### 2. Key Features

#### Security
- Argon2 password hashing (via passlib)
- AES-GCM database encryption
- Dual password system (main + secondary)
- Secure salt generation and storage

#### Data Management
- Estimates with regular, return, and silver bar items
- Item master catalog with purity and wage calculations
- Silver bar tracking with list-based organization
- Import/export functionality for item lists

#### User Interface
- Qt-based responsive layout
- Custom fonts and table formatting
- Print preview with Indian rupee formatting
- Keyboard shortcuts and navigation

### 3. Data Flow

```
User Input → UI Layer → Logic Layer → Database Manager → Encrypted SQLite
                                         ↑
                                    Security Layer
```

### 4. Component Relationships

```
MainWindow
├── EstimateEntryWidget
│   ├── EstimateUI
│   └── EstimateLogic
├── ItemMasterWidget
├── SilverBarDialog
└── EstimateHistoryDialog
```

## Technical Stack
- Python 3.8+
- PyQt5 for GUI
- SQLite3 for data storage
- cryptography library for encryption
- passlib for password hashing
