#include <pybind11/pybind11.h>

#include <string>

#include "../include/graph.hpp"

namespace py = pybind11;

PYBIND11_MODULE(conduit_core, m) {
    m.doc() = "Conduit routing engine (C++ core)";

    // Throwaway toolchain check. gonna replace in next steps
    m.def("_smoke_node_count", [](const std::string& path) {
        conduit::RoadGraph graph;
        graph.loadFromFile(path);
        return graph.nodeCount();
    });
}