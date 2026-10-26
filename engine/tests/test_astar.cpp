#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include "../include/graph.hpp"
#include "../include/router.hpp"

using conduit::NodeId;
using conduit::Path;
using conduit::RoadGraph;
using conduit::Router;

namespace {

const std::string kSamples = CONDUIT_SAMPLES_DIR;
using Nodes = std::vector<NodeId>;

// Is `p` a real route from `from` to `to`, and does its length add up?
// Checked by walking the streets, so it works even when two routes tie.
bool isValidPath(const RoadGraph& g, const Path& p, NodeId from, NodeId to) {
    if (!p.found || p.nodes.empty() || p.nodes.front() != from ||
        p.nodes.back() != to) {
        return false;
    }
    double total = 0.0;
    for (std::size_t i = 0; i + 1 < p.nodes.size(); ++i) {
        double best = std::numeric_limits<double>::infinity();
        for (const auto& e : g.outEdges(p.nodes[i])) {
            if (e.to == p.nodes[i + 1]) {
                best = std::min(best, e.weight);
            }
        }
        if (std::isinf(best)) {
            return false;  // consecutive nodes with no street between them
        }
        total += best;
    }
    return std::abs(total - p.distance) < 1e-9;
}

// A* and Dijkstra must agree on every possible (from, to) pair.
void expectAgreeOnAllPairs(const RoadGraph& g) {
    Router router(g);
    for (NodeId from = 0; from < g.nodeCount(); ++from) {
        for (NodeId to = 0; to < g.nodeCount(); ++to) {
            SCOPED_TRACE("from " + std::to_string(from) + " to " + std::to_string(to));
            const Path astar = router.findRoute(from, to);
            const Path dijkstra = router.routeDijkstra(from, to);
            ASSERT_EQ(astar.found, dijkstra.found);
            if (!dijkstra.found) {
                EXPECT_TRUE(astar.nodes.empty());
                continue;
            }
            EXPECT_NEAR(astar.distance, dijkstra.distance, 1e-9);
            EXPECT_TRUE(isValidPath(g, astar, from, to));
        }
    }
}

class AStarTiny : public ::testing::Test {
protected:
    void SetUp() override { graph.loadFromFile(kSamples + "/tiny.graph"); }
    RoadGraph graph;
};

}  // namespace

TEST_F(AStarTiny, ShortestPathAcrossTown) {
    Router router(graph);
    const Path p = router.findRoute(0, 5);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 282.0);
    EXPECT_EQ(p.nodes, (Nodes{0, 1, 4, 5}));
}

TEST_F(AStarTiny, OneWayStreetForcesTheLongWayBack) {
    Router router(graph);
    const Path p = router.findRoute(4, 3);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 309.0);
    EXPECT_EQ(p.nodes, (Nodes{4, 1, 0, 3}));
}

TEST_F(AStarTiny, StartEqualsDestination) {
    Router router(graph);
    const Path p = router.findRoute(2, 2);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 0.0);
    EXPECT_EQ(p.nodes, (Nodes{2}));
}

TEST_F(AStarTiny, UnreachableDestinationIsNotAnError) {
    Router router(graph);
    const Path p = router.findRoute(0, 6);
    EXPECT_FALSE(p.found);
    EXPECT_TRUE(p.nodes.empty());
}

TEST_F(AStarTiny, UnknownNodeThrows) {
    Router router(graph);
    EXPECT_THROW(router.findRoute(99, 0), std::out_of_range);
    EXPECT_THROW(router.findRoute(0, 99), std::out_of_range);
}

TEST_F(AStarTiny, AgreesWithDijkstraOnEveryPair) {
    expectAgreeOnAllPairs(graph);
}

TEST(AStarDetour, PrefersShorterOverFewerStreets) {
    RoadGraph graph;
    graph.loadFromFile(kSamples + "/detour.graph");
    Router router(graph);
    const Path p = router.findRoute(0, 2);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 180.0);
    EXPECT_EQ(p.nodes, (Nodes{0, 1, 2}));
}

TEST(AStarDetour, AgreesWithDijkstraOnEveryPair) {
    RoadGraph graph;
    graph.loadFromFile(kSamples + "/detour.graph");
    expectAgreeOnAllPairs(graph);
}