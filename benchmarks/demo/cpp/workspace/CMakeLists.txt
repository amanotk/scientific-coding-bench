cmake_minimum_required(VERSION 3.16)

project(demo_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_path(CXXOPTS_INCLUDE_DIR cxxopts.hpp)
if(NOT CXXOPTS_INCLUDE_DIR)
  message(FATAL_ERROR "Could not find cxxopts.hpp")
endif()

add_executable(rk2_cli
  src/main.cpp
  src/rk2.cpp
)

target_include_directories(rk2_cli PRIVATE
  src
  "${CXXOPTS_INCLUDE_DIR}"
)

set_target_properties(rk2_cli PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
