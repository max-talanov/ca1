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


def rheobase_rate(rates, response, criterion_hz):
    idx = np.where(response >= criterion_hz)[0]
    return float(rates[idx[0]]) if len(idx) else float("nan")


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
    /<population>/
        attrs: a, b, c, d, I_e, rheobase_hz, max_response_hz
        response_hz      mean output rate per swept rate [n_rates] (float32)
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

        for label, params in CANDIDATE_PARAMS.items():
            g = h5.create_group(label)
            for k, v in params.items():
                g.attrs[k] = v
            rh  = rheobase_rate(rates_hz, response_hz[label], criterion_hz)
            g.attrs["rheobase_hz"]     = rh
            g.attrs["max_response_hz"] = float(response_hz[label].max())

            g.create_dataset("response_hz",
                              data=response_hz[label].astype(np.float32))
            g.create_dataset("spk_times",   data=raw_spikes[label]["times"],   **compress)
            g.create_dataset("spk_senders", data=raw_spikes[label]["senders"], **compress)
            g.create_dataset("spk_rate_idx", data=raw_spikes[label]["rate_idx"], **compress)

        # cross-population summary, mirrors the console [OK]/[FLAG] check
        r_low  = h5["mc_low"].attrs["rheobase_hz"]
        r_high = h5["mc_high"].attrs["rheobase_hz"]
        if r_low and not np.isnan(r_low) and r_high and not np.isnan(r_high):
            h5.attrs["mc_high_low_ratio"] = float(r_high / r_low)

    print(f">>> Saved calibration data -> {outpath}")


def plot_calibration(rates_hz, response_hz, criterion_hz, out_png):
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = {"ppgc_hgc": "seagreen", "dg_basket": "mediumorchid",
              "mc_low": "steelblue", "mc_high": "firebrick"}
    for label, resp in response_hz.items():
        rh = rheobase_rate(rates_hz, resp, criterion_hz)
        ax.plot(rates_hz, resp, lw=1.8, color=colors[label],
                label=f"{label} (rheobase@{criterion_hz:.0f}Hz = {rh:.0f} Hz)")
        if not np.isnan(rh):
            ax.axvline(rh, color=colors[label], ls="--", lw=0.8, alpha=0.6)
    ax.set_xlabel("Poisson drive rate (Hz), one-to-one")
    ax.set_ylabel("Output firing rate (Hz)")
    ax.set_title("DG-CA3 extension: NEST 3.9 f-I confirmation (Phase 6.1)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f">>> Saved plot -> {out_png}")


def print_report(rates_hz, response_hz, criterion_hz):
    print("\n=== Rheobase table (NEST 3.9) ===")
    for label, resp in response_hz.items():
        rh = rheobase_rate(rates_hz, resp, criterion_hz)
        print(f"  {label:12s} rheobase = {rh:7.1f} Hz   max = {resp.max():6.1f} Hz")

    r_low  = rheobase_rate(rates_hz, response_hz["mc_low"],  criterion_hz)
    r_high = rheobase_rate(rates_hz, response_hz["mc_high"], criterion_hz)
    if r_low and not np.isnan(r_low) and r_high and not np.isnan(r_high):
        ratio = r_high / r_low
        print(f"\n  MC_HIGH / MC_LOW ratio = {ratio:.2f}x  (target 5.0x)")
        if not (4.0 <= ratio <= 6.0):
            print("  [FLAG] ratio outside +/-20% of target -- re-tune I_e for "
                  "MC_HIGH before Phase 6.2 (see izh_calibrate.py numpy sweep "
                  "for the search procedure).")
        else:
            print("  [OK] within tolerance -- parameters confirmed for Phase 6.2.")


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
                         help="Drive-rate sweep step, Hz (default: 200)")
    parser.add_argument("--weight", type=float, default=20.0,
                         help="Synaptic weight of the Poisson probe (default: 20.0)")
    parser.add_argument("--delay", type=float, default=1.0,
                         help="Synaptic delay, ms (default: 1.0)")
    parser.add_argument("--criterion-hz", type=float, default=2.0,
                         help="Rheobase criterion: first output rate to sustain, Hz (default: 2.0)")
    parser.add_argument("--out-hdf5", type=str, default=None, metavar="FILE",
                         help="Path for output HDF5 file. If omitted, written to "
                              "calibration_output/dg_ca3_fi_calib.h5")
    parser.add_argument("--no-figures", action="store_true",
                         help="Skip PNG figure generation (data-only run)")
    args = parser.parse_args()

    n_threads = (args.threads if args.threads is not None
                 else int(os.environ.get("OMP_NUM_THREADS", 4)))

    rates_hz = np.arange(0, args.rate_max + args.rate_step, args.rate_step)

    print(">>> Running DG-CA3 f-I calibration sweep in NEST 3.9 ...")
    print(f"    threads={n_threads}  sim_ms={args.sim_ms}  n_repeats={args.n_repeats}  "
          f"rates=0..{args.rate_max:.0f}Hz step {args.rate_step:.0f}Hz")

    response_hz, raw_spikes = run_fi_sweep(
        rates_hz, args.weight, args.delay, args.sim_ms, args.n_repeats, n_threads)

    print_report(rates_hz, response_hz, args.criterion_hz)

    out_dir  = os.path.join(_script_dir, "calibration_output")
    os.makedirs(out_dir, exist_ok=True)
    hdf5_path = args.out_hdf5 if args.out_hdf5 else os.path.join(out_dir, "dg_ca3_fi_calib.h5")

    save_calibration_hdf5(hdf5_path, rates_hz, response_hz, raw_spikes,
                          args.weight, args.delay, args.sim_ms, args.n_repeats,
                          args.criterion_hz)

    if not args.no_figures:
        plot_calibration(rates_hz, response_hz, args.criterion_hz,
                         os.path.join(out_dir, "nest_fi_calibration.png"))
    else:
        print(">>> Figure generation skipped (--no-figures). "
              "Plot locally from the HDF5 with your own script.")
