#include <gtest/gtest.h>

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

// Loads tiny.graph fresh for every test.
class DijkstraTiny : public ::testing::Test {
protected:
    void SetUp() override { graph.loadFromFile(kSamples + "/tiny.graph"); }
    RoadGraph graph;
};

using Nodes = std::vector<NodeId>;

}  // namespace

TEST_F(DijkstraTiny, ShortestPathAcrossTown) {
    Router router(graph);
    const Path p = router.routeDijkstra(0, 5);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 282.0);
    EXPECT_EQ(p.nodes, (Nodes{0, 1, 4, 5}));
}

TEST_F(DijkstraTiny, OneWayStreetForcesTheLongWayBack) {
    Router router(graph);
    const Path p = router.routeDijkstra(4, 3);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 309.0);
    EXPECT_EQ(p.nodes, (Nodes{4, 1, 0, 3}));
}

TEST_F(DijkstraTiny, DirectOneWayStreet) {
    Router router(graph);
    const Path p = router.routeDijkstra(3, 4);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 87.0);
    EXPECT_EQ(p.nodes, (Nodes{3, 4}));
}

TEST_F(DijkstraTiny, StraightRun) {
    Router router(graph);
    const Path p = router.routeDijkstra(0, 2);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 175.0);
    EXPECT_EQ(p.nodes, (Nodes{0, 1, 2}));
}

TEST_F(DijkstraTiny, StartEqualsDestination) {
    Router router(graph);
    const Path p = router.routeDijkstra(2, 2);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 0.0);
    EXPECT_EQ(p.nodes, (Nodes{2}));
}

TEST_F(DijkstraTiny, UnreachableDestinationIsNotAnError) {
    Router router(graph);
    const Path p = router.routeDijkstra(0, 6);
    EXPECT_FALSE(p.found);
    EXPECT_TRUE(p.nodes.empty());
}

TEST_F(DijkstraTiny, IslandCannotLeave) {
    Router router(graph);
    const Path p = router.routeDijkstra(6, 0);
    EXPECT_FALSE(p.found);
    EXPECT_TRUE(p.nodes.empty());
}

TEST_F(DijkstraTiny, UnknownNodeThrows) {
    Router router(graph);
    EXPECT_THROW(router.routeDijkstra(99, 0), std::out_of_range);
    EXPECT_THROW(router.routeDijkstra(0, 99), std::out_of_range);
}

TEST(DijkstraDetour, PrefersShorterOverFewerStreets) {
    RoadGraph graph;
    graph.loadFromFile(kSamples + "/detour.graph");
    Router router(graph);
    const Path p = router.routeDijkstra(0, 2);
    ASSERT_TRUE(p.found);
    EXPECT_DOUBLE_EQ(p.distance, 180.0);
    EXPECT_EQ(p.nodes, (Nodes{0, 1, 2}));
}