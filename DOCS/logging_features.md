# Enhanced Logging Features for Silver Estimation App

## Overview

The Silver Estimation App now includes enhanced logging capabilities that provide better control over log management and automatic cleanup. These features help maintain system performance while ensuring important information is captured for troubleshooting.

## Features

### 1. Configurable Log Levels

You can now enable or disable specific log levels:

- **Normal Logs (INFO)**: Day-to-day application events and operations
- **Critical Logs (ERROR/CRITICAL)**: Error conditions and critical issues
- **Debug Logs**: Detailed diagnostic information (only when Debug Mode is enabled)

### 2. Automatic Log Cleanup

The application can automatically delete old log files to prevent disk space issues:

- Configure how many days to keep logs (1-365 days)
- Automatic cleanup runs at midnight each day
- Manual cleanup option available in settings

### 3. Debug Mode

Debug mode can be enabled to capture detailed diagnostic information:

- Provides comprehensive logging of application operations
- Useful for troubleshooting issues
- May slightly impact performance when enabled

## Configuration

All logging settings can be configured through the Settings dialog:

1. Open the application
2. Go to Tools → Settings
3. Select the "Logging" tab
4. Adjust settings as needed
5. Click "Apply" or "OK" to save changes

Changes to logging settings take effect immediately without requiring an application restart.

## Log Files

The application maintains several log files:

- **silver_app.log**: Normal application events (INFO level and above)
- **silver_app_error.log**: Error conditions and critical issues
- **silver_app_debug.log**: Detailed debug information (only when Debug Mode is enabled)

These files are stored in the `logs` directory within the application folder.

## Best Practices

- **For normal use**: Keep normal and critical logs enabled, with debug mode disabled
- **When troubleshooting**: Enable debug mode and all log levels
- **For long-term deployment**: Enable automatic cleanup with an appropriate retention period (7-30 days recommended)

## Technical Details

The logging system uses Python's standard logging module with custom handlers and formatters. Log rotation is handled automatically to prevent individual log files from growing too large.