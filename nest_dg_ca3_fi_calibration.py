#!/usr/bin/env python3
"""
nest_dg_ca3_fi_calibration.py
==============================
NEST 3.9 confirmation of the DG-CA3 extension's single-neuron f-I
calibration (Phase 6.1). Run this on MN5 to confirm/replace the numbers
derived from the numpy Izhikevich stand-in (izh_calibrate.py) BEFORE
they are written into build_dg_ca3_network() (Phase 6.2).

Populations calibrated here:
  PPGC / HGC : RS granule cell     (a=0.02, b=0.2, c=-65, d=8,  I_e=0)
               -- same intrinsic type as existing pyr_params. HGC and
                  PPGC are given IDENTICAL intrinsic parameters: per
                  Kassab & Alexandre 2018, the PPGC/HGC distinction is
                  a connectivity/recruitment distinction (both are DG
                  granule cells), not an intrinsic-electrophysiology one.
  DG_BASKET  : FS interneuron       (a=0.10, b=0.2, c=-65, d=2,  I_e=0)
               -- reused verbatim from existing basket_params, no new
                  tuning needed for a fast feedback-inhibition role.
  MC_LOW     : RS + I_e=0.0        -- low-threshold mossy cell
  MC_HIGH    : RS + I_e=-9.0       -- high-threshold mossy cell

  MC_LOW/MC_HIGH tuned in the numpy stand-in to reproduce the ~5x
  low/high threshold separation implied by Kassab & Alexandre's own
  rate-model defaults (theta_l=0.1, theta_h=0.5 -> ratio 5.0). Confirm
  that ratio holds under NEST's actual solver before trusting it.

Requirements: NEST >= 3.9, numpy, matplotlib, scipy optional.
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import nest
from tiny import safe_set_seeds  # reuse existing seeding convention

CANDIDATE_PARAMS = {
    "PPGC_HGC":   dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "DG_BASKET":  dict(a=0.10, b=0.2,  c=-65.0, d=2.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "MC_LOW":     dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=0.0),
    "MC_HIGH":    dict(a=0.02, b=0.2,  c=-65.0, d=8.0, V_m=-65.0, U_m=-13.0, I_e=-9.0),
}

RATES_HZ   = np.arange(0, 6200, 200)
WEIGHT     = 20.0     # matches the numpy stand-in's working regime -- NOT a
                       # claim about final network weights, purely a probe value
DELAY      = 1.0
SIM_MS     = 3000.0
N_REPEATS  = 8
CRITERION_HZ = 2.0     # rheobase criterion: first rate reaching >=2 Hz output


def rheobase_rate(rates, response, criterion_hz=CRITERION_HZ):
    idx = np.where(response >= criterion_hz)[0]
    return rates[idx[0]] if len(idx) else np.nan


def run_fi_sweep():
    nest.ResetKernel()
    nest.SetKernelStatus({"resolution": 0.1, "local_num_threads": 4,
                           "print_time": False, "overwrite_files": True})
    safe_set_seeds()

    # Build every (population, rate) combination as N_REPEATS independent
    # neurons in ONE network -- avoids per-condition kernel resets.
    neuron_index = {}   # (label, rate) -> NodeCollection of N_REPEATS neurons
    spk_index    = {}   # (label, rate) -> spike_recorder

    for label, params in CANDIDATE_PARAMS.items():
        for rate in RATES_HZ:
            neurons = nest.Create("izhikevich", N_REPEATS, params=params)
            # independent Poisson realisations per repeat -> separate generators
            gens = nest.Create("poisson_generator", N_REPEATS,
                                params={"rate": float(rate)})
            nest.Connect(gens, neurons, conn_spec="one_to_one",
                         syn_spec={"weight": float(WEIGHT), "delay": DELAY})
            spk = nest.Create("spike_recorder")
            nest.Connect(neurons, spk)
            neuron_index[(label, rate)] = neurons
            spk_index[(label, rate)] = spk

    nest.Simulate(SIM_MS)

    results = {label: np.zeros(len(RATES_HZ)) for label in CANDIDATE_PARAMS}
    for label in CANDIDATE_PARAMS:
        for i, rate in enumerate(RATES_HZ):
            ev = nest.GetStatus(spk_index[(label, rate)], "events")[0]
            n_spikes = len(ev["times"])
            results[label][i] = n_spikes / (N_REPEATS * SIM_MS / 1000.0)

    return results


def plot_and_report(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = {"PPGC_HGC": "seagreen", "DG_BASKET": "mediumorchid",
              "MC_LOW": "steelblue", "MC_HIGH": "firebrick"}

    rheobases = {}
    for label, resp in results.items():
        rh = rheobase_rate(RATES_HZ, resp)
        rheobases[label] = rh
        ax.plot(RATES_HZ, resp, lw=1.8, color=colors[label],
                label=f"{label} (rheobase@{CRITERION_HZ:.0f}Hz = {rh:.0f} Hz)")
        if not np.isnan(rh):
            ax.axvline(rh, color=colors[label], ls="--", lw=0.8, alpha=0.6)

    ax.set_xlabel(f"Poisson drive rate (Hz), one-to-one, weight={WEIGHT:.0f}")
    ax.set_ylabel("Output firing rate (Hz)")
    ax.set_title("DG-CA3 extension: NEST 3.9 f-I confirmation (Phase 6.1)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    p = os.path.join(out_dir, "nest_fi_calibration.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)

    print("\n=== Rheobase table (NEST 3.9) ===")
    for label, rh in rheobases.items():
        print(f"  {label:12s} rheobase = {rh:7.1f} Hz   max = {results[label].max():6.1f} Hz")

    r_low, r_high = rheobases["MC_LOW"], rheobases["MC_HIGH"]
    if r_low and not np.isnan(r_low) and r_high and not np.isnan(r_high):
        ratio = r_high / r_low
        print(f"\n  MC_HIGH / MC_LOW ratio = {ratio:.2f}x  (target 5.0x)")
        if not (4.0 <= ratio <= 6.0):
            print("  [FLAG] ratio outside +/-20% of target -- re-tune I_e "
                  "for MC_HIGH before Phase 6.2 (see izh_calibrate.py numpy "
                  "sweep for the search procedure).")
        else:
            print("  [OK] within tolerance -- parameters confirmed for Phase 6.2.")
    print(f"\nSaved: {p}")


if __name__ == "__main__":
    print(">>> Running DG-CA3 f-I calibration sweep in NEST 3.9 ...")
    results = run_fi_sweep()
    out_dir = os.path.join(_script_dir, "calibration_output")
    plot_and_report(results, out_dir)
