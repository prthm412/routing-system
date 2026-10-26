#include <gtest/gtest.h>

#include <string>

#include "../include/geo.hpp"
#include "../include/graph.hpp"

using conduit::haversine;
using conduit::RoadGraph;

TEST(Haversine, OneDegreeOfLatitudeIsAbout111Km) {
    EXPECT_NEAR(haversine(0.0, 0.0, 1.0, 0.0), 111195.0, 1.0);
}

TEST(Haversine, ZeroForSamePointAndSymmetric) {
    EXPECT_DOUBLE_EQ(haversine(40.7, -74.0, 40.7, -74.0), 0.0);
    EXPECT_DOUBLE_EQ(haversine(40.7, -74.0, 40.8, -73.9),
                     haversine(40.8, -73.9, 40.7, -74.0));
}

// The A* contract: no street may be shorter than the straight line between its ends.
// If a fixture ever breaks this, A* results become untrustworthy.
TEST(Haversine, NoFixtureEdgeIsShorterThanTheStraightLine) {
    for (const char* name : {"tiny.graph", "detour.graph"}) {
        RoadGraph g;
        g.loadFromFile(std::string(CONDUIT_SAMPLES_DIR) + "/" + name);
        for (conduit::NodeId u = 0; u < g.nodeCount(); ++u) {
            for (const auto& e : g.outEdges(u)) {
                const auto& a = g.node(e.from);
                const auto& b = g.node(e.to);
                EXPECT_GE(e.weight, haversine(a.lat, a.lon, b.lat, b.lon))
                    << name << ": edge " << e.from << "->" << e.to;
            }
        }
    }
}