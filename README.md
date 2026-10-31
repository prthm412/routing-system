# Conduit - Routing-System

A real-time delivery routing and AI-assisted fleet dispatch system.

## Project status

Development - 1 : C++ Routing Engine and NYC Data Pipeline

Development - 2 : Python Bindings for the C++ Routing Engine

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
 - Python bridge (pybind11): the `conduit_core` module exposes `load_city`, `nearest_node` and `find_route` to Python; results are plain data and engine errors become Python exceptions
 - pytest suite for the bridge, including checks against the real New York graph (skipped when the graph has not been generated)

The routing engine can be called from Python. The API, simulation and dashboard are not built yet.

Design decisions: 
 - [docs/adr/0001-nyc-single-city-bounded-graph.md](docs/adr/0001-nyc-single-city-bounded-graph.md)
 - [docs/adr/0002-python-bridge-city-handle.md](docs/adr/0002-python-bridge-city-handle.md)

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
pytest
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

If you run a container command directly from Git Bash with a Linux path in it, put `MSYS_NO_PATHCONV=1` in front, otherwise Git Bash rewrites the path.

Instructions for later components will be added as they are implemented and verified.