import time
import threading
from typing import Generic, TypeVar, Optional, Dict, Tuple

K = TypeVar('K')
V = TypeVar('V')

class Node(Generic[K, V]):
    __slots__ = ('key', 'value', 'expiry', 'prev', 'next')
    def __init__(self, key: Optional[K] = None, value: Optional[V] = None, expiry: float = float('inf')):
        self.key: Optional[K] = key
        self.value: Optional[V] = value
        self.expiry: float = expiry
        self.prev: Optional['Node[K, V]'] = None
        self.next: Optional['Node[K, V]'] = None

class LRUCache(Generic[K, V]):
    def __init__(self, capacity: int, cleanup_interval: float = 60.0):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")
        self.capacity: int = capacity
        self.cache: Dict[K, Node[K, V]] = {}
        
        self.head: Node[K, V] = Node()
        self.tail: Node[K, V] = Node()
        self.head.next = self.tail
        self.tail.prev = self.head
        
        self.lock: threading.RLock = threading.RLock()
        
        # Start background cleanup thread
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._background_cleanup, 
            args=(cleanup_interval,), 
            daemon=True
        )
        self._cleanup_thread.start()

    def _background_cleanup(self, interval: float) -> None:
        while not self._stop_event.is_set():
            # Use threading.Event.wait for safe and non-busy sleeping with early exit capability
            if self._stop_event.wait(interval):
                break
            try:
                self.cleanup_expired()
            except Exception:
                # Prevent background thread from dying due to unexpected errors
                pass

    def stop(self) -> None:
        """Stops the background cleanup thread."""
        self._stop_event.set()

    def _remove(self, node: Node[K, V]) -> None:
        prev_node = node.prev
        next_node = node.next
        if prev_node and next_node:
            prev_node.next = next_node
            next_node.prev = prev_node

    def _add_to_front(self, node: Node[K, V]) -> None:
        next_node = self.head.next
        self.head.next = node
        node.prev = self.head
        node.next = next_node
        if next_node:
            next_node.prev = node

    def _is_expired(self, node: Node[K, V], current_time: float) -> bool:
        return current_time >= node.expiry

    def get(self, key: K) -> Optional[V]:
        current_time = time.time()
        with self.lock:
            self.cleanup_expired()
            node = self.cache.get(key)
            if not node:
                return None
            
            if self._is_expired(node, current_time):
                self._remove(node)
                del self.cache[key]
                return None
            
            self._remove(node)
            self._add_to_front(node)
            return node.value

    def put(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        current_time = time.time()
        expiry = current_time + ttl if ttl is not None else float('inf')
        
        # Do not add items that are already expired
        if expiry <= current_time:
            return

        with self.lock:
            self.cleanup_expired()
            if key in self.cache:
                node = self.cache[key]
                node.value = value
                node.expiry = expiry
                self._remove(node)
                self._add_to_front(node)
                return

            if len(self.cache) >= self.capacity:
                lru_node = self.tail.prev
                if lru_node and lru_node != self.head:
                    self._remove(lru_node)
                    del self.cache[lru_node.key]

            new_node = Node(key, value, expiry)
            self.cache[key] = new_node
            self._add_to_front(new_node)

    def delete(self, key: K) -> bool:
        with self.lock:
            node = self.cache.get(key)
            if not node:
                return False
            self._remove(node)
            del self.cache[key]
            return True

    def cleanup_expired(self) -> int:
        current_time = time.time()
        removed_count = 0
        with self.lock:
            current = self.tail.prev
            while current and current != self.head:
                prev_node = current.prev
                if self._is_expired(current, current_time):
                    self._remove(current)
                    if current.key in self.cache:
                        del self.cache[current.key]
                    removed_count += 1
                current = prev_node
        return removed_count

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.head.next = self.tail
            self.tail.prev = self.head

    def __len__(self) -> int:
        self.cleanup_expired()
        with self.lock:
            return len(self.cache)