import os
import time
from collections import OrderedDict
from threading import Lock
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-Memory Cache Store with LRU eviction and TTL
class LRUCache:
    def __init__(self, capacity=1000):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            val, expiry = self.cache[key]
            if expiry and time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return val

    def set(self, key, value, ttl=None):
        with self.lock:
            expiry = (time.time() + ttl) if ttl else None
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, expiry)
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

cache_store = LRUCache(capacity=5000)

# Pre-configured keys for testing (Free tier key included)
API_KEYS = {
    "tantod-free-demo-key": {"tier": "free", "requests": 0, "limit": 100},
    "tantod-vip-pro-key": {"tier": "pro", "requests": 0, "limit": 100000}
}

@app.before_request
def authenticate():
    if request.path in ["/", "/health", "/pricing"]:
        return
    api_key = request.headers.get("X-API-KEY")
    if not api_key or api_key not in API_KEYS:
        return jsonify({
            "error": "Unauthorized",
            "message": "Valid 'X-API-KEY' header required. Use 'tantod-free-demo-key' for trial or upgrade at /pricing"
        }), 401

    client_data = API_KEYS[api_key]
    if client_data["requests"] >= client_data["limit"]:
        return jsonify({
            "error": "Quota Exceeded",
            "message": f"Daily limit reached for {client_data['tier']} tier. Upgrade at /pricing"
        }), 429
    client_data["requests"] += 1

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "T.A.N.T.O.D. Autonomous LRU Cache SaaS",
        "status": "online",
        "endpoints": {
            "GET /health": "Health check",
            "GET /pricing": "Tier info & payment links",
            "GET /cache?key=<k>": "Retrieve cached item",
            "POST /cache": "Set key-value pair with optional TTL"
        }
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route("/pricing", methods=["GET"])
def pricing():
    return jsonify({
        "tiers": [
            {
                "tier": "Free Developer",
                "price": "$0",
                "limit": "100 req/day",
                "key": "tantod-free-demo-key"
            },
            {
                "tier": "Pro Unlimited",
                "price": "$9/month",
                "limit": "Unlimited",
                "checkout_link": "https://buy.stripe.com/test_placeholder"
            }
        ]
    })

@app.route("/cache", methods=["GET"])
def get_cache():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "Query param 'key' is required"}), 400
    val = cache_store.get(key)
    if val is None:
        return jsonify({"found": False, "key": key}), 404
    return jsonify({"found": True, "key": key, "value": val})

@app.route("/cache", methods=["POST"])
def set_cache():
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    value = data.get("value")
    ttl = data.get("ttl_seconds")
    if not key or value is None:
        return jsonify({"error": "'key' and 'value' are required in JSON body"}), 400
    cache_store.set(key, value, ttl=ttl)
    return jsonify({"status": "stored", "key": key, "ttl_seconds": ttl}), 201

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)