# 🧾 Silver Estimation App — v1.71

A desktop application built using **PyQt5** and **SQLite** for managing silver sales estimates, including item-wise entries, silver bar inventory, returns, and print-ready formatted outputs.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)
![Version](https://img.shields.io/badge/version-v1.71-orange.svg)

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Security](#security)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

## 🎯 Overview

The Silver Estimation App is a comprehensive solution designed for silver shops to:
- Generate itemized silver estimates
- Track gross, net, and fine silver weights
- Manage silver bar inventory and returns
- Print formatted estimate slips
- Maintain secure, encrypted data storage
- Import/export item catalogs

## 🏗️ Architecture

The Silver Estimation App follows a modular, layered architecture designed for maintainability and security.

### System Components

```
┌─────────────────┐     ┌─────────────────────┐
│   PyQt5 UI      │◄──►│ EstimateEntryLogic   │
│   Components    │     │ Business Logic &    │
│      (Views)    │     │ Calculations        │
└─────────────────┘     └─────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐     ┌─────────────────────┐
│ DatabaseManager │◄──►│   Encrypted SQLite  │
│   Operations    │     │   Database         │
│ Encryption/CRUD │     │                    │
└─────────────────┘     └─────────────────────┘
         │
         ▼
┌─────────────────┐
│ Support Modules │
│ • PrintManager  │
│ • Settings      │
│ • Logger        │
│ • ItemManager   │
└─────────────────┘
```

### Key Design Principles
- **Separation of Concerns**: UI, business logic, and data access are cleanly separated
- **Security-First**: Multi-layered encryption with dual-password protection
- **Modular Design**: Components can be independently tested and maintained
- **Event-Driven**: Signal/slot pattern for responsive UI updates
- **Data Integrity**: Robust validation and transaction management

### Component Responsibilities
- **UI Layer**: Handles user interactions, data display, and navigation
- **Business Logic**: Processes calculations, validations, and workflow orchestration
- **Data Layer**: Provides secure, encrypted storage and retrieval operations
- **Support Layer**: Manages printing, configuration, logging, and integrations

For detailed architectural documentation, see [`DOCS/project-architecture.md`](DOCS/project-architecture.md).

## ✨ Features

### 💼 Core Functionality
- **Estimate Management**: Create, edit, and track silver estimates
- **Item Catalog**: Maintain a comprehensive database of silver items
- **Silver Bar Tracking**: Advanced inventory management with list-based organization
- **Return Processing**: Handle customer returns with proper accounting
- **Last Balance**: Track and include previous customer balances

### 🔒 Security
- **Database Encryption**: AES-256-GCM file-level encryption
- **Password Protection**: Argon2 hashing with dual-password system
- **Data Wipe**: Emergency data destruction capability
- **Secure Storage**: Protected QSettings for sensitive data

### 🖨️ Printing & Reporting
- **Formatted Estimates**: Professional print layouts with Indian rupee formatting
- **Silver Bar Reports**: Inventory lists and movement tracking
- **Print Preview**: Full preview with customizable settings
- **Custom Fonts**: Configurable printing fonts and sizes

### 🔄 Import/Export
- **Item Import**: Bulk import from delimited files
- **Export Capability**: Generate item catalogs for backup
- **Format Flexibility**: Support for multiple delimiters
- **Duplicate Handling**: Smart conflict resolution

### 💻 User Interface
- **Keyboard Navigation**: Efficient data entry shortcuts
- **Real-time Calculations**: Instant totals and validations
- **Status Feedback**: Comprehensive status bar messages
- **Mode Indicators**: Clear visual cues for operation modes

## 📸 Screenshots

*Note: Add screenshots of your application here*

```
[Main Estimate Entry Screen]
[Item Master Screen]
[Silver Bar Management]
[Print Preview]
```

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Windows/Linux/macOS operating system

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/silver-estimation-app.git
   cd silver-estimation-app
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

### Building Executable

To create a standalone executable, prefer building with the provided spec (includes required hidden imports for Passlib/Argon2). The output file name includes the app version from `app_constants.py` (e.g., `dist/SilverEstimate-v1.71.exe`).

**Recommended Build Method:**
```bash
pyinstaller --clean silverestimate.spec
```

**Alternative Build (Quick Test):**
```bash
pyinstaller --onefile --windowed --name "SilverEstimate" \
  --hidden-import=passlib.handlers.argon2 \
  --hidden-import=passlib.handlers.bcrypt \
  --hidden-import=passlib \
  --icon=icon.ico \
  --version-file=version.info \
  main.py
```

**Automated Windows Build:**
```bash
# Using provided PowerShell script
pwsh scripts/build_windows.ps1
# Output: dist/ and zip file with current version
```

**Common Build Issues:**
- Ensure Argon2 backend is installed: `pip install "passlib[argon2]" argon2_cffi`
- For Windows: Use PowerShell, not Command Prompt for the script
- Clean dist/ folder before rebuilding

For detailed build and packaging instructions, see [`DOCS/deployment-guide.md`](DOCS/deployment-guide.md).

## 📖 Usage

### First Run
1. Launch the application
2. Create your primary and secondary passwords
3. The database will be initialized automatically

### Creating an Estimate
1. Click "Generate" for a new voucher number
2. Enter item codes or search for items
3. Input weights and adjust values as needed
4. Save to create silver bars (if applicable)
5. Print preview opens automatically

### Managing Silver Bars
1. Access via Tools → Silver Bar Management
2. Create lists to organize bars
3. Assign/unassign bars to lists
4. Track bar movements and status

### Importing Items
1. Tools → Settings → Import/Export
2. Select your file (CSV, TSV, etc.) and configure parsing options
3. Preview imported data with validation feedback
4. Choose duplicate handling strategy (skip/update/overwrite)
5. Execute import with progress tracking

### Managing Inventory
1. Add items via Item Master (Tools → Item Master)
2. Search, filter, and organize item catalog
3. Update prices and specifications as needed
4. Export catalogs for backup or sharing

### Processing Returns
1. Use return mode (LB button changes to return mode)
2. Input negative quantities for returned items
3. System automatically adjusts silver bar calculations
4. Print adjusted estimate with proper formatting

For detailed workflow guides, see [`DOCS/workflow-business-logic.md`](DOCS/workflow-business-logic.md).

## 🔐 Security

### Password System
- **Primary Password**: Regular application access
- **Secondary Password**: Triggers data wipe when used

### Encryption
- Database file is encrypted at rest
- Temporary decrypted file during runtime only
- Automatic cleanup on application exit

### Data Protection
- Secure key derivation (PBKDF2) with AES-256-GCM encryption
- Unique salt per installation with Argon2 password hashing
- No plaintext password storage and secure temporary file management

For detailed security architecture, see [`DOCS/security-architecture.md`](DOCS/security-architecture.md).

## 📝 Logging & Error Handling

### Logging System
- **Structured Logging**: Comprehensive logging system replacing print() statements
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR, and CRITICAL levels
- **Selective Log Levels**: Ability to enable/disable specific log levels individually
- **File Rotation**: Size-based log rotation (5–10MB) with archived backups
- **Automatic Cleanup**: Configurable daily deletion of old log files (1–365 days retention)
- **PyQt5 Integration**: Qt message redirection, status bar logging, and UI event tracking
- **Security-Focused**: Automatic sanitization of sensitive data and environment variable overrides
- **Multi-File Streams**: Separate logs for main events, errors, and debug information
- **Performance Optimization**: Options to disable verbose logging in production environments

### Log Files
- **Main Log**: General application events (INFO and above)
- **Error Log**: Application errors (ERROR and CRITICAL only)
- **Debug Log**: Detailed troubleshooting information (when debug mode enabled)

### Error Handling
- **Context Managers**: Specialized handlers for database operations
- **Enhanced Exceptions**: Proper exception handling with detailed context
- **User Feedback**: Clear error messages with appropriate detail levels

### Log Management
- **Settings UI**: Dedicated logging configuration tab in Settings dialog
- **Performance Optimization**: Options to disable verbose logging in production
- **Disk Space Management**: Automatic and manual cleanup options

For detailed information, see the [`logging-system-technical-guide.md`](DOCS/logging-system-technical-guide.md).

## ⚙️ Configuration

### Application Settings

Settings are stored securely in QSettings and include:

**Print Configuration:**
- Font family and size for estimate printing
- Page margins (top, bottom, left, right in mm)
- Print preview zoom level and display options
- Custom number formatting and currency display

**UI Configuration:**
- Table font sizes for optimal readability
- Keyboard shortcut preferences
- Status bar display options
- Mode indicator styling

**Logging Configuration:**
- Log level settings (INFO, ERROR, DEBUG independently)
- Automatic log rotation and cleanup settings
- Custom log directory paths
- Performance optimization toggles

**Data Management:**
- Import/export delimiter preferences
- Duplicate handling strategies
- Backup location settings

Access via: **Tools → Settings** (organized in tabs for easy navigation)

### Environment Variables
```bash
APP_ENV=development                    # or production
SILVER_APP_DEBUG=true                  # Enable debug logging
SILVER_APP_LOG_DIR=logs                # Custom log directory path
SILVER_APP_ENCRYPTION_KEY=custom_key   # Advanced: Override default encryption (use with caution)
SILVER_APP_AUTO_BACKUP=true           # Enable automatic backups
```

For detailed configuration options, see [`DOCS/api-reference.md`](DOCS/api-reference.md).

## 👩‍💻 Development

### Project Structure
```
silver-estimation-app/
│
├── 📁 Core Modules
│   ├── main.py                 # Application entry point & UI initialization
│   ├── estimate_entry.py       # Main estimate widget and workflow
│   ├── estimate_entry_ui.py    # UI components and event handling
│   ├── estimate_entry_logic.py # Business logic and calculations
│   └── database_manager.py     # Database operations & encryption
│
├── 📁 Supporting Modules
│   ├── print_manager.py        # Print functionality & templates
│   ├── logger.py              # Comprehensive logging system
│   ├── item_master.py         # Item catalog management
│   ├── settings_dialog.py     # Application configuration UI
│   ├── login_dialog.py        # Authentication interface
│   └── message_bar.py         # Status messaging system
│
├── 📁 Advanced Features
│   ├── silver_bar_management.py    # Silver bar inventory tracking
│   ├── item_import_manager.py     # Bulk data import utilities
│   ├── estimate_history.py        # Historical data viewer
│   ├── item_export_manager.py     # Data export functionality
│   └── item_selection_dialog.py   # Item selection interface
│
├── 📁 Configuration & Assets
│   ├── requirements.txt       # Python dependencies
│   ├── app_constants.py       # Application constants & versioning
│   ├── silverestimate.spec    # PyInstaller build specification
│   └── fonts/                 # Custom font resources
│
├── 📁 Documentation
│   ├── readme.md              # This file
│   ├── CHANGELOG.md           # Version history & release notes
│   ├── DOCS/                  # Detailed documentation library
│   └── logging_features.md    # Logging system documentation
│
├── 📁 Scripts & Build
│   ├── scripts/
│   │   └── build_windows.ps1  # Windows build automation
│   ├── .git/                  # Version control
│   └── database/              # Database files & schemas
│
└── 📁 Development & Testing
    ├── test files...          # Test suite (when available)
    └── .claude/               # AI assistance workspace
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where possible
- Document all public methods
- Write comprehensive docstrings

### Adding Features
1. Create feature branch
2. Implement with tests
3. Update documentation
4. Submit pull request

## 🧪 Testing

Run the test suite:
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. tests/

# Run specific test
pytest tests/test_database.py
```

## 📦 Deployment

### Creating a Release
1. Update version numbers in `app_constants.py` and README.md
2. Run full test suite: `pytest --cov=.` for coverage
3. Build executables for all platforms
4. Generate and update changelog based on commit history
5. Tag release in git and create GitHub release
6. Upload assets to release and update distribution channels

### Build Targets

**Windows:**
- PyInstaller onefile executable (.exe)
- PowerShell automation script for consistent builds
- Inno Setup installer for enterprise deployment
- Automated CI builds via GitHub Actions

**Cross-Platform Support:**
- macOS: .app bundle with codesigning and notarization
- Linux: AppImage for distribution independence
- Docker containers for development and testing

### Distribution Channels
- **GitHub Releases**: Direct download with release notes
- **Enterprise Distribution**: MSI/EXE installers with certificate
- **Package Managers**: Future consideration for winget/choco/scoop
- **Cloud Distribution**: Automated CDN deployment via CI/CD

### CI/CD Pipeline
- Automated builds on push to main branch
- Multi-platform testing and deployment
- Integration with issue tracking and milestones
- Automated version tagging and changelog generation

For comprehensive deployment documentation, see [`DOCS/deployment-guide.md`](DOCS/deployment-guide.md).

## 🤝 Contributing

1. Fork the repository
2. Set up development environment (see Installation section)
3. Create feature branch (`git checkout -b feature/amazing-feature`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a pull request

**Development Resources:**
- Code style: PEP 8 with type hints
- Testing: Write tests for new features
- Documentation: Update DOCS/ files during development

For detailed contributing guidelines, see [`DOCS/project-summary.md`](DOCS/project-summary.md).

## 📞 Support

For support and troubleshooting:
- **GitHub Issues**: Open detailed reports for bugs and features
- **Documentation**: Comprehensive guides in [`DOCS/`](DOCS/) folder
- **Email**: support@silverestimate.com
- **Community Resources**: Online documentation and tutorials

**Troubleshooting Resources:**
- [Common issues and solutions](`DOCS/troubleshooting-maintenance.md`)
- [Performance optimization tips](`DOCS/performance-optimization.md`)
- [Detailed changelog](CHANGELOG.md)

## 📄 License

This project is proprietary software. All rights reserved.

© 2023-2025 Silver Estimation App

---

## 🔄 Version History

### v1.71 (Current)
- Comprehensive README updates with enhanced documentation structure
- Expanded logging system integration and security documentation
- Added architectural diagrams and project structure enhancements
- Improved installation details and deployment guides
- Enhanced cross-references to detailed documentation in DOCS/ folder
- Feature consistency fixes and expanded configuration options

### v1.70 (2025-09-06)
- Enhanced tooltips system with comprehensive help and format guidance
- Mode button visual enhancement with distinct color schemes (blue for Return, orange for Silver Bar)
- Improved status bar integration and message routing
- Updated version to v1.70 and prepared for executable build

### v1.69 (2025-09-05)
- Refined status messages with inline display in header area
- Improved startup messaging and message bar management
- Rebuilt executable as v1.69 with Git tag and release
- Updated dependency management and logging configuration

### v1.62 (2025-08)
- Added import/export functionality with bulk data handling
- Improved error handling and user feedback
- Enhanced UI responsiveness and keyboard navigation

### v1.61 (2025-07)
- Implemented full database encryption with AES-256-GCM
- Added dual-password system with Argon2 hashing
- Comprehensive security enhancements and data protection

### v1.52 (2025-04)
- Added estimate notes feature with print integration
- Improved silver bar management with list-based organization
- Major UI/UX improvements and user experience refinements

[See full changelog](CHANGELOG.md)

### Build Locally (Windows)
- Prereqs: Python 3.11+, PowerShell, internet access.
- Run: `pwsh scripts/build_windows.ps1`
- Output: `dist/SilverEstimate-vX.YY-win64.zip` and `dist/SilverEstimate/` folder.

### GitHub Release (CI)
- Tag the version and push:
  - Update `app_constants.py:APP_VERSION`.
  - `git commit -am "chore: bump version to vX.YY"`
  - `git tag vX.YY`
  - `git push origin main --tags`
- The workflow `.github/workflows/release-windows.yml` builds the Windows zip and attaches it to the GitHub Release automatically.

---

## 🙏 Acknowledgments

- PyQt5 framework
- SQLite database engine
- Cryptography library
- All contributors and testers

---

**Note**: For AI systems working with this codebase, please refer to [`DOCS/ai-readme.md`](DOCS/ai-readme.md) for structured navigation and analysis entry points.
