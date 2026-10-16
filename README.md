# High-Speed In-Memory LRU Cache Daemon

A high-performance, thread-safe, in-memory Least Recently Used (LRU) cache daemon featuring per-item Time-To-Live (TTL) expiration, O(1) time complexity operations, and automated background garbage collection.

---

## Architecture Overview & Capabilities

Designed with low-latency execution and high concurrency in mind, this service is engineered for use-cases requiring rapid data retrieval and memory bounding.

### Key Capabilities
- **O(1) Time Complexity:** Built on Python's `collections.OrderedDict`, ensuring constant-time performance for both reads (`get`) and writes (`set`).
- **Thread-Safe Concurrency:** Utilizes a reentrant lock (`threading.RLock`) to safely handle concurrent multi-threaded operations without deadlocks.
- **TTL & Expiration:** Supports optional Time-To-Live (TTL) expiration on a per-key basis, evaluated lazily on access and actively via background sweeping.
- **Memory Bounding:** Enforces strict capacity limits. When capacity is exceeded, the least recently used keys are automatically evicted.
- **Memory Optimization:** Implements `__slots__` on internal node representations to drastically reduce memory overhead and garbage collection pressure.
- **Background Cleanup Daemon:** A resilient, non-blocking background thread periodically sweeps and purges expired keys to free up memory autonomously.

---

## Available Endpoints & Usage

*(Note: Assuming an HTTP/REST or RPC wrapper exposing the underlying core capabilities demonstrated in the codebase).*

### 1. Set a Cache Entry
Stores a key-value pair with an optional TTL (in seconds).

```bash
curl -X POST http://localhost:8080/cache \
  -H "Content-Type: application/json" \
  -d '{"key": "session_123", "value": {"user": "alice", "role": "admin"}, "ttl": 300}'
```

**Response:**
```json
{
  "status": "success",
  "message": "Key stored successfully"
}
```

### 2. Retrieve a Cache Entry
Fetches the value associated with a key, updating its recency status in the LRU chain. Returns `404` if the key is missing or expired.

```bash
curl -X GET http://localhost:8080/cache/session_123
```

**Response:**
```json
{
  "key": "session_123",
  "value": {"user": "alice", "role": "admin"}
}
```

### 3. Purge Expired Items (Manual Trigger)
Forces an immediate cleanup sweep of all expired keys across the cache store.

```bash
curl -X POST http://localhost:8080/cache/purge
```

---

## Native Execution

### Prerequisites
- Python 3.9+
- `pip`

### Installation & Running

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/in-memory-lru-cache.git
   cd in-memory-lru-cache
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the daemon:**
   ```bash
   python -m cache_daemon.main
   ```

---

## Docker Execution

To run the cache daemon in an isolated containerized environment:

### 1. Build the Docker Image
```bash
docker build -t lru-cache-daemon .
```

### 2. Run the Container
```bash
docker run -d \
  --name cache-service \
  -p 8080:8080 \
  -e CACHE_CAPACITY=20000 \
  -e CLEANUP_INTERVAL=30.0 \
  lru-cache-daemon
```

### 3. View Container Logs
```bash
docker logs -f cache-service