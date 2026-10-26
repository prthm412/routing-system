#include <gtest/gtest.h>

#include <filesystem>
#include <iostream>

#include "../include/geo.hpp"
#include "../include/graph.hpp"

namespace fs = std::filesystem;

// Exported city graphs live in data/processed (git-ignored; made by data-pipeline).
// This checks whatever is there and skips if nothing has been exported.
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