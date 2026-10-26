#include "../include/spatial_index.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>

#include "../include/geo.hpp"

namespace conduit {
    namespace {
        constexpr double kDegToRad = 3.14159265358979323846 / 180.0;
    }

    // Degrees -> meters on a flat sheet centered ono (refLat_, refLon_)
    SpatialIndex::Point SpatialIndex::project(double lat, double lon, NodeId id) const {
        return {(lon - refLon_) * kDegToRad * kEarthRadiusMeters * cosRefLat_, (lat - refLat_) * kDegToRad * kEarthRadiusMeters, id};
    }

    SpatialIndex::SpatialIndex(const RoadGraph& graph) {
        const std::size_t n = graph.nodeCount();
        if (n == 0) return;

        double latSum = 0.0;
        double lonSum = 0.0;
        for (NodeId i = 0; i < n; i++) {
            latSum += graph.node(i).lat;
            lonSum += graph.node(i).lon;
        }
        refLat_ = latSum / static_cast<double>(n);
        refLon_ = lonSum / static_cast<double>(n);
        cosRefLat_ = std::cos(refLat_ * kDegToRad);

        points_.reserve(n);
        for (NodeId i = 0; i < n; i++) {
            const Node& node = graph.node(i);
            points_.push_back(project(node.lat, node.lon, node.id));
        }
        build(0, n, 0);
    }

    std::size_t SpatialIndex::size() const { return points_.size(); }

    /* tree lives inside vector itself
    For the slice [lo, hi):
    the middle element is the splitting point
    [lo, mid) is everything on the low side, [mid+1, hi) is high side
    Even depths split on x (east-west), odd depths on y (north-south) */
    void SpatialIndex::build(std::size_t lo, std::size_t hi, int depth) {
        if (hi - lo <= 1) {
            return;
        }
        const std::size_t mid = lo + (hi - lo) / 2;
        const auto first = points_.begin() + static_cast<std::ptrdiff_t>(lo);
        const auto middle = points_.begin() + static_cast<std::ptrdiff_t>(mid);
        const auto last = points_.begin() + static_cast<std::ptrdiff_t>(hi);

        if (depth % 2 == 0) {
            std::nth_element(first, middle, last,
                                [](const Point& a, const Point& b)
                                { return a.x < b.x; });
        } else {
            std::nth_element(first, middle, last,
                                [](const Point& a, const Point& b)
                                { return a.y < b.y; });
        }
        build(lo, mid, depth + 1);
        build(mid + 1, hi, depth + 1);
    }

    void SpatialIndex::search(std::size_t lo, std::size_t hi, int depth, double qx, double qy, NodeId& bestId, double& bestD2) const {
        if (lo >= hi) return;
        const std::size_t mid = lo + (hi - lo) / 2;
        const Point& p = points_[mid];

        // 1. Is the splitting point itself best so far? (squared meters)
        const double dx = p.x - qx;
        const double dy = p.y - qy;
        const double d2 = dx * dx + dy * dy;
        if (d2 < bestD2 || (d2 == bestD2 && p.id < bestId)) {
            bestD2 = d2;
            bestId = p.id;
        }

        // 2. Which side of the cut are we on? Walk that side first.
        const double diff = (depth % 2 == 0) ? (qx - p.x) : (qy - p.y);
        const bool lowSideFirst = diff < 0.0;
        if (lowSideFirst) search(lo, mid, depth + 1, qx, qy, bestId, bestD2);
        else search(mid + 1, hi, depth + 1, qx, qy, bestId, bestD2);

        // 3. Walking back out: the other side can only help if the cut line itself
        //    is closer than the best we have otherwise skip that whole half.
        if (diff * diff <= bestD2) {
            if (lowSideFirst) search(mid + 1, hi, depth + 1, qx, qy, bestId, bestD2);
            else search(lo, mid, depth + 1, qx, qy, bestId, bestD2);
        }
    }

    NodeId SpatialIndex::nearest(double lat, double lon) const {
        if (!std::isfinite(lat) || lat < -90.0 || lat > 90.0) {
            throw std::invalid_argument("spatial index: latitude must be finite and in [-90, 90]");
        }
        if (!std::isfinite(lon) || lon < -180.0 || lon > 180.0) {
            throw std::invalid_argument("spatial index: longitude must be finite and in [-180, 180]");
        }
        if (points_.empty()) return kInvalidNode;

        const Point q = project(lat, lon, kInvalidNode);
        NodeId bestId = kInvalidNode;
        double bestD2 = std::numeric_limits<double>::infinity();
        search(0, points_.size(), 0, q.x, q.y, bestId, bestD2);
        return bestId;
    }
}