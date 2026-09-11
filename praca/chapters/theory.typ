#set text(lang: "en")

= Theoretical foundations of the SAR radar model <ch-teoria>

== Scope of the chapter

Synthetic aperture radar is an active imaging system placed on a moving platform, most often a satellite. While it moves, the antenna transmits electromagnetic pulses and receives part of the energy backscattered by the observed surface. The motion of the platform means that the same area is illuminated many times from successive positions, as long as it remains in the radar coverage. In the digital signal-processing stage these observations can be combined so that they look as if they came from a receiver much longer than the real one.

This chapter discusses the phenomena represented in the simulator code: side-looking observation geometry, range and azimuth resolution, range history and Doppler frequency, antenna directivity, backscattering and speckle, radar shadow, a simplified power budget, thermal noise, gaseous attenuation, and coherent accumulation of aperture samples. Particular attention is given to the mechanics and the operating theory of synthetic aperture radars.

== Imaging geometry

=== Coordinate system

#figure(
  [
    #image("../images/moreira-convention.png", width: 250pt),
  ],
  caption: [Coordinate system following Moreira's convention @moreira2013[p. 10, Fig. 2]],
) <moreira-convention>

In the model presented in @moreira2013[p. 10, Fig. 2] and shown in @moreira-convention, the platform motion direction is identified with the azimuth axis $y$. The across-track direction $x$ describes the distance of the satellite from the incidence point, and the last axis ($z$) is height. The radar observes the scene from the side. This geometry corresponds to the basic SAR geometry, in which one distinguishes azimuth, slant range, and ground range. We will follow this convention throughout the thesis.

For a satellite position $bold(s) = (x_s, y_s, z_s)$ and a scene point $bold(p) = (x_p, y_p, z_p)$, the slant range used in the program is

$ R = norm(bold(s) - bold(p))
    = sqrt((x_s-x_p)^2 + (y_s-y_p)^2 + (z_s-z_p)^2). $ <eq-slant-range>

This is the exact Euclidean distance in a local Cartesian frame. The implementation neglects Earth's curvature and rotation. The flat-Earth assumption should therefore be understood as a local approximation, caused by the small size of the studied scene relative to the size of Earth's orbit.

The platform position at the mid-aperture instant is obtained from a given height $H$ and a reference incidence angle $theta_"ref"$:

$ d_"ground" = H tan(theta_"ref"). $ <eq-ground-offset>

The sign of the offset depends on the chosen look side. Subsequent positions form a straight-line trajectory with constant speed $v_s$:

$ y_s(t_a) = y_0 + v_s t_a, quad
   t_a in [-T_"int"/2, T_"int"/2]. $ <eq-trajectory>

This is the formula for uniform motion. Time $t_a$ is called slow time, because it describes the platform motion in azimuth. The time associated with pulse propagation is called fast time @moreira2013[p. 10].

=== Local incidence angle and shadow

The incidence angle is essential for how the signal is reflected from the terrain surface. It is this angle that decides how much energy returns to the antenna. More about how this angle is computed can be found in section @sec-incidence-angle in the practical part of the thesis.

The maximum value of the returning-signal power coefficient is 1, or 0 dB. Our antenna is both the receiver and the transmitter, so the antenna gain is the same in both cases. This means that the drop in returning power is directly proportional to the square of the antenna gain. Moreover, the incidence angle is uniquely linked to the slant range from the satellite to a point on the ground, and the returning power decreases with the fourth power of distance. These two effects together mean that we are only interested in large incidence angles. Unfortunately, they also reduce the effective observation area. In this thesis we will keep the reference angle given in the Sentinel-1 specification.

Radar shadow occurs where terrain or an object blocks the direct path between the antenna and the cell under study. The larger the incidence angle, the greater the risk of shadow.

== Resolution and the synthetic aperture

=== Range resolution

In a system that uses a signal of bandwidth $B$, the theoretical resolution in slant range is

$ delta_r = c / (2 B), $ <eq-range-resolution>

where $c$ denotes the speed of light. This relation defines the range resolution as a function of bandwidth, and therefore of pulse duration. One should remember, however, that this value also affects how long a given area is illuminated. In the world of signals, nothing comes for free.

=== Azimuth resolution

==== Classical pulsed radars and SAR

In traditional pulsed radars the angular (azimuth) resolution is directly limited by the width of the physical antenna beam $theta_"az" approx lambda / L_a$. The linear azimuth resolution at distance $R_0$ for such a system is:

$ delta_(a, "class") approx R_0 theta_"az" = (lambda R_0) / L_a. $

From this relation it follows that in a classical radar the resolution degrades drastically as the distance to the target $R_0$ grows. To obtain high resolution at large distances (for example in satellite observations), one would need giant antennas of length $L_a$ reaching hundreds of metres or kilometres, which is technically infeasible.

This limitation is solved by the synthetic aperture radar (SAR) technique. It uses the motion of the platform (an aircraft or a satellite) to digitally synthesize a very long antenna along the flight path.

In the case of synthetic aperture radar, $lambda = c/f$ is the carrier wavelength. A point remains in the beam over a segment that forms the synthetic aperture. In the model its length and the integration time are computed as

$ L_"synth" = (lambda R_0) / L_a, quad
   T_"int" = L_"synth" / v_s. $ <eq-aperture>

where $T_"int"$ is the integration time, which describes how long a given point on the ground is illuminated. This leads to the theoretical azimuth resolution:

$ delta_a = L_a / 2, $ <eq-azimuth-resolution>

independent of distance $R_0$ @moreira2013[p. 10].

The number of pulses that a real radar would transmit during the integration time is estimated as

$ N_"pulses" = T_"int" "PRF", $ <eq-pulses>

where PRF denotes the pulse repetition frequency. Moreira's paper also gives an azimuth sampling condition: the PRF should be at least equal to the Doppler bandwidth @moreira2013[p. 13].

#figure(
  [
    #table(
      columns: (31mm, 32mm, 1fr),
      align: (left, center, left),
      inset: 5pt,
      stroke: 0.5pt + luma(180),
      fill: (_, y) => if y == 0 { luma(230) },
      table.header([*Quantity*], [*Relation*], [*Role in the implementation*]),
      [Wavelength], [$lambda = c/f$], [Antenna pattern, phase, and Doppler.],
      [Range resolution], [$delta_r = c/(2B)$], [Diagnostic parameter and cell area.],
      [Azimuth resolution], [$delta_a = L_a/2$], [Diagnostic parameter and cell area.],
      [Aperture length], [$L_"synth" = lambda R_0/L_a$], [Extent of the straight-line trajectory.],
      [Integration time], [$T_"int" = L_"synth"/v_s$], [Slow-time interval.],
    )
    #v(3pt)
  ],
  caption: [Relations describing resolution and the synthetic aperture used in the simulator.],
) <tab-rozdzielczosc>

== Range history, phase, and the Doppler effect

For a point observed under straight-line platform motion, the exact range history is computed from equation @eq-slant-range. For a point at the centre of the aperture and at constant height it can be written as

$ R(t_a) = sqrt(R_0^2 + v_s^2 t_a^2)
   approx R_0 + (v_s^2 t_a^2)/(2R_0). $ <eq-range-history>

The quadratic approximation is valid when the platform displacement during the observation is much smaller than $R_0$. In our case this is a fully reasonable assumption. While the platform moves, the signal phase changes in time according to the Doppler effect:

$ phi(t_a) = -(4 pi)/(lambda) R(t_a). $ <eq-phase-history>

The factor $4 pi$ comes from two-way signal propagation. The derivative of the phase gives the Doppler frequency. After combining the information from equations @eq-range-history and @eq-phase-history and carrying out simple rearrangements we obtain:

$ f_D(t_a) = -2/lambda dif R(t_a)/dif t_a
           = -(2 v_s (y_s(t_a)-y))/(lambda R(t_a)). $ <eq-doppler>

The range-history, phase, and Doppler relations correspond to equations (3), (5), and (6) in Moreira's tutorial @moreira2013[pp. 10–11]. The approximate rate of change of the Doppler frequency can be computed by substituting into equation (11) @eq-doppler the formula for uniform platform motion (we assume that it moves linearly). After computing the derivative and simplifying we obtain:

$ K_a = -(2 v_s^2)/(lambda R_0)
$. <eq-doppler-rate>

Because the Doppler frequency changes at a constant rate, we can easily see that the bandwidth varies linearly according to the relation:
#v(10pt)
#align(center)[
$B_D = abs(K_a) T_"int"$ <eq-doppler-rate>]

== Backscattering and speckle

=== The coefficient $sigma^0$

The coefficient $sigma^0$ describes the radar cross section normalized to area. After calibration, SAR image intensity can represent this quantity @moreira2013[p. 11]. It has a key effect on what fraction of the signal power returns to the antenna from a given area.

=== Speckle

Speckle is the result of coherent summation of the responses of many elementary scatterers located in one resolution cell. For fully developed speckle the intensity has an exponential distribution, and the phase a uniform one @moreira2013[p. 12] @goodman1976.

== Radiometric model

=== Antenna gain and received power

For any aperture of area $A$ the maximum antenna gain is

$ G = eta (4 pi A)/(lambda^2), $ <eq-gain>

where $eta$ is the aperture efficiency and $lambda$ is the wavelength. The power received from a scene cell is then estimated by the standard radar equation:

$ P_r = (P_t G^2 lambda^2 sigma^0 A_"res")
  / ((4 pi)^3 R^4 L_"sys" L_"atm"), $ <eq-received-power>

with cell area

$ A_"res" = (delta_r delta_a)/(sin theta_i). $ <eq-resolution-cell>

The $R^(-4)$ dependence comes from the two-way travel of the wave between the radar and the target.

=== Thermal noise and SNR

The receiver noise power is modelled by

$ P_n = k T_"sys" B, quad
   T_"sys" = T_"ref" 10^("NF"/10), $ <eq-noise>

where $k$ is Boltzmann's constant, $T_"sys"$ is the equivalent noise temperature, and NF is the noise figure in decibels.

=== Atmospheric gaseous attenuation

Oxygen and water vapour absorb part of the microwave energy. Recommendation ITU-R P.676 describes methods for computing gaseous attenuation for terrestrial and slant paths; its Annex 2 contains an approximate method based on pressure, temperature, and water-vapour density @itu676.

The model splits the specific attenuation of oxygen $gamma_o$ and water vapour $gamma_w$ and specifies them as values in dB/km. The detailed implementation is presented in @sec-atmosphere in the practical part of the thesis.

== Linking theory to the implementation

#figure(
  [
    #table(
      columns: (38mm, 42mm, 1fr),
      align: (left, left, left),
      inset: 5pt,
      stroke: 0.5pt + luma(180),
      fill: (_, y) => if y == 0 { luma(230) },
      table.header([*Topic*], [*Implementation location*], [*Scope of the model*]),
      [Geometry and shadow], [`SARRaytracer`], [Local flat frame, terrain gradient, and discrete ray tracing.],
      [Radar parameters], [`Satellite`], [Wavelength, gain, losses, noise temperature],
      [Scattering], [`compute_sigma0`], [Terrain classes, angular correction, and single-look speckle.],
      [Radiometry], [`received_power`, `noise_power`, `snr`], [Diagnostic power and SNR maps.],
      [Atmosphere], [`atmospheric_loss`], [Two-way oxygen and water-vapour attenuation.],
      [Motion and Doppler], [`SARTrajectory`], [Straight trajectory, range history, and Doppler.],
      [Image formation], [`backproject`], [Coherent sum of the reflectivity field.],
    )
    #v(3pt)
  ],
  caption: [Link between the discussed theoretical topics and the simulator components.],
) <tab-teoria-implementacja>
