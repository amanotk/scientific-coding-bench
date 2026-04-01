cmake_minimum_required(VERSION 3.16)

project(magnetohydrodynamics_shared_reference LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(mhd1d_reference
  src/full_mhd1d.cpp
  src/hlld.cpp
)

target_include_directories(mhd1d_reference PUBLIC
  src
  ../../common/include
)

add_executable(full_mhd1d_reference
  src/full_main.cpp
)

target_link_libraries(full_mhd1d_reference PRIVATE
  mhd1d_reference
)

set_target_properties(full_mhd1d_reference PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
