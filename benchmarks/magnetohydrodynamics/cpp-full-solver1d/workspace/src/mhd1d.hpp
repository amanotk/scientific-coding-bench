#pragma once

#include <array>
#include <cstddef>
#include <experimental/mdspan>
#include <utility>
#include <vector>

namespace mhd1d
{

namespace stdex = std::experimental;

constexpr std::size_t kStateWidth = 7;

using StateVector    = std::array<double, kStateWidth>;
using StateExtents   = stdex::dextents<std::size_t, 2>;
using StateView      = stdex::mdspan<double, StateExtents>;
using ConstStateView = stdex::mdspan<const double, StateExtents>;

struct StateArray2D {
  StateArray2D();
  explicit StateArray2D(std::size_t rows);

  StateArray2D(const StateArray2D& other);
  StateArray2D(StateArray2D&& other) noexcept;
  StateArray2D& operator=(const StateArray2D& other);
  StateArray2D& operator=(StateArray2D&& other) noexcept;

  [[nodiscard]] std::size_t rows() const;
  [[nodiscard]] std::size_t cols() const;

  [[nodiscard]] double*       row_data(std::size_t row);
  [[nodiscard]] const double* row_data(std::size_t row) const;

  [[nodiscard]] StateVector load(std::size_t row) const;
  void                      store(std::size_t row, const StateVector& state);

  double&       operator()(std::size_t row, std::size_t col);
  const double& operator()(std::size_t row, std::size_t col) const;

  [[nodiscard]] StateView      view();
  [[nodiscard]] ConstStateView view() const;

  std::vector<double> buffer;

private:
  void rebind_view();

  StateView view_;
};

struct ProblemConfig {
  std::size_t nx              = 0;
  double      x_left          = 0.0;
  double      x_right         = 1.0;
  double      discontinuity_x = 0.5;
  double      dt              = 0.0;
  double      t_final         = 0.0;
  double      gamma           = 0.0;
  double      bx              = 0.0;
  StateVector left_primitive{};
  StateVector right_primitive{};
};

ProblemConfig make_brio_wu_example();

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma);

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma);

StateArray2D mc2_slopes(const StateArray2D& primitive_cells);

std::pair<StateArray2D, StateArray2D>
reconstruct_mc2_interfaces(const StateArray2D& primitive_cells);

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

std::vector<double> cell_centers(std::size_t nx, double x_left, double x_right);

StateArray2D pad_zero_gradient_ghost_cells(const StateArray2D& cells);

StateArray2D brio_wu_initial_profile(const ProblemConfig& problem);

StateArray2D run_full_simulation(const ProblemConfig& problem);

StateArray2D compute_semidiscrete_rhs(const StateArray2D& conservative_cells, double bx = 0.75,
                                      double gamma = 2.0);

StateArray2D compute_semidiscrete_rhs(const StateArray2D& conservative_cells, double dx, double bx,
                                      double gamma);

StateArray2D ssp_rk3_step(const StateArray2D& conservative_cells, double dt, double bx = 0.75,
                          double gamma = 2.0);

StateArray2D ssp_rk3_step(const StateArray2D& conservative_cells, double dt, double dx, double bx,
                          double gamma);

StateArray2D evolve_ssp_rk3_fixed_dt(const StateArray2D& conservative_cells, double t_final,
                                     double dt, double bx = 0.75, double gamma = 2.0);

StateArray2D evolve_ssp_rk3_fixed_dt(const StateArray2D& conservative_cells, double t_final,
                                     double dt, double dx, double bx, double gamma);

} // namespace mhd1d
