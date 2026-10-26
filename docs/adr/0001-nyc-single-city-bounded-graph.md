# 0001: Single-city, bounded New York graph

Status: accepted

## Context
The MVP proves the routing approach on one city. A larger graph would be slower to download, export and draw without proving anything more.

## Decision
- Area: west -74.020, south 40.700, east -73.965, north 40.765 (roughly 4.6 km x 7.2 km, Lower Manhattan up through Midtown, plus edges of Brooklyn and Queens).
- Source: OpenStreetMap drivable network via osmnx 2.1.1. osmnx simplifies the network at download time, so there is no separate simplify step. Only the strongly connected part is kept, so every node can reach every other.
- Measured: 2210 nodes / 4465 edges downloaded; 2151 / 4364 after the connectivity filter; 2151 nodes / 4353 edges exported (self-loops dropped, parallel edges merged to the shortest).
- Graph contract ("conduit-graph v1"): dense node ids 0..N-1; directed edges (one-way streets are one edge); weight in meters; no edge shorter than the straight-line distance between its endpoints, which keeps the A* heuristic admissible; one edge per (from, to).

## Consequences
- The engine snaps any coordinate to its nearest node, even one thousands of meters away (a test point in Harlem snapped 5262.6 m). The API (Phase 3) must reject points outside the box or beyond a maximum snap distance.
- A bigger area is the same pipeline run with a new box. Other cities are deferred.
- Generated graphs are not committed (`data/raw`, `data/processed`); the pipeline regenerates them.
- Map data is (c) OpenStreetMap contributors (ODbL) and needs attribution wherever it is displayed.