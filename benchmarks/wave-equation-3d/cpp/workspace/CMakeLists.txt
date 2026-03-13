cmake_minimum_required(VERSION 3.16)

project(wave_equation_3d_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(fd3d_cli
  src/main.cpp
  src/wave3d.cpp
)

target_include_directories(fd3d_cli PRIVATE
  src
  "${CMAKE_CURRENT_SOURCE_DIR}/../../../common/include"
)

set_target_properties(fd3d_cli PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
