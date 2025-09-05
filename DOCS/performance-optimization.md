# Performance Optimization Guide

## Overview

This guide provides strategies and techniques for optimizing the Silver Estimation App's performance, covering UI responsiveness, database operations, memory management, and startup time.

## UI Performance Optimization

### 1. Table Operations

#### Batch Updates
```python
def update_multiple_rows(self, data_list):
    """Efficient batch update of table rows."""
    self.item_table.blockSignals(True)
    try:
        # Disable viewport updates during batch operation
        self.item_table.setUpdatesEnabled(False)
        
        for row, data in enumerate(data_list):
            for col, value in enumerate(data):
                item = self.item_table.item(row, col)
                if item:
                    item.setText(str(value))
                else:
                    self.item_table.setItem(row, col, QTableWidgetItem(str(value)))
    finally:
        self.item_table.setUpdatesEnabled(True)
        self.item_table.blockSignals(False)
        # Single viewport update
        self.item_table.viewport().update()
```

#### Virtual Scrolling
```python
class VirtualTableModel(QAbstractTableModel):
    """Efficient model for large datasets."""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.cache = {}
        self.cache_size = 1000
        
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            
            # Check cache first
            if row in self.cache:
                return self.cache[row][index.column()]
            
            # Load data in chunks
            chunk_start = (row // 100) * 100
            chunk_data = self.data_manager.get_data_chunk(chunk_start, 100)
            
            # Update cache
            for i, row_data in enumerate(chunk_data):
                self.cache[chunk_start + i] = row_data
            
            # Maintain cache size
            if len(self.cache) > self.cache_size:
                self._trim_cache()
            
            return self.cache[row][index.column()]
    
    def _trim_cache(self):
        """Remove least recently used items from cache."""
        # Implementation depends on access tracking
        pass
```

### 2. Event Handling

#### Deferred Operations
```python
def handle_cell_changed(self, row, column):
    """Handle cell changes with deferred updates."""
    # Cancel previous timer
    if hasattr(self, '_update_timer'):
        self._update_timer.stop()
    
    # Set new timer to batch rapid changes
    self._update_timer = QTimer()
    self._update_timer.setSingleShot(True)
    self._update_timer.timeout.connect(
        lambda: self._process_cell_change(row, column)
    )
    self._update_timer.start(100)  # 100ms delay
    
def _process_cell_change(self, row, column):
    """Process deferred cell change."""
    if column in [COL_GROSS, COL_POLY, COL_PURITY]:
        self.calculate_totals()
```

#### Signal Throttling
```python
class ThrottledSignal(QObject):
    """Throttle frequent signals."""
    
    throttled = pyqtSignal(object)
    
    def __init__(self, delay_ms=100):
        super().__init__()
        self.delay_ms = delay_ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._emit_throttled)
        self.pending_data = None
        
    def emit_signal(self, data):
        """Store data and start/restart timer."""
        self.pending_data = data
        if not self.timer.isActive():
            self.timer.start(self.delay_ms)
    
    def _emit_throttled(self):
        """Emit the throttled signal."""
        if self.pending_data is not None:
            self.throttled.emit(self.pending_data)
            self.pending_data = None
```

### 3. Layout Optimization

#### Lazy Loading
```python
class LazyLoadingWidget(QWidget):
    """Widget that loads content on demand."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded = False
        self.layout = QVBoxLayout(self)
        
    def showEvent(self, event):
        """Load content when widget becomes visible."""
        if not self.loaded:
            self._load_content()
            self.loaded = True
        super().showEvent(event)
    
    def _load_content(self):
        """Load widget content."""
        # Heavy initialization here
        pass
```

## Database Performance

### 1. Query Optimization

#### Indexing Strategy
```sql
-- Create indexes for frequently searched columns
CREATE INDEX IF NOT EXISTS idx_items_code ON items(code);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_estimates_date ON estimates(date);
CREATE INDEX IF NOT EXISTS idx_estimate_items_voucher ON estimate_items(voucher_no);
CREATE INDEX IF NOT EXISTS idx_silver_bars_status ON silver_bars(status);
```

#### Prepared Statements
```python
class OptimizedDatabaseManager:
    def __init__(self):
        self.prepared_statements = {}
        
    def prepare_statements(self):
        """Prepare frequently used statements."""
        self.prepared_statements['get_item'] = self.conn.prepare(
            "SELECT * FROM items WHERE code = ?"
        )
        self.prepared_statements['add_item'] = self.conn.prepare(
            "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)"
        )
    
    def get_item_by_code(self, code):
        """Use prepared statement for faster execution."""
        stmt = self.prepared_statements['get_item']
        stmt.execute((code,))
        return stmt.fetchone()
```

#### Query Batching
```python
def add_multiple_items(self, items_data):
    """Batch insert multiple items."""
    self.conn.execute('BEGIN TRANSACTION')
    try:
        self.cursor.executemany(
            "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
            items_data
        )
        self.conn.commit()
    except:
        self.conn.rollback()
        raise
```

### 2. Connection Pooling

```python
class ConnectionPool:
    """Simple connection pool for SQLite."""
    
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = []
        self.in_use = []
        
    def get_connection(self):
        """Get a connection from the pool."""
        if self.connections:
            conn = self.connections.pop()
            self.in_use.append(conn)
            return conn
        elif len(self.in_use) < self.pool_size:
            conn = sqlite3.connect(self.db_path)
            self.in_use.append(conn)
            return conn
        else:
            # Wait for connection to be available
            # In practice, implement proper waiting mechanism
            raise Exception("No connections available")
    
    def release_connection(self, conn):
        """Return connection to the pool."""
        if conn in self.in_use:
            self.in_use.remove(conn)
            self.connections.append(conn)
```

### 3. Caching

```python
class QueryCache:
    """Cache for expensive queries."""
    
    def __init__(self, max_size=1000, ttl=300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        
    def get(self, key):
        """Get value from cache."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        """Set value in cache."""
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        self.cache[key] = (value, time.time())
    
    def _evict_oldest(self):
        """Remove oldest cache entry."""
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
        del self.cache[oldest_key]
```

## Memory Optimization

### 1. Object Pooling

```python
class ObjectPool:
    """Pool for frequently created/destroyed objects."""
    
    def __init__(self, factory, initial_size=10):
        self.factory = factory
        self.pool = [factory() for _ in range(initial_size)]
        self.in_use = []
        
    def acquire(self):
        """Get object from pool."""
        if self.pool:
            obj = self.pool.pop()
        else:
            obj = self.factory()
        self.in_use.append(obj)
        return obj
    
    def release(self, obj):
        """Return object to pool."""
        if obj in self.in_use:
            self.in_use.remove(obj)
            obj.reset()  # Assuming objects have reset method
            self.pool.append(obj)
```

### 2. Memory Profiling

```python
import tracemalloc
import gc

class MemoryProfiler:
    """Memory usage profiler."""
    
    def __init__(self):
        self.snapshots = []
        
    def start(self):
        """Start memory profiling."""
        tracemalloc.start()
        self.snapshots.append(tracemalloc.take_snapshot())
    
    def take_snapshot(self, label=""):
        """Take memory snapshot."""
        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append((label, snapshot))
        
    def compare_snapshots(self, index1=-2, index2=-1):
        """Compare two snapshots."""
        if len(self.snapshots) < 2:
            return "Not enough snapshots"
        
        snapshot1 = self.snapshots[index1]
        snapshot2 = self.snapshots[index2]
        
        if isinstance(snapshot1, tuple):
            snapshot1 = snapshot1[1]
        if isinstance(snapshot2, tuple):
            snapshot2 = snapshot2[1]
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        for stat in top_stats[:10]:
            print(stat)
    
    def get_memory_usage(self):
        """Get current memory usage."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
```

### 3. Garbage Collection

```python
def optimize_garbage_collection():
    """Optimize garbage collection for application."""
    # Disable garbage collection during critical operations
    gc.disable()
    
    try:
        # Critical operations
        pass
    finally:
        gc.enable()
    
    # Manual collection after large operations
    gc.collect()
    
    # Tune garbage collection thresholds
    gc.set_threshold(700, 10, 10)  # Default is (700, 10, 10)
```

## Startup Optimization

### 1. Lazy Loading

```python
class LazyLoader:
    """Lazy load modules on demand."""
    
    def __init__(self, module_path):
        self.module_path = module_path
        self._module = None
    
    def __getattr__(self, name):
        if self._module is None:
            import importlib
            self._module = importlib.import_module(self.module_path)
        return getattr(self._module, name)

# Usage
heavy_module = LazyLoader('heavy_module')
# Module is only imported when actually used
heavy_module.some_function()
```

### 2. Splash Screen

```python
class SplashScreen(QSplashScreen):
    """Splash screen with progress."""
    
    def __init__(self):
        pixmap = QPixmap("splash.png")
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.progress = 0
        
    def drawContents(self, painter):
        """Draw progress bar on splash screen."""
        super().drawContents(painter)
        
        # Draw progress bar
        painter.setPen(Qt.white)
        painter.setBrush(Qt.white)
        progress_width = int(self.width() * self.progress / 100)
        painter.drawRect(0, self.height() - 10, progress_width, 10)
        
    def setProgress(self, value):
        """Update progress."""
        self.progress = value
        self.repaint()
```

### 3. Initialization Queue

```python
class InitializationManager:
    """Manage application initialization."""
    
    def __init__(self):
        self.tasks = []
        self.total_weight = 0
        
    def add_task(self, task, weight=1):
        """Add initialization task."""
        self.tasks.append((task, weight))
        self.total_weight += weight
    
    def run(self, progress_callback=None):
        """Run all initialization tasks."""
        current_weight = 0
        
        for task, weight in self.tasks:
            task()
            current_weight += weight
            
            if progress_callback:
                progress = int(current_weight / self.total_weight * 100)
                progress_callback(progress)
```

## Algorithm Optimization

### 1. Calculation Optimization

```python
class OptimizedCalculator:
    """Optimized calculation methods."""
    
    @staticmethod
    def calculate_totals_optimized(items):
        """Calculate totals with minimal iterations."""
        totals = {
            'regular': {'gross': 0, 'net': 0, 'fine': 0, 'wage': 0},
            'return': {'gross': 0, 'net': 0, 'fine': 0, 'wage': 0},
            'silver_bar': {'gross': 0, 'net': 0, 'fine': 0, 'wage': 0}
        }
        
        # Single pass through items
        for item in items:
            category = 'return' if item.is_return else \
                      'silver_bar' if item.is_silver_bar else 'regular'
            
            totals[category]['gross'] += item.gross
            totals[category]['net'] += item.net_wt
            totals[category]['fine'] += item.fine
            totals[category]['wage'] += item.wage
        
        return totals
```

### 2. Search Optimization

```python
class TrieNode:
    """Trie node for fast string search."""
    
    def __init__(self):
        self.children = {}
        self.is_end = False
        self.data = None

class Trie:
    """Trie for fast item code/name search."""
    
    def __init__(self):
        self.root = TrieNode()
    
    def insert(self, key, data):
        """Insert key-data pair."""
        node = self.root
        for char in key.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True
        node.data = data
    
    def search(self, prefix):
        """Search for all items with prefix."""
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        
        return self._collect_all(node, prefix)
    
    def _collect_all(self, node, prefix):
        """Collect all items from node."""
        results = []
        if node.is_end:
            results.append(node.data)
        
        for char, child in node.children.items():
            results.extend(self._collect_all(child, prefix + char))
        
        return results
```

## Resource Management

### 1. File Handle Management

```python
class FileHandlePool:
    """Pool for file handles."""
    
    def __init__(self, max_handles=100):
        self.max_handles = max_handles
        self.handles = {}
        self.lru = []  # Least recently used
        
    def get_handle(self, path, mode='r'):
        """Get file handle."""
        if path in self.handles:
            handle = self.handles[path]
            self._update_lru(path)
            return handle
        
        if len(self.handles) >= self.max_handles:
            self._evict_oldest()
        
        handle = open(path, mode)
        self.handles[path] = handle
        self.lru.append(path)
        return handle
    
    def _update_lru(self, path):
        """Update LRU list."""
        if path in self.lru:
            self.lru.remove(path)
        self.lru.append(path)
    
    def _evict_oldest(self):
        """Evict least recently used handle."""
        if self.lru:
            oldest_path = self.lru.pop(0)
            handle = self.handles.pop(oldest_path)
            handle.close()
    
    def close_all(self):
        """Close all handles."""
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()
        self.lru.clear()
```

### 2. Thread Pool Management

```python
from concurrent.futures import ThreadPoolExecutor
import queue

class ManagedThreadPool:
    """Thread pool with task prioritization."""
    
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.priority_queue = queue.PriorityQueue()
        self.worker_thread = None
        self.running = False
        
    def start(self):
        """Start the thread pool."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_queue)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def submit(self, priority, func, *args, **kwargs):
        """Submit task with priority."""
        future = self.executor.submit(func, *args, **kwargs)
        self.priority_queue.put((priority, future))
        return future
    
    def _process_queue(self):
        """Process tasks by priority."""
        while self.running:
            try:
                priority, future = self.priority_queue.get(timeout=1)
                # Task is already running in executor
            except queue.Empty:
                continue
    
    def shutdown(self, wait=True):
        """Shutdown the thread pool."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
        self.executor.shutdown(wait=wait)
```

## Rendering Optimization

### 1. Double Buffering

```python
class DoubleBufferedWidget(QWidget):
    """Widget with double buffering."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.buffer = QPixmap(self.size())
        self.buffer.fill(Qt.transparent)
        
    def resizeEvent(self, event):
        """Handle resize event."""
        self.buffer = QPixmap(event.size())
        self.buffer.fill(Qt.transparent)
        self.update()
    
    def paintEvent(self, event):
        """Paint from buffer."""
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.buffer)
    
    def updateBuffer(self):
        """Update the buffer."""
        painter = QPainter(self.buffer)
        # Draw content to buffer
        self._drawContent(painter)
        painter.end()
        self.update()
    
    def _drawContent(self, painter):
        """Draw actual content."""
        # Implementation specific
        pass
```

### 2. Viewport Optimization

```python
class OptimizedTableView(QTableView):
    """Table view with viewport optimization."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewportUpdateMode(QAbstractItemView.SmartViewportUpdate)
        
    def dataChanged(self, topLeft, bottomRight, roles=[]):
        """Handle data changes efficiently."""
        # Only update visible portion
        visible_rect = self.viewport().rect()
        update_rect = self.visualRect(topLeft).united(self.visualRect(bottomRight))
        
        if visible_rect.intersects(update_rect):
            super().dataChanged(topLeft, bottomRight, roles)
        else:
            # Data changed outside visible area, no update needed
            pass
```

## Network Optimization

### 1. Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class OptimizedHTTPClient:
    """HTTP client with connection pooling and retry."""
    
    def __init__(self, pool_connections=10, pool_maxsize=10, max_retries=3):
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get(self, url, **kwargs):
        """GET request with connection reuse."""
        return self.session.get(url, **kwargs)
    
    def post(self, url, **kwargs):
        """POST request with connection reuse."""
        return self.session.post(url, **kwargs)
```

### 2. Request Batching

```python
class RequestBatcher:
    """Batch multiple requests together."""
    
    def __init__(self, batch_size=10, timeout=0.1):
        self.batch_size = batch_size
        self.timeout = timeout
        self.queue = []
        self.timer = None
        
    def add_request(self, request):
        """Add request to batch."""
        self.queue.append(request)
        
        if len(self.queue) >= self.batch_size:
            self._send_batch()
        elif not self.timer:
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._send_batch)
            self.timer.start(int(self.timeout * 1000))
    
    def _send_batch(self):
        """Send batched requests."""
        if not self.queue:
            return
        
        batch = self.queue[:self.batch_size]
        self.queue = self.queue[self.batch_size:]
        
        # Send batch
        self._process_batch(batch)
        
        if self.timer:
            self.timer.stop()
            self.timer = None
        
        # Continue with remaining items
        if self.queue:
            self.add_request(None)  # Trigger next batch
    
    def _process_batch(self, batch):
        """Process a batch of requests."""
        # Implementation specific
        pass
```

## Profiling Tools

### 1. Performance Profiler

```python
import cProfile
import pstats
import io

class PerformanceProfiler:
    """Comprehensive performance profiler."""
    
    def __init__(self):
        self.profiler = cProfile.Profile()
        
    def start(self):
        """Start profiling."""
        self.profiler.enable()
    
    def stop(self):
        """Stop profiling."""
        self.profiler.disable()
    
    def get_stats(self, sort_by='cumulative'):
        """Get profiling statistics."""
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats(sort_by)
        ps.print_stats()
        return s.getvalue()
    
    def save_stats(self, filename):
        """Save stats to file."""
        self.profiler.dump_stats(filename)
    
    @contextmanager
    def profile(self):
        """Context manager for profiling."""
        self.start()
        try:
            yield
        finally:
            self.stop()
```

### 2. Memory Leak Detector

```python
import weakref
import gc

class MemoryLeakDetector:
    """Detect potential memory leaks."""
    
    def __init__(self):
        self.objects = weakref.WeakKeyDictionary()
        self.baseline = None
        
    def track_object(self, obj, name=""):
        """Track an object."""
        self.objects[obj] = name
    
    def take_baseline(self):
        """Take memory baseline."""
        gc.collect()
        self.baseline = {id(obj): (type(obj), name) 
                        for obj, name in self.objects.items()}
    
    def find_leaks(self):
        """Find potential leaks."""
        gc.collect()
        current = {id(obj): (type(obj), name) 
                  for obj, name in self.objects.items()}
        
        if self.baseline is None:
            return "No baseline taken"
        
        leaks = []
        for obj_id, (obj_type, name) in current.items():
            if obj_id not in self.baseline:
                leaks.append((obj_type, name))
        
        return leaks
```

## Performance Monitoring

### 1. Real-time Monitor

```python
class PerformanceMonitor(QObject):
    """Real-time performance monitoring."""
    
    performance_data = pyqtSignal(dict)
    
    def __init__(self, interval=1000):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self._collect_data)
        self.interval = interval
        
    def start(self):
        """Start monitoring."""
        self.timer.start(self.interval)
    
    def stop(self):
        """Stop monitoring."""
        self.timer.stop()
    
    def _collect_data(self):
        """Collect performance data."""
        import psutil
        process = psutil.Process()
        
        data = {
            'cpu_percent': process.cpu_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'threads': process.num_threads(),
            'handles': process.num_handles() if hasattr(process, 'num_handles') else 0,
            'timestamp': time.time()
        }
        
        self.performance_data.emit(data)
```

### 2. Performance Dashboard

```python
class PerformanceDashboard(QWidget):
    """Visual performance dashboard."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.monitor = PerformanceMonitor()
        self.monitor.performance_data.connect(self.update_display)
        self.data_history = []
        
    def setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        
        # CPU usage
        self.cpu_label = QLabel("CPU: 0%")
        layout.addWidget(self.cpu_label)
        
        # Memory usage
        self.memory_label = QLabel("Memory: 0 MB")
        layout.addWidget(self.memory_label)
        
        # Thread count
        self.thread_label = QLabel("Threads: 0")
        layout.addWidget(self.thread_label)
        
        # Graph
        self.graph_widget = QWidget()
        self.graph_widget.setMinimumHeight(200)
        layout.addWidget(self.graph_widget)
    
    def update_display(self, data):
        """Update the display with new data."""
        self.cpu_label.setText(f"CPU: {data['cpu_percent']}%")
        self.memory_label.setText(f"Memory: {data['memory_mb']:.1f} MB")
        self.thread_label.setText(f"Threads: {data['threads']}")
        
        self.data_history.append(data)
        if len(self.data_history) > 60:  # Keep 1 minute of data
            self.data_history.pop(0)
        
        self._update_graph()
    
    def _update_graph(self):
        """Update the performance graph."""
        # Implementation depends on graphing library
        pass
```

## Best Practices Summary

### 1. UI Performance
- Block signals during batch operations
- Use deferred updates for rapid changes
- Implement virtual scrolling for large datasets
- Double buffer complex widgets
- Lazy load expensive components

### 2. Database Performance
- Use prepared statements
- Implement proper indexing
- Batch operations where possible
- Use connection pooling
- Cache expensive queries

### 3. Memory Management
- Pool frequently used objects
- Profile memory usage regularly
- Optimize garbage collection
- Close resources promptly
- Monitor for memory leaks

### 4. General Optimization
- Profile before optimizing
- Focus on bottlenecks
- Test optimizations thoroughly
- Monitor performance continuously
- Balance speed vs. maintainability