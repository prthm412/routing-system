#include <gtest/gtest.h>

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>

#include "../include/geo.hpp"
#include "../include/graph.hpp"
#include "../include/spatial_index.hpp"

using conduit::haversine;
using conduit::kInvalidNode;
using conduit::NodeId;
using conduit::RoadGraph;
using conduit::SpatialIndex;

namespace {

const std::string kSamples = CONDUIT_SAMPLES_DIR;

std::filesystem::path writeTemp(const std::string& name, const std::string& content) {
    const auto path = std::filesystem::temp_directory_path() / name;
    std::ofstream out(path, std::ios::binary);
    out << content;
    return path;
}

class IndexTiny : public ::testing::Test {
protected:
    void SetUp() override { graph.loadFromFile(kSamples + "/tiny.graph"); }
    RoadGraph graph;
};

}  // namespace

TEST_F(IndexTiny, EveryNodeFindsItself) {
    SpatialIndex index(graph);
    EXPECT_EQ(index.size(), 7u);
    for (NodeId id = 0; id < graph.nodeCount(); ++id) {
        EXPECT_EQ(index.nearest(graph.node(id).lat, graph.node(id).lon), id);
    }
}

TEST_F(IndexTiny, PointNearANodeFindsThatNode) {
    SpatialIndex index(graph);
    EXPECT_EQ(index.nearest(40.70003, -73.99997), 0u);  // a few meters off node 0
    EXPECT_EQ(index.nearest(40.7019, -73.9971), 6u);    // next to the island
    EXPECT_EQ(index.nearest(40.7004, -73.9996), 0u);    // nearer 0 than 1, 3 or 4
}

TEST_F(IndexTiny, FarAwayPointStillGetsTheNearestNode) {
    SpatialIndex index(graph);
    EXPECT_EQ(index.nearest(41.0, -73.0), 6u);   // far north-east
    EXPECT_EQ(index.nearest(40.0, -75.0), 0u);   // far south-west
}

TEST(SpatialIndex, EmptyGraphReturnsInvalidNode) {
    const auto path = writeTemp("conduit_idx_empty.graph", "conduit-graph v1\nnodes 0\nedges 0\n");
    RoadGraph g;
    g.loadFromFile(path.string());
    SpatialIndex index(g);
    EXPECT_EQ(index.nearest(40.7, -74.0), kInvalidNode);
    std::filesystem::remove(path);
}

TEST_F(IndexTiny, RejectsBadCoordinates) {
    SpatialIndex index(graph);
    const double nan = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(index.nearest(nan, -74.0), std::invalid_argument);
    EXPECT_THROW(index.nearest(40.7, nan), std::invalid_argument);
    EXPECT_THROW(index.nearest(91.0, -74.0), std::invalid_argument);
    EXPECT_THROW(index.nearest(40.7, 181.0), std::invalid_argument);
}

TEST(SpatialIndex, ExactTieGoesToLowestId) {
    // Two nodes exactly the same distance from the query point.
    const auto path = writeTemp(
        "conduit_idx_tie.graph",
        "conduit-graph v1\nnodes 2\nedges 0\n0 40.0 -74.0\n1 40.0 -73.0\n");
    RoadGraph g;
    g.loadFromFile(path.string());
    SpatialIndex index(g);
    EXPECT_EQ(index.nearest(40.0, -73.5), 0u);
    std::filesystem::remove(path);
}

// The strong test: 2000 random nodes, 5000 random queries, and every answer is
// compared against checking all nodes one by one with haversine.
TEST(SpatialIndex, MatchesBruteForceOnRandomData) {
    std::mt19937 rng(12345);
    std::uniform_real_distribution<double> nodeLat(40.70, 40.80);
    std::uniform_real_distribution<double> nodeLon(-74.02, -73.93);

    constexpr int kNodes = 2000;
    std::ostringstream text;
    text << "conduit-graph v1\nnodes " << kNodes << "\nedges 0\n" << std::fixed
         << std::setprecision(6);
    for (int i = 0; i < kNodes; ++i) {
        text << i << ' ' << nodeLat(rng) << ' ' << nodeLon(rng) << '\n';
    }
    const auto path = writeTemp("conduit_idx_random.graph", text.str());
    RoadGraph g;
    g.loadFromFile(path.string());
    std::filesystem::remove(path);

    SpatialIndex index(g);

    // Queries come from a slightly wider box, so some are outside the nodes.
    std::uniform_real_distribution<double> queryLat(40.68, 40.82);
    std::uniform_real_distribution<double> queryLon(-74.05, -73.90);

    for (int q = 0; q < 5000; ++q) {
        const double lat = queryLat(rng);
        const double lon = queryLon(rng);

        double bestDist = std::numeric_limits<double>::infinity();
        for (NodeId id = 0; id < g.nodeCount(); ++id) {
            bestDist = std::min(bestDist, haversine(lat, lon, g.node(id).lat, g.node(id).lon));
        }

        const NodeId got = index.nearest(lat, lon);
        ASSERT_NE(got, kInvalidNode);
        const double gotDist = haversine(lat, lon, g.node(got).lat, g.node(got).lon);
        // Half a meter of slack: the index measures on a flat sheet, brute force on a sphere.
        EXPECT_LE(gotDist, bestDist + 0.5) << "query " << q << " at " << lat << "," << lon;
    }
}