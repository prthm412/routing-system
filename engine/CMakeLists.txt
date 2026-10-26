cmake_minimum_required(VERSION 3.20)

project(ConduitEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The engine itself, as a library. The tests (and later the Python
# bindings) link against it.
add_library(conduit_engine STATIC
    src/graph.cpp
    src/router.cpp
    src/spatial_index.cpp
)
target_include_directories(conduit_engine PUBLIC include)
target_compile_options(conduit_engine PRIVATE -Wall -Wextra)

# Phase 0 smoke test, kept for now.
add_executable(conduit_smoke_test src/main.cpp)

add_executable(route_cli src/route_cli.cpp)
target_link_libraries(route_cli PRIVATE conduit_engine)
target_compile_options(route_cli PRIVATE -Wall -Wextra)

# Tests
enable_testing()
include(FetchContent)
FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(googletest)

# In the container, /workspace/../data/samples is /data/samples.
set(CONDUIT_SAMPLES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../data/samples"
    CACHE PATH "Folder holding small test graphs")

set(CONDUIT_PROCESSED_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../data/processed"
    CACHE PATH "Folder holding exported city graphs")

add_executable(conduit_tests tests/test_graph.cpp tests/test_router.cpp tests/test_geo.cpp tests/test_astar.cpp tests/test_spatial_index.cpp tests/test_real_graph.cpp)
target_link_libraries(conduit_tests PRIVATE conduit_engine GTest::gtest_main)
target_compile_options(conduit_tests PRIVATE -Wall -Wextra)
target_compile_definitions(conduit_tests PRIVATE
    CONDUIT_SAMPLES_DIR="${CONDUIT_SAMPLES_DIR}"
    CONDUIT_PROCESSED_DIR="${CONDUIT_PROCESSED_DIR}")