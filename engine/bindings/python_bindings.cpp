#include <pybind11/pybind11.h>

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

    // No py::init: Python can only get a City from load_city()
    py::class_<City>(m, "City")
        .def_property_readonly("node_count", &City::nodeCount)
        .def_property_readonly("edge_count", &City::edgeCount)
        .def("__repr__", [](const City& city) {
            return "<City nodes=" + std::to_string(city.nodeCount()) + " edges=" + std::to_string(city.edgeCount()) + ">";
        });
    
    m.def("load_city", [](const std::string& path) { return std::make_unique<City>(path); },
    py::arg("path"), "Load a conduit-graph file and return a City.");
}