# Data Model & Relationships - Silver Estimation App

## Database Schema Relationships

### Entity Relationship Diagram (Conceptual)

```
estimates (1) ----< (M) estimate_items
estimates (1) ----< (M) silver_bars
items (1) ----< (M) estimate_items
silver_bars (M) >---- (1) silver_bar_lists
silver_bars (1) ----< (M) bar_transfers
```

## Core Tables

### 1. items
**Purpose**: Master catalog of silver items

| Column     | Type    | Constraints        | Description              |
|------------|---------|-------------------|--------------------------|
| code       | TEXT    | PRIMARY KEY       | Unique item identifier   |
| name       | TEXT    | NOT NULL          | Item description         |
| purity     | REAL    | DEFAULT 0         | Silver purity %          |
| wage_type  | TEXT    | DEFAULT 'P'       | 'PC' or 'WT'            |
| wage_rate  | REAL    | DEFAULT 0         | Rate per piece/weight    |

### 2. estimates
**Purpose**: Estimate header records

| Column              | Type    | Constraints        | Description                |
|--------------------|---------|-------------------|----------------------------|
| voucher_no         | TEXT    | PRIMARY KEY       | Unique estimate ID         |
| date               | TEXT    | NOT NULL          | Estimate date              |
| silver_rate        | REAL    | DEFAULT 0         | Current silver rate        |
| total_gross        | REAL    | DEFAULT 0         | Gross weight total         |
| total_net          | REAL    | DEFAULT 0         | Net weight total           |
| total_fine         | REAL    | DEFAULT 0         | Fine silver total          |
| total_wage         | REAL    | DEFAULT 0         | Total wage amount          |
| note               | TEXT    |                   | Optional note              |
| last_balance_silver| REAL    | DEFAULT 0         | Previous balance (silver)  |
| last_balance_amount| REAL    | DEFAULT 0         | Previous balance (amount)  |

### 3. estimate_items
**Purpose**: Line items for estimates

| Column      | Type    | Constraints                           | Description         |
|-------------|---------|---------------------------------------|---------------------|
| id          | INTEGER | PRIMARY KEY AUTOINCREMENT             | Unique ID           |
| voucher_no  | TEXT    | FOREIGN KEY → estimates ON DELETE CASCADE | Parent estimate   |
| item_code   | TEXT    | FOREIGN KEY → items ON DELETE SET NULL    | Item reference    |
| item_name   | TEXT    |                                       | Item description    |
| gross       | REAL    | DEFAULT 0                             | Gross weight        |
| poly        | REAL    | DEFAULT 0                             | Poly/stone weight   |
| net_wt      | REAL    | DEFAULT 0                             | Net weight          |
| purity      | REAL    | DEFAULT 0                             | Purity %            |
| wage_rate   | REAL    | DEFAULT 0                             | Applied rate        |
| pieces      | INTEGER | DEFAULT 1                             | Quantity            |
| wage        | REAL    | DEFAULT 0                             | Wage amount         |
| fine        | REAL    | DEFAULT 0                             | Fine silver weight  |
| is_return   | INTEGER | DEFAULT 0                             | Return flag         |
| is_silver_bar| INTEGER| DEFAULT 0                             | Silver bar flag     |

### 4. silver_bars
**Purpose**: Silver bar inventory tracking

| Column             | Type    | Constraints                              | Description          |
|-------------------|---------|------------------------------------------|----------------------|
| bar_id            | INTEGER | PRIMARY KEY AUTOINCREMENT                | Unique bar ID        |
| estimate_voucher_no| TEXT   | FOREIGN KEY → estimates ON DELETE CASCADE | Source estimate      |
| weight            | REAL    | DEFAULT 0                                | Bar weight           |
| purity            | REAL    | DEFAULT 0                                | Bar purity           |
| fine_weight       | REAL    | DEFAULT 0                                | Fine silver content  |
| date_added        | TEXT    |                                          | Creation timestamp   |
| status            | TEXT    | DEFAULT 'In Stock'                       | Current status       |
| list_id           | INTEGER | FOREIGN KEY → silver_bar_lists ON DELETE SET NULL | Assigned list |

### 5. silver_bar_lists
**Purpose**: Grouping mechanism for silver bars

| Column         | Type    | Constraints                | Description           |
|----------------|---------|---------------------------|-----------------------|
| list_id        | INTEGER | PRIMARY KEY AUTOINCREMENT  | Unique list ID        |
| list_identifier| TEXT    | UNIQUE NOT NULL           | Human-readable ID     |
| creation_date  | TEXT    | NOT NULL                  | Creation timestamp    |
| list_note      | TEXT    |                           | Optional description  |

### 6. bar_transfers
**Purpose**: Silver bar movement history

| Column        | Type    | Constraints                               | Description         |
|---------------|---------|-------------------------------------------|---------------------|
| id            | INTEGER | PRIMARY KEY AUTOINCREMENT                 | Unique transfer ID  |
| transfer_no   | TEXT    |                                           | Transfer reference  |
| date          | TEXT    |                                           | Transfer timestamp  |
| silver_bar_id | INTEGER | FOREIGN KEY → silver_bars ON DELETE CASCADE | Bar reference      |
| list_id       | INTEGER | FOREIGN KEY → silver_bar_lists ON DELETE SET NULL | List reference |
| from_status   | TEXT    |                                           | Previous status     |
| to_status     | TEXT    |                                           | New status          |
| notes         | TEXT    |                                           | Transfer notes      |

### 7. schema_version
**Purpose**: Database migration tracking

| Column       | Type    | Constraints        | Description           |
|--------------|---------|-------------------|-----------------------|
| id           | INTEGER | PRIMARY KEY       | Version ID            |
| version      | INTEGER | NOT NULL          | Schema version number |
| applied_date | TEXT    | NOT NULL          | Migration timestamp   |

## Data Relationships & Cascading Rules

### 1. Estimates → Estimate Items
- **Relationship**: One-to-Many
- **Cascade**: DELETE CASCADE
- **Behavior**: Deleting an estimate removes all its items

### 2. Items → Estimate Items
- **Relationship**: One-to-Many
- **Cascade**: ON DELETE SET NULL
- **Behavior**: Deleting an item leaves references as NULL

### 3. Estimates → Silver Bars
- **Relationship**: One-to-Many
- **Cascade**: DELETE CASCADE
- **Behavior**: Deleting an estimate removes its silver bars

### 4. Silver Bar Lists → Silver Bars
- **Relationship**: One-to-Many
- **Cascade**: ON DELETE SET NULL
- **Behavior**: Deleting a list unassigns bars but keeps them

### 5. Silver Bars → Bar Transfers
- **Relationship**: One-to-Many
- **Cascade**: DELETE CASCADE
- **Behavior**: Deleting a bar removes its transfer history

## Data Integrity Rules

1. **Item Codes**: Must be unique, uppercase
2. **Voucher Numbers**: Sequential, numeric
3. **Silver Bars**: Created only on first estimate save
4. **Calculations**: Net = Gross - Poly, Fine = Net × (Purity/100)
5. **Wage Types**: PC (per piece) or WT (per weight)
6. **Status Values**: 'In Stock', 'Assigned', 'Sold', 'Melted'

## Schema Evolution

### Version 0 → 1
- Added silver_bars table with new structure
- Added silver_bar_lists table
- Modified bar_transfers table
- Implemented versioning system
