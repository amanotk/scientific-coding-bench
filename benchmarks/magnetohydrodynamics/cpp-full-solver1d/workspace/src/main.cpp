#include "mhd1d.hpp"

#include <iomanip>
#include <iostream>
#include <vector>

namespace
{

constexpr std::size_t        kBrioWuNx             = 400;
constexpr double             kBrioWuXLeft          = 0.0;
constexpr double             kBrioWuXRight         = 1.0;
constexpr double             kBrioWuDiscontinuityX = 0.5;
constexpr double             kBrioWuDt             = 5.0e-4;
constexpr double             kBrioWuTFinal         = 0.1;
constexpr double             kBrioWuGamma          = 2.0;
constexpr double             kBrioWuBx             = 0.75;
constexpr mhd1d::StateVector kBrioWuLeftPrimitive{
    1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
};
constexpr mhd1d::StateVector kBrioWuRightPrimitive{
    0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0,
};

void fill_brio_wu_initial_profile(mhd1d::ArrayView profile)
{
  const std::vector<double> centers = mhd1d::cell_centers(kBrioWuNx, kBrioWuXLeft, kBrioWuXRight);

  for (std::size_t index = 0; index < centers.size(); ++index) {
    const mhd1d::StateVector& state =
        (centers[index] < kBrioWuDiscontinuityX) ? kBrioWuLeftPrimitive : kBrioWuRightPrimitive;
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      profile(index, component) = state[component];
    }
  }
}

void primitive_to_conservative_profile(mhd1d::ConstArrayView primitive_cells,
                                       mhd1d::ArrayView      conservative_cells)
{
  const int nx = static_cast<int>(primitive_cells.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t  x = static_cast<std::size_t>(ix);
    mhd1d::StateVector primitive{};
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      primitive[component] = primitive_cells(x, component);
    }
    const mhd1d::StateVector conservative =
        mhd1d::primitive_to_conservative(primitive, kBrioWuBx, kBrioWuGamma);
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      conservative_cells(x, component) = conservative[component];
    }
  }
}

void conservative_to_primitive_profile(mhd1d::ConstArrayView conservative_cells,
                                       mhd1d::ArrayView      primitive_cells)
{
  const int nx = static_cast<int>(conservative_cells.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t  x = static_cast<std::size_t>(ix);
    mhd1d::StateVector conservative{};
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      conservative[component] = conservative_cells(x, component);
    }
    const mhd1d::StateVector primitive =
        mhd1d::conservative_to_primitive(conservative, kBrioWuBx, kBrioWuGamma);
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      primitive_cells(x, component) = primitive[component];
    }
  }
}

std::vector<double> run_brio_wu_simulation()
{
  std::vector<double> primitive_buffer(kBrioWuNx * mhd1d::kStateWidth);
  std::vector<double> conservative_buffer(kBrioWuNx * mhd1d::kStateWidth);
  std::vector<double> final_primitive_buffer(kBrioWuNx * mhd1d::kStateWidth);

  fill_brio_wu_initial_profile(
      mhd1d::ArrayView(primitive_buffer.data(), kBrioWuNx, mhd1d::kStateWidth));

  primitive_to_conservative_profile(
      mhd1d::ConstArrayView(primitive_buffer.data(), kBrioWuNx, mhd1d::kStateWidth),
      mhd1d::ArrayView(conservative_buffer.data(), kBrioWuNx, mhd1d::kStateWidth));

  const double dx = (kBrioWuXRight - kBrioWuXLeft) / static_cast<double>(kBrioWuNx);
  mhd1d::evolve_ssp_rk3_fixed_dt(
      mhd1d::ConstArrayView(conservative_buffer.data(), kBrioWuNx, mhd1d::kStateWidth),
      mhd1d::ArrayView(conservative_buffer.data(), kBrioWuNx, mhd1d::kStateWidth), kBrioWuTFinal,
      kBrioWuDt, dx, kBrioWuBx, kBrioWuGamma);

  conservative_to_primitive_profile(
      mhd1d::ConstArrayView(conservative_buffer.data(), kBrioWuNx, mhd1d::kStateWidth),
      mhd1d::ArrayView(final_primitive_buffer.data(), kBrioWuNx, mhd1d::kStateWidth));

  return final_primitive_buffer;
}

} // namespace

int main()
{
  const std::vector<double>   final_primitive_buffer = run_brio_wu_simulation();
  const mhd1d::ConstArrayView final_primitive_cells(final_primitive_buffer.data(), kBrioWuNx,
                                                    mhd1d::kStateWidth);
  const std::vector<double>   centers = mhd1d::cell_centers(kBrioWuNx, kBrioWuXLeft, kBrioWuXRight);

  std::cout << "x,rho,u,v,w,p,by,bz\n";
  std::cout << std::setprecision(17);
  for (std::size_t index = 0; index < kBrioWuNx; ++index) {
    std::cout << centers[index] << ',' << final_primitive_cells(index, 0) << ','
              << final_primitive_cells(index, 1) << ',' << final_primitive_cells(index, 2) << ','
              << final_primitive_cells(index, 3) << ',' << final_primitive_cells(index, 4) << ','
              << final_primitive_cells(index, 5) << ',' << final_primitive_cells(index, 6) << '\n';
  }

  return 0;
}
