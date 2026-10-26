#include "../include/router.hpp";

#include <algorithm>
#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <string>
#include <utility>

namespace conduit {
    Router::Router(const RoadGraph& graph) : graph_(graph) {}

    void Router::checkNode(NodeId id, const char* which) const {
        if (id >= graph_.nodeCount()) {
            throw std::out_of_range(std::string("router: '") + which + "' node id " + std::to_string(id) + " is not in the graph (it has " + std::to_string(graph_.nodeCount()) + " nodes)");
        }
    }

    Path Router::routeDijkstra(NodeId from, NodeId to) const {
        checkNode(from, "from");
        checkNode(to, "to");

        constexpr double kInf = std::numeric_limits<double>::infinity();
        const std::size_t n = graph_.nodeCount();

        std::vector<double> dist(n, kInf); // best from 'from'
        std::vector<NodeId> prev(n, kInvalidNode); // who we came from on the best path

        // (distance, node)
        using Entry = std::pair<double, NodeId>;
        std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> open;

        dist[from] = 0.0;
        open.push({0.0, from});

        while (!open.empty()) {
            const auto [d, u] = open.top();
            open.pop();

            if (d > dist[u]) {
                continue; // we already found something better
            }
            if (u == to) {
                break; // closest unfinished node is the destination, so its final
            }
            for (const Edge& e : graph_.outEdges(u)) {
                const double candidate = d + e.weight;
                if (candidate < dist[e.to]) {
                    dist[e.to] = candidate;
                    prev[e.to] = u;
                    open.push({candidate, e.to});
                }
            }
        }

        Path path;
        if (dist[to] == kInf) {
            return path;    // found == false
        }

        path.found = true;
        path.distance = dist[to];
        for (NodeId at = to; at != kInvalidNode; at = prev[at]) {
            path.nodes.push_back(at);
        }
        std::reverse(path.nodes.begin(), path.nodes.end());
        return path;
    }
}