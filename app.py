import threading
import time
import json
from collections import OrderedDict
from typing import Any, Optional

class CacheNode:
    __slots__ = ('key', 'value', 'expiry')
    
    def __init__(self, key: Any, value: Any, expiry: Optional[float]):
        self.key = key
        self.value = value
        self.expiry = expiry

class HighSpeedCache:
    def __init__(self, capacity: int = 10000, cleanup_interval: float = 60.0):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")
        
        self.capacity = capacity
        self._cache: OrderedDict[Any, CacheNode] = OrderedDict()
        self._lock = threading.RLock()
        
        # Background thread for periodic expiration cleanup
        self._cleanup_interval = cleanup_interval
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()

    def _is_expired(self, node: CacheNode, current_time: float) -> bool:
        return node.expiry is not None and current_time >= node.expiry

    def _periodic_cleanup(self) -> None:
        while not self._stop_event.wait(self._cleanup_interval):
            try:
                self.purge_expired()
            except Exception:
                pass

    def close(self) -> None:
        self._stop_event.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join()

    def get(self, key: Any) -> Optional[Any]:
        current_time = time.time()
        
        with self._lock:
            node = self._cache.get(key)
            
            if node is None:
                return None
            
            if self._is_expired(node, current_time):
                self._cache.pop(key, None)
                return None
            
            self._cache.move_to_end(key)
            return node.value

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        current_time = time.time()
        expiry = current_time + ttl if ttl is not None and ttl > 0 else None
        
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                node = self._cache[key]
                node.value = value
                node.expiry = expiry
                return

            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
                
            self._cache[key] = CacheNode(key, value, expiry)

    def delete(self, key: Any) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def purge_expired(self) -> int:
        current_time = time.time()
        purged_count = 0
        
        with self._lock:
            keys_to_delete = [
                key for key, node in self._cache.items() 
                if self._is_expired(node, current_time)
            ]
            for key in keys_to_delete:
                del self._cache[key]
                purged_count += 1
                
        return purged_count

    def save_to_disk(self, filepath: str) -> None:
        current_time = time.time()
        with self._lock:
            data = {
                str(k): node.value for k, node in self._cache.items() 
                if not self._is_expired(node, current_time)
            }
            with open(filepath, 'w') as f:
                json.dump(data, f)

    def load_from_disk(self, filepath: str, ttl: Optional[float] = None) -> None:
        current_time = time.time()
        expiry = current_time + ttl if ttl is not None and ttl > 0 else None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        with self._lock:
            for k, v in data.items():
                if len(self._cache) >= self.capacity:
                    self._cache.popitem(last=False)
                self._cache[k] = CacheNode(k, v, expiry)

    def __len__(self) -> int:
        current_time = time.time()
        with self._lock:
            return sum(1 for node in self._cache.values() if not self._is_expired(node, current_time))