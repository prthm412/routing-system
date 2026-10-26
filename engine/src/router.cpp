#include "../include/router.hpp";

#include <algorithm>
#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <string>
#include <utility>

#include "../include/geo.hpp";

namespace conduit {

    namespace {
        constexpr double kInf = std::numeric_limits<double>::infinity();

        // Follows the came from notes backwards from 'to', then flips the list
        Path buildPath(const std::vector<double>& dist, const std::vector<NodeId>& prev, NodeId to) {
            Path path;
            if (dist[to] == kInf) {
                return path;    // found == false
            }
            path.found = true;
            path.distance = dist[to];
            for (NodeId at = to; at != kInvalidNode; at = prev[at]) {
                path.nodes.push_back(at);   // built backwards: to ... from
            }
            std::reverse(path.nodes.begin(), path.nodes.end());
            return path;
        }
    }
    Router::Router(const RoadGraph& graph) : graph_(graph) {}

    void Router::checkNode(NodeId id, const char* which) const {
        if (id >= graph_.nodeCount()) {
            throw std::out_of_range(std::string("router: '") + which + "' node id " + std::to_string(id) + " is not in the graph (it has " + std::to_string(graph_.nodeCount()) + " nodes)");
        }
    }

    Path Router::routeDijkstra(NodeId from, NodeId to) const {
        checkNode(from, "from");
        checkNode(to, "to");

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

        return buildPath(dist, prev, to);
    }

    Path Router::findRoute(NodeId from, NodeId to) const {
        checkNode(from, "from");
        checkNode(to, "to");
        
        const Node& goal = graph_.node(to);
        // straight-line meters from 'id' to the goal
        auto heuristic = [&](NodeId id) {
            const Node& n = graph_.node(id);
            return haversine(n.lat, n.lon, goal.lat, goal.lon);
        };

        const std::size_t n = graph_.nodeCount();
        std::vector<double> dist(n, kInf);
        std::vector<NodeId> prev(n, kInvalidNode);

        struct Entry {
            double f;
            double g;
            NodeId node;
        };
        auto later = [](const Entry& a, const Entry& b) { return a.f > b.f; };
        std::priority_queue<Entry, std::vector<Entry>, decltype(later)> open(later);

        dist[from] = 0.0;
        open.push({heuristic(from), 0.0, from});

        while (!open.empty()) {
            const Entry cur = open.top();
            open.pop();

            if (cur.g > dist[cur.node]) {
                continue;
            }
            if (cur.node == to) {
                break;  // with consistent heuristic
            }
            for (const Edge& e : graph_.outEdges(cur.node)) {
                const double candidate = cur.g + e.weight;
                if (candidate < dist[e.to]) {
                    dist[e.to] = candidate;
                    prev[e.to] = cur.node;
                    open.push({candidate + heuristic(e.to), candidate, e.to});
                }
            }
        }
        
        return buildPath(dist, prev, to);
    }
}