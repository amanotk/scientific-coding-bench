#if __has_include("hlld.hpp")
#include "hlld.hpp"
#else
#include "../../../workspace/src/hlld.hpp"
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

TEST_CASE("equal conservative states reduce to the physical flux")
{
  const double            bx    = 0.35;
  const double            gamma = 1.4;
  const PrimitiveState    primitive{0.9, -0.45, 0.2, 0.15, 0.8, -0.3, 0.55};
  const ConservativeState state = primitive_to_conservative(primitive, bx, gamma);

  const FluxState actual   = hlld_flux_from_conservative(state, state, bx, gamma);
  const FluxState expected = physical_flux_x(state, bx, gamma);

  require_close(actual, expected);
}

TEST_CASE("nontrivial primitive solve returns finite values")
{
  const double bx    = -0.65;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.08, 0.45, -0.12, 0.08, 0.95, 0.4, -0.3};
  const PrimitiveState right{0.72, -0.25, 0.16, -0.05, 0.58, -0.2, 0.35};

  const FluxState flux = hlld_flux_from_primitive(left, right, bx, gamma);

  for (double value : flux) {
    REQUIRE(std::isfinite(value));
  }
}

TEST_CASE("hidden reference flux case 1 matches expected HLLD result")
{
  const double bx    = -0.65;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.08, 0.45, -0.12, 0.08, 0.95, 0.4, -0.3};
  const PrimitiveState right{0.72, -0.25, 0.16, -0.05, 0.58, -0.2, 0.35};
  const FluxState      expected{
      0.3324233585009154, 1.3204052114557712,  0.06638064166463348,  -0.022436684783467387,
      0.7427148869798962, 0.20070323090296055, -0.18527478786984644,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("hidden reference flux case 2 matches expected HLLD result")
{
  const double bx    = 0.35;
  const double gamma = 1.4;

  const PrimitiveState left{0.9, -0.45, 0.2, 0.15, 0.8, -0.3, 0.55};
  const PrimitiveState right{1.15, 0.18, -0.12, -0.08, 1.05, 0.22, -0.4};
  const FluxState      expected{
      -0.15164205717520077, 0.6302921311068539,   0.025882982020760857, 0.06707828676255045,
      -0.35658597023319155, -0.06350044448634364, 0.14687345745300118,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}
