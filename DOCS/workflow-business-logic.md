# Workflow & Business Logic - Silver Estimation App

## Core Business Processes

### 1. Estimate Creation Workflow

#### Process Flow
1. Generate/Enter voucher number
2. Set silver rate and date
3. Add line items (Regular/Return/Silver Bar)
4. System calculates totals automatically
5. Save estimate → Creates silver bars if applicable
6. Open print preview automatically
7. Clear form for new estimate

#### Calculation Logic
```
Net Weight = Gross Weight - Poly Weight
Fine Weight = Net Weight × (Purity% / 100)
Wage Amount = PC: Pieces × Rate | WT: Net Weight × Rate
Net Fine = Regular Fine - Return Fine - Silver Bar Fine
Net Wage = Regular Wage - Return Wage - Silver Bar Wage (usually 0)
Grand Total = (Net Fine × Silver Rate) + Net Wage + Last Balance Amount
```

### 2. Item Management Workflow

#### Item Creation
1. Validate unique code (uppercase)
2. Set name, purity, wage type/rate
3. Prevent duplicates
4. Set defaults for empty fields

#### Item Usage
1. Code entry → Lookup or selection dialog
2. Auto-populate item details
3. Override purity/wage if needed
4. Navigate to next editable field

### 3. Silver Bar Management

#### Bar Creation
1. Created automatically from estimate silver bar items
2. One bar per line item
3. Linked to source estimate
4. Default status: 'In Stock'

#### List Management
1. Create lists with unique identifiers
2. Assign bars to lists
3. Track status changes
4. Generate transfer records

#### Bar Lifecycle
```
Creation → In Stock → Assigned to List → [Sold/Melted/Returned to Stock]
```

### 4. Authentication and Security

#### Login Flow
1. Check for existing password hashes
2. First run: Dual password setup
3. Subsequent runs: Verify main password
4. Secondary password triggers data wipe

#### Data Protection
1. AES-GCM encryption at rest
2. Temporary decrypted files during session
3. Secure key derivation with PBKDF2
4. Salt stored in QSettings

### 5. Import/Export Processes

#### Item Import
1. Parse file with configurable delimiter
2. Map columns to data fields
3. Handle Q-type rate conversion
4. Apply adjustment factors
5. Manage duplicates (skip/update)

#### Item Export
1. Generate pipe-delimited file
2. Include standard header
3. Export all items in catalog
4. Maintain import compatibility

## Business Rules

### 1. Estimate Rules
- Voucher numbers must be unique
- Return items reduce totals
- Silver bars create inventory records
- Last balance adds to final calculation
- Notes persist with estimates

### 2. Item Master Rules
- Codes must be unique and uppercase
- Purity range: 0-999999.99%
- Wage types: PC (per piece) or WT (per weight)
- Deletion blocked if used in estimates

### 3. Silver Bar Rules
- Created only on first estimate save
- Permanent once created
- Status tracking mandatory
- List assignment exclusive
- Transfer history maintained

### 4. Calculation Rules
- All weights in grams
- Purity as percentage
- Wage rates in rupees
- Rounding: 3 decimals for weights, 2 for money
- Indian number formatting for display

### 5. Navigation Rules
- Tab/Enter moves to next logical field
- Backspace in empty field moves back
- Auto-add row on last column completion
- Code field triggers lookup on exit

## Error Handling

### 1. Input Validation
- Numeric fields use validators
- Code format enforced
- Purity range checked
- Required fields validated

### 2. Database Operations
- Transaction control for multi-step operations
- Cascade deletion protection
- Foreign key enforcement
- Schema version checking

### 3. File Operations
- Multiple encoding attempts for import
- Graceful handling of malformed data
- Temporary file cleanup
- Encryption failure recovery

## User Interface Logic

### 1. Mode Management
- Regular/Return/Silver Bar toggles
- Visual indicators for modes
- Mutually exclusive activation
- Mode-specific calculations

### 2. Table Navigation
- Cell-based focus control
- Keyboard-driven workflow
- Skip calculated fields
- Conditional column access

### 3. Form Management
- Clear with confirmation
- Load with validation
- Save with recalculation
- Print with formatting

## Performance Considerations

### 1. Database Access
- Batch operations where possible
- Index optimization
- Transaction grouping
- Row factory for result sets

### 2. UI Responsiveness
- Signal blocking during updates
- Deferred operations with QTimer
- Progress indication for long tasks
- Efficient table updates

### 3. Memory Management
- Temporary file cleanup
- Resource disposal
- Event loop consideration
- Widget recycling
