#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

// Graph file format "conduit-graph v1" (plain text, one item per line)
// conduit-graph v1
// nodes <N>
// edges <E>
// <id> <lat> <lon>        (N lines, ids are 0..N-1 in order)
// <from> <to> <meters>    (E lines, directed, meters >= 0)

namespace conduit {
    using NodeId = std::uint32_t;
    constexpr NodeId kInvalidNode = std::numeric_limits<NodeId>::max();

    struct Node {
        NodeId id;
        double lat;
        double lon;
    };

    struct Edge {
        NodeId from;
        NodeId to;
        double weight;  // meters
    };

    class RoadGraph {
        public:
        // Replaces current contents.
        // runtime_error on any problem with line number.
        // On failure, the graph is left exactly as it was.
        void loadFromFile(const std::string& path);
        
        std::size_t nodeCount() const;
        std::size_t edgeCount() const;

        // id must be < nodeCount()
        const Node& node(NodeId id) const;
        const std::vector<Edge>& outEdges(NodeId id) const;

        private:
        std::vector<Node> nodes_;
        std::vector<std::vector<Edge>> adjacency_; // adjacency_[id] -> edges leaving 'id'
        std::size_t edgeCount_ = 0;
    };
}