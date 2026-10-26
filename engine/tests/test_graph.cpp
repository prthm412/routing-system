#include <gtest/gtest.h>

#include <cmath>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

#include "../include/graph.hpp";

using conduit::Edge;
using conduit::NodeId;
using conduit::RoadGraph;

namespace {

const std::string kTinyPath = std::string(CONDUIT_SAMPLES_DIR) + "/tiny.graph";

// Writes text to a temp file (binary mode: bytes are written exactly as given).
std::filesystem::path writeTemp(const std::string& name,
                                const std::string& content) {
    const auto path = std::filesystem::temp_directory_path() / name;
    std::ofstream out(path, std::ios::binary);
    out << content;
    return path;
}

// Loading `content` must throw, and the message must contain `expected`.
void expectLoadError(const std::string& content, const std::string& expected) {
    const auto path = writeTemp("conduit_bad.graph", content);
    RoadGraph g;
    try {
        g.loadFromFile(path.string());
        FAIL() << "expected loadFromFile to throw";
    } catch (const std::runtime_error& e) {
        EXPECT_NE(std::string(e.what()).find(expected), std::string::npos)
            << "actual message: " << e.what();
    }
    std::filesystem::remove(path);
}

const Edge* findEdge(const RoadGraph& g, NodeId from, NodeId to) {
    for (const auto& e : g.outEdges(from)) {
        if (e.to == to) {
            return &e;
        }
    }
    return nullptr;
}

}  // namespace

TEST(GraphLoader, LoadsTinyGraph) {
    RoadGraph g;
    g.loadFromFile(kTinyPath);
    EXPECT_EQ(g.nodeCount(), 7u);
    EXPECT_EQ(g.edgeCount(), 13u);
    EXPECT_DOUBLE_EQ(g.node(0).lat, 40.7000);
    EXPECT_DOUBLE_EQ(g.node(0).lon, -74.0000);
    EXPECT_DOUBLE_EQ(g.node(6).lat, 40.7020);
    EXPECT_DOUBLE_EQ(g.node(6).lon, -73.9970);
    EXPECT_EQ(g.outEdges(0).size(), 2u);
    EXPECT_EQ(g.outEdges(4).size(), 2u);
    EXPECT_TRUE(g.outEdges(6).empty());  // the island
}

TEST(GraphLoader, TinyGraphKeepsOneWayStreetsOneWay) {
    RoadGraph g;
    g.loadFromFile(kTinyPath);
    const Edge* forward = findEdge(g, 3, 4);
    ASSERT_NE(forward, nullptr);
    EXPECT_DOUBLE_EQ(forward->weight, 87.0);
    EXPECT_EQ(findEdge(g, 4, 3), nullptr);  // no way back
    ASSERT_NE(findEdge(g, 0, 1), nullptr);  // two-way street: both directions
    ASSERT_NE(findEdge(g, 1, 0), nullptr);
}

TEST(GraphLoader, EmptyGraphIsValid) {
    const auto path =
        writeTemp("conduit_empty.graph", "conduit-graph v1\nnodes 0\nedges 0\n");
    RoadGraph g;
    g.loadFromFile(path.string());
    EXPECT_EQ(g.nodeCount(), 0u);
    EXPECT_EQ(g.edgeCount(), 0u);
    std::filesystem::remove(path);
}

TEST(GraphLoader, AcceptsWindowsLineEndings) {
    const auto path = writeTemp(
        "conduit_crlf.graph",
        "conduit-graph v1\r\nnodes 1\r\nedges 0\r\n0 40.0 -74.0\r\n");
    RoadGraph g;
    g.loadFromFile(path.string());
    EXPECT_EQ(g.nodeCount(), 1u);
    std::filesystem::remove(path);
}

TEST(GraphLoader, MissingFileThrows) {
    RoadGraph g;
    try {
        g.loadFromFile("/no/such/file.graph");
        FAIL() << "expected loadFromFile to throw";
    } catch (const std::runtime_error& e) {
        EXPECT_NE(std::string(e.what()).find("cannot open"), std::string::npos);
    }
}

TEST(GraphLoader, RejectsBadHeader) {
    expectLoadError("conduit-graph v2\nnodes 0\nedges 0\n", "line 1");
}

TEST(GraphLoader, RejectsOutOfOrderNodeIds) {
    expectLoadError(
        "conduit-graph v1\nnodes 2\nedges 0\n0 40.0 -74.0\n5 40.0 -74.0\n",
        "line 5");
}

TEST(GraphLoader, RejectsEdgeToUnknownNode) {
    expectLoadError(
        "conduit-graph v1\nnodes 1\nedges 1\n0 40.0 -74.0\n0 9 10\n",
        "unknown node");
}

TEST(GraphLoader, RejectsNegativeWeight) {
    expectLoadError(
        "conduit-graph v1\nnodes 2\nedges 1\n0 40.0 -74.0\n1 40.0 -74.0\n"
        "0 1 -5\n",
        "line 6");
}

TEST(GraphLoader, RejectsTruncatedFile) {
    expectLoadError("conduit-graph v1\nnodes 2\nedges 0\n0 40.0 -74.0\n",
                    "file ended");
}

TEST(GraphLoader, RejectsTrailingContent) {
    expectLoadError("conduit-graph v1\nnodes 0\nedges 0\nsurprise\n", "line 4");
}

TEST(GraphLoader, FailedLoadKeepsPreviousGraph) {
    RoadGraph g;
    g.loadFromFile(kTinyPath);

    const auto bad = writeTemp("conduit_bad2.graph", "not a graph at all\n");
    EXPECT_THROW(g.loadFromFile(bad.string()), std::runtime_error);
    std::filesystem::remove(bad);

    EXPECT_EQ(g.nodeCount(), 7u);
    EXPECT_EQ(g.edgeCount(), 13u);
}