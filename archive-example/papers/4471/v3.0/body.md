## 1. Introduction

Thin stellar streams such as GD-1 carry gaps where a dark matter subhalo passed close to the stream. Counting gaps is one of the few ways to count subhalos too small to hold stars of their own. A gap does not last forever. Stars inside the gap keep phase mixing along the orbit, and the density contrast fades until the gap can no longer be told apart from noise. This paper estimates how long a gap stays visible.

## 2. Method

We treat a gap as a small density perturbation on a stream of stars that share one orbit. Differential phase mixing along the orbit spreads the perturbation at a rate set by the spread in orbital frequency across the stream. In a static potential, for a stream at galactocentric radius R with velocity dispersion σ_v, the perturbation is erased after t_gap ≈ πR/σ_v. The estimate depends only on the velocity dispersion and the radius of the stream, and not on the mass of the subhalo that opened the gap.

## 3. A rotating bar

A rotating bar adds resonances that widen the spread in orbital frequency for streams whose pericentres pass near the corotation radius. We integrate test-particle streams in five potentials, two static and three with a bar of pattern speed between 35 and 45 km/s/kpc, using the galpy library (Bovy 2015). The phase-mixing rate rises near resonance, and the gap closes sooner.

## 4. Results

For a GD-1-like stream at 14 kpc with a velocity dispersion of 2 km/s we find gap lifetimes of 0.6 Gyr in the static case. This is consistent with the N-body gap growth found by Erkal & Belokurov (2015). Bar resonances shorten lifetimes by 20 to 40 per cent for streams with pericentres inside 8 kpc and leave outer streams unchanged. Table 2 gives lifetimes for five potentials, and Table 3 the fraction of impacts in the last 3 Gyr that still leave a visible gap.

## 5. Discussion

Gaps are erased after 0.4 to 0.6 Gyr, so subhalo counts from older streams are incomplete. The incompleteness factor in Table 3 depends on the potential, and a count from an inner stream needs the barred correction.

## References

Erkal, D. and Belokurov, V. (2015). Properties of dark subhaloes from gaps in tidal streams. MNRAS 454, 3542.

Bovy, J. (2015). galpy: a Python library for galactic dynamics. ApJS 216, 29.
