#!/usr/bin/env python3
"""
nest_dg_ca3_fi_calibration.py
==============================
NEST 3.9 confirmation of the DG-CA3 extension's single-neuron f-I
calibration (Phase 6.1). Run on MN5 to confirm/replace the numbers
derived from the numpy Izhikevich stand-in (izh_calibrate.py) BEFORE
they are written into build_dg_ca3_network() (Phase 6.2).

Populations calibrated here:
  PPGC_HGC : RS granule cell  (a=0.02, b=0.2, c=-65, d=8,  I_e=0)
             HGC and PPGC given IDENTICAL intrinsic parameters -- per
             Kassab & Alexandre 2018 the PPGC/HGC distinction is a
             connectivity/recruitment distinction (both are DG granule
             cells), not an intrinsic-electrophysiology one.
  DG_BASKET: FS interneuron    (a=0.10, b=0.2, c=-65, d=2,  I_e=0)
             reused verbatim from existing basket_params.
  MC_LOW   : RS + I_e=0.0     -- low-threshold mossy cell
  MC_HIGH  : RS + I_e=-9.0    -- high-threshold mossy cell
             tuned to reproduce Kassab & Alexandre's own theta_l=0.1 /
             theta_h=0.5 ratio (5.0x) under the numpy stand-in; this
             script confirms whether that ratio holds under NEST's
             actual solver.

Output
------
Raw data (NOT just plots) is written to HDF5, following the same
schema philosophy as save_replay_hdf5() in replay_scaled.py: root
attrs + one group per population with attrs (intrinsic params,
rheobase) and datasets (per-rate response curve + raw spike times/
senders, compressed). This keeps simulation (NEST, on MN5) and
analysis (numpy/h5py, local) separated, matching the project's
established HDF5 pipeline.

CLI mirrors replay_scaled.py conventions: --threads, --out-hdf5,
--no-figures.

Sweep resolution (2026-07-22 revision)
--------------------------------------
The first MN5 run (res/2026-07-22/dg_ca3_fi_calib.h5) returned an identical
200 Hz rheobase for all four populations and mc_high_low_ratio = 1.00,
tripping the [FLAG] check. That was a measurement artifact, not a
disconfirmation of the parameter sets:

  * --rate-step was 200 Hz, so the first non-zero grid point was 200 Hz;
  * --criterion-hz was 2.0 Hz, which every population already exceeded at
    that first point (MC ~15-25 Hz, DG_BASKET ~85 Hz).

Rheobase was therefore floored at the grid's first point for all four, which
is indistinguishable from "all equal" in the saved summary -- even though the
f-I curves are visibly separated everywhere above threshold.

Four changes address this:
  1. build_rate_grid() -- fine grid (default 20 Hz) up to --fine-rate-max,
     coarse grid (default 200 Hz) above it, so the threshold region is
     resolved without paying for a fine sweep out to 6.2 kHz.
  2. rheobase_rate() interpolates between bracketing grid points instead of
     snapping to the first point at or above criterion.
  3. threshold_by_extrapolation() supplies the primary, criterion-free
     metric, and now drives the [OK]/[FLAG] verdict. A criterion-based
     rheobase measures `threshold + criterion/gain`, so the ratio it yields
     is biased toward 1.0 and CANNOT test the 5.0x target: on a synthetic
     pair with a true 5.00x ratio the measured value is 4.13x at a 1 Hz
     criterion and 2.06x at 10 Hz. Raising the criterion makes this worse,
     not better -- the fix for the 2026-07-22 run is the finer grid, not a
     higher criterion, which is why --criterion-hz stays at 2.0.
  4. Every run reports the ratio across a criterion ladder (CRITERIA_HZ) as
     a diagnostic, so the criterion-dependence is visible rather than
     implicit.

check_grid_resolves_criterion() now warns explicitly when the floor
condition recurs, so a future run cannot fail this way silently.

Caveat carried forward: applying the same interpolation to the OLD 07-22
response curves gives an MC_HIGH/MC_LOW ratio near 2x rather than 5x. That
estimate is itself unreliable (it interpolates across a single 200 Hz
interval), but it is a hint that the 5.0x target may not survive the finer
sweep, and that MC_HIGH's I_e = -9.0 will need re-tuning.

Requirements: NEST >= 3.9, numpy, matplotlib, h5py.
"""

import argparse
import os
import sys
import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    import h5py
    _HDF5_AVAILABLE = True
except ImportError:
    _HDF5_AVAILABLE = False

import nest
from tiny import safe_set_seeds  # reuse existing seeding convention

CANDIDATE_PARAMS = {
    "ppgc_hgc":  dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "dg_basket": dict(a=0.10, b=0.2,  c=-65.0, d=2.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "mc_low":    dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "mc_high":   dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=-9.0),
}

# The MC_HIGH/MC_LOW ratio is a function of where the rheobase criterion is
# placed, so a single criterion cannot tell you whether the target 5.0x
# separation exists -- it only tells you whether it exists at that one point.
# Every run reports the ratio across this ladder; --criterion-hz picks which
# entry drives the [OK]/[FLAG] verdict.
CRITERIA_HZ = [2.0, 5.0, 10.0, 20.0, 50.0]

MC_RATIO_TARGET = 5.0   # Kassab & Alexandre 2018 theta_h/theta_l
MC_RATIO_TOL    = 0.20  # +/-20%


def rheobase_rate(rates, response, criterion_hz, interpolate=True):
    """Drive rate at which the response first reaches criterion_hz.

    The grid-snapping version of this ("first swept rate at or above
    criterion") quantises the answer to the sweep step, which is what
    collapsed MC_LOW and MC_HIGH onto an identical 200 Hz rheobase in the
    2026-07-22 MN5 run even though their f-I curves are clearly separated
    everywhere above threshold. Linear interpolation between the bracketing
    grid points recovers sub-step resolution.
    """
    rates    = np.asarray(rates,    dtype=float)
    response = np.asarray(response, dtype=float)
    idx = np.where(response >= criterion_hz)[0]
    if not len(idx):
        return float("nan")
    i = idx[0]
    if not interpolate or i == 0:
        return float(rates[i])
    r_lo, r_hi = response[i - 1], response[i]
    if r_hi <= r_lo:                      # non-monotonic / flat: no gradient
        return float(rates[i])
    frac = (criterion_hz - r_lo) / (r_hi - r_lo)
    return float(rates[i - 1] + frac * (rates[i] - rates[i - 1]))


def threshold_by_extrapolation(rates, response, fit_lo_hz=5.0, fit_hi_hz=60.0):
    """Criterion-free threshold: x-intercept of the f-I curve's linear region.

    Any criterion-based rheobase measures `threshold + criterion/gain`, not
    `threshold`. Because that offset term is shared, the MC_HIGH/MC_LOW ratio
    it produces is biased toward 1.0, and the bias grows with the criterion:
    for a synthetic pair with a true 5.00x threshold ratio and matched gain,
    the measured ratio is 4.13x at a 1 Hz criterion but only 2.06x at 10 Hz.
    A criterion-based rheobase therefore cannot test the 5.0x target on its
    own, no matter how fine the rate grid is.

    Fitting the near-threshold linear region and extrapolating to zero
    response removes the criterion term entirely. The fit band defaults to
    5-60 Hz output: above the curvature at onset, below the saturation of the
    fast-spiking curve.

    Returns (threshold_hz, gain_hz_per_hz, n_fit_points). threshold is NaN
    when the fit is not trustworthy, rather than a number that merely looks
    like one: fewer than MIN_FIT_POINTS points in the band, a non-positive
    slope, or an extrapolated threshold outside the swept range. That last
    guard matters -- on the coarse 2026-07-22 grid only 3 points land in the
    band and they sit far above threshold, so the extrapolation runs off to
    negative drive rates and would otherwise report a confident, meaningless
    ratio.
    """
    MIN_FIT_POINTS = 4
    rates    = np.asarray(rates,    dtype=float)
    response = np.asarray(response, dtype=float)
    sel = (response >= fit_lo_hz) & (response <= fit_hi_hz)
    n_fit = int(sel.sum())
    if n_fit < MIN_FIT_POINTS:
        return float("nan"), float("nan"), n_fit
    slope, intercept = np.polyfit(rates[sel], response[sel], 1)
    if slope <= 0:
        return float("nan"), float(slope), n_fit
    thr = -intercept / slope
    if not (0.0 <= thr <= float(rates.max())):
        return float("nan"), float(slope), n_fit
    return float(thr), float(slope), n_fit


def build_rate_grid(fine_max, fine_step, rate_max, rate_step):
    """Fine grid near threshold, coarse grid out to rate_max.

    Rheobase lives in the first few hundred Hz, so that region needs a step
    small enough to separate populations; the upper range only has to
    characterise the slope and max response, where a coarse step is fine.
    """
    if fine_max <= 0 or fine_step <= 0:
        return np.arange(0.0, rate_max + rate_step, rate_step)
    fine   = np.arange(0.0, min(fine_max, rate_max) + fine_step, fine_step)
    coarse = np.arange(fine[-1] + rate_step, rate_max + rate_step, rate_step)
    return np.unique(np.concatenate([fine, coarse]))


def run_fi_sweep(rates_hz, weight, delay, sim_ms, n_repeats, n_threads):
    nest.ResetKernel()
    nest.SetKernelStatus({"resolution": 0.1, "local_num_threads": n_threads,
                           "print_time": False, "overwrite_files": True})
    safe_set_seeds()

    neuron_index = {}
    spk_index    = {}
    for label, params in CANDIDATE_PARAMS.items():
        for rate in rates_hz:
            neurons = nest.Create("izhikevich", n_repeats, params=params)
            gens = nest.Create("poisson_generator", n_repeats,
                                params={"rate": float(rate)})
            nest.Connect(gens, neurons, conn_spec="one_to_one",
                         syn_spec={"weight": float(weight), "delay": delay})
            spk = nest.Create("spike_recorder")
            nest.Connect(neurons, spk)
            neuron_index[(label, rate)] = neurons
            spk_index[(label, rate)]    = spk

    nest.Simulate(sim_ms)

    # response_hz[label]  : mean output rate per swept drive rate
    # raw_spikes[label]    : (times, senders_local, rate_idx) concatenated
    #                        across all rate conditions, for HDF5 export
    response_hz = {label: np.zeros(len(rates_hz)) for label in CANDIDATE_PARAMS}
    raw_spikes  = {label: {"times": [], "senders": [], "rate_idx": []}
                   for label in CANDIDATE_PARAMS}

    for label in CANDIDATE_PARAMS:
        for i, rate in enumerate(rates_hz):
            ev = nest.GetStatus(spk_index[(label, rate)], "events")[0]
            t  = np.asarray(ev["times"],   dtype=np.float32)
            s  = np.asarray(ev["senders"], dtype=np.int32)
            response_hz[label][i] = len(t) / (n_repeats * sim_ms / 1000.0)
            raw_spikes[label]["times"].append(t)
            raw_spikes[label]["senders"].append(s)
            raw_spikes[label]["rate_idx"].append(
                np.full(len(t), i, dtype=np.int16))

    for label in CANDIDATE_PARAMS:
        for key in ("times", "senders", "rate_idx"):
            raw_spikes[label][key] = (np.concatenate(raw_spikes[label][key])
                                       if raw_spikes[label][key] else
                                       np.array([], dtype=np.float32 if key == "times"
                                                 else (np.int32 if key == "senders" else np.int16)))

    return response_hz, raw_spikes


def save_calibration_hdf5(outpath, rates_hz, response_hz, raw_spikes,
                           weight, delay, sim_ms, n_repeats, criterion_hz):
    """
    Schema
    ------
    /                    root attrs: created_utc, nest_version, weight, delay_ms,
                         sim_ms, n_repeats, criterion_hz
    /rates_hz            swept drive rates [n_rates] (float32)
    /criteria_hz         rheobase criterion ladder [n_criteria] (float32)
    /mc_high_low_ratio_by_criterion
                         MC_HIGH/MC_LOW rheobase ratio per criterion
                         [n_criteria] (float32)
    /<population>/
        attrs: a, b, c, d, I_e, rheobase_hz, max_response_hz
        response_hz      mean output rate per swept rate [n_rates] (float32)
        rheobase_by_criterion
                         interpolated rheobase per criterion [n_criteria] (float32)
        spk_times        raw spike times, all conditions concatenated (float32, compressed)
        spk_senders      raw spike senders, local per-condition NodeCollection id (int32, compressed)
        spk_rate_idx     index into /rates_hz for each spike above (int16, compressed)
    """
    if not _HDF5_AVAILABLE:
        print(">>> [WARNING] h5py not installed -- skipping HDF5 export.")
        return

    os.makedirs(os.path.dirname(os.path.abspath(outpath)), exist_ok=True)
    compress = dict(compression="gzip", compression_opts=4)

    with h5py.File(outpath, "w") as h5:
        h5.attrs["created_utc"]  = datetime.datetime.utcnow().isoformat()
        h5.attrs["weight"]       = float(weight)
        h5.attrs["delay_ms"]     = float(delay)
        h5.attrs["sim_ms"]       = float(sim_ms)
        h5.attrs["n_repeats"]    = int(n_repeats)
        h5.attrs["criterion_hz"] = float(criterion_hz)
        try:
            h5.attrs["nest_version"] = nest.__version__
        except Exception:
            pass

        h5.create_dataset("rates_hz", data=np.asarray(rates_hz, dtype=np.float32))
        h5.create_dataset("criteria_hz", data=np.asarray(CRITERIA_HZ, dtype=np.float32))

        for label, params in CANDIDATE_PARAMS.items():
            g = h5.create_group(label)
            for k, v in params.items():
                g.attrs[k] = v
            rh  = rheobase_rate(rates_hz, response_hz[label], criterion_hz)
            g.attrs["rheobase_hz"]     = rh
            g.attrs["max_response_hz"] = float(response_hz[label].max())
            t, gain, n_fit = threshold_by_extrapolation(rates_hz, response_hz[label])
            g.attrs["threshold_hz"]    = t       # criterion-free; primary metric
            g.attrs["fi_gain_hz_per_hz"] = gain
            g.attrs["threshold_fit_n"] = n_fit

            g.create_dataset("response_hz",
                              data=response_hz[label].astype(np.float32))
            g.create_dataset(
                "rheobase_by_criterion",
                data=np.array([rheobase_rate(rates_hz, response_hz[label], c)
                               for c in CRITERIA_HZ], dtype=np.float32))
            g.create_dataset("spk_times",   data=raw_spikes[label]["times"],   **compress)
            g.create_dataset("spk_senders", data=raw_spikes[label]["senders"], **compress)
            g.create_dataset("spk_rate_idx", data=raw_spikes[label]["rate_idx"], **compress)

        # cross-population summary, mirrors the console [OK]/[FLAG] check
        ratios = []
        for c in CRITERIA_HZ:
            r_low  = rheobase_rate(rates_hz, response_hz["mc_low"],  c)
            r_high = rheobase_rate(rates_hz, response_hz["mc_high"], c)
            ratios.append(r_high / r_low
                          if (r_low and not np.isnan(r_low) and not np.isnan(r_high))
                          else np.nan)
        h5.create_dataset("mc_high_low_ratio_by_criterion",
                          data=np.asarray(ratios, dtype=np.float32))

        r_low  = h5["mc_low"].attrs["rheobase_hz"]
        r_high = h5["mc_high"].attrs["rheobase_hz"]
        if r_low and not np.isnan(r_low) and r_high and not np.isnan(r_high):
            h5.attrs["mc_high_low_ratio"] = float(r_high / r_low)

        # Primary verdict metric: criterion-free, so this is the one to compare
        # against the 5.0x target (see threshold_by_extrapolation docstring).
        t_low  = h5["mc_low"].attrs["threshold_hz"]
        t_high = h5["mc_high"].attrs["threshold_hz"]
        if t_low and not np.isnan(t_low) and t_high and not np.isnan(t_high):
            h5.attrs["mc_high_low_threshold_ratio"] = float(t_high / t_low)

    print(f">>> Saved calibration data -> {outpath}")


def plot_calibration(rates_hz, response_hz, criterion_hz, out_png, fine_max=None):
    """Full f-I sweep plus a zoom on the threshold region.

    The single full-range panel used previously squeezed the entire rheobase
    region into the leftmost few pixels, which is why the MC_LOW/MC_HIGH
    separation was invisible in the 2026-07-22 figure.
    """
    colors = {"ppgc_hgc": "seagreen", "dg_basket": "mediumorchid",
              "mc_low": "steelblue", "mc_high": "firebrick"}
    fig, (ax, axz) = plt.subplots(1, 2, figsize=(12, 5))

    for label, resp in response_hz.items():
        rh = rheobase_rate(rates_hz, resp, criterion_hz)
        ax.plot(rates_hz, resp, lw=1.8, color=colors[label],
                label=f"{label} (rheobase@{criterion_hz:.0f}Hz = {rh:.1f} Hz)")
        axz.plot(rates_hz, resp, lw=1.8, marker="o", ms=2.5, color=colors[label])
        if not np.isnan(rh):
            for a in (ax, axz):
                a.axvline(rh, color=colors[label], ls="--", lw=0.8, alpha=0.6)

    ax.set_xlabel("Poisson drive rate (Hz), one-to-one")
    ax.set_ylabel("Output firing rate (Hz)")
    ax.set_title("Full sweep", fontsize=10, loc="left")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    zoom_hi = fine_max if fine_max else float(rates_hz[-1]) * 0.15
    axz.axhline(criterion_hz, color="k", ls=":", lw=1.0,
                label=f"criterion = {criterion_hz:.0f} Hz")
    axz.set_xlim(0, zoom_hi)
    _in = np.asarray(rates_hz) <= zoom_hi
    _hi = max([float(np.asarray(r)[_in].max()) for r in response_hz.values()] or [1.0])
    axz.set_ylim(0, max(_hi * 1.05, criterion_hz * 2.0))
    axz.set_xlabel("Poisson drive rate (Hz), one-to-one")
    axz.set_ylabel("Output firing rate (Hz)")
    axz.set_title("Threshold region (rheobase zoom)", fontsize=10, loc="left")
    axz.legend(fontsize=8, loc="upper left")
    axz.grid(alpha=0.25)

    fig.suptitle("DG-CA3 extension: NEST 3.9 f-I confirmation (Phase 6.1)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f">>> Saved plot -> {out_png}")


def print_report(rates_hz, response_hz, criterion_hz):
    step_lo = float(np.min(np.diff(rates_hz))) if len(rates_hz) > 1 else float("nan")
    print(f"\n=== Rheobase table (NEST 3.9)  criterion = {criterion_hz:.0f} Hz, "
          f"interpolated, finest grid step = {step_lo:.0f} Hz ===")
    for label, resp in response_hz.items():
        rh = rheobase_rate(rates_hz, resp, criterion_hz)
        print(f"  {label:12s} rheobase = {rh:7.1f} Hz   max = {resp.max():6.1f} Hz")

    # Criterion ladder: shows whether the MC separation is criterion-dependent,
    # which a single-criterion check cannot distinguish from "no separation".
    print("\n=== MC_HIGH / MC_LOW separation vs criterion ===")
    print(f"  {'crit(Hz)':>9s} {'mc_low':>9s} {'mc_high':>9s} {'ratio':>8s}")
    for c in CRITERIA_HZ:
        r_low  = rheobase_rate(rates_hz, response_hz["mc_low"],  c)
        r_high = rheobase_rate(rates_hz, response_hz["mc_high"], c)
        ratio  = (r_high / r_low
                  if (r_low and not np.isnan(r_low) and not np.isnan(r_high))
                  else float("nan"))
        mark = "  <-- criterion" if abs(c - criterion_hz) < 1e-9 else ""
        print(f"  {c:9.0f} {r_low:9.1f} {r_high:9.1f} {ratio:8.2f}{mark}")

    print("  (ratios above are biased toward 1.0 by the criterion itself; the "
          "verdict below\n   uses the criterion-free extrapolated threshold.)")

    # Primary, criterion-free metric.
    print("\n=== Extrapolated threshold (linear fit -> zero response) ===")
    thr = {}
    for label, resp in response_hz.items():
        t, gain, n_fit = threshold_by_extrapolation(rates_hz, resp)
        thr[label] = t
        print(f"  {label:12s} threshold = {t:7.1f} Hz   gain = {gain:6.4f} "
              f"Hz/Hz   ({n_fit} fit pts)")

    t_low, t_high = thr.get("mc_low"), thr.get("mc_high")
    if (t_low and not np.isnan(t_low) and t_high and not np.isnan(t_high)):
        ratio = t_high / t_low
        lo = MC_RATIO_TARGET * (1.0 - MC_RATIO_TOL)
        hi = MC_RATIO_TARGET * (1.0 + MC_RATIO_TOL)
        print(f"\n  MC_HIGH / MC_LOW threshold ratio = {ratio:.2f}x  "
              f"(target {MC_RATIO_TARGET:.1f}x, accept {lo:.1f}-{hi:.1f}x)")
        if not (lo <= ratio <= hi):
            print("  [FLAG] ratio outside +/-20% of target -- re-tune I_e for "
                  "MC_HIGH before Phase 6.2 (see izh_calibrate.py numpy sweep "
                  "for the search procedure).")
            if abs(ratio - 1.0) < 0.05:
                print("  [FLAG] ratio ~1.0 -- check the sweep resolved threshold "
                      "at all (see the floored-grid warning below).")
        else:
            print("  [OK] within tolerance -- parameters confirmed for Phase 6.2.")
    else:
        print("\n  [FLAG] threshold fit failed for MC_LOW and/or MC_HIGH -- too "
              "few points in the 5-60 Hz output band, or the fit extrapolates "
              "outside the swept range. Lower --fine-rate-step (and/or raise "
              "--fine-rate-max) and rerun; no verdict on the 5.0x target is "
              "possible from this sweep.")


def check_grid_resolves_criterion(rates_hz, response_hz, criterion_hz):
    """Warn when the sweep cannot measure the criterion it was asked to measure.

    This is the failure mode of the 2026-07-22 run: every population was already
    above the 2 Hz criterion at the first non-zero swept rate, so all four
    rheobases floored to that rate and the ratio came out as exactly 1.0.
    """
    floored = [label for label, resp in response_hz.items()
               if len(resp) > 1 and resp[1] >= criterion_hz]
    if floored:
        first_rate = rates_hz[1] if len(rates_hz) > 1 else float("nan")
        print(f"\n>>> [WARNING] {', '.join(floored)} already exceed the "
              f"{criterion_hz:.0f} Hz criterion at the first swept rate "
              f"({first_rate:.0f} Hz). Their rheobase is floored by the grid, "
              f"not measured. Reduce --fine-rate-step -- do NOT raise "
              f"--criterion-hz, which biases the MC ratio further toward 1.0.")
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DG-CA3 extension Phase 6.1: NEST 3.9 f-I calibration for "
                    "PPGC/HGC, DG_BASKET, MC_LOW, MC_HIGH")
    parser.add_argument("--threads", type=int, default=None,
                         help="OpenMP threads (default: $OMP_NUM_THREADS or 4)")
    parser.add_argument("--sim-ms", type=float, default=3000.0,
                         help="Simulation duration per condition, ms (default: 3000)")
    parser.add_argument("--n-repeats", type=int, default=8,
                         help="Independent neurons per (population, rate) condition (default: 8)")
    parser.add_argument("--rate-max", type=float, default=6200.0,
                         help="Max swept drive rate, Hz (default: 6200)")
    parser.add_argument("--rate-step", type=float, default=200.0,
                         help="Coarse drive-rate sweep step above --fine-rate-max, Hz (default: 200)")
    parser.add_argument("--fine-rate-max", type=float, default=800.0,
                         help="Upper bound of the fine (threshold-resolving) grid, Hz "
                              "(default: 800; set 0 to disable and use a uniform sweep)")
    parser.add_argument("--fine-rate-step", type=float, default=20.0,
                         help="Step within the fine grid, Hz (default: 20)")
    parser.add_argument("--weight", type=float, default=20.0,
                         help="Synaptic weight of the Poisson probe (default: 20.0)")
    parser.add_argument("--delay", type=float, default=1.0,
                         help="Synaptic delay, ms (default: 1.0)")
    parser.add_argument("--criterion-hz", type=float, default=2.0,
                         help="Rheobase criterion: first output rate to sustain, Hz "
                              "(default: 2.0). Diagnostic only -- the [OK]/[FLAG] "
                              "verdict uses the criterion-free extrapolated "
                              "threshold, since criterion-based ratios are biased "
                              "toward 1.0.")
    parser.add_argument("--out-hdf5", type=str, default=None, metavar="FILE",
                         help="Path for output HDF5 file. If omitted, written to "
                              "calibration_output/dg_ca3_fi_calib.h5")
    parser.add_argument("--no-figures", action="store_true",
                         help="Skip PNG figure generation (data-only run)")
    args = parser.parse_args()

    n_threads = (args.threads if args.threads is not None
                 else int(os.environ.get("OMP_NUM_THREADS", 4)))

    rates_hz = build_rate_grid(args.fine_rate_max, args.fine_rate_step,
                                args.rate_max, args.rate_step)

    print(">>> Running DG-CA3 f-I calibration sweep in NEST 3.9 ...")
    print(f"    threads={n_threads}  sim_ms={args.sim_ms}  n_repeats={args.n_repeats}")
    if args.fine_rate_max > 0:
        print(f"    fine   0..{args.fine_rate_max:.0f}Hz step {args.fine_rate_step:.0f}Hz")
        print(f"    coarse {args.fine_rate_max:.0f}..{args.rate_max:.0f}Hz "
              f"step {args.rate_step:.0f}Hz")
    else:
        print(f"    uniform 0..{args.rate_max:.0f}Hz step {args.rate_step:.0f}Hz")
    print(f"    {len(rates_hz)} rate conditions x {len(CANDIDATE_PARAMS)} populations "
          f"x {args.n_repeats} repeats = "
          f"{len(rates_hz) * len(CANDIDATE_PARAMS) * args.n_repeats} neurons")

    response_hz, raw_spikes = run_fi_sweep(
        rates_hz, args.weight, args.delay, args.sim_ms, args.n_repeats, n_threads)

    print_report(rates_hz, response_hz, args.criterion_hz)
    check_grid_resolves_criterion(rates_hz, response_hz, args.criterion_hz)

    out_dir  = os.path.join(_script_dir, "calibration_output")
    os.makedirs(out_dir, exist_ok=True)
    hdf5_path = args.out_hdf5 if args.out_hdf5 else os.path.join(out_dir, "dg_ca3_fi_calib.h5")

    save_calibration_hdf5(hdf5_path, rates_hz, response_hz, raw_spikes,
                          args.weight, args.delay, args.sim_ms, args.n_repeats,
                          args.criterion_hz)

    if not args.no_figures:
        plot_calibration(rates_hz, response_hz, args.criterion_hz,
                         os.path.join(out_dir, "nest_fi_calibration.png"),
                         fine_max=args.fine_rate_max)
    else:
        print(">>> Figure generation skipped (--no-figures). "
              "Plot locally from the HDF5 with your own script.")
