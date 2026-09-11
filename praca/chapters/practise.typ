#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#set text(lang: "en")

#let module-node(pos, label, tint: blue, ..args) = node(
  pos,
  align(center, label),
  width: 30mm,
  inset: 5pt,
  fill: tint.lighten(75%),
  stroke: 0.8pt + tint.darken(20%),
  corner-radius: 4pt,
  ..args,
)

= Implementation of the SAR radar simulator <ch-implementacja>

This chapter presents the design and implementation of a synthetic aperture radar (SAR) simulator. The program was written in Python, using mainly the NumPy, SciPy, and Matplotlib libraries. The adopted model is based on the geometry and aperture-synthesis relations described by theoretical chapters.

== Program architecture

The code is split into modules that follow the processing stages: acquiring and preparing input data, system configuration, geometric and radiometric calculations, image formation, and presentation of results. This split reduces coupling between parts of the program and makes it possible to change scene or radar parameters independently.

#figure(
[
  #align(center)[
    #diagram(
      spacing: (28pt, 20pt),
      cell-size: (18mm, 14mm),
      edge-stroke: 0.8pt + luma(80),
      edge-corner-radius: 6pt,
      mark-scale: 70%,

      module-node((0, 0), [`Satellite`], tint: orange),
      module-node((0, 2), [`Scene`], tint: orange),

      module-node((2, 0), [`SARTrajectory`], tint: red, width: 34mm),
      module-node((2, 1), [`SARRaytracer`], tint: red, width: 34mm),

      module-node((4, 2), [`run_sar.main`], tint: green, width: 34mm),

      // Edges with better-chosen bend points
      edge((4, 2), (0, 0), "->", label: text(size: 7.5pt)[creates], corner: left),
      edge((4, 2), (0, 2), "->", label: text(size: 7.5pt)[loads]),
      edge((4, 2), (2, 1), "->", label: text(size: 7.5pt)[creates], corner: right),

      edge((2, 1), (0, 0), "->", label: text(size: 7.5pt)[`sat`], corner: right),
      edge((2, 1), (0, 2), "->", label: text(size: 7.5pt)[`scene`], corner: left),
      edge((2, 1), (2, 0), "->", label: text(size: 7.5pt)[creates]),

      edge((2, 0), (0, 0), "->", label: text(size: 7.5pt)[`sat`]),
    )
  ]
  #v(4pt)
  #text(size: 8pt)[_Source: own work based on the program code._]
],
  caption: [Dependencies between the main classes and modules of the simulator.],
) <fig-architektura-sar>

#figure(
  [
    #table(
    columns: (32mm, 1fr),
    align: (left, left),
    inset: 5pt,
    stroke: 0.5pt + luma(180),
    fill: (_, y) => if y == 0 { luma(230) },

    table.header([*Module*], [*Responsibility*]),
    [`get_data.py`], [Downloading the digital surface model and the land-cover map from Geoportal services.],
    [`config.py`], [Physical constants, radar-system parameters, and scattering parameters assigned to terrain classes.],
    [`Scene.py`], [Loading rasters, matching their size, and representing the scene],
    [`Satelite.py`], [Representation of satellite parameters and computation of derived quantities.],
    [`loss.py`], [Computation of two-way gaseous atmospheric attenuation.],
    [`sar_simulator.py`], [Geometric and radiometric calculations, shadow detection, and control of the simulation process.],
    [`sar_mechanics.py`], [Trajectory model, Doppler history, and coherent image formation by back-projection.],
    [`run_sar.py`], [Command-line interface and coordination of the successive computation stages.],
    [`visualise.py`], [Alternative module for generating diagnostic maps and result summaries.],
    )
    #v(3pt)
    #text(size: 8pt)[_Source: own work based on the program code._]
  ],
  caption: [Responsibilities of the simulator modules.],
) <tab-moduly>

The dependencies shown in @fig-architektura-sar are uses and associations, not inheritance. `SARRaytracer` holds references to one scene and one `Satellite` object, and during a full simulation it creates a `SARTrajectory` object. The latter also holds a reference to the `Satellite` object. The `main` function creates the listed objects and starts the calculations. The central module `sar_simulator.py` also uses functions from `loss.py` and `sar_mechanics.py`.

== Input data and scene representation

=== Acquisition of terrain data

The module `get_data.py` downloads two rasters for a rectangular area given in the national PL-1992 coordinate system (EPSG:2180). The WCS service allows raster data to be downloaded, including elevation models @geoportalwcs:

- a digital surface model (DSM, Polish NMPT) provided as an ESRI ASCII Grid,
- a land-cover class map from the WCS service, stored as a PNG image.

The DSM describes surface height, so it includes not only the terrain relief but also objects on the surface. This distinction matters when computing local slope and radar shadow. Land-cover data are used to assign backscattering parameters to pixels.

=== Scene model

The `Scene` class stores the height matrix `dem`, the class matrix `land_cover`, and raster metadata: the number of rows and columns, the coordinates of the lower-left corner, and the cell size. No-data values are replaced with `NaN` on load, so they can be excluded from later calculations.

The ASCII Grid parser accepts different header field names found in WCS services. Cell-centre coordinates are computed separately for both axes, with the first matrix row corresponding to the northern edge of the scene. The land-cover map is scaled to the DSM size by nearest-neighbour interpolation, and each pixel is then assigned to one of ten classes by the smallest distance in RGB space.

=== Computing the incidence angle <sec-incidence-angle>

The incidence angle is not taken as constant for all cells. From the gradient of the digital surface model $z(x,y)$ the local normal is computed as

$ bold(n) = (-partial z / partial x, -partial z / partial y, 1)
              / norm((-partial z / partial x, -partial z / partial y, 1)). $

If $bold(r)$ is the unit vector from the scene cell to the satellite, the local incidence angle satisfies

$ theta_i = arccos(bold(r) dot bold(n)). $ <eq-incidence>


== Radar system configuration

Input parameters are collected in the module `config.py`. This makes it easier to run successive experiments without changing the simulator algorithms. The configuration also stores the speed of light, Boltzmann's constant, land-cover class names, and empirical values of the backscattering coefficient $sigma^0$.

#figure(
  [
    #table(
    columns: (35mm, 29mm, 1fr),
    align: (left, left, left),
    inset: 4pt,
    stroke: 0.5pt + luma(180),
    fill: (_, y) => if y == 0 { luma(230) },

    table.header([*Parameter*], [*Value*], [*Meaning*]),
    [`orbit_height`], [693 km], [Orbit height above the Earth's surface.],
    [`velocity`], [7511.8 m/s], [Satellite speed along the flight path.],
    [`look_side`], [`right`], [Look side relative to the flight direction.],
    [`frequency`], [5.405 GHz], [Radar carrier frequency, C-band.],
    [`bandwidth`], [100 MHz], [Signal bandwidth.],
    [`pulse_duration`], [50 µs], [Pulse duration.],
    [`prf`], [1500 Hz], [Pulse repetition frequency.],
    [`tx_power`], [4400 W], [Peak transmitter power.],
    [`antenna_length`], [12.3 m], [Antenna length in the azimuth direction.],
    [`antenna_height`], [0.84 m], [Antenna size in the elevation direction.],
    [`aperture_eff`], [0.6], [Antenna aperture efficiency.],
    [`noise_figure`], [3.0 dB], [Receiver noise figure.],
    [`losses_system`], [3.5 dB], [Combined hardware and processing losses.],
    [`T_ref`], [290 K], [Receiver reference temperature.],
    )
    #v(3pt)
    #text(size: 8pt)[Source: own work based on `src/config.py`; comparison of instrument parameters:]
  ],
  caption: [Baseline simulator configuration parameters, taken from the Sentinel-1 C-SAR instrument.],
) <tab-konfiguracja>

The values listed in @tab-konfiguracja do not describe all Sentinel-1 operating modes and should not be treated as a complete instrument specification. The program configuration rounds some of these values and selects a single working set.

=== Satellite model

The `Satellite` class, defined in `Satelite.py`, stores the configuration parameters and exposes derived quantities computed on demand. The relations themselves are given in @ch-teoria; @tab-parametry-pochodne shows how they are named in the code.

#figure(
  [
    #table(
    columns: (37mm, 45mm, 1fr),
    align: (left, center, left),
    inset: 5pt,
    stroke: 0.5pt + luma(180),
    fill: (_, y) => if y == 0 { luma(230) },

    table.header([*Quantity*], [*Relation*], [*Meaning*]),
    [`wavelength`], [$lambda = c / f$], [Carrier wavelength.],
    [`antenna_gain`], [$G = eta (4 pi A) / lambda^2$], [Linear gain of an antenna of area $A$.],
    [`antenna_gain_dB`], [$G_"dB" = 10 log_10 G$], [Antenna gain on a decibel scale.],
    [`L_sys`], [$L_"sys" = 10^(L_"dB" / 10)$], [Linear form of system losses.],
    [`T_sys`], [$T_"sys" = T_"ref" 10^("NF" / 10)$], [Equivalent system noise temperature.],
    [`range_resolution`], [$delta_r = c / (2 B)$], [Slant-range resolution.],
    [`azimuth_resolution`], [$delta_a = L_a / 2$], [Theoretical azimuth resolution in stripmap mode.],
    )
    #v(3pt)
  ],
  caption: [Derived quantities computed by the `Satellite` class.],
) <tab-parametry-pochodne>

== Geometric and radiometric model

=== Observation geometry

The `SARRaytracer` class from `sar_simulator.py` implements the first, geometric–radiometric phase of the simulation. To limit the computational cost, the input scene can be subsampled with a step given by `subsample`. The satellite position is set relative to the scene centre, assuming side-looking observation at a reference incidence angle of 38° by default.

For each pixel the slant range is computed from @eq-slant-range. The local surface normal and the incidence angle are obtained as in @sec-incidence-angle.

=== Backscattering

The function `compute_sigma0` assigns each pixel a $sigma^0$ value that depends on the land-cover class and the incidence angle. For the reference angle each class has a mean value in decibels, a deviation, and an angular-correction exponent. The relation used in the program is

$ sigma^0(theta) = sigma^0(theta_"ref") (cos theta / cos theta_"ref")^n. $

A small class-dependent random perturbation is added to the decibel values. Then, if the speckle model is enabled, the linear $sigma^0$ is multiplied by an exponentially distributed random variable. The pseudorandom generator has a fixed seed, so successive runs on the same data are repeatable.

The scattering parameters are empirical and indicative. The model does not account for polarisation, soil moisture, vegetation state, or the orientation of buildings, among other effects.

=== Received power, noise, and atmospheric attenuation <sec-atmosphere>

Received power from a distributed target is computed with @eq-received-power, using the resolution-cell area from @eq-resolution-cell. Thermal noise power follows @eq-noise, and the signal-to-noise ratio is $"SNR" = P_r / P_n$. The program also computes a quantity named NESZ. The expression used for it is not dimensionally consistent with the dimensionless $sigma^0$ and needs a separate check, so the `nesz` result is not treated as a verified quality parameter.

The module `loss.py` includes attenuation caused by oxygen and water vapour. The structure of the calculation is inspired by the approximate method in Annex 2 of Recommendation ITU-R P.676 @itu676. Specific attenuation is converted to a slant propagation path and then doubled, because the signal crosses the atmosphere from the radar to the surface and back. The function returns a linear loss factor $L_"atm" >= 1$.

=== Radar shadow and the slant-range image

The shadow mask is built by sampling the segment that joins each pixel to the satellite. If at any intermediate point the DSM height exceeds the ray height, the pixel is marked as unilluminated. The number of samples along the ray is set by `shadow_steps`; increasing it improves accuracy at the cost of runtime.

In the geometric phase, visible points are grouped by slant range. For each scene row the $sigma^0$ values are assigned to one of the range bins, after which their mean is computed. This produces a phase-incoherent projective image. It is not yet the result of coherent SAR processing, but it makes it possible to assess the effect of geometry and shadow.

== Aperture synthesis and simplified image formation

=== Antenna response and coherent accumulation

Azimuth antenna directivity is approximated by

$ w_n(x,y) = sinc^2(psi_n / theta_"az"), $ <eq-antenna-weight>

where $psi_n$ is the angle between the look direction of a given cell and the across-track direction for the $n$-th satellite position, and $theta_"az" = lambda / L_a$. The NumPy function defines $"sinc"(u) = sin(pi u)/(pi u)$. The weight $w_n$ is non-negative and represents the adopted two-way azimuth pattern.

The reflectivity field passed to the accumulation has the form

$ rho(x,y) = sqrt(sigma^0(x,y)) exp(j phi_"rnd"(x,y)), $ <eq-reflectivity>

where the phase $phi_"rnd"$ is drawn uniformly from $[0,2pi)$. The function named `backproject` in the code sums, for each platform position,

$ I(x,y) = 1/N sum_(n=1)^N rho(x,y) w_n(x,y)
  exp(-j (4 pi)/(lambda) (R_n(x,y)-R_0)). $ <eq-implemented-sum>

This is a coherent accumulation of samples along the modelled aperture, because complex numbers are summed with phase preserved.

A standard image-formation chain includes range and azimuth compression and range-cell migration correction @moreira2013[pp. 10–12]. Received power, SNR, and the quantity labelled NESZ in the code are diagnostic outputs of the radiometric phase. They are not used to scale reflectivity or to add noise during coherent accumulation, so they do not directly affect the look of the output image.

=== Trajectory and Doppler history

The module `sar_mechanics.py` models straight-line satellite motion at constant speed and height, as in @eq-trajectory. The flight direction follows the scene azimuth axis, the observation is at zero squint, and the aperture centre corresponds to the instant of closest approach to the scene centre.

The synthetic aperture length and the integration time follow @eq-aperture. The theoretical number of pulses collected during the integration time is given by @eq-pulses. For computational reasons the program uses 128 equally spaced satellite positions by default. This is aperture subsampling, not a simulation of every pulse implied by the PRF.

For any scene point the exact range history $R(t_a)$ and the corresponding Doppler frequency @eq-doppler are computed. Under the zero-squint assumption the Doppler centroid is zero. The diagnostic module also computes the Doppler rate, the Doppler bandwidth, and a comparison of the exact phase history with the quadratic approximation.

== Running the program and presenting results

The program entry point is the `main` function in `run_sar.py`. The command-line interface lets the user specify input files and change three parameters that affect computational cost:

- `--subsample` — scene-raster subsampling step,
- `--shadows` — number of samples used during shadow detection,
- `--n_pos` — number of satellite positions used for aperture synthesis.

The option `--no_sar` stops the calculations after the geometric–radiometric phase. In the full mode, coherent azimuth accumulation is also performed. The program writes diagnostic images showing, among other things, the DSM, land-cover classes, the shadow mask, $sigma^0$, SNR, atmospheric losses, and the output image. The console also prints SNR distribution statistics, the value labelled NESZ in the code, image power, and synthetic-aperture and Doppler parameters.

== Model assumptions and limitations

When assessing the simulation results, the following assumptions should be taken into account:

- the model assumes zero squint and perfect knowledge of the platform position;
- the $sigma^0$ parameters are assigned to whole terrain classes and do not account for polarisation or environmental conditions;
- radar shadow is detected by discrete ray tracing, whose accuracy depends on the scene resolution and the number of samples;
- subsampling of the rasters and of the aperture is used to limit runtime and can cause loss of detail;
- the PRF is used to obtain the theoretical number of pulses, but it does not set the spacing between positions in the subsampled aperture;
- the radiometric parameters SNR and the value labelled NESZ do not modify the image obtained by coherent accumulation;
- the model does not include a full transmit–receive chain, quantisation, motion errors, or complete processing of raw SAR data.
