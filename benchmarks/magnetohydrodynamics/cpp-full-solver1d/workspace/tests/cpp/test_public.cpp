#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <vector>

#include "mhd1d.hpp"

namespace
{

constexpr double kTolerance = 1.0e-12;

void require_state_vector_close(const mhd1d::StateVector& actual,
                                const mhd1d::StateVector& expected)
{
  for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
    REQUIRE(std::fabs(actual[component] - expected[component]) <= kTolerance);
  }
}

} // namespace

TEST_CASE("primitive_to_conservative converts a known state", "[mhd1d][conversion]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.5, 2.0, -1.0, 0.5, 3.0, 0.25, -0.5};
  const auto   actual = mhd1d::primitive_to_conservative(state, bx, gamma);

  const auto expected = mhd1d::StateVector{1.5, 3.0, -1.5, 0.75, 7.375, 0.25, -0.5};
  require_state_vector_close(actual, expected);
}

TEST_CASE("conservative_to_primitive converts a known state", "[mhd1d][conversion]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.5, 3.0, -1.5, 0.75, 7.375, 0.25, -0.5};
  const auto   actual = mhd1d::conservative_to_primitive(state, bx, gamma);

  const auto expected = mhd1d::StateVector{1.5, 2.0, -1.0, 0.5, 3.0, 0.25, -0.5};
  require_state_vector_close(actual, expected);
}

TEST_CASE("primitive and conservative states round-trip", "[mhd1d][conversion]")
{
  const double bx    = 0.75;
  const double gamma = 2.0;
  const auto   input = mhd1d::StateVector{0.875, -1.25, 0.5, 0.75, 2.125, -0.2, 0.35};

  const auto conservative = mhd1d::primitive_to_conservative(input, bx, gamma);
  const auto output       = mhd1d::conservative_to_primitive(conservative, bx, gamma);

  require_state_vector_close(output, input);
}

TEST_CASE("mc2_slopes preserve a constant primitive state", "[mhd1d][reconstruction]")
{
  const auto constant_state = mhd1d::StateVector{1.25, -0.5, 0.25, -0.125, 2.75, 0.4, -0.3};
  mhd1d::StateArray2D cells(4);
  for (std::size_t index = 0; index < cells.rows(); ++index) {
    cells.store(index, constant_state);
  }

  const auto slopes = mhd1d::mc2_slopes(cells);

  REQUIRE(slopes.rows() == cells.rows());
  for (std::size_t index = 0; index < slopes.rows(); ++index) {
    require_state_vector_close(slopes.load(index), mhd1d::StateVector{});
  }
}

TEST_CASE("reconstruct_mc2_interfaces preserves a constant primitive state exactly",
          "[mhd1d][reconstruction]")
{
  const auto          constant_state = mhd1d::StateVector{0.9, 0.3, -0.2, 0.1, 1.8, -0.45, 0.6};
  mhd1d::StateArray2D cells(4);
  for (std::size_t index = 0; index < cells.rows(); ++index) {
    cells.store(index, constant_state);
  }

  const auto [left_states, right_states] = mhd1d::reconstruct_mc2_interfaces(cells);

  REQUIRE(left_states.rows() == cells.rows() - 1U);
  REQUIRE(right_states.rows() == cells.rows() - 1U);
  for (std::size_t index = 0; index < left_states.rows(); ++index) {
    require_state_vector_close(left_states.load(index), constant_state);
  }
  for (std::size_t index = 0; index < right_states.rows(); ++index) {
    require_state_vector_close(right_states.load(index), constant_state);
  }
}

TEST_CASE("hlld_flux_from_primitive matches the physical flux for identical states",
          "[mhd1d][flux]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.4, -0.6, 0.25, 0.1, 1.9, -0.35, 0.5};
  const auto   actual = mhd1d::hlld_flux_from_primitive(state, state, bx, gamma);

  const double rho = state[0];
  const double u   = state[1];
  const double v   = state[2];
  const double w   = state[3];
  const double p   = state[4];
  const double by  = state[5];
  const double bz  = state[6];
  const double bx2 = bx * bx;
  const double pt  = p + 0.5 * (bx2 + by * by + bz * bz);
  const double e =
      p / (gamma - 1.0) + 0.5 * rho * (u * u + v * v + w * w) + 0.5 * (bx2 + by * by + bz * bz);

  const auto expected = mhd1d::StateVector{
      rho * u,
      rho * u * u + pt - bx2,
      rho * u * v - bx * by,
      rho * u * w - bx * bz,
      u * (e + pt - bx2) - bx * (v * by + w * bz),
      by * u - bx * v,
      bz * u - bx * w,
  };

  require_state_vector_close(actual, expected);
}

TEST_CASE("pad_zero_gradient_ghost_cells duplicates edge states on both sides", "[mhd1d][boundary]")
{
  mhd1d::StateArray2D cells(3);
  cells.store(0, mhd1d::StateVector{1.0, 0.5, -0.25, 0.125, 2.0, 0.1, -0.05});
  cells.store(1, mhd1d::StateVector{1.2, 0.6, -0.2, 0.15, 2.2, 0.12, -0.02});
  cells.store(2, mhd1d::StateVector{1.4, 0.7, -0.15, 0.175, 2.4, 0.14, 0.01});

  const auto padded = mhd1d::pad_zero_gradient_ghost_cells(cells);

  REQUIRE(padded.rows() == cells.rows() + 4U);
  require_state_vector_close(padded.load(0), cells.load(0));
  require_state_vector_close(padded.load(1), cells.load(0));
  require_state_vector_close(padded.load(2), cells.load(0));
  require_state_vector_close(padded.load(3), cells.load(1));
  require_state_vector_close(padded.load(4), cells.load(2));
  require_state_vector_close(padded.load(5), cells.load(2));
  require_state_vector_close(padded.load(6), cells.load(2));
}

TEST_CASE("pad_zero_gradient_ghost_cells handles a single interior cell", "[mhd1d][boundary]")
{
  const auto          cell = mhd1d::StateVector{1.5, -0.75, 0.25, 0.0, 3.5, -0.1, 0.2};
  mhd1d::StateArray2D cells(1);
  cells.store(0, cell);

  const auto padded = mhd1d::pad_zero_gradient_ghost_cells(cells);

  REQUIRE(padded.rows() == 5U);
  for (std::size_t index = 0; index < padded.rows(); ++index) {
    require_state_vector_close(padded.load(index), cell);
  }
}

TEST_CASE("StateArray2D rows are contiguous in the right-most dimension", "[mhd1d][storage]")
{
  mhd1d::StateArray2D cells(3);
  cells.store(1, mhd1d::StateVector{1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0});

  const double* row_ptr = cells.row_data(1);
  REQUIRE(row_ptr[0] == 1.0);
  REQUIRE(row_ptr[6] == 7.0);
  REQUIRE(cells.row_data(2) - cells.row_data(1) == static_cast<std::ptrdiff_t>(mhd1d::kStateWidth));
}
