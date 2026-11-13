# 0003: Delivery assignment, persistence and request validation

Status: accepted

## Context
Phase 3 turns the routing engine into a service: a delivery request must be validated, assigned to a vehicle, routed and stored, and two requests arriving together must never get the same vehicle. The engine always snaps a point to some node (see 0002), so the service has to decide what is too far away.

## Decision
Persistence
- PostgreSQL with PostGIS (`postgis/postgis:16-3.4`), SQLAlchemy 2 with psycopg 3, synchronous sessions in plain `def` endpoints, hand-written Alembic migrations.
- Tables `vehicles`, `deliveries`, `routes`. Statuses are VARCHAR with CHECK constraints: vehicle `idle` / `to_pickup` / `to_dropoff`, delivery `assigned` / `picked_up` / `delivered`.
- PostGIS and GeoAlchemy2 are used for one column only: `routes.geometry` (LineString, SRID 4326, GiST index created in the migration). Writes use WKT, reads use `ST_AsGeoJSON`; no shapely and no other spatial queries. The first migration runs `CREATE EXTENSION IF NOT EXISTS postgis`, because a database created from the default template does not have it (tested).
- Each delivery has two route rows, `to_pickup` (vehicle -> pickup) and `to_dropoff` (pickup -> dropoff), unique per `(delivery_id, leg)`. The plan has one route per delivery; two legs need two rows. Distance is stored in meters (`distance_m`; the plan says km). `duration_sec` and `eta` stay empty until a speed model exists. A leg with a single node (vehicle already at the pickup) has `geometry = NULL` and an empty path in the API.

Assignment
- The pickup -> dropoff leg is planned first. Then each idle vehicle is routed to the pickup with A*, starting from the node its position snaps to. Vehicles that cannot reach the pickup are skipped, the nearest by road distance wins, and ties go to the lowest id.
- A* runs outside any transaction. The claim is one `UPDATE vehicles SET status = 'to_pickup' WHERE id = ... AND status = 'idle'`; 0 rows updated means another request took that vehicle, so the next candidate is tried. The claim and all inserts commit in one transaction, so a failure rolls the claim back (tested).
- Second line of defense: a partial unique index on `deliveries(vehicle_id)` for the active statuses, so a vehicle can never have two active deliveries even if the code is wrong.
- Rejected: `FOR UPDATE SKIP LOCKED` on the idle vehicles while ranking. It would hold locks during A* and could make concurrent requests see an empty fleet.
- Verified: 8 simultaneous requests for one idle vehicle create exactly one delivery, in the integration test and against the running app (one 201, seven 409).

Validation
- Both points must lie inside the box from 0001 (the edges count as inside) and snap within `MAX_SNAP_DISTANCE_M = 300` m of a node. Pickup and dropoff on the same node are rejected.
- Measured on the real graph with a 0.001 degree grid over the box (3696 points): median 76 m, 90th percentile 635 m, maximum 1529 m, 828 points (22.4%) above 300 m; the worst points lie along the box edges. Ten hand-picked land spots (coordinates from memory) snapped within 74-218 m, the worst being Stuyvesant Town. The distances have no clean gap, so 300 m is a judgement call: it leaves about 80 m above the worst land spot.
- Our errors are `{"detail": {"code", "message"}}`: 422 `outside_map`, `too_far_from_road`, `same_location`, `route_not_found`; 409 `no_idle_vehicle`; 404 `delivery_not_found`. FastAPI's own validation errors keep their list-shaped `detail`, so clients must handle both.
- JSON points are `{lat, lon}` and paths are `[lat, lon]` pairs, the order Leaflet expects. WKT and GeoJSON are lon/lat, so the swap happens at the API boundary.

Engine access
- `app/core/engine_bridge.py` is the only module that imports `conduit_core`. The city is loaded once at startup and the app refuses to start without it. The bridge gained `City.snap` and `City.coordinates`, both bounds-checked in C++.
- The GIL stays held, so FastAPI's worker threads call the engine one at a time. Thread-safety of the engine itself is still not analysed.

## Consequences
- Route lines join intersections with straight segments. The graph has no street shapes, so lines cut corners on curved streets.
- Pickup and dropoff are stored as requested, but the legs run between their snapped nodes (up to 300 m away).
- Assignment runs one A* per idle vehicle. That is fine for the 5-vehicle demo fleet; no timings have been measured.
- Assignment assumes an idle vehicle sits on a node (seeded vehicles do). Any other position is snapped to the nearest node.
- A request with no idle vehicle is rejected with 409; there is no waiting queue.
- Vehicles do not move yet. The simulator (Phase 4) must drive the status changes after `to_pickup`.