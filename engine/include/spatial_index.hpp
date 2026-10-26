#pragma once

#include <cstddef>
#include <vector>

#include "graph.hpp"

namespace conduit {
    // Finds the graph node closest to a lat/lon point (a k-d tree on a flat local projection,
    // so it assumes a city-sized area, not one crossing +-180 degrees)
    class SpatialIndex {
        public:
        // Copies what it needs; graph can be destroyed aftewards
        explicit SpatialIndex(const RoadGraph& graph);

        //Closest node by straight-line distance
        // Ties go to the lowest id
        // Returns kInvalidNode if the graph ha no nodes
        // Throws invalid_argument if lat/lon is NaN/inf or out of range
        NodeId nearest(double lat, double lon) const;

        std::size_t size() const;

        private:
        struct Point {
            double x;   // meters east of the reference point
            double y;   // meters north of the reference point
            NodeId id;
        };

        Point project(double lat, double lon, NodeId id) const;
        void build(std::size_t lo, std::size_t hi, int depth);
        void search(std::size_t lo, std::size_t hi, int depth, double qx, double qy, NodeId& bestId, double& bestD2) const;

        std::vector<Point> points_;
        double refLat_ = 0.0;
        double refLon_ = 0.0;
        double cosRefLat_ = 1.0;
    };
}