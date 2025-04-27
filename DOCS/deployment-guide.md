# Deployment & Packaging Guide

## Packaging Overview

This guide covers the complete process of packaging the Silver Estimation App for distribution on different platforms, including executables, installers, and updates.

## PyInstaller Configuration

### 1. Basic Executable Creation

```bash
# Single-file executable with all dependencies
pyinstaller --onefile \
            --windowed \
            --name "SilverEstimate-v1.62" \
            --icon=app_icon.ico \
            --hidden-import=passlib.handlers.argon2 \
            --hidden-import=passlib.handlers.bcrypt \
            --hidden-import=cryptography \
            main.py
```

### 2. Advanced Spec File

```python
# silver_estimate.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('README.md', '.'),
        ('database/', 'database/'),
        ('resources/icons/', 'resources/icons/'),
    ],
    hiddenimports=[
        'passlib.handlers.argon2',
        'passlib.handlers.bcrypt',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.ciphers.aead',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SilverEstimate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
    version='version_info.txt'
)
```

### 3. Version Information File

```text
# version_info.txt
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 62, 0, 0),
    prodvers=(1, 62, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Silver Estimate App'),
        StringStruct(u'FileDescription', u'Silver Estimation and Management'),
        StringStruct(u'FileVersion', u'1.62.0.0'),
        StringStruct(u'InternalName', u'SilverEstimate'),
        StringStruct(u'LegalCopyright', u'© 2025 Silver Estimate App'),
        StringStruct(u'OriginalFilename', u'SilverEstimate.exe'),
        StringStruct(u'ProductName', u'Silver Estimation App'),
        StringStruct(u'ProductVersion', u'1.62.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
```

## Platform-Specific Packaging

### 1. Windows Installer (Inno Setup)

```iss
; silver_estimate.iss
[Setup]
AppName=Silver Estimation App
AppVersion=1.62
AppPublisher=Silver Estimate App
AppPublisherURL=https://example.com
DefaultDirName={commonpf}\SilverEstimate
DefaultGroupName=Silver Estimate
OutputBaseFilename=SilverEstimate_Setup_v1.62
Compression=lzma2
SolidCompression=yes
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\SilverEstimate.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\SilverEstimate.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "database\*"; DestDir: "{app}\database"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Silver Estimation App"; Filename: "{app}\SilverEstimate.exe"
Name: "{commondesktop}\Silver Estimation App"; Filename: "{app}\SilverEstimate.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SilverEstimate.exe"; Description: "{cm:LaunchProgram,Silver Estimation App}"; Flags: nowait postinstall skipifsilent
```

### 2. macOS App Bundle

```bash
# Create app bundle structure
mkdir -p SilverEstimate.app/Contents/{MacOS,Resources}

# Copy executable
cp dist/SilverEstimate SilverEstimate.app/Contents/MacOS/

# Create Info.plist
cat > SilverEstimate.app/Contents/Info.plist << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SilverEstimate</string>
    <key>CFBundleIdentifier</key>
    <string>com.silverestimate.app</string>
    <key>CFBundleName</key>
    <string>Silver Estimate</string>
    <key>CFBundleVersion</key>
    <string>1.62</string>
    <key>CFBundleShortVersionString</key>
    <string>1.62</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOL

# Sign the app (requires Apple Developer account)
codesign --deep --force --verify --verbose --sign "Developer ID Application" SilverEstimate.app

# Create DMG
hdiutil create -volname "Silver Estimate" -srcfolder SilverEstimate.app -ov -format UDZO SilverEstimate-v1.62.dmg
```

### 3. Linux AppImage

```bash
# Create AppDir structure
mkdir -p SilverEstimate.AppDir/usr/{bin,lib,share/icons}

# Copy files
cp dist/SilverEstimate SilverEstimate.AppDir/usr/bin/
cp app_icon.png SilverEstimate.AppDir/usr/share/icons/

# Create desktop entry
cat > SilverEstimate.AppDir/SilverEstimate.desktop << EOL
[Desktop Entry]
Name=Silver Estimate
Exec=SilverEstimate
Icon=app_icon
Type=Application
Categories=Office;Finance;
EOL

# Create AppRun script
cat > SilverEstimate.AppDir/AppRun << EOL
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/SilverEstimate" "$@"
EOL
chmod +x SilverEstimate.AppDir/AppRun

# Build AppImage
./appimagetool-x86_64.AppImage SilverEstimate.AppDir
```

## Dependency Management

### 1. Requirements File

```text
# requirements.txt
PyQt5==5.15.9
cryptography==41.0.0
passlib[argon2]==1.7.4
argon2_cffi==21.3.0
pyinstaller==5.13.0
pytest==7.4.0
pytest-qt==4.2.0
pytest-cov==4.1.0
```

### 2. Development Requirements

```text
# requirements-dev.txt
-r requirements.txt
black==23.7.0
pylint==2.17.0
mypy==1.4.0
pytest-xdist==3.3.0
coverage==7.2.0
```

### 3. Virtual Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

## Build Automation

### 1. Makefile

```makefile
# Makefile
.PHONY: clean build test package

VERSION=1.62
NAME=SilverEstimate

clean:
	rm -rf build dist *.spec __pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

test:
	pytest tests/ -v --cov=. --cov-report=html

lint:
	pylint *.py
	black --check .
	mypy .

build: clean
	pyinstaller --clean silver_estimate.spec

package-windows: build
	iscc installer/windows/silver_estimate.iss

package-mac: build
	./scripts/build_mac.sh

package-linux: build
	./scripts/build_linux.sh

all: test lint build package-windows package-mac package-linux
```

### 2. Build Scripts

```python
# build.py
import os
import sys
import shutil
import subprocess
from pathlib import Path

VERSION = "1.62"
APP_NAME = "SilverEstimate"

def clean_build():
    """Clean previous build artifacts."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # Clean .pyc files
    for ext in ['*.pyc', '*.pyo', '*.pyd']:
        for file in Path('.').rglob(ext):
            file.unlink()

def run_tests():
    """Run test suite."""
    result = subprocess.run(['pytest', 'tests/', '-v'])
    if result.returncode != 0:
        print("Tests failed. Aborting build.")
        sys.exit(1)

def build_executable():
    """Build the executable using PyInstaller."""
    cmd = [
        'pyinstaller',
        '--clean',
        '--onefile',
        '--windowed',
        '--name', f'{APP_NAME}-v{VERSION}',
        '--icon', 'resources/app_icon.ico',
        '--hidden-import', 'passlib.handlers.argon2',
        '--hidden-import', 'passlib.handlers.bcrypt',
        'main.py'
    ]
    
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Build failed.")
        sys.exit(1)

def create_installer():
    """Create platform-specific installer."""
    if sys.platform == 'win32':
        subprocess.run(['iscc', 'installer/windows/setup.iss'])
    elif sys.platform == 'darwin':
        subprocess.run(['./scripts/create_dmg.sh'])
    elif sys.platform.startswith('linux'):
        subprocess.run(['./scripts/create_appimage.sh'])

if __name__ == '__main__':
    clean_build()
    run_tests()
    build_executable()
    create_installer()
```

## Auto-Update System

### 1. Update Check Module

```python
# update_checker.py
import requests
import json
from packaging import version

class UpdateChecker:
    def __init__(self, current_version):
        self.current_version = current_version
        self.update_url = "https://api.silverestimate.com/updates/latest"
        
    def check_for_updates(self):
        """Check if updates are available."""
        try:
            response = requests.get(self.update_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data['version']
                
                if version.parse(latest_version) > version.parse(self.current_version):
                    return {
                        'available': True,
                        'version': latest_version,
                        'download_url': data['download_url'],
                        'release_notes': data['release_notes']
                    }
            return {'available': False}
        except Exception as e:
            print(f"Update check failed: {e}")
            return {'available': False, 'error': str(e)}
```

### 2. Update Dialog

```python
# update_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, 
                            QPushButton, QTextEdit, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import requests

class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        
    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(self.save_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress = int((downloaded / total_size) * 100)
                            self.progress.emit(progress)
            
            self.finished.emit(True, self.save_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class UpdateDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Update Available")
        layout = QVBoxLayout(self)
        
        # Version info
        version_label = QLabel(f"New version available: {self.update_info['version']}")
        layout.addWidget(version_label)
        
        # Release notes
        notes_label = QLabel("What's new:")
        layout.addWidget(notes_label)
        
        notes_text = QTextEdit()
        notes_text.setReadOnly(True)
        notes_text.setPlainText(self.update_info['release_notes'])
        layout.addWidget(notes_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        self.download_button = QPushButton("Download Update")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        
        self.close_button = QPushButton("Remind Me Later")
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.close_button)
```

## Environment Configuration

### 1. Development Environment

```ini
# config/development.ini
[app]
debug = true
log_level = DEBUG
database_path = database/test.db

[security]
iterations = 10000
salt_bytes = 16

[ui]
theme = default
font_family = Arial
font_size = 10
```

### 2. Production Environment

```ini
# config/production.ini
[app]
debug = false
log_level = INFO
database_path = database/estimation.db

[security]
iterations = 100000
salt_bytes = 16

[ui]
theme = default
font_family = Courier New
font_size = 9
```

### 3. Environment Manager

```python
# environment.py
import configparser
import os

class Environment:
    def __init__(self):
        self.env = os.getenv('APP_ENV', 'development')
        self.config = configparser.ConfigParser()
        self.load_config()
        
    def load_config(self):
        config_file = f'config/{self.env}.ini'
        if os.path.exists(config_file):
            self.config.read(config_file)
        else:
            raise FileNotFoundError(f"Config file not found: {config_file}")
    
    def get(self, section, key, default=None):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    @property
    def is_production(self):
        return self.env == 'production'
    
    @property
    def is_development(self):
        return self.env == 'development'
```

## Deployment Checklist

### 1. Pre-Deployment

- [ ] Update version numbers in all files
- [ ] Run full test suite
- [ ] Update documentation
- [ ] Check all dependencies
- [ ] Review error handling
- [ ] Test on clean environment
- [ ] Verify database migrations
- [ ] Check security settings

### 2. Build Process

- [ ] Clean build directories
- [ ] Run linters and type checkers
- [ ] Build executable
- [ ] Test executable on target platforms
- [ ] Create installers
- [ ] Sign executables/installers
- [ ] Generate checksums

### 3. Post-Deployment

- [ ] Test auto-update mechanism
- [ ] Verify installation on clean systems
- [ ] Monitor error reports
- [ ] Update documentation site
- [ ] Notify users of update
- [ ] Archive release artifacts
- [ ] Tag release in version control

## Release Management

### 1. Version Numbering

```text
MAJOR.MINOR.PATCH

MAJOR: Breaking changes
MINOR: New features, backward compatible
PATCH: Bug fixes, backward compatible
```

### 2. Release Branch Strategy

```bash
# Create release branch
git checkout -b release/v1.62

# Make release-specific changes
# Update version numbers, documentation

# Merge to main
git checkout main
git merge release/v1.62

# Tag release
git tag -a v1.62 -m "Release version 1.62"
git push origin v1.62
```

### 3. Changelog Generation

```python
# generate_changelog.py
import subprocess
from datetime import datetime

def generate_changelog(from_tag, to_tag='HEAD'):
    """Generate changelog from git commits."""
    cmd = f'git log {from_tag}..{to_tag} --pretty=format:"- %s (%h)"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    changelog = f"# Changelog\n\n## {to_tag} - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    changelog += result.stdout
    
    with open('CHANGELOG.md', 'w') as f:
        f.write(changelog)
```

## Distribution Channels

### 1. Direct Download
- Host on company website
- Provide checksums
- Include installation instructions

### 2. App Stores
- Microsoft Store (Windows)
- Mac App Store (macOS)
- Snapcraft/Flathub (Linux)

### 3. Enterprise Distribution
- MSI packages for Windows
- PKG for macOS
- DEB/RPM for Linux

## Support and Maintenance

### 1. Error Reporting

```python
# error_reporter.py
import traceback
import platform
import requests

class ErrorReporter:
    def __init__(self, api_endpoint):
        self.api_endpoint = api_endpoint
        
    def report_error(self, error):
        """Send error report to server."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error),
            'traceback': traceback.format_exc(),
            'platform': platform.platform(),
            'version': APP_VERSION,
            'python_version': platform.python_version()
        }
        
        try:
            requests.post(self.api_endpoint, json=report, timeout=5)
        except Exception:
            # Fail silently to avoid interrupting user
            pass
```

### 2. Analytics

```python
# analytics.py
class Analytics:
    def __init__(self, tracking_id):
        self.tracking_id = tracking_id
        
    def track_event(self, category, action, label=None, value=None):
        """Track user events (with user consent)."""
        # Implementation depends on analytics service
        pass
    
    def track_screen(self, screen_name):
        """Track screen views."""
        pass
```

### 3. Support Tools

```python
# support_tools.py
def generate_support_bundle():
    """Generate diagnostic information for support."""
    import zipfile
    import json
    
    bundle_data = {
        'system_info': {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'app_version': APP_VERSION
        },
        'logs': read_log_files(),
        'settings': get_app_settings(),
        'database_stats': get_db_statistics()
    }
    
    with zipfile.ZipFile('support_bundle.zip', 'w') as zf:
        zf.writestr('info.json', json.dumps(bundle_data, indent=2))
        # Add log files
        for log_file in get_log_files():
            zf.write(log_file)
```