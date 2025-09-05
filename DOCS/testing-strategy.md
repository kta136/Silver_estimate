# Testing Strategy & Quality Assurance

## Testing Architecture

### 1. Testing Levels

#### Unit Testing
- Individual function/method testing
- Class-level testing
- Calculation accuracy verification
- Edge case handling

#### Integration Testing
- Component interaction testing
- Database operation testing
- UI-Logic integration
- Signal-Slot connections

#### System Testing
- End-to-end workflow testing
- Multi-step processes
- Error recovery scenarios
- Performance testing

#### User Acceptance Testing
- Business logic verification
- UI/UX validation
- Print output verification
- Data integrity checks

### 2. Test Categories

#### Functional Testing
- Core business logic
- Calculation accuracy
- Data persistence
- UI responsiveness

#### Security Testing
- Authentication mechanisms
- Encryption/decryption
- Data wipe functionality
- Access control

#### Performance Testing
- Load testing with large datasets
- Memory usage monitoring
- Database query optimization
- UI responsiveness metrics

#### Compatibility Testing
- Cross-platform testing
- Different PyQt versions
- Various screen resolutions
- Font rendering verification

## Test Implementation

### 1. Unit Test Structure

```python
import unittest
from unittest.mock import Mock, patch
from PyQt5.QtTest import QTest

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        """Initialize test environment."""
        self.db = DatabaseManager(':memory:', 'test_password')
        
    def tearDown(self):
        """Clean up test environment."""
        self.db.close()
        
    def test_add_item(self):
        """Test adding item to database."""
        result = self.db.add_item('TEST001', 'Test Item', 99.9, 'PC', 10.0)
        self.assertTrue(result)
        
        # Verify item exists
        item = self.db.get_item_by_code('TEST001')
        self.assertIsNotNone(item)
        self.assertEqual(item['name'], 'Test Item')
        
    def test_duplicate_item(self):
        """Test adding duplicate item fails."""
        self.db.add_item('TEST001', 'Item 1', 99.9, 'PC', 10.0)
        result = self.db.add_item('TEST001', 'Item 2', 99.9, 'PC', 10.0)
        self.assertFalse(result)
```

### 2. UI Testing

```python
class TestEstimateEntry(unittest.TestCase):
    def setUp(self):
        self.app = QApplication([])
        self.db = Mock()
        self.main_window = Mock()
        self.widget = EstimateEntryWidget(self.db, self.main_window)
        
    def test_add_empty_row(self):
        """Test adding empty row to table."""
        initial_rows = self.widget.item_table.rowCount()
        self.widget.add_empty_row()
        self.assertEqual(self.widget.item_table.rowCount(), initial_rows + 1)
        
    def test_calculate_net_weight(self):
        """Test net weight calculation."""
        self.widget.item_table.setRowCount(1)
        self.widget.item_table.setItem(0, COL_GROSS, QTableWidgetItem("100.5"))
        self.widget.item_table.setItem(0, COL_POLY, QTableWidgetItem("10.5"))
        
        self.widget.current_row = 0
        self.widget.calculate_net_weight()
        
        net_item = self.widget.item_table.item(0, COL_NET_WT)
        self.assertEqual(net_item.text(), "90.000")
```

### 3. Integration Testing

```python
class TestEstimateSaveLoad(unittest.TestCase):
    def setUp(self):
        """Set up test database and UI components."""
        self.db = DatabaseManager(':memory:', 'test_pass')
        self.widget = EstimateEntryWidget(self.db, None)
        
    def test_save_and_load_estimate(self):
        """Test saving and loading estimate with items."""
        # Create test data
        voucher_no = "TEST001"
        self.widget.voucher_edit.setText(voucher_no)
        self.widget.silver_rate_spin.setValue(75.5)
        
        # Add item
        self.widget.item_table.setRowCount(1)
        self.widget.item_table.setItem(0, COL_CODE, QTableWidgetItem("CODE1"))
        self.widget.item_table.setItem(0, COL_GROSS, QTableWidgetItem("100.0"))
        
        # Save
        self.widget.save_estimate()
        
        # Clear and reload
        self.widget.clear_form(confirm=False)
        self.widget.voucher_edit.setText(voucher_no)
        self.widget.load_estimate()
        
        # Verify
        self.assertEqual(self.widget.silver_rate_spin.value(), 75.5)
        self.assertEqual(self.widget.item_table.item(0, COL_CODE).text(), "CODE1")
```

### 4. Security Testing

```python
class TestSecurity(unittest.TestCase):
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "TestPassword123!"
        hashed = LoginDialog.hash_password(password)
        
        # Verify hash is created
        self.assertIsNotNone(hashed)
        self.assertNotEqual(password, hashed)
        
        # Verify verification works
        self.assertTrue(LoginDialog.verify_password(hashed, password))
        self.assertFalse(LoginDialog.verify_password(hashed, "WrongPassword"))
        
    def test_encryption_decryption(self):
        """Test database encryption/decryption."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            db_path = temp_file.name
            
        db = DatabaseManager(db_path, 'test_password')
        
        # Add test data
        db.add_item('TEST', 'Test Item', 99.9, 'PC', 10.0)
        
        # Close (encrypts)
        db.close()
        
        # Reopen (decrypts)
        db2 = DatabaseManager(db_path, 'test_password')
        item = db2.get_item_by_code('TEST')
        
        self.assertIsNotNone(item)
        self.assertEqual(item['name'], 'Test Item')
        
        db2.close()
        os.unlink(db_path)
```

## Test Data Management

### 1. Test Data Sets

```python
class TestData:
    ITEMS = [
        {'code': 'CH001', 'name': 'Chain', 'purity': 92.5, 'wage_type': 'WT', 'wage_rate': 50.0},
        {'code': 'BG001', 'name': 'Bangle', 'purity': 99.9, 'wage_type': 'PC', 'wage_rate': 200.0},
        {'code': 'RN001', 'name': 'Ring', 'purity': 91.6, 'wage_type': 'PC', 'wage_rate': 150.0}
    ]
    
    ESTIMATES = [
        {
            'voucher_no': 'EST001',
            'date': '2024-04-27',
            'silver_rate': 75.5,
            'items': [
                {'code': 'CH001', 'gross': 100.0, 'poly': 10.0},
                {'code': 'BG001', 'gross': 50.0, 'poly': 0.0}
            ]
        }
    ]
```

### 2. Mock Objects

```python
class MockDatabaseManager:
    def __init__(self):
        self.items = {}
        self.estimates = {}
        
    def add_item(self, code, name, purity, wage_type, wage_rate):
        if code in self.items:
            return False
        self.items[code] = {
            'code': code, 'name': name, 'purity': purity,
            'wage_type': wage_type, 'wage_rate': wage_rate
        }
        return True
        
    def get_item_by_code(self, code):
        return self.items.get(code)
```

## Performance Testing

### 1. Load Testing

```python
def test_large_estimate_performance():
    """Test performance with large number of items."""
    import time
    
    db = DatabaseManager(':memory:', 'test_pass')
    widget = EstimateEntryWidget(db, None)
    
    # Add 1000 items
    start_time = time.time()
    
    for i in range(1000):
        widget.item_table.insertRow(i)
        widget.item_table.setItem(i, COL_CODE, QTableWidgetItem(f"ITEM{i:04d}"))
        widget.item_table.setItem(i, COL_GROSS, QTableWidgetItem("100.0"))
        
    # Calculate totals
    widget.calculate_totals()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Time for 1000 items: {duration:.3f} seconds")
    assert duration < 5.0  # Should complete within 5 seconds
```

### 2. Memory Profiling

```python
import tracemalloc

def test_memory_usage():
    """Profile memory usage during operations."""
    tracemalloc.start()
    
    # Perform operations
    db = DatabaseManager(':memory:', 'test_pass')
    widget = EstimateEntryWidget(db, None)
    
    # Add many items
    for i in range(100):
        widget.add_empty_row()
        
    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024:.1f} KB")
    print(f"Peak memory usage: {peak / 1024:.1f} KB")
    
    tracemalloc.stop()
```

## Continuous Integration

### 1. CI Pipeline

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
        
    - name: Install dependencies
      run: |
        pip install PyQt5
        pip install cryptography
        pip install passlib[argon2]
        pip install pytest
        
    - name: Run tests
      run: pytest tests/
```

### 2. Test Coverage

```python
# Run with coverage
pytest --cov=. --cov-report=html

# Coverage configuration (.coveragerc)
[run]
omit = 
    */tests/*
    */venv/*
    
[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if __name__ == .__main__.:
```

## Quality Metrics

### 1. Code Quality Metrics
- Line coverage > 80%
- Branch coverage > 70%
- Cyclomatic complexity < 10
- Maintainability index > 20

### 2. Performance Metrics
- Startup time < 3 seconds
- UI response time < 100ms
- Database queries < 50ms
- Memory usage < 200MB

### 3. Security Metrics
- No plaintext passwords
- All encryption tests passing
- No SQL injection vulnerabilities
- Secure temp file handling

## Testing Best Practices

### 1. Test Organization
```
tests/
├── unit/
│   ├── test_database.py
│   ├── test_calculations.py
│   └── test_security.py
├── integration/
│   ├── test_estimate_workflow.py
│   └── test_silver_bar_management.py
├── ui/
│   ├── test_estimate_entry.py
│   └── test_item_master.py
└── conftest.py  # Shared fixtures
```

### 2. Test Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Clear, descriptive names

### 3. Test Documentation
```python
def test_calculate_fine_weight():
    """Test fine weight calculation.
    
    Fine weight = Net weight * (Purity / 100)
    
    Test cases:
    1. Normal calculation
    2. Zero purity
    3. Maximum purity
    4. Edge cases
    """
```

## Error Injection Testing

### 1. Database Errors
```python
def test_database_failure_handling():
    """Test graceful handling of database failures."""
    with patch('sqlite3.connect', side_effect=sqlite3.Error):
        with self.assertRaises(DatabaseError):
            db = DatabaseManager('test.db', 'password')
```

### 2. Encryption Errors
```python
def test_decryption_with_wrong_password():
    """Test handling of incorrect decryption password."""
    # Create encrypted database
    db1 = DatabaseManager('test.db', 'correct_password')
    db1.close()
    
    # Try to open with wrong password
    with self.assertRaises(EncryptionError):
        db2 = DatabaseManager('test.db', 'wrong_password')
```

## Regression Testing

### 1. Regression Test Suite
```python
class RegressionTests(unittest.TestCase):
    """Tests for fixed bugs to prevent regression."""
    
    def test_issue_123_net_weight_calculation(self):
        """Verify fix for net weight calculation bug."""
        # Bug: Net weight not updating when gross changes
        # Fixed in: v1.14
        
    def test_issue_124_silver_bar_calculation(self):
        """Verify fix for silver bar subtraction."""
        # Bug: Silver bars were added instead of subtracted
        # Fixed in: v1.14
```

## Test Reporting

### 1. HTML Report Generation
```python
# Generate detailed HTML report
pytest --html=report.html --self-contained-html

# Custom report formatting
import pytest_html
def pytest_html_results_table_header(cells):
    cells.insert(2, html.th('Description'))
    cells.pop()
```

### 2. Test Results Dashboard
```
Test Summary:
✓ 156 passed
✗ 2 failed
⚠ 3 skipped

Coverage: 85%
Duration: 45.2s
```