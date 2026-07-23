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

| Column     | Type    | Constraints                         | Description                         |
|------------|---------|-------------------------------------|-------------------------------------|
| code       | TEXT    | PRIMARY KEY                         | Unique item identifier              |
| name       | TEXT    | NOT NULL                            | Item description                    |
| tunch      | TEXT    | NULL                                | Optional free-text Tunch value for print |
| purity     | REAL    | DEFAULT 0                           | Silver purity %                     |
| wage_type  | TEXT    | DEFAULT 'P'                         | 'PC' or 'WT'                        |
| wage_rate  | REAL    | DEFAULT 0                           | Rate per piece/weight               |

### 2. estimates
**Purpose**: Estimate header records

| Column              | Type    | Constraints        | Description                |
|--------------------|---------|-------------------|----------------------------|
| voucher_no         | TEXT    | PRIMARY KEY       | Unique estimate ID         |
| voucher_no_int     | INTEGER |                   | Numeric voucher key for ordering/pagination |
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
| wage_type   | TEXT    |                                       | Applied `PC`/`WT` wage mode |
| wage        | REAL    | DEFAULT 0                             | Wage amount         |
| fine        | REAL    | DEFAULT 0                             | Fine silver weight  |
| is_return   | INTEGER | DEFAULT 0                             | Return flag         |
| is_silver_bar| INTEGER| DEFAULT 0                             | Silver bar flag     |
| line_key    | TEXT    |                                       | Stable line identity used for bar synchronization |

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
| source_line_key   | TEXT    |                                          | Stable source estimate-line identity |

### 5. silver_bar_lists
**Purpose**: Grouping mechanism for silver bars

| Column         | Type    | Constraints                | Description                 |
|----------------|---------|---------------------------|-----------------------------|
| list_id        | INTEGER | PRIMARY KEY AUTOINCREMENT  | Unique list ID              |
| list_identifier| TEXT    | UNIQUE NOT NULL           | Human-readable ID           |
| creation_date  | TEXT    | NOT NULL                  | Creation timestamp          |
| list_note      | TEXT    |                           | Optional description        |
| issued_date    | TEXT    |                           | Timestamp when list issued  |

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
**Purpose**: Current schema-format gate

| Column       | Type    | Constraints        | Description           |
|--------------|---------|-------------------|-----------------------|
| id           | INTEGER | PRIMARY KEY       | Version ID            |
| version      | INTEGER | NOT NULL          | Schema version number |
| applied_date | TEXT    | NOT NULL          | Schema creation timestamp |

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
6. **Status Values**: `In Stock`, `Assigned`, `Issued`, and `Sold`
7. **Stable Line Identity**: `estimate_items.line_key` links a source line to `silver_bars.source_line_key`
8. **Tunch**: Optional free-text item-master value; estimates resolve the current master value when printed

## Historical Schema Versions

The current runtime does not contain upgrade branches for these versions. It
creates fresh databases directly at version 8 and accepts existing databases
only when they already report version 8.

### Version 0 → 1
- Established the silver-bar/list/transfer schema and normalized missing baseline columns.

### Version 1 → 2
- Added `issued_date` to `silver_bar_lists` for issuance/reactivation history.

### Version 2 → 3
- Added `estimates.voucher_no_int` and backfilled numeric voucher values for stable keyset ordering.

### Version 3 → 4
- Added `estimate_items.wage_type` so persisted lines retain their applied wage mode.

### Version 4 → 5
- Added `estimate_items.line_key` and `silver_bars.source_line_key` for stable, idempotent bar synchronization.

### Version 5 → 6
- Recomputed stored regular-item `total_gross` and `total_net` estimate summaries.
- Added/validated the silver-bar availability index used by filtered keyset pages.

### Version 6 → 7
- Added nullable `items.tunch`.
- Tunch remains an item-master value and is not copied into `estimate_items`.

### Version 7 → 8
- Changed `items.tunch` from a constrained numeric value to free text.

Fresh schema creation, mandatory indexes, validation, and the schema-version
write run in one transaction. Any failure rolls the full setup back.

## Performance-Critical Indexes

- Estimate history: `(voucher_no_int DESC, voucher_no DESC)`
- Estimate lines: `(voucher_no, line_key)`
- Available bars: `(status, list_id, weight, date_added DESC, bar_id DESC)`
- Bar synchronization: `(estimate_voucher_no, source_line_key)`
