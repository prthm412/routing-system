"""
Convert a downloaded GraphML street network into the engine's text format.
Reads /data/raw/<name>.graphml
Writes /data/processed/<name>.graph ("conduit-graph v1", see engine/include/graph.hpp)

Same input -> byte-identical output.
"""

import argparse
import math
from pathlib import Path

import osmnx as ox

RAW_DIR = Path("/data/raw")
OUT_DIR = Path("/data/processed")

# Must match kEarthRadiusMeters in engine/include/geo.hpp
EARTH_RADIUS_M = 6371000.0

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Same formula as the C++ haversine(): straight-line meters on a sphere."""
    to_rad = math.pi / 180.0
    phi1, phi2 = lat1 * to_rad, lat2 * to_rad
    d_phi = (lat2 - lat1) * to_rad
    d_lambda = (lon2 - lon1) * to_rad
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="graph name, no extension")
    args = parser.parse_args()

    src = RAW_DIR / f"{args.name}.graphml"
    if not src.exists():
        parser.error(f"{src} not found; run fetch_city.py first")

    G = ox.load_graphml(src)

    # 1. Dense ids: sort the OSM ids, number them 0..N-1.
    osm_ids = sorted(G.nodes)
    new_id = {osm: i for i, osm in enumerate(osm_ids)}
    # Round coordinates to 7 decimals (~1cm) BEFORE doing any math with them
    # So the numbers we check are exactly the numbers the engine will read
    coords = [
        (round(float(G.nodes[osm]["y"]), 7), round(float(G.nodes[osm]["x"]), 7))
        for osm in osm_ids
    ]

    # 2. One edge per (from, to): keep the shortest when OSM has parallel streets.
    #    Drop self-loops (a street that returns to its own start is useless for routing).
    shortest: dict[tuple[int, int], float] = {}
    loops = 0
    merged = 0
    for u, v, data in G.edges(data=True):
        if u == v:
            loops += 1
            continue
        length = float(data["length"])
        if not math.isfinite(length) or length < 0:
            raise ValueError(f"bad edge length {length} on edge {u}->{v}")
        key = (new_id[u], new_id[v])
        if key in shortest:
            merged += 1
            shortest[key] = min(shortest[key], length)
        else:
            shortest[key] = length

    # 3. Weights in meters, rounded UP to the next centimeter
    #    NEVER below the straight-line distance (the A* contract).
    edge_lines = []
    raised = 0
    max_raise = 0.0
    for a, b in sorted(shortest):
        length = shortest[(a, b)]
        straight = haversine(*coords[a], *coords[b])
        if straight > length:
            raised += 1
            max_raise = max(max_raise, straight - length)
        weight = math.ceil(max(length, straight) * 100 + 0.001) / 100
        edge_lines.append(f"{a} {b} {weight:.2f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.name}.graph"
    with open(out, "w", newline="\n") as f:
        f.write("conduit-graph v1\n")
        f.write(f"nodes {len(coords)}\n")
        f.write(f"edges {len(edge_lines)}\n")
        for i, (lat, lon) in enumerate(coords):
            f.write(f"{i} {lat:.7f} {lon:.7f}\n")
        for line in edge_lines:
            f.write(line + "\n")

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    print(f"nodes: {len(coords)}")
    print(f"edges kept: {len(edge_lines)}  (self-loops dropped: {loops}, parallel edges merged: {merged})")
    print(f"edges raised to straight-line length: {raised}  (largest raise: {max_raise:.3f} m)")
    print(f"lat {min(lats):.5f}..{max(lats):.5f}  lon {min(lons):.5f}..{max(lons):.5f}")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KiB)")

if __name__ == "__main__":
    main()