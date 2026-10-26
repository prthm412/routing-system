// Dijkstra for now
#pragma once

#include <vector>
#include "graph.hpp";

namespace conduit {
    struct Path {
        bool found = false;
        double distance = 0.0;
        std::vector<NodeId> nodes;
    };

    class Router {
        public:
        // Router keeps a reference to the graph, so the graph must outlive it
        explicit Router(const RoadGraph& graph);
        Router(const RoadGraph&&) = delete;

        // Reference implementation: plain Dijkstra
        // Throws outofrange if from/to is not a node of the graph
        Path routeDijkstra(NodeId from, NodeId to) const;

        private:
        void checkNode(NodeId id, const char* which) const;

        const RoadGraph& graph_;
    };
}