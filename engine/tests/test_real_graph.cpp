#include <gtest/gtest.h>

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <limits>
#include <random>
#include <string>

#include "../include/geo.hpp"
#include "../include/graph.hpp"
#include "../include/router.hpp"

namespace fs = std::filesystem;

// Exported city graphs live in data/processed (git-ignored; made by data-pipeline).
// These tests check whatever is there and skip if nothing has been exported.
TEST(RealGraph, EveryExportedGraphLoadsAndHonoursTheAStarContract) {
    const fs::path dir = CONDUIT_PROCESSED_DIR;
    int checked = 0;

    if (fs::exists(dir)) {
        for (const auto& entry : fs::directory_iterator(dir)) {
            if (entry.path().extension() != ".graph") {
                continue;
            }
            SCOPED_TRACE(entry.path().string());

            conduit::RoadGraph g;
            g.loadFromFile(entry.path().string());
            ASSERT_GT(g.nodeCount(), 0u);
            ASSERT_GT(g.edgeCount(), 0u);

            std::size_t violations = 0;
            for (conduit::NodeId u = 0; u < g.nodeCount(); ++u) {
                for (const auto& e : g.outEdges(u)) {
                    const auto& a = g.node(e.from);
                    const auto& b = g.node(e.to);
                    if (e.weight < conduit::haversine(a.lat, a.lon, b.lat, b.lon)) {
                        ++violations;
                    }
                }
            }
            EXPECT_EQ(violations, 0u) << "edges shorter than the straight line";

            std::cout << "[  INFO  ] " << entry.path().filename().string() << ": "
                      << g.nodeCount() << " nodes, " << g.edgeCount() << " edges\n";
            ++checked;
        }
    }

    if (checked == 0) {
        GTEST_SKIP() << "no .graph files in " << dir;
    }
}

// A* must match Dijkstra on real streets, not just on the hand-drawn graph.
// 500 seeded random pairs per graph. The pipeline keeps only the strongly
// connected part, so every pair must have a route.
TEST(RealGraph, AStarAgreesWithDijkstraOnRandomPairs) {
    const fs::path dir = CONDUIT_PROCESSED_DIR;
    int checked = 0;

    if (fs::exists(dir)) {
        for (const auto& entry : fs::directory_iterator(dir)) {
            if (entry.path().extension() != ".graph") {
                continue;
            }
            SCOPED_TRACE(entry.path().string());

            conduit::RoadGraph g;
            g.loadFromFile(entry.path().string());
            ASSERT_GT(g.nodeCount(), 0u);
            const conduit::Router router(g);

            std::mt19937 rng(2024);
            std::uniform_int_distribution<conduit::NodeId> pick(
                0, static_cast<conduit::NodeId>(g.nodeCount() - 1));

            for (int i = 0; i < 500; ++i) {
                const conduit::NodeId from = pick(rng);
                const conduit::NodeId to = pick(rng);
                SCOPED_TRACE("pair " + std::to_string(from) + " -> " + std::to_string(to));

                const conduit::Path a = router.findRoute(from, to);
                const conduit::Path d = router.routeDijkstra(from, to);

                ASSERT_EQ(a.found, d.found);
                ASSERT_TRUE(d.found) << "graph is supposed to be strongly connected";
                EXPECT_NEAR(a.distance, d.distance, 1e-6);
                ASSERT_EQ(a.nodes.front(), from);
                ASSERT_EQ(a.nodes.back(), to);

                // The path must really walk streets and add up to the claimed distance.
                double sum = 0.0;
                for (std::size_t k = 0; k + 1 < a.nodes.size(); ++k) {
                    double best = std::numeric_limits<double>::infinity();
                    for (const auto& e : g.outEdges(a.nodes[k])) {
                        if (e.to == a.nodes[k + 1]) {
                            best = std::min(best, e.weight);
                        }
                    }
                    ASSERT_FALSE(std::isinf(best)) << "no street between consecutive path nodes";
                    sum += best;
                }
                EXPECT_NEAR(sum, a.distance, 1e-6);
            }
            ++checked;
        }
    }

    if (checked == 0) {
        GTEST_SKIP() << "no .graph files in " << dir;
    }
}