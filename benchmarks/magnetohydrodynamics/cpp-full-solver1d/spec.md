# cpp-full-solver1d

Implement a 1D ideal MHD full solver in C++.

## Task

The benchmark contract is fixed around these choices:

- domain: `[0, 1]`
- initial discontinuity: `x = 0.5`
- conservative evolution
- primitive reconstruction: MC2
- flux function: HLLD
- time integration: SSP-RK3
- boundary conditions: zero-gradient
- output format: CSV with columns `x,rho,u,v,w,p,by,bz`
- default problem: Brio-Wu with `gamma = 2` and `Bx = 0.75`

## Numerical method

The solver implements the following numerical scheme:

1. **Reconstruction**: MC2 (minmod with centered differences) for primitive variables
2. **Riemann solver**: HLLD approximate Riemann solver for ideal MHD fluxes
3. **Time integration**: SSP-RK3 (strong stability preserving Runge-Kutta, 3rd order)
4. **Boundary conditions**: Zero-gradient ghost cells (2 cells per side)

### State ordering

Primitive state vector (7 components):
```
[rho, u, v, w, p, By, Bz]
```

Conservative state vector (7 components):
```
[rho, mx, my, mz, E, By, Bz]
```

where `mx = rho * u`, `my = rho * v`, `mz = rho * w`, and total energy
`E = p/(gamma-1) + 0.5*rho*(u^2+v^2+w^2) + 0.5*(Bx^2+By^2+Bz^2)`.

### Default constants

| Parameter | Value |
|-----------|-------|
| `gamma` | 2.0 |
| `Bx` | 0.75 |
| `dt` | 5.0e-4 |
| `t_final` | 0.1 |
| `nx` | 400 |

## Building

```bash
mkdir build && cd build
cmake ..
cmake --build .
```

The solver executable is placed at `build/bin/cpp_full_solver1d`.

## Usage

```bash
./bin/cpp_full_solver1d
```

The solver uses hardcoded Brio-Wu defaults and writes CSV output to stdout.

### Running and saving output

```bash
./bin/cpp_full_solver1d > solution.csv
```

## Visualization

A plot helper script is provided for quick inspection of results:

```bash
python scripts/plot_solution.py solution.csv
```

This displays profiles for density (`rho`), velocity (`u`), pressure (`p`), and
magnetic field (`by`).

## API reference

### Core functions (`mhd1d.hpp`)

Type aliases used by the API:

- `StateVector = std::array<double, 7>`
- `ArrayView = std::experimental::mdspan<double, dextents<size_t,2>>`
- `ConstArrayView = std::experimental::mdspan<const double, dextents<size_t,2>>`

#### `StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma)`

Converts a primitive state vector to conservative form.

**Parameters:**
- `primitive`: 7-component primitive state `[rho, u, v, w, p, By, Bz]`
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** 7-component conservative state `[rho, mx, my, mz, E, By, Bz]`

#### `StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma)`

Converts a conservative state vector to primitive form.

**Parameters:**
- `conservative`: 7-component conservative state
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** 7-component primitive state

#### `void pad_zero_gradient_ghost_cells(ConstArrayView cells, ArrayView padded)`

Fills the padded array with two zero-gradient ghost cells on each side.

**Parameters:**
- `cells`: interior cell-centered states with shape `(nx, 7)`
- `padded`: output with shape `(nx + 4, 7)`

#### `void mc2_slopes(ConstArrayView primitive_cells, ArrayView slopes)`

Computes MC2-limited slopes for primitive variables.

**Parameters:**
- `primitive_cells`: primitive states with shape `(nx, 7)`
- `slopes`: output slopes with shape `(nx, 7)`

#### `void reconstruct_mc2_interfaces(ConstArrayView primitive_cells, ArrayView left_states, ArrayView right_states)`

Performs MC2 reconstruction at interfaces.

**Parameters:**
- `primitive_cells`: primitive states with shape `(nx, 7)`
- `left_states`: left interface states with shape `(nx - 1, 7)`
- `right_states`: right interface states with shape `(nx - 1, 7)`

#### `StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx, double gamma)`

Computes the HLLD numerical flux given left and right primitive states.

**Parameters:**
- `left`: Left primitive state at interface
- `right`: Right primitive state at interface
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** Numerical flux vector

#### `void compute_semidiscrete_rhs(ConstArrayView conservative_cells, ArrayView rhs, double dx, double bx = 0.75, double gamma = 2.0)`

Computes the semidiscrete RHS with an explicit cell width.

**Parameters:**
- `conservative_cells`: conservative states with shape `(nx, 7)`
- `rhs`: output RHS with shape `(nx, 7)`
- `dx`: cell width
- `bx`: constant `Bx`
- `gamma`: adiabatic index

#### `void ssp_rk3_step(ConstArrayView conservative_cells, ArrayView output, double dt, double dx, double bx = 0.75, double gamma = 2.0)`

Performs one SSP-RK3 time step.

**Parameters:**
- `conservative_cells`: input conservative states with shape `(nx, 7)`
- `output`: output conservative states with shape `(nx, 7)`
- `dt`: time step
- `dx`: cell width
- `bx`: constant `Bx`
- `gamma`: adiabatic index

#### `void evolve_ssp_rk3_fixed_dt(ConstArrayView conservative_cells, ArrayView output, double t_final, double dt, double dx, double bx = 0.75, double gamma = 2.0)`

Runs repeated SSP-RK3 updates with fixed `dt` until `t_final`.

**Parameters:**
- `conservative_cells`: input conservative states with shape `(nx, 7)`
- `output`: output conservative states with shape `(nx, 7)`
- `t_final`: final time
- `dt`: fixed time step (final step is clipped to hit `t_final`)
- `dx`: cell width
- `bx`: constant `Bx`
- `gamma`: adiabatic index

## Evaluation

The hidden evaluation compares solver output against a reference solution using:

- **Scored variables**: `rho`, `u`, `p`, `by`
- **Comparison window**: Interior cells only (excludes 2 edge-adjacent cells per side)
- **Metrics**: L1 and Linf absolute errors
- **Tolerances**: Defined in `shared/eval/fixtures/mhd1d/brio_wu_fixture.json`
