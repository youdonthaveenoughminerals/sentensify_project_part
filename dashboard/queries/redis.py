import os
import json
import redis
import streamlit as st
from typing import List, Dict, Any

# Re-use the client connection logic from mongo.py to ensure singleton pattern if possible
# But to avoid circular imports if mongo imports this, we might define a base or just duplicate the connection logic
# Since mongo.py is already existing and we are adding this, let's just import get_redis_client from mongo
# assuming mongo.py doesn't import redis.py. 
# Checking mongo.py... it imports 'redis'. It does NOT import 'dashboard.queries.redis'. So it is safe.
from .mongo import get_redis_client

def get_redis_info() -> Dict[str, Any]:
    """Returns Redis INFO command output (filtered)."""
    try:
        r = get_redis_client()
        info = r.info()
        return {
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
            "uptime_in_days": info.get("uptime_in_days", 0),
            "total_keys": r.dbsize()
        }
    except Exception as e:
        return {"error": str(e)}

def get_cache_stats(patterns: List[str]) -> Dict[str, int]:
    """Counts keys matching the given patterns."""
    r = get_redis_client()
    stats = {}
    try:
        for pattern in patterns:
            # For production with many keys, scan_iter is better, 
            # but for inspection/dashboard of MVP, keys() is acceptable and faster for small datasets.
            keys = r.keys(pattern)
            stats[pattern] = len(keys)
    except Exception as e:
        stats["error"] = str(e)
    return stats

def get_key_samples(pattern: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches sample keys matching a single pattern, sorted by recency (idle time).
    Uses 'OBJECT IDLETIME' to estimate last access/update.
    """
    r = get_redis_client()
    try:
        keys = r.keys(pattern)
        key_stats = []
        
        for k in keys:
            try:
                key_type = r.type(k)
                ttl = r.ttl(k)
                idle = r.object("idletime", k)  # Seconds since last access/write
                
                val_str = "N/A"
                if key_type == "string":
                    val = r.get(k)
                    try:
                        if val:
                            parsed = json.loads(val)
                            val_str = json.dumps(parsed, ensure_ascii=False)[:50] + "..."
                        else:
                            val_str = str(val)[:50]
                    except:
                        val_str = str(val)[:50] + "..."
                elif key_type == "hash":
                    val = r.hgetall(k)
                    val_str = str(val)[:50] + "..."
                else:
                    val_str = f"({key_type})"
                
                key_stats.append({
                    "key": k,
                    "type": key_type,
                    "ttl": ttl,
                    "idle": idle,
                    "value": val_str
                })
            except Exception:
                continue

        # Sort by idle time ascending (recently touched first)
        key_stats.sort(key=lambda x: x["idle"] if x["idle"] is not None else 999999)
        return key_stats[:limit]
        
    except Exception as e:
        return [{"error": str(e)}]
