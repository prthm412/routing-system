// Try a route on a real graph:
//      route_cli <graph-file> <from-lat> <from-lon> <to-lat> <to-lon>

#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

#include "../include/geo.hpp"
#include "../include/graph.hpp"
#include "../include/router.hpp"
#include "../include/spatial_index.hpp"

namespace {
    using Clock = std::chrono::steady_clock;
    constexpr int kRuns = 200;  // each search is repeated this many times for timing

    double msSince(Clock::time_point start) {
        return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
    }
}

int main(int argc, char** argv) {
    if (argc != 6) {
        std::cerr << "usage: route_cli <graph-file> <from-lat> <from-lon> <to-lat> <to-lon>\n";
        return 2;
    }

    try {
        const std::string graphPath = argv[1];
        const double fromLat = std::stod(argv[2]);
        const double fromLon = std::stod(argv[3]);
        const double toLat   = std::stod(argv[4]);
        const double toLon   = std::stod(argv[5]);

        conduit::RoadGraph graph;
        auto t = Clock::now();
        graph.loadFromFile(graphPath);
        const double loadMs = msSince(t);

        t = Clock::now();
        const conduit::SpatialIndex index(graph);
        const double indexMs = msSince(t);

        const conduit::NodeId from = index.nearest(fromLat, fromLon);
        const conduit::NodeId to   = index.nearest(toLat, toLon);
        if (from == conduit::kInvalidNode || to == conduit::kInvalidNode) {
            std::cerr << "graph has no nodes\n";
            return 1;
        }

        const conduit::Node& a = graph.node(from);
        const conduit::Node& b = graph.node(to);
        const double snapFrom = conduit::haversine(fromLat, fromLon, a.lat, a.lon);
        const double snapTo   = conduit::haversine(toLat, toLon, b.lat, b.lon);
        const double straight = conduit::haversine(a.lat, a.lon, b.lat, b.lon);

        const conduit::Router router(graph);
        const conduit::Path astar = router.findRoute(from, to);
        const conduit::Path dijkstra = router.routeDijkstra(from, to);

        std::cout << std::fixed << std::setprecision(1);
        std::cout << "graph: " << graph.nodeCount() << " nodes, " << graph.edgeCount() << " edges\n";
        std::cout << "from:  node " << from << " (snapped " << snapFrom << " m from your point)\n";
        std::cout << "to:    node " << to << " (snapped " << snapTo << " m from your point)\n";
        std::cout << "straight line between those nodes: " << straight << " m\n";

        if (!astar.found) {
            std::cout << "no route between those nodes\n";
            return 0;
        }
        std::cout << "route: " << astar.distance << " m over " << astar.nodes.size()
                  << " nodes (" << std::setprecision(2) << astar.distance / std::max(straight, 1.0)
                  << "x the straight line)\n";

        const bool agree = dijkstra.found && std::abs(astar.distance - dijkstra.distance) < 1e-6;
        std::cout << (agree ? "A* and Dijkstra agree\n" : "MISMATCH: A* and Dijkstra disagree\n");

        t = Clock::now();
        for (int i = 0; i < kRuns; i++) {
            router.findRoute(from, to);
        }
        const double astarUs = msSince(t) * 1000.0 / kRuns;

        t = Clock::now();
        for (int i = 0; i < kRuns; i++) {
            router.routeDijkstra(from, to);
        }
        const double dijkstraUs = msSince(t) * 1000.0 / kRuns;

        std::cout << std::setprecision(1);
        std::cout << "timing (avg of " << kRuns << " runs): A* " << astarUs << " us, Dijkstra " << dijkstraUs << " us\n";
        std::cout << "one-off costs: load " << loadMs << " ms, index build " << indexMs << " ms\n";
        return agree ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}