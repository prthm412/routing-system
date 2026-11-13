# Conduit - Routing-System

A real-time delivery routing and AI-assisted fleet dispatch system.

## Project status

Development - 1 : C++ Routing Engine and NYC Data Pipeline

Development - 2 : Python Bindings for the C++ Routing Engine

Development - 3 : FastAPI Service, PostgreSQL/PostGIS Persistence and Vehicle Assignment

## Planned technology stack

- C++: A* routing engine and spatial indexing
- Python: FastAPI, pybind11, vehicle simulation
- PostgreSQL + PostGIS: Spatial data persistence
- Redis + WebSockets: Real-time updates
- React + Leaflet: Live fleet dashboard
- Machine Learning: Delivery ETA prediction
- Claude API: Tool-calling dispatch engine
- Docker Compose: Containerized development

## Initial Scope

This will initially support a bounded New York City road network and a simulated fleet of delivery vehicles.

I will implement it incrementally with verified integration checkpoints.

## Current functionality

 - Data pipeline: downloads drivable street network for a bounding box from OpenStreetMap (osmnx) and exports it to a simple text format
 - C++ graph loader with validation (directed edges, distance in meters)
 - A* router with a straight-line heuristic haversine, checked against a reference Dijkstra implementation
 - k-d tree spatial index that finds the nearest road intersection to a coordinate
 - Unit tests (GoogleTest), including checks on the real New York graph
 - `route-cli`: a command-line tool for trying routes on a real graph
 - Python bridge (pybind11): the `conduit_core` module exposes `load_city`, `nearest_node`, `snap`, `coordinates` and `find_route` to Python; results are plain data and engine errors become Python exceptions
 - pytest suite for the bridge, including checks against the real New York graph (skipped when the graph has not been generated)
 - FastAPI service: loads the city graph once at startup (the app refuses to start without it) and serves `POST /deliveries`, `GET /deliveries/{id}`, `GET /vehicles` and `GET /health`; interactive API docs at `/docs`
 - Delivery requests are validated: both points inside the map box, each within 300 m of a road node, pickup and dropoff on different nodes; errors are explicit (`outside_map`, `too_far_from_road`, `same_location`, `route_not_found`, `no_idle_vehicle`)
 - Vehicle assignment: the nearest idle vehicle by road distance, with a route for each leg (vehicle to pickup, pickup to dropoff); two simultaneous requests can never get the same vehicle (atomic claim in one transaction, backed by a database constraint)
 - PostgreSQL + PostGIS persistence: vehicles, deliveries and routes (each route leg stored as a PostGIS line), with the schema managed by Alembic migrations
 - Demo fleet: `python -m app.db.seed` puts 5 idle vehicles on road nodes, the same ones every time
 - Test suites: unit tests that need no database, and integration tests that build a temporary database from the migrations, including a test where simultaneous requests race for one vehicle

A delivery can be requested through the REST API, assigned to the nearest idle vehicle and routed. Vehicles do not move yet and the ETA is not computed yet. The simulation, real-time updates and the dashboard are not built yet.

Design decisions: 
 - [docs/adr/0001-nyc-single-city-bounded-graph.md](docs/adr/0001-nyc-single-city-bounded-graph.md)
 - [docs/adr/0002-python-bridge-city-handle.md](docs/adr/0002-python-bridge-city-handle.md)
 - [docs/adr/0003-delivery-assignment-and-persistence.md](docs/adr/0003-delivery-assignment-and-persistence.md)

Road data: (c) OpenStreetMap contributors (ODbL).

## Future work

Multi-city support, advanced assignment optimization, an independent analytics worker and extended observability are planned after the MVP.

## Development

Everything runs in Docker. Commands are for Git Bash on Windows from the repository root.

Generate the graph (graph files are git-ignored, so a fresh clone needs this first; the download depends on the public OpenStreetMap server and can take a minute or two):

```bash
docker compose run --rm pipeline python fetch_city.py --name nyc --west=-74.020 --south=40.700 --east=-73.965 --north=40.765
docker compose run --rm pipeline python export_graph.py --name nyc
```

Build and test the engine:

```bash
docker compose run --rm engine bash
cmake -S . -B /build
cmake --build /build
/build/conduit_tests
```

Try a route (release build, inside the same container shell):

```bash
cmake -S . -B /build/release -DCMAKE_BUILD_TYPE=Release
cmake --build /build/release --target route_cli
/build/release/route_cli /data/processed/nyc.graph 40.7484 -73.9857 40.7527 -73.9772
```

Arguments are `<graph-file> <from-lat> <from-lon> <to-lat> <to-lon>`.

Build the Python bridge and run its tests (the real-graph tests need the graph from the first step and are skipped without it):

```bash
docker compose run --rm service bash
cmake -S /engine -B /build-py -DCONDUIT_BUILD_PYTHON=ON -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build /build-py --target conduit_core
pytest tests/unit
```

Use it from Python (inside the same container shell):
```python
import conduit_core

city = conduit_core.load_city("/data/processed/nyc.graph")
a = city.nearest_node(40.7484, -73.9857)
b = city.nearest_node(40.7527, -73.9772)
route = city.find_route(a, b)
print(route.found, route.distance_m, route.nodes)
```

Create the settings file (the defaults work for local development; `.env` is git-ignored):

```bash
cp .env.example .env
```

Run the API. It needs the graph from the first step and the compiled bridge from the previous one. Start the database, create the tables and put the demo fleet on the map:

```bash
docker compose up -d db
docker compose run --rm service alembic upgrade head
docker compose run --rm service python -m app.db.seed
```

Open the service shell with `--service-ports` in one window only (a second shell with it would collide on port 8000), then start the server:

```bash
docker compose run --rm --service-ports service bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

The API docs are at http://localhost:8000/docs. From another Git Bash window, without `--service-ports`:

```bash
curl -s http://localhost:8000/vehicles
curl -s -X POST http://localhost:8000/deliveries -H "Content-Type: application/json" -d '{"pickup": {"lat": 40.7484, "lon": -73.9857}, "dropoff": {"lat": 40.7527, "lon": -73.9772}}'
```

Vehicles do not move yet, so they stay busy after being assigned. To reset the dev data:

```bash
docker compose exec db psql -U conduit -d conduit -c "TRUNCATE routes, deliveries"
docker compose exec db psql -U conduit -d conduit -c "UPDATE vehicles SET status = 'idle'"
```

Run the service tests. Unit tests need no database; integration tests create and drop their own temporary databases (`conduit_test_*`) on the running `db` container and never touch the dev data:

```bash
docker compose run --rm service pytest tests/unit
docker compose up -d db
docker compose run --rm service pytest tests/integration
```

If you change `POSTGRES_PASSWORD` in `.env` after the first start, the database keeps the old password. Reset only its volume (not `docker compose down -v`, which also deletes the compiled bridge):

```bash
docker compose down
docker volume rm routing-system_db-data
```

If you run a container command directly from Git Bash with a Linux path in it, put `MSYS_NO_PATHCONV=1` in front, otherwise Git Bash rewrites the path.

Instructions for later components will be added as they are implemented and verified.