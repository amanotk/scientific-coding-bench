cmake_minimum_required(VERSION 3.16)

project(demo_f90 LANGUAGES Fortran)

find_file(FLAP_MOD flap.mod PATHS /usr/local/include /usr/local/include/FLAP)
find_file(FACE_MOD face.mod PATHS /usr/local/include /usr/local/include/FACE)
find_file(PENF_MOD penf.mod PATHS /usr/local/include /usr/local/include/PENF)
find_library(FLAP_LIB NAMES FLAP PATHS /usr/local/lib)
find_library(FACE_LIB NAMES FACE PATHS /usr/local/lib)
find_library(PENF_LIB NAMES PENF PATHS /usr/local/lib)

if(NOT FLAP_MOD OR NOT FACE_MOD OR NOT PENF_MOD)
  message(FATAL_ERROR "Could not find FLAP/FACE/PENF Fortran module files")
endif()

if(NOT FLAP_LIB OR NOT FACE_LIB OR NOT PENF_LIB)
  message(FATAL_ERROR "Could not find FLAP/FACE/PENF libraries")
endif()

get_filename_component(FLAP_MOD_DIR "${FLAP_MOD}" DIRECTORY)
get_filename_component(FACE_MOD_DIR "${FACE_MOD}" DIRECTORY)
get_filename_component(PENF_MOD_DIR "${PENF_MOD}" DIRECTORY)

add_executable(rk2_cli
  src/rk2_solver.f90
  src/main.f90
)

target_include_directories(rk2_cli PRIVATE
  "${FLAP_MOD_DIR}"
  "${FACE_MOD_DIR}"
  "${PENF_MOD_DIR}"
)

target_link_libraries(rk2_cli PRIVATE
  "${FLAP_LIB}"
  "${FACE_LIB}"
  "${PENF_LIB}"
)

set_target_properties(rk2_cli PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
