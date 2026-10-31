# 0002: Python bridge: one City handle, plain-data results

Status: accepted

## Context
The service needs the C++ router from Python. The `Router` keeps a reference to the `RoadGraph`, so the graph must outlive it, and a copied router would point at the wrong graph.

## Decision
- Module `conduit_core`, built with pybind11 2.13.6 from `engine/bindings/python_bindings.cpp`, only when `CONDUIT_BUILD_PYTHON=ON`.
- Built and run in the `service` dev container (`python:3.12-slim`), the same Python the service will run. The engine's own tests stay in the gcc 15 container. The extension is compiled by the service image's g++ (14 when this was written).
- `load_city(path)` returns a `City` that owns the graph, router and spatial index, declared in that order so the graph is built first and destroyed last. `City` cannot be copied or moved, and Python cannot construct one directly.
- Results are plain data. `Route` (`found`, `distance_m`, `nodes`) is a copy and stays valid after its `City` is gone.
- Errors: unreadable, malformed or empty graph file -> `RuntimeError`; non-finite or out-of-range coordinates -> `ValueError`; unknown node id -> `IndexError`; negative, too large or non-integer node ids -> `TypeError`. An unreachable destination is `Route.found == False`, not an exception.
- Empty graphs are refused at load, so `nearest_node` can never return the engine's internal "no node" marker.
- Dijkstra stays a C++ test reference and is not exposed.

## Consequences
- `nearest_node` always returns a node, however far away. The API (Phase 3) must reject points outside the box or beyond a maximum snap distance (see 0001).
- Node coordinates are not exposed yet. Phase 3 adds them when routes need to be drawn.
- The GIL is held during `find_route`, so concurrent Python threads cannot run it at the same time. Thread-safety of the engine itself has not been analysed.
- The module is built without Release flags in development. Any benchmark or deployment must use a Release build.