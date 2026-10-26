// A*
#pragma once

#include <algorithm>
#include <cmath>

namespace conduit {
    constexpr double kEarthRadiusMeters = 6371000.0;

    // Great-circle ("as the crow flies") distance in meters between
    // two lat/lon points given in degrees
    inline double haversine(double lat1, double lon1, double lat2, double lon2) {   // meters
        constexpr double kDegToRad = 3.14159265358979323846 / 180.0;
        const double phi1 = lat1 * kDegToRad;
        const double phi2 = lat2 * kDegToRad;
        const double dPhi = (lat2 - lat1) * kDegToRad;
        const double dLambda = (lon2 - lon1) * kDegToRad;

        const double sinHalfPhi = std::sin(dPhi / 2.0);
        const double sinHalfLambda = std::sin(dLambda / 2.0);
        const double a = sinHalfPhi * sinHalfLambda + std::cos(phi1) * std::cos(phi2) * sinHalfLambda * sinHalfLambda;

        // min() guards against a = 1.0000000002 from rounding, which would make asin return NaN
        return 2.0 * kEarthRadiusMeters * std::asin(std::min(1.0, std::sqrt(a)));
    }
}