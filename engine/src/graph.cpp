#include "../include/graph.hpp";

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace conduit {
    namespace {
        // Do not trust a count from a file enough to preallocate unlimited memory
        constexpr std::size_t kReserveCap = 10'000'000;

        [[noreturn]] void fail(std::size_t lineNo, const std::string& message) {
            throw std::runtime_error("graph file, line " + std::to_string(lineNo) + ": " + message);
        }

        // Reads one line
        // Strips a trailing '\r', counts it
        // Returns false at the end of file
        bool nextLine(std::istream& in, std::string& line, std::size_t& lineNo) {
            if (!std::getline(in, line)) {
                return false;
            }
            lineNo++;
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }
            return 1;
        }

        // True if the line has nothing left after already parsed
        bool nothingLeft(std::istringstream& ss) {
            std::string extra;
            return !(ss >> extra);
        }

        // Parses a line like 'nodes 7' or 'edges 13'
        std::size_t readCount(std::istream& in, std::size_t& lineNo, const std::string& keyword) {
            std::string line;
            if (!nextLine(in, line, lineNo)) {
                fail(lineNo + 1, "file ended; expected '" + keyword + " <count>'");
            }
            std::istringstream ss(line);
            std::string word;
            long long count = 0;
            if (!(ss >> word >> count) || word != keyword || count < 0 || !nothingLeft(ss)) {
                fail(lineNo, "expected '" + keyword + " <count>'");
            }
            return static_cast<std::size_t>(count);
        }
    }

    void RoadGraph::loadFromFile(const std::string& path) {
        std::ifstream in (path);
        if (!in) {
            throw std::runtime_error("cannot open graph file: " + path);
        }

        std::size_t lineNo = 0;
        std::string line;

        if (!nextLine(in, line, lineNo) || line != "conduit-graph v1") {
            fail(1, "expected header 'conduit-graph v1'");
        }

        const std::size_t nodeTotal = readCount(in, lineNo, "nodes");
        if (nodeTotal >= kInvalidNode) {
            fail(lineNo, "too many nodes");
        }
        const std::size_t edgeTotal = readCount(in, lineNo, "edges");

        // Everything below goes into scratch containers
        // Real members are only touched at the end after the file has passed
        std::vector<Node> nodes;
        nodes.reserve(std::min<std::size_t>(nodeTotal, kReserveCap));

        for (std::size_t i = 0; i < nodeTotal; i++) {
            if (!nextLine(in, line, lineNo)) {
                fail(lineNo + 1, "file ended; expected " + std::to_string(nodeTotal) + " node lines");
            }
            std::istringstream ss(line);
            long long id = 0;
            double lat = 0.0;
            double lon = 0.0;
            if (!(ss >> id >> lat >> lon) || !nothingLeft(ss)) {
                fail(lineNo, "expected '<id> <lat> <lon>'");
            }
            if (id != static_cast<long long>(i)) {
                fail(lineNo, "node ids must be 0..N-1 in order; expected " + std::to_string(i) + ", got " + std::to_string(id));
            }
            if (!std::isfinite(lat) || lat < -90.0 || lat > 90.0) {
                fail(lineNo, "latitude must be between -90 and 90");
            }
            if (!std::isfinite(lon) || lon < -180.0 || lon > 180.0) {
                fail(lineNo, "longitude must be between -180 and 180");
            }
            nodes.push_back({static_cast<NodeId>(i), lat, lon});
        }

        std::vector<std::vector<Edge>> adjacency(nodeTotal);
        const auto nodeLimit = static_cast<long long>(nodeTotal);

        for (std::size_t i = 0; i < edgeTotal; i++) {
            if (!nextLine(in, line, lineNo)) {
                fail(lineNo + 1, "file ended; expected " + std::to_string(edgeTotal) + " edge lines");
            }
            std::istringstream ss(line);
            long long from = 0;
            long long to = 0;
            double meters = 0.0;
            if (!(ss >> from >> to >> meters) || !nothingLeft(ss)) {
                fail(lineNo, "expected '<from> <to> <meters>'");
            }
            if (from < 0 || from >= nodeLimit || to < 0 || to >= nodeLimit) {
                fail(lineNo, "edge refers to an unknown node");
            }
            if (!std::isfinite(meters) || meters < 0.0) {
                fail(lineNo, "edge weight must be a finite number >= 0");
            }
            adjacency[static_cast<std::size_t>(from)].push_back({static_cast<NodeId>(from), static_cast<NodeId>(to), meters});
        }

        // Anything left must be blank
        while (nextLine(in, line, lineNo)) {
            if (line.find_first_not_of(" \t") != std::string::npos) {
                fail(lineNo, "unexpected content after the last edge");
            }
        }

        nodes_ = std::move(nodes);
        adjacency_ = std::move(adjacency);
        edgeCount_ = edgeTotal;
    }

    std::size_t RoadGraph::nodeCount() const { return nodes_.size(); }
    std::size_t RoadGraph::edgeCount() const { return edgeCount_; }
    const Node& RoadGraph::node(NodeId id) const { return nodes_[id]; }

    const std::vector<Edge>& RoadGraph::outEdges(NodeId id) const {
        return adjacency_[id];
    }
}