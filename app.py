import json
import time
import threading
from typing import Generic, TypeVar, Optional, Dict

K = TypeVar('K')
V = TypeVar('V')

class Node(Generic[K, V]):
    __slots__ = ('key', 'value', 'expiry', 'prev', 'next')
    def __init__(self, key: Optional[K] = None, value: Optional[V] = None, expiry: float = 0.0):
        self.key: Optional[K] = key
        self.value: Optional[V] = value
        self.expiry: float = expiry
        self.prev: Optional['Node[K, V]'] = None
        self.next: Optional['Node[K, V]'] = None

class LRUCacheWithTTL(Generic[K, V]):
    def __init__(self, capacity: int = 10000):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")
        self.capacity = capacity
        self.map: Dict[K, Node[K, V]] = {}
        self.lock = threading.RLock()
        
        self.head = Node[K, V]()
        self.tail = Node[K, V]()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node[K, V]) -> None:
        p = node.prev
        n = node.next
        if p is not None:
            p.next = n
        if n is not None:
            n.prev = p
        node.prev = None
        node.next = None

    def _add_to_front(self, node: Node[K, V]) -> None:
        n = self.head.next
        self.head.next = node
        node.prev = self.head
        node.next = n
        if n is not None:
            n.prev = node

    def _evict(self) -> None:
        now = time.time()
        # Eviction Optimization: Prefer evicting expired entries first if available
        current = self.tail.prev
        while current is not None and current != self.head:
            if current.expiry != 0.0 and now >= current.expiry:
                prev_node = current.prev
                self._remove(current)
                if current.key is not None:
                    self.map.pop(current.key, None)
                current = prev_node
            else:
                break

        # If after checking expired items we still need to evict (or none were expired), evict the actual LRU
        lru = self.tail.prev
        if lru is not None and lru != self.head:
            self._remove(lru)
            if lru.key is not None:
                self.map.pop(lru.key, None)

    def _is_expired(self, node: Node[K, V], now: float) -> bool:
        return node.expiry != 0.0 and now >= node.expiry

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        now = time.time()
        expiry = now + ttl if ttl is not None and ttl > 0 else 0.0

        with self.lock:
            if key in self.map:
                node = self.map[key]
                node.value = value
                node.expiry = expiry
                self._remove(node)
                self._add_to_front(node)
                return

            if len(self.map) >= self.capacity:
                self._evict()

            node = Node(key=key, value=value, expiry=expiry)
            self._add_to_front(node)
            self.map[key] = node

    def get(self, key: K) -> Optional[V]:
        now = time.time()
        with self.lock:
            if key not in self.map:
                return None
            
            node = self.map[key]
            if self._is_expired(node, now):
                self._remove(node)
                self.map.pop(key, None)
                return None

            self._remove(node)
            self._add_to_front(node)
            return node.value

    def delete(self, key: K) -> bool:
        with self.lock:
            if key not in self.map:
                return False
            node = self.map.pop(key)
            self._remove(node)
            return True

    def clear(self) -> None:
        with self.lock:
            # Memory Management: Ensure all nodes are properly unlinked from the list
            while self.head.next and self.head.next != self.tail:
                node_to_remove = self.head.next
                self._remove(node_to_remove)
            self.map.clear()
            self.head.next = self.tail
            self.tail.prev = self.head

    def __len__(self) -> int:
        now = time.time()
        with self.lock:
            expired_keys = [
                k for k, node in self.map.items() 
                if self._is_expired(node, now)
            ]
            for k in expired_keys:
                node = self.map.pop(k, None)
                if node:
                    self._remove(node)
            return len(self.map)

    def save(self, filename: str) -> None:
        with self.lock:
            now = time.time()
            data = []
            for k, node in self.map.items():
                if not self._is_expired(node, now):
                    ttl = node.expiry - now if node.expiry != 0.0 else None
                    data.append({'key': k, 'value': node.value, 'ttl': ttl})
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f)

    def load(self, filename: str) -> None:
        with self.lock:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.clear()
                now = time.time()
                for item in data:
                    expiry = item.get('ttl')
                    actual_ttl = expiry if expiry is not None and expiry > 0 else None
                    self.set(item['key'], item['value'], ttl=actual_ttl)