# Redis Geo — How It Works in FindMyTaste

## What problem does it solve?

When a user opens the app we need to answer: **"Which vendors are near me, sorted by distance?"**

The naive approach is to load every vendor from the database, then run a distance formula (Haversine) in Python for each one. That works fine with 10 vendors. With 10,000 vendors it means 10,000 maths operations per request, per user — it falls over fast.

Redis has a built-in geospatial index (`GEOADD` / `GEORADIUS`) that answers the same question in **O(log N + M)** time — it does not matter if you have 100 or 10 million vendors, the query time barely changes.

---

## How Redis stores locations

Redis geo uses a **sorted set** internally. Every vendor's latitude + longitude is encoded into a single 52-bit integer called a **geohash**, which becomes the score in the sorted set. The member (the value) is the vendor's UUID.

```
Key: "vendors:geo"  (a sorted set)

Member              Score (geohash, shown as coords for readability)
------------------  -------------------------------------------------
"uuid-vendor-A"     (6.5508, 3.4044)   → Lagos, Nigeria
"uuid-vendor-B"     (8.4715, 4.6068)   → Ilorin, Nigeria
"uuid-vendor-C"     (9.0579, 7.4951)   → Abuja, Nigeria
...
```

This is **not** a separate data structure you maintain manually — it is just a Redis sorted set with coordinates baked into the scores.

---

## How a user query works

When a user at coordinates `(8.4715, 4.6068)` opens the app:

```
1. App sends:  GET /api/v1/vendors/hot-picks/?latitude=8.4715&longitude=4.6068

2. Backend calls:
   GEORADIUS vendors:geo 4.6068 8.4715 500 km WITHDIST ASC

3. Redis returns (nearest first):
   [
     ("uuid-vendor-B", 0.01),    ← 10 metres away
     ("uuid-vendor-A", 251.36),  ← 251 km away
     ("uuid-vendor-C", 197.5),   ← 197 km away
   ]

4. Backend looks those UUIDs up in one DB query:
   SELECT * FROM vendor WHERE id IN (uuid-B, uuid-A, uuid-C)

5. Attaches distance_km to each vendor object, sorts, serialises, returns.
```

The key insight: **Redis does the distance maths**, the database just fetches the rows. No Python loops.

---

## The index lifecycle

### Initial population (run once on first deploy)

```bash
python manage.py populate_redis_geo
```

This command:
1. Queries the DB for all `approved + is_active + has coordinates` vendors
2. Deletes the old `vendors:geo` key
3. Pipelines all `GEOADD` commands in one round-trip to Redis
4. Prints how many were indexed

### Staying in sync automatically (signals)

`vendor/signals.py` hooks into Django's `post_save` signal on the `Vendor` model:

```
Vendor saved → approved + active + has coords?
    YES → GEOADD vendors:geo  (adds or updates position)
    NO  → ZREM  vendors:geo   (removes from index)
```

This covers every case:
- Admin **approves** a vendor → they appear in search immediately
- Admin **rejects** a vendor → they disappear immediately
- Vendor **updates their address** → their position updates
- Vendor **deactivated** → removed from index

You never need to re-run `populate_redis_geo` after the first deploy unless you manually bulk-insert vendors directly into the database (bypassing Django).

### Checking the index

```bash
# How many vendors are indexed?
docker compose exec redis redis-cli ZCARD vendors:geo

# List all indexed vendor UUIDs
docker compose exec redis redis-cli ZRANGE vendors:geo 0 -1

# Find vendors within 10km of a point (lon lat)
docker compose exec redis redis-cli GEORADIUS vendors:geo 4.6068 8.4715 10 km WITHDIST ASC
```

---

## The fallback path

If Redis is unreachable (network blip, restart, misconfiguration), the app does **not** go dark. `filter_and_sort_vendors_by_distance` in `helpers/vendor_discovery.py` falls back automatically to the Python Haversine loop:

```
Redis available?
    YES → GEORADIUS (fast)
    NO  → Haversine loop over all vendors (slower but always works)
```

The fallback also uses `_local_distance_cache` (a process-level dict in `helpers/order_utils.py`) so within a single request the same coordinate pair is never calculated twice.

---

## enforce_delivery_radius — browsing vs ordering

Every call to `filter_and_sort_vendors_by_distance` / `nearest_first_vendors` has an `enforce_delivery_radius` flag:

| Flag value | Used for | Effect |
|---|---|---|
| `False` | Browsing (hot-picks, featured, all vendors, category pages) | All vendors shown regardless of their delivery radius |
| `True` | Order placement | Vendor must be able to deliver to the user's location |

This is intentional — customers should be able to **see** any vendor on the app, even vendors 200km away. The delivery radius only matters when they actually try to place an order.

---

## How each endpoint uses it

| Endpoint | Redis geo? | enforce_delivery_radius |
|---|---|---|
| `GET /vendors/hot-picks/` | Yes | False |
| `GET /vendors/featured/` | Yes | False |
| `GET /vendors/` (listing + search) | Yes | False |
| `GET /vendors/cached/` | Yes | False |
| `GET /products/system-categories/<id>/vendors` | Yes | False |
| `GET /marketplace/categories/<id>/vendors` | No — rating sort only | N/A |
| `POST /products/order/create-mobile-v2` (order placement) | No — direct distance check | True |

---

## Production Redis setup

### Option 1 — Redis Cloud (recommended for small/medium scale)

Redis Cloud has a free 30MB tier, enough for tens of thousands of vendors. Paid plans start at ~$7/month.

1. Sign up at [redis.io/cloud](https://redis.io/cloud)
2. Create a database, copy the connection URL: `redis://default:<password>@<host>:<port>/0`
3. Set in your production `.env`:

```env
REDIS_URL=redis://default:yourpassword@redis-xxxxx.c52.us-east-1-4.ec2.redns.redis-cloud.com:11618/0
```

That's it. `REDIS_URL` takes priority in `settings.py` over everything else.

### Option 2 — Redis on your own server (VPS/EC2)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install redis-server -y

# Enable persistence so the geo index survives restarts
sudo nano /etc/redis/redis.conf
# Set:  save 900 1
#       save 300 10
#       save 60  10000
#       appendonly yes

sudo systemctl enable redis-server
sudo systemctl start redis-server

# Lock it down — bind to localhost or your private network only
# In redis.conf:   bind 127.0.0.1
# Set a password:  requirepass yourStrongPassword
```

Then set in `.env`:
```env
REDIS_URL=redis://:yourStrongPassword@your-server-ip:6379/0
```

### Option 3 — Docker in production (current docker-compose.yml)

Your existing `docker-compose.yml` already runs Redis 7 as a service. For production just add persistence so the geo index survives container restarts:

```yaml
redis:
  image: redis:7
  command: redis-server --appendonly yes --save 900 1 --save 300 10
  ports:
    - "6379:6379"   # don't expose publicly — remove this in prod
  volumes:
    - redis_data:/data
  restart: always
```

Remove the port mapping (`6379:6379`) in production so Redis is not exposed to the internet — only the `web` container needs to reach it via the Docker internal network using hostname `redis`.

### After any production Redis setup

Always re-run the populate command after first deploy or after restoring from backup:

```bash
python manage.py populate_redis_geo
```

Check it worked:
```bash
redis-cli -u $REDIS_URL ZCARD vendors:geo
# Should print the number of indexed vendors
```

---

## Scaling numbers (for reference)

| Vendors indexed | GEORADIUS query time | RAM used |
|---|---|---|
| 1,000 | ~0.1 ms | ~100 KB |
| 100,000 | ~1 ms | ~10 MB |
| 1,000,000 | ~5 ms | ~100 MB |

Redis geo scales to millions of entries on a single node. You will not need to think about sharding for a very long time.
