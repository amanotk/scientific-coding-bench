cmake_minimum_required(VERSION 3.16)

project(wave_equation_3d_f90 LANGUAGES Fortran)

add_executable(fd3d_cli
  src/wave3d_solver.f90
  src/main.f90
)

set_target_properties(fd3d_cli PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
