import redis
import sys

def get_generalized_pattern(key):
    """
    Generalizes a Redis key by replacing UUID-like or numeric segments with '*'.
    """
    parts = key.split(':')
    generalized_parts = []
    for part in parts:
        # Check for UUID-like (len 32 or 36 with dashes) or purely numeric
        if len(part) >= 32 or part.isdigit():
            generalized_parts.append('*')
        # Heuristic for shorter IDs (e.g. mix of nums and chars, length > 8)
        elif len(part) > 8 and any(c.isdigit() for c in part):
             generalized_parts.append('*')
        else:
            generalized_parts.append(part)
    return ":".join(generalized_parts)

def main():
    # Connect to Redis
    host = 'localhost'
    port = 6379
    try:
        r = redis.Redis(host=host, port=port, decode_responses=True)
        if not r.ping():
            print(f"Failed to ping Redis at {host}:{port}")
            return
    except Exception as e:
        print(f"Error connecting to Redis at {host}:{port}: {e}")
        # Fallback to checking environment variables if needed, 
        # but the prompt specified localhost:6379.
        return

    try:
        keys = r.keys('*')
    except Exception as e:
        print(f"Error fetching keys: {e}")
        return

    if not keys:
        print("Redis is empty (0 keys found).")
        return

    print(f"Found {len(keys)} total keys.\n")

    # Group keys by pattern
    groups = {}
    for key in keys:
        pattern = get_generalized_pattern(key)
        if pattern not in groups:
            groups[pattern] = []
        groups[pattern].append(key)

    # Print details for each group
    print(f"{'PATTERN':<40} | {'COUNT':<5} | {'EXAMPLE KEY'}")
    print("-" * 80)
    
    for pattern, key_list in groups.items():
        count = len(key_list)
        example_key = key_list[0]
        print(f"{pattern:<40} | {count:<5} | {example_key}")

    print("\n--- Detail Inspection (One per Group) ---")
    for pattern, key_list in groups.items():
        example_key = key_list[0]
        try:
            k_type = r.type(example_key)
            ttl = r.ttl(example_key)
            
            val_preview = ""
            if k_type == 'string':
                val = r.get(example_key)
                val_preview = str(val)
            elif k_type == 'hash':
                val = r.hgetall(example_key)
                val_preview = str(val)
            elif k_type == 'list':
                val = r.lrange(example_key, 0, 10)
                val_preview = str(val)
            elif k_type == 'set':
                val = r.smembers(example_key)
                val_preview = str(val)
            elif k_type == 'zset':
                val = r.zrange(example_key, 0, 10, withscores=True)
                val_preview = str(val)
            elif k_type == 'stream':
                # Just get length for stream
                length = r.xlen(example_key)
                val_preview = f"(Stream len={length})"
            else:
                val_preview = "(unknown structure)"

            # Truncate
            if len(val_preview) > 150:
                val_preview = val_preview[:150] + "..."

            print(f"\nPattern: {pattern}")
            print(f"  Sample: {example_key}")
            print(f"  Type:   {k_type}")
            print(f"  TTL:    {ttl}")
            print(f"  Value:  {val_preview}")

        except Exception as e:
            print(f"  Error inspecting {example_key}: {e}")

if __name__ == "__main__":
    main()
