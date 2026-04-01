#include "mhd1d.hpp"

#include <iomanip>
#include <iostream>
#include <vector>

namespace
{

constexpr std::size_t        kBrioWuNx    = 400;
constexpr double             kBrioWuGamma = 2.0;
constexpr double             kBrioWuBx    = 0.75;
constexpr mhd1d::StateVector kBrioWuLeftPrimitive{
    1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
};
constexpr mhd1d::StateVector kBrioWuRightPrimitive{
    0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0,
};

} // namespace

mhd1d::SolverWorkspace initialize(std::size_t nx, double gamma, double bx,
                                  const mhd1d::StateVector& left_state,
                                  const mhd1d::StateVector& right_state)
{
  mhd1d::SolverWorkspace workspace(nx, gamma, bx);

  for (std::size_t index = workspace.Lbx; index <= workspace.Ubx; ++index) {
    const std::size_t         center_index = index - workspace.Lbx;
    const mhd1d::StateVector& state = (workspace.x(center_index) < 0.5) ? left_state : right_state;
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      workspace.primitive(index, component) = state[component];
    }
  }

  mhd1d::set_boundary(workspace.primitive, workspace.Lbx, workspace.Ubx);
  mhd1d::primitive_profile_to_conservative(workspace.primitive, workspace.conservative, bx, gamma);

  return workspace;
}

int main()
{
  const double delt = 5.0e-4;
  const double tmax = 0.1;

  auto workspace =
      initialize(kBrioWuNx, kBrioWuGamma, kBrioWuBx, kBrioWuLeftPrimitive, kBrioWuRightPrimitive);

  mhd1d::evolve_ssp_rk3(workspace, delt, tmax);

  std::cout << "x,rho,u,v,w,p,by,bz\n";
  std::cout << std::setprecision(17);
  for (std::size_t index = workspace.Lbx; index <= workspace.Ubx; ++index) {
    const std::size_t center_index = index - workspace.Lbx;
    std::cout << workspace.x(center_index) << ',' << workspace.primitive(index, 0) << ','
              << workspace.primitive(index, 1) << ',' << workspace.primitive(index, 2) << ','
              << workspace.primitive(index, 3) << ',' << workspace.primitive(index, 4) << ','
              << workspace.primitive(index, 5) << ',' << workspace.primitive(index, 6) << '\n';
  }

  return 0;
}
