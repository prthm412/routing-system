#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <cstddef>
#include <memory>
#include <stdexcept>

#include "../include/graph.hpp"
#include "../include/router.hpp"
#include "../include/spatial_index.hpp"

namespace py = pybind11;

namespace conduit::bridge {
    namespace {
        RoadGraph loadGraphOrThrow(const std::string& path) {
            RoadGraph graph;
            graph.loadFromFile(path);
            if (graph.nodeCount() == 0) {
                throw std::runtime_error("graph file has no nodes: " + path);
            }
            return graph;
        }
    }

    // Everything the engine needs for one city
    class City {
        public:
        explicit City(const std::string& path) : graph_(loadGraphOrThrow(path)), router_(graph_), index_(graph_) {}

        // router_ -- reference --> graph_
        // copy (or move) would keep pointing at ORIGINAL city's graph so neither is allowed.
        City(const City&) = delete;
        City& operator=(const City&) = delete;
        City(City&&) = delete;
        City& operator=(City&&) = delete;

        std::size_t nodeCount() const { return graph_.nodeCount(); }
        std::size_t edgeCount() const { return graph_.edgeCount(); }

        NodeId nearestNode(double lat, double lon) const {
            return index_.nearest(lat, lon);
        }

        Path findRoute(NodeId from, NodeId to) const {
            return router_.findRoute(from, to);
        }

        private:
        // members are built top to bottom and destroyed bottom to top
        // so graph_ is built first and destroyed last
        RoadGraph graph_;
        Router router_;
        SpatialIndex index_;
    };
}

using conduit::bridge::City;

PYBIND11_MODULE(conduit_core, m) {
    m.doc() = "Conduit routing engine (C++ core)";

    py::class_<conduit::Path>(m, "Route")
        .def_readonly("found", &conduit::Path::found)
        .def_readonly("distance_m", &conduit::Path::distance)
        .def_readonly("nodes", &conduit::Path::nodes)
        .def("__repr__", [](const conduit::Path& p) {
            return std::string("<Route found=") + (p.found ? "True" : "False") +
                   " distance_m=" + std::to_string(p.distance) +
                   " nodes=" + std::to_string(p.nodes.size()) + ">";
        });
    
    // No py::init: Python can only get a City from load_city()
    py::class_<City>(m, "City")
        .def_property_readonly("node_count", &City::nodeCount)
        .def_property_readonly("edge_count", &City::edgeCount)
        .def("nearest_node", &City::nearestNode, py::arg("lat"), py::arg("lon"),
            "Id of the road node closest to (lat, lon). Always returns a "
            "node, however far away.")
        .def("find_route", &City::findRoute, py::arg("from_node"), py::arg("to_node"),
            "A* route between two node ids. found is False if there is no route. "
            "Raises IndexError for a node id that is not in the graph.")
        .def("__repr__", [](const City& city) {
            return "<City nodes=" + std::to_string(city.nodeCount()) + " edges=" + std::to_string(city.edgeCount()) + ">";
        });
    
    m.def("load_city", [](const std::string& path) { return std::make_unique<City>(path); },
    py::arg("path"), "Load a conduit-graph file and return a City.");
}