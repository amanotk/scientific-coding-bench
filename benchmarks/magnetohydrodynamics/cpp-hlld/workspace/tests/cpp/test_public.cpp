#if __has_include("hlld.hpp")
#include "hlld.hpp"
#else
#include "../../src/hlld.hpp"
#endif

#if __has_include(<catch2/catch_test_macros.hpp>)
#include <catch2/catch_test_macros.hpp>
#else
#include "/usr/local/include/catch2/catch_test_macros.hpp"
#endif

#include <cmath>

namespace
{

constexpr double kTolerance = 1e-12;

ConservativeState primitive_to_conservative(const PrimitiveState& state, double bx, double gamma)
{
  const double rho = state[0];
  const double u   = state[1];
  const double v   = state[2];
  const double w   = state[3];
  const double p   = state[4];
  const double by  = state[5];
  const double bz  = state[6];

  const double kinetic  = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic = 0.5 * (bx * bx + by * by + bz * bz);
  const double energy   = p / (gamma - 1.0) + kinetic + magnetic;

  return ConservativeState{
      rho, rho * u, rho * v, rho * w, energy, by, bz,
  };
}

FluxState physical_flux_x(const ConservativeState& state, double bx, double gamma)
{
  const double rho    = state[0];
  const double mx     = state[1];
  const double my     = state[2];
  const double mz     = state[3];
  const double energy = state[4];
  const double by     = state[5];
  const double bz     = state[6];

  const double u              = mx / rho;
  const double v              = my / rho;
  const double w              = mz / rho;
  const double kinetic        = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic       = 0.5 * (bx * bx + by * by + bz * bz);
  const double pressure       = (gamma - 1.0) * (energy - kinetic - magnetic);
  const double total_pressure = pressure + magnetic;

  return FluxState{
      rho * u,
      rho * u * u + total_pressure - bx * bx,
      rho * v * u - bx * by,
      rho * w * u - bx * bz,
      (energy + total_pressure) * u - bx * (u * bx + v * by + w * bz),
      by * u - bx * v,
      bz * u - bx * w,
  };
}

void require_close(const FluxState& actual, const FluxState& expected)
{
  for (std::size_t i = 0; i < actual.size(); ++i) {
    REQUIRE(std::abs(actual[i] - expected[i]) <= kTolerance);
  }
}

} // namespace

TEST_CASE("equal primitive states reduce to the physical flux")
{
  const double            bx    = 0.75;
  const double            gamma = 1.4;
  const PrimitiveState    state{1.1, 0.2, -0.3, 0.4, 0.9, 0.5, -0.6};
  const ConservativeState conservative = primitive_to_conservative(state, bx, gamma);

  const FluxState actual   = hlld_flux_from_primitive(state, state, bx, gamma);
  const FluxState expected = physical_flux_x(conservative, bx, gamma);

  require_close(actual, expected);
}

TEST_CASE("primitive and conservative entry points agree")
{
  const double bx    = -0.4;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.3, 0.1, -0.2, 1.0, 0.7, -0.5};
  const PrimitiveState right{0.8, -0.1, -0.4, 0.25, 0.7, -0.2, 0.3};

  const ConservativeState left_cons  = primitive_to_conservative(left, bx, gamma);
  const ConservativeState right_cons = primitive_to_conservative(right, bx, gamma);

  const FluxState from_primitive    = hlld_flux_from_primitive(left, right, bx, gamma);
  const FluxState from_conservative = hlld_flux_from_conservative(left_cons, right_cons, bx, gamma);

  require_close(from_primitive, from_conservative);
}

TEST_CASE("nontrivial public reference flux matches expected HLLD result")
{
  const double bx    = 0.75;
  const double gamma = 1.4;

  const PrimitiveState left{1.0, 0.3, 0.1, -0.2, 1.0, 0.7, -0.5};
  const PrimitiveState right{0.8, -0.1, -0.4, 0.25, 0.7, -0.2, 0.3};
  const FluxState      expected{
      0.2959755324688338, 1.1841244172856562, -0.17006720148138638, 0.020437274707554964,
      1.1895179713786177, 0.4579156493939873, -0.29354464377682116,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}
