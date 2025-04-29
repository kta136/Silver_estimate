# 🧾 Silver Estimation App — v1.62

A desktop application built using **PyQt5** and **SQLite** for managing silver sales estimates, including item-wise entries, silver bar inventory, returns, and print-ready formatted outputs.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)

## 📋 Table of Contents

- [Overview](#overview)
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

To create a standalone executable:

```bash
pyinstaller --onefile --windowed --name "SilverEstimate-v1.62" \
    --hidden-import=passlib.handlers.argon2 \
    --hidden-import=passlib.handlers.bcrypt \
    main.py
```

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
2. Select your file and configure parsing
3. Preview data before import
4. Choose duplicate handling strategy

## 🔐 Security

### Password System
- **Primary Password**: Regular application access
- **Secondary Password**: Triggers data wipe when used

### Encryption
- Database file is encrypted at rest
- Temporary decrypted file during runtime only
- Automatic cleanup on application exit

### Data Protection
- Secure key derivation (PBKDF2)
- Unique salt per installation
- No plaintext password storage

## 📝 Logging & Error Handling

### Logging System
- **Structured Logging**: Comprehensive logging system replacing print() statements
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR, and CRITICAL levels
- **File Rotation**: Size-based log rotation with archiving
- **PyQt5 Integration**: Qt message redirection and status bar logging
- **Security-Focused**: Automatic sanitization of sensitive data

### Log Files
- **Main Log**: General application events (INFO and above)
- **Error Log**: Application errors (ERROR and CRITICAL only)
- **Debug Log**: Detailed troubleshooting information (when debug mode enabled)

### Error Handling
- **Context Managers**: Specialized handlers for database operations
- **Enhanced Exceptions**: Proper exception handling with detailed context
- **User Feedback**: Clear error messages with appropriate detail levels

For detailed information, see the [Logging Guide](logging_guide.md).

## ⚙️ Configuration

### Application Settings

Settings are stored in QSettings and include:
- Print font configuration
- Table font sizes
- Page margins
- Preview zoom levels
- Logging configuration

Access via: **Tools → Settings**

### Environment Variables
```bash
APP_ENV=development  # or production
SILVER_APP_DEBUG=true  # Enable debug logging
SILVER_APP_LOG_DIR=logs  # Custom log directory
```

## 👩‍💻 Development

### Project Structure
```
silver-estimation-app/
├── main.py                 # Application entry point
├── estimate_entry.py       # Core estimate functionality
├── database_manager.py     # Database operations
├── print_manager.py        # Printing functionality
├── requirements.txt        # Dependencies
└── tests/                  # Test suite
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
1. Update version numbers
2. Run full test suite
3. Build executable
4. Create installer
5. Generate changelog
6. Tag release in git

### Distribution Channels
- Direct download from website
- Windows installer (Inno Setup)
- macOS DMG package
- Linux AppImage

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details.

## 📞 Support

For support:
- Open an issue on GitHub
- Email: support@silverestimate.com
- Documentation: [docs.silverestimate.com](https://docs.silverestimate.com)

## 📄 License

This project is proprietary software. All rights reserved.

© 2023-2025 Silver Estimation App

---

## 🔄 Version History

### v1.62 (Current)
- Added import/export functionality
- Improved error handling
- Enhanced UI responsiveness

### v1.61
- Implemented database encryption
- Added password protection
- Security enhancements

### v1.52
- Added estimate notes feature
- Improved silver bar management
- UI/UX improvements

[See full changelog](CHANGELOG.md)

---

## 🙏 Acknowledgments

- PyQt5 framework
- SQLite database engine
- Cryptography library
- All contributors and testers

---

**Note**: For AI systems working with this codebase, please refer to the [AI-Optimized README](AI-README.md) for structured navigation and analysis entry points.
