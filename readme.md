# Silver Estimation App

## Overview

The Silver Estimation App is a comprehensive tool designed for silver jewelers and traders to manage silver item estimations, inventory, and silver bar tracking. It provides functionality for:

- Creating and managing silver item estimations
- Maintaining a catalog of silver items
- Tracking silver bar inventory
- Creating and managing silver bar lists for assignment and transfer
- Generating printable reports and estimates

## System Requirements

- Python 3.x
- PyQt5
- SQLite3

## Application Structure

The application follows a modular architecture with separate components for different functionalities:

### Main Application

- **main.py**: Entry point for the application with the main window setup

### Database Management

- **database_manager.py**: Handles all database operations using SQLite
  - Manages tables for items, estimates, silver bars, and silver bar lists
  - Provides methods for CRUD operations on all entities
  - Handles database schema setup and migrations

### Estimation Module

- **estimate_entry.py**: Widget for entering and managing silver estimations
- **estimate_entry_ui.py**: UI layout for the estimation widget
- **estimate_entry_logic.py**: Business logic for estimate calculations
- **estimate_history.py**: Dialog for viewing and managing past estimates

### Item Management

- **item_master.py**: Widget for managing the item catalog
- **item_selection_dialog.py**: Dialog for selecting items during estimate entry

### Silver Bar Management

- **silver_bar_management.py**: Dialog for managing silver bar inventory and lists

### Printing

- **print_manager.py**: Manages printing functionality for estimates and reports

## Database Schema

The application uses SQLite with the following main tables:

### items
- `code` (TEXT, PRIMARY KEY): Unique identifier for each item
- `name` (TEXT): Descriptive name
- `purity` (REAL): Default silver purity percentage (0-100)
- `wage_type` (TEXT): Wage calculation method ('P' for per piece, 'WT' for weight-based)
- `wage_rate` (REAL): Default wage rate

### estimates
- `voucher_no` (TEXT, PRIMARY KEY): Unique identifier for each estimate
- `date` (TEXT): Date of the estimate
- `silver_rate` (REAL): Silver rate used for calculations
- `total_gross` (REAL): Total gross weight
- `total_net` (REAL): Total net weight
- `total_fine` (REAL): Total net fine weight
- `total_wage` (REAL): Total net wage

### estimate_items
- `id` (INTEGER, PRIMARY KEY): Unique identifier
- `voucher_no` (TEXT): Reference to estimates table
- `item_code` (TEXT): Reference to items table
- `item_name` (TEXT): Item name
- `gross` (REAL): Gross weight
- `poly` (REAL): Poly/stone weight
- `net_wt` (REAL): Net weight (gross - poly)
- `purity` (REAL): Purity percentage
- `wage_rate` (REAL): Wage rate
- `pieces` (INTEGER): Number of pieces
- `wage` (REAL): Calculated wage
- `fine` (REAL): Fine weight
- `is_return` (INTEGER): Flag for return items (1 = return)
- `is_silver_bar` (INTEGER): Flag for silver bars (1 = silver bar)

### silver_bars
- `id` (INTEGER, PRIMARY KEY): Unique identifier
- `bar_no` (TEXT): Bar number
- `weight` (REAL): Bar weight
- `purity` (REAL): Purity percentage
- `fine_weight` (REAL): Fine weight (weight * purity/100)
- `date_added` (TEXT): Date added to inventory
- `status` (TEXT): Status ('In Stock', 'Assigned', 'Transferred', 'Sold', 'Melted')
- `list_id` (INTEGER): Reference to silver_bar_lists table

### silver_bar_lists
- `list_id` (INTEGER, PRIMARY KEY): Unique identifier
- `list_identifier` (TEXT): Human-readable identifier
- `creation_date` (TEXT): Creation date
- `list_note` (TEXT): Notes for the list

### bar_transfers
- `id` (INTEGER, PRIMARY KEY): Unique identifier
- `transfer_no` (TEXT): Transfer reference
- `date` (TEXT): Transfer date
- `bar_id` (INTEGER): Reference to silver_bars table
- `list_id` (INTEGER): Reference to silver_bar_lists table
- `from_status` (TEXT): Previous status
- `to_status` (TEXT): New status
- `notes` (TEXT): Transfer notes

## Features

### Estimate Entry
- Create new estimates with auto-generated voucher numbers
- Add items to estimates with automatic calculation of net weight, fine weight, and wage
- Support for regular items, return items, and silver bars in a single estimate
- Separate tracking of regular, return, and silver bar totals
- Net calculations automatically subtracting return items
- Save and load estimates

### Item Master
- Manage silver item catalog
- Define default purity and wage rates for items
- Search and filter items

### Silver Bar Management
- Add new silver bars to inventory
- Track bar status ('In Stock', 'Assigned', 'Transferred', 'Sold', 'Melted')
- Transfer bars between statuses
- Create lists of silver bars for tracking
- Assign and unassign bars to/from lists
- View detailed list contents

### Printing
- Print estimates in a traditional format
- Print silver bar inventory reports
- Print silver bar list details

## Calculations

### Weight Calculations
- Net Weight = Gross Weight - Poly Weight
- Fine Weight = Net Weight * (Purity / 100)
- Fine Value = Fine Weight * Silver Rate

### Wage Calculations
- Per Weight: Wage = Net Weight * Wage Rate
- Per Piece: Wage = Pieces * Wage Rate

### Net Calculations
- Net Fine = (Regular Fine + Bar Fine) - Return Fine
- Net Wage = (Regular Wage + Bar Wage) - Return Wage
- Net Value = Net Fine * Silver Rate

## Usage Guide

### Starting the Application
Run the application using:
```bash
python main.py
```

### Creating a New Estimate
1. Navigate to the Estimate Entry screen
2. The system generates a new voucher number automatically
3. Set the date and silver rate
4. Add items by entering item codes and weights
5. Toggle between regular, return, and silver bar modes as needed
6. Save the estimate when complete

### Managing Items
1. Navigate to the Item Master screen
2. Add new items with code, name, purity, wage type, and rate
3. Search for existing items to edit or delete

### Managing Silver Bars
1. Open Silver Bar Management from the Tools menu
2. Add new bars with bar number, weight, and purity
3. Select bars and transfer to different statuses
4. Create lists to group bars
5. View, edit, or delete existing lists

### Viewing Estimate History
1. Open Estimate History from the Reports menu
2. Filter by date range or voucher number
3. Select an estimate to load or print

## Project Notes

- The application uses a single SQLite database file ('database/estimation.db')
- The UI is built using PyQt5 with a custom style
- The application handles validation for numeric inputs
- The printing system uses HTML formatting with fixed-width fonts for estimates
- Silver bar lists provide a way to group and track collections of bars