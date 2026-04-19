# Rider Dispatch — Redis Geo Available Orders

## What changed?

The rider dispatch flow now works more like Uber/Chowdeck:

- a new order is shown to **all eligible riders near the vendor**
- Redis Geo is used to find nearby riders fast
- the backend still uses the database as the final source of truth for assignment
- the **first rider to accept wins**
- once one rider accepts, the order is removed from the other riders

This is intentionally different from the old behavior where proximity logic was scattered in multiple places and could feel like only one nearby rider got the order.

---

## The goal

When an order becomes available, the system should answer:

**"Which riders near this vendor should see this order right now?"**

The system should then:

1. fan the order out to all eligible nearby riders
2. let the first rider claim it
3. remove it from everyone else

That is the core dispatch loop.

---

## Redis keys used

The new rider geo flow uses two Redis keys:

```text
riders:geo
riders:geo:freshness
```

### `riders:geo`

This is a Redis geo index storing rider coordinates.

Example mental model:

```text
Key: riders:geo

Member            Coordinates
----------------  -------------------
"rider-uuid-1"    (6.5244, 3.3792)
"rider-uuid-2"    (6.6018, 3.3515)
"rider-uuid-3"    (6.4654, 3.4064)
```

### `riders:geo:freshness`

This is a sorted set storing the rider's latest location timestamp.

Example mental model:

```text
Key: riders:geo:freshness

Member            Score
----------------  ----------
"rider-uuid-1"    1713545200
"rider-uuid-2"    1713545205
"rider-uuid-3"    1713545198
```

This lets us remove stale riders if they stop sending location updates.

---

## Main flow

## 1. Rider location updates

When a rider updates location:

- the rider's `current_latitude/current_longitude` is saved in the DB
- `location_updated_at` is updated
- if the rider is online, the rider is added/updated in Redis Geo

This happens in [models.py](file:///Users/smith/Documents/findmytaste-project/backend/account/models.py#L696-L735).

If a rider goes offline, the rider is removed from Redis Geo in [models.py](file:///Users/smith/Documents/findmytaste-project/backend/account/models.py#L737-L748).

---

## 2. Order becomes available

When a vendor-side order enters `looking_for_rider` or `awaiting_rider`, the backend needs candidate riders.

That candidate lookup now lives centrally in [websocket_notification.py](file:///Users/smith/Documents/findmytaste-project/backend/helpers/websocket_notification.py#L76-L174).

The key function is:

- `get_candidate_riders_for_order(order)`

It now works like this:

1. determine the current dispatch radius for the order
2. build neighborhood search bands
3. query Redis Geo around the vendor
4. fetch those riders from the DB
5. apply final eligibility rules
6. return ordered candidate riders

---

## 3. Neighborhood expansion

The dispatch flow uses neighborhood bands:

```text
3km -> 8km -> 15km -> 25km -> 35km
```

And it also uses a time-based dispatch radius:

```text
0s - 30s   -> 15km
31s - 120s -> 25km
120s+      -> 35km
```

This means:

- very fresh orders stay tighter first
- older unclaimed orders expand to more riders

That gives a better balance between:

- relevance
- speed
- fairness
- coverage

It is much closer to a real dispatch system than a single hard-coded radius.

---

## 4. Eligibility rules

Not every rider returned by Redis is allowed to see the order.

The backend still checks:

- rider is `active`
- rider is `verified`
- rider is `online`
- rider has not already declined that order
- rider is not busy when multi-stop is disabled
- rider is still within the current dispatch radius

This final validation happens in:

- `is_order_visible_to_rider()`

This is important:

- Redis answers **who is geographically nearby**
- the database answers **who is actually eligible**

That split is what makes the system fast but still correct.

---

## 5. How available orders are returned

The rider app calls the available-order endpoint:

- [views.py](file:///Users/smith/Documents/findmytaste-project/backend/rider/views.py#L827-L894)

That endpoint:

1. gets the rider location
2. loads available orders
3. uses the same shared visibility logic
4. returns only orders the rider should truly see

This matters because it keeps:

- websocket fanout
- push fanout
- polling/API visibility

all aligned to the same rule.

Before this, different paths could disagree.

---

## 6. How push notifications are sent

Vendor-side rider push fanout now also uses the same candidate selector:

- [vendor/views.py](file:///Users/smith/Documents/findmytaste-project/backend/vendor/views.py#L1932-L1956)

So when a new order is sent:

- nearby rider list comes from the same dispatch engine
- push and websocket do not drift apart

---

## 7. First accept wins

The final assignment still happens in the database, not Redis.

That happens in:

- [views.py](file:///Users/smith/Documents/findmytaste-project/backend/rider/views.py#L896-L931)

The flow is:

1. rider taps accept
2. backend opens a DB transaction
3. order row is locked with `select_for_update()`
4. if another rider already got it, reject this acceptance
5. otherwise assign the rider

This is the critical correctness rule.

Redis helps with **fast lookup**, but the database guarantees:

- no double assignment
- first-accept wins

---

## 8. Removing the order from other riders

Once one rider accepts:

- the accepted rider gets assignment notification
- other nearby riders get an `order_accepted_notification`
- their apps remove the order from available orders

That cleanup logic lives in:

- [websocket_notification.py](file:///Users/smith/Documents/findmytaste-project/backend/helpers/websocket_notification.py#L176-L197)

This is what makes the “race” feel clean in the UI.

---

## Redis fallback behavior

If Redis is unavailable:

- the dispatch logic does **not** break
- the backend falls back to the DB/Python distance scan

That means:

- slower, but still functional
- no total outage for available orders

This fallback is implemented in:

- [websocket_notification.py](file:///Users/smith/Documents/findmytaste-project/backend/helpers/websocket_notification.py#L111-L174)

---

## Freshness and stale riders

The backend now tracks rider freshness in Redis and can remove stale riders from the geo index.

This is handled in:

- [redis_rider_geo.py](file:///Users/smith/Documents/findmytaste-project/backend/helpers/redis_rider_geo.py)

Key behavior:

- rider location update writes both geo position and timestamp
- stale riders can be removed from Redis by freshness
- query path performs stale cleanup before searching

This prevents long-dead locations from staying in the nearby rider pool forever.

---

## Management commands

Two new commands support operations:

### Rebuild the rider geo index

```bash
python manage.py populate_rider_redis_geo
```

Use this:

- after first deploy
- after Redis reset
- after restoring a backup
- after large rider data imports

### Cleanup stale rider geo entries

```bash
python manage.py cleanup_rider_redis_geo
python manage.py cleanup_rider_redis_geo --max-age-seconds 180
```

Use this:

- from cron
- from a scheduler
- during ops/debugging

---

## Why Redis helps available orders

Without Redis:

- every dispatch query needs to inspect lots of riders in Python/DB
- distance checks grow with rider count
- latency grows as the city grows

With Redis Geo:

- nearby-rider lookup is fast
- neighborhood expansion is cheap
- fanout can scale to many riders
- the DB is reserved for correctness and final assignment

In simple terms:

- Redis decides **who is near**
- Django/DB decides **who is eligible**
- SQL transaction decides **who wins**

That is the right split for a dispatch system.

---

## Recommended production routine

On deploy:

1. ensure Redis is reachable
2. run:

```bash
python manage.py populate_rider_redis_geo
```

3. verify counts:

```bash
redis-cli -u $REDIS_URL ZCARD riders:geo
redis-cli -u $REDIS_URL ZCARD riders:geo:freshness
```

4. optionally schedule:

```bash
python manage.py cleanup_rider_redis_geo --max-age-seconds 120
```

every 1-5 minutes

---

## Current architecture summary

The available-order system now behaves like this:

```text
Rider updates location
    -> DB location updated
    -> Redis GEO updated

Order becomes available
    -> Redis finds nearby riders by neighborhood bands
    -> DB filters final eligibility
    -> websocket + push fanout to all eligible nearby riders

One rider accepts
    -> DB row lock enforces first-accept-wins
    -> assigned rider gets the order
    -> other riders get removal event
```

That is the new stable dispatch model.
