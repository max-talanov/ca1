# tinyHippo — results summary

A bio-plausible spiking model of the rat hippocampus (NEST 3.9, Izhikevich
neurons) demonstrating **memory consolidation through bidirectional replay and
sharp-wave ripples** across the full entorhinal–hippocampal loop.

```
EC LII → DG → CA3 → CA1 → EC LII/LV → mPFC
   ↑                            │
   └────────────────────────────┘
```

Scales 1 % → 100 % of the rat hippocampus from one code path
([`replay_scaled.py`](replay_scaled.py)); 12 % ≈ 101 k neurons on MareNostrum 5.

![overview](figures/consolidation_overview.png)

---

## 1. Bidirectional replay

Forward and reverse sequence replay during SWRs, scored as Spearman ρ between
CA3 sequence-group index and mean spike time.

| scale | ρ forward | ρ reverse |
|---|---|---|
| 12 % (+ real DG, consolidating) | **+0.613** (p<0.001) | **−0.789** (p<0.001) |
| 1 % full stack | +0.782 (p=0.008) | −0.794 (p=0.006) |

Both directions pass the ±0.5 criterion **while consolidation is running** —
the two are not in tension.

> **Correction to an earlier conclusion.** Reverse replay previously appeared
> incompatible with consolidation (ρ_rev ≈ −0.03). That was a scoring-window
> artifact: `replay_score()` was called with `(swr_start−5, swr_stop+30)`, and
> the +30 ms tail reaches into the post-SWR rebound where the strong forward
> chain re-ignites a *forward*-propagating burst. That rebound shares the
> forward ordering (so forward was unaffected) but cancels the reverse ordering.
> Re-scoring the archived runs on the SWR window itself recovers reverse replay
> everywhere, including runs from months earlier:
>
> | run | ρ_rev padded | ρ_rev SWR-window |
> |---|---|---|
> | 12 % STC (May) | −0.035 | −0.437 |
> | 25 % STC+LV+mPFC (May) | −0.033 | −0.512 |
> | 12 % + DG (Aug) | −0.094 | **−0.789** |
>
> ρ_fwd is essentially unchanged (+0.622 → +0.613), confirming a one-sided
> distortion. Fixed at all three call sites.

## 2. Synaptic tagging and capture

CA1→EC LII synapses carry STDP-derived tags; a per-EC-neuron PRP pool
accumulates one unit per SWR activation; L-LTP is captured where PRP crosses
threshold **and** a tag is still alive (Frey & Morris 1997).

At 12 %, 28 SWR events: tagging is immediate, the PRP pool builds linearly, and
L-LTP stays at zero until **event 15**, then rises sharply to **98 %** of the
612 k CA1→EC synapses. Mean weight 1.01 → 1.50. The threshold-then-jump shape
is the tag-and-capture signature, not gradual drift.

## 3. Memory consolidation

Consolidation is driven by replay: EC LII fires during SWRs, the PRP pool
builds, and tagged synapses are captured into L-LTP. With the real DG in the
loop the full cortical stack is active (EC LII 6.1 Hz, EC LV 13.0 Hz, mPFC
5.7 Hz) and the consolidation curve matches the pre-DG reference (600 250 vs
600 247 L-LTP synapses).

**Replay ⊥ consolidation.** Blocking L-LTP capture (`--prp-threshold 999`)
leaves replay quality identical (Δρ_fwd = 0.000) while cortical consolidation
goes to zero — the two mechanisms are dissociable in the same model
([`figures/final_comparison_fig9.png`](figures/final_comparison_fig9.png)).

## 4. Dentate gyrus — pattern separation

Real granule cells, two mossy-cell classes and basket feedback replace the
former Poisson proxy; CA3 is driven through mossy-fibre detonator synapses
(low in-degree, high weight).

- Granule active fraction **2.1 % per SWR window** at 12 % (target 2–4 %).
- MC_HIGH / MC_LOW DC-rheobase ratio **4.97×** vs the 5.0× Kassab & Alexandre
  target, confirmed on MN5 (`I_e = −15.1`; the original −9.0 gave only 3.25×).

Rheobase must be measured by **DC current injection**, not Poisson drive: at
weight 20.0 a single EPSP equals the granule cell's entire 20 mV
rest→threshold gap, so the cell relays rather than integrates.

## 5. CA3 — pattern completion

A partial cue of a stored assembly is restored by the recurrent collaterals.

![pattern completion](replay_output_1pct/pattern_completion.png)

| cue | intact | ablated (`sup_local=0`) |
|---|---|---|
| 10 % | 0.01 | 0.00 |
| 30 % | 0.50 | 0.00 |
| 50 % | 0.92 | 0.00 |
| 70 % | 1.00 | 0.00 |

Sharp attractor threshold ≈ 30 % cue; the ablated control is flat at zero with
cue recall still 1.0, proving the collaterals — not the cue — do the work
(Marr 1971; Nakazawa et al. 2002). The probe needs CA3 primed to a
sharp-wave-like state and a local E/I rebalance; the replay-tuned CA3 is
inhibition-dominated and is not an autonomous attractor without it.

---

## 6. Cortical association build-up (EC LV → mPFC)

A replay-gated Hebbian hook potentiates EC LV→mPFC synapses when an SWR
co-activates both ends, with weak heterosynaptic depression when the target
fires without the source. mPFC also has a k-winners-take-all interneuron loop
(pyramidal → FS → pyramidal), mirroring the DG.

**The association builds, but it is not yet an engram.** Weights grow steadily
(1.00 → 1.10 over 12 replay events at 1 %), but every synapse moves together:
the final weight distribution has a **single unique value**, CV = 0.0000.

The cause is upstream of mPFC, so lateral inhibition cannot fix it. EC LV fires
**all-or-nothing** per SWR window — 600/600 cells or 0/600 — so every mPFC cell
receives identical drive and the winners-take-all loop has no differences to
amplify. mPFC correspondingly fires 120/120 or 0/120. A genuine engram needs
pattern-specific activity to survive the CA1→EC→mPFC path so that different
replayed sequences recruit different cortical subsets.

> An earlier version of this section reported "37.5 % of synapses associated"
> as evidence of a selective engram. That was wrong: `frac_associated` compares
> uniform weights against a threshold that moves with event count, so it can
> report an apparent fraction while every synapse is identical. Weight CV is
> the honest test and is now what the report and HDF5 record.

## 7. Pattern discrimination — why the engram needs a temporal code

An engram is only meaningful with more than one thing to remember: "selective"
means selective for A rather than B. `--n-patterns P` splits the CA3 sequence
groups into P interleaved assemblies, each replayed in its own epochs, making
downstream selectivity measurable for the first time.

**Cortex does not discriminate the patterns.** Jaccard overlap of the active-cell
set, within-pattern (same pattern, different epochs) vs between-pattern:

| population | active | within | between | separation |
|---|---|---|---|---|
| CA3 SUP | 98.3 % | 0.968 | 0.967 | 0.001 |
| CA1 PYR | 49.3 % | 0.290 | 0.288 | 0.002 |
| EC LII | 46.9 % | 0.145 | 0.202 | −0.057 |
| EC LV | 71.0 % | 0.507 | 0.478 | 0.028 |
| mPFC | 86.1 % | 0.117 | 0.226 | −0.110 |

**But the patterns are strongly encoded in CA3 — in spike timing.** Correlating
the per-group *activation-time* profile across epochs, versus the per-group
*active-cell-count* profile:

| code | within | between | separation |
|---|---|---|---|
| **timing** (when each group fires) | **+0.954** | **−0.114** | **+1.069** |
| identity (how many cells fire) | +0.745 | +0.242 | +0.503 |

Timing discriminates the two patterns almost perfectly and ~2× better than
identity. The same conclusion follows from the replay score itself, which is a
timing measure (ρ = +0.72 / −0.55) and works fine.

So the information is present and temporal; what loses it is the readout. Every
projection in the model uses a **single scalar delay** (`d_fast=1.5`,
`d_slow=3.0`, `delay_ca1_ec=3.0`, `delay_lv_mpfc=8.0`), so all spikes arrive
simultaneously and timing carries nothing downstream — and the association hook
is a window-coincidence rule, which is blind to timing by construction.

This is the empirical case for a **polychronization**-style temporal code
(Izhikevich 2006): per-synapse delay heterogeneity plus STDP, so that a
polychronous group — a directed graph of (neuron, delay) edges — becomes the
carrier of pattern identity. It also motivates the cheaper complement: sparser,
more topographic Schaffer connectivity so identity survives CA3→CA1.

## 8. Phase C step 1 — delay heterogeneity alone is not sufficient

`--delay-jitter MS` gives each synapse on the feedforward readout projections
(Schaffer, CA1→EC LII/LV, EC LII→LV, EC LV→mPFC) its own delay, drawn uniformly
around the projection's base value. The CA3 sequence chain and EC LV→CA3
feedback stay scalar: those delays are load-bearing for replay *generation*, so
jittering them would perturb the thing being measured.

Controlled test at 1 %, 2 patterns × 4 replays (12 within-pattern pairs).
`--delay-jitter-wcomp` scales the jittered weights, because spreading arrival
times reduces coincident summation and lowers downstream rates — a confound
that has to be controlled rather than ignored.

| condition | CA3 | CA1 | EC LII | EC LV | mPFC |
|---|---|---|---|---|---|
| base, jitter 0 | **+0.200** | −0.057 | −0.033 | +0.052 | −0.037 |
| jitter 4 ms, w×1.0 | **+0.210** | +0.032 | −0.024 | −0.060 | — |
| jitter 4 ms, w×1.5 | **+0.206** | +0.001 | +0.025 | −0.014 | +0.032 |

(timing separation = within-pattern minus between-pattern correlation)

CA3 is unchanged across all three (+0.200 / +0.210 / +0.206), confirming the
manipulation is correctly targeted — replay generation is untouched. But no
condition produces downstream discrimination: every cortical value sits in
±0.06, i.e. noise.

The rate confound is **bracketed** rather than exactly matched: w×1.0 leaves
cortex at 87–89 % of baseline and w×1.5 overshoots to 128–163 %. Since the two
straddle 100 % and neither shows the effect, the negative result holds across a
±60 % range of cortical firing rate and is not a rate artifact.

This is the expected outcome from polychronization theory: in Izhikevich (2006)
it is **STDP that selects delay-matched paths**. Heterogeneous delays are the
substrate; without a mechanism that potentiates the delay-matched combinations,
jitter only smears arrival times. Delays are necessary but not sufficient —
so the informative next experiment is delays **plus** STDP, not delays alone.

## Open items

- **Cortical selectivity → temporal code.** Pattern identity is carried in CA3
  spike timing but every projection uses a single fixed delay, so it cannot
  propagate (§7). Next step: per-synapse delay heterogeneity + STDP on the
  cortical projections (polychronization), and/or sparser Schaffer
  connectivity.
- **Ripple background is still epoch-0 only.** The replay drive (trigger +
  staggered scaffold) now repeats every epoch, so epochs 1…*n*−1 do contain
  real replay. The sharp-wave/ripple *background* does not: repeating it needs
  ~16 k `sinusoidal_poisson_generator`s per window (one per neuron across
  CA3+CA1), and NEST steps every generator at every timestep regardless of its
  start/stop — at 6 epochs that is ~211 k generators and a 1 % run had not
  finished after 3 h. Doing it cheaply needs
  `inhomogeneous_poisson_generator` (one node, scheduled rate profile).
- **EC LII→DG loop gain** is set by synchrony, not mean rate: EC fires in
  SWR-locked bursts, so K·w must stay well under the 20 mV granule
  rest→threshold gap or the loop saturates DG. Validated at 1 %; 12 % pending.

## Reproducing

```bash
# 1% test: replay + DG, ~1 min
python replay_scaled.py --scale 1 --dg --dg-scale 2 --no-figures

# full stack with consolidation
python replay_scaled.py --scale 1 --dg --ec-lii --stc --ec-lv --mpfc --n-swr 6

# CA3 pattern completion (intact vs ablated)
python replay_scaled.py --scale 1 --pattern-completion

# figures from any output
python plot_consolidation_figure.py --in <file.h5>
python plot_pattern_completion.py  --in <pattern_completion.h5>
```

On MareNostrum 5 (see [`run.sh`](run.sh)):

```bash
sbatch --export=ALL,SCALE=12,DG=1,N_SWR=14 run.sh
```
