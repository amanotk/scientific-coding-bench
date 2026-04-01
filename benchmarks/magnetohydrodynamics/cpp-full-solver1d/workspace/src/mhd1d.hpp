#pragma once

#include <array>
#include <utility>
#include <vector>

#include <experimental/mdspan>

namespace mhd1d
{

namespace stdex = std::experimental;

constexpr int kStateWidth = 7;
constexpr int kGhostWidth = 1;

using StateVector = std::array<double, kStateWidth>;
using ArrayView1D = stdex::mdspan<double, stdex::dextents<int, 1>>;
using ArrayView2D = stdex::mdspan<double, stdex::dextents<int, 2>>;

struct SolverWorkspace {
  struct Storage {
    explicit Storage(int nx_total)
        : conservative(nx_total * kStateWidth), primitive(nx_total * kStateWidth),
          primitive_left(nx_total * kStateWidth), primitive_right(nx_total * kStateWidth),
          rhs(nx_total * kStateWidth), prev(nx_total * kStateWidth), flux(nx_total * kStateWidth),
          x(nx_total)
    {
    }

    std::vector<double> conservative;
    std::vector<double> primitive;
    std::vector<double> primitive_left;
    std::vector<double> primitive_right;
    std::vector<double> rhs;
    std::vector<double> prev;
    std::vector<double> flux;
    std::vector<double> x;
  };

  explicit SolverWorkspace(int nx, double gamma, double bx)
      : Nx(nx), Lbx(kGhostWidth), Ubx(kGhostWidth + nx - 1),
        dx(nx == 0 ? 0.0 : 1.0 / static_cast<double>(nx)), gamma(gamma), bx(bx),
        storage(Nx + 2 * kGhostWidth)
  {
    init_views(Nx + 2 * kGhostWidth);

    for (int ix = Lbx; ix <= Ubx; ++ix) {
      x(ix) = (static_cast<double>(ix - Lbx) + 0.5) * dx;
    }
  }

  int    Nx;
  int    Lbx;
  int    Ubx;
  double dx;
  double gamma;
  double bx;

  Storage storage;

  ArrayView2D conservative;
  ArrayView2D primitive;
  ArrayView2D primitive_left;
  ArrayView2D primitive_right;
  ArrayView2D rhs;
  ArrayView2D prev;
  ArrayView2D flux;
  ArrayView1D x;

  void init_views(int nx_total)
  {
    conservative    = ArrayView2D(storage.conservative.data(), nx_total, kStateWidth);
    primitive       = ArrayView2D(storage.primitive.data(), nx_total, kStateWidth);
    primitive_left  = ArrayView2D(storage.primitive_left.data(), nx_total, kStateWidth);
    primitive_right = ArrayView2D(storage.primitive_right.data(), nx_total, kStateWidth);
    rhs             = ArrayView2D(storage.rhs.data(), nx_total, kStateWidth);
    prev            = ArrayView2D(storage.prev.data(), nx_total, kStateWidth);
    flux            = ArrayView2D(storage.flux.data(), nx_total, kStateWidth);
    x               = ArrayView1D(storage.x.data(), nx_total);
  }
};

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma);

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma);

void primitive_profile_to_conservative(ArrayView2D primitive_cells, ArrayView2D conservative_cells,
                                       double bx, double gamma);

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

void set_left_boundary(ArrayView2D dst, ArrayView2D src, int lbx);

void set_right_boundary(ArrayView2D dst, ArrayView2D src, int ubx);

void reconstruct_mc2(SolverWorkspace& workspace);

void compute_flux_hlld(SolverWorkspace& workspace, double bx, double gamma);

void compute_rhs(SolverWorkspace& workspace);

void push_ssp_rk3(SolverWorkspace& workspace, double dt);

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final);

} // namespace mhd1d
