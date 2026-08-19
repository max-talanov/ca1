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

## 9. Phase C step 2 — delay-aware STDP: **does not replicate**

Pair-based STDP on the Schaffer collateral using each synapse's **own** delay,
`dt = (t_post − t_pre) − delay_ij` — the polychronous selection rule, applied at
CA3→CA1 because that is where the signal still exists.

The **mechanism** demonstrably operates: Schaffer weight **CV rises
0.0008 → 0.0388** over 16 replay events, so synapses differentiate rather than
drift together.

A first run showed EC LV timing separation **+0.120**, surviving two static
controls that bracketed (and exceeded) its firing rates. That looked like a
controlled positive. **It does not survive replication.**

Three independent seeds (`--seed` sets both the NEST kernel RNG and the numpy
RNG; varying only one leaves runs partially identical):

| run | CA3 | CA1 | EC LII | EC LV | mPFC |
|---|---|---|---|---|---|
| original | 0.143 | 0.025 | 0.067 | **+0.120** | 0.048 |
| seed 101 | 0.159 | 0.021 | 0.012 | −0.037 | −0.035 |
| seed 202 | 0.171 | 0.018 | **0.556** | −0.029 | −0.002 |
| seed 303 | 0.195 | 0.046 | **0.135** | −0.006 | 0.042 |

EC LV across the three new seeds: mean **−0.024**, sd 0.016. The original
+0.120 sits ~9 sd above that — an outlier, not an effect.

Two further signs it is noise rather than signal:

- The population that "discriminates" **flips between runs**: CA3+EC LV, then
  CA3 only, then CA3+EC LII twice. A real effect lands on the same population
  each time.
- EC LII swings from 0.012 to 0.556 across seeds — a range no mechanism explains.

What *is* robust is the source: **CA3 timing separation 0.167 ± 0.022** across
all four runs. The encoding is real and reproducible; the downstream
transmission is not.

**Conclusion.** Delay heterogeneity alone does not carry the timing code to
cortex (§8), and delay-aware Schaffer STDP does not either. Polychronization
remains a plausible route — the substrate and the selection mechanism are now
both implemented and the mechanism verifiably runs — but at this scale, epoch
count and connectivity it produces no reproducible cortical discrimination.
Candidate next factors: far longer training (Izhikevich ran ~24 h simulated for
polychronous groups to form; these runs are 8 s), recurrent rather than
feedforward cortical targets, and larger populations.

## 10. Cortical sparsity, and a first readable Test 3 (PRELIMINARY)

Test 3 (hippocampal lesion -> cortical recall) was previously unaskable: mPFC
fired 120/120 cells, so there was no assembly to cue, and cortex had no
recurrent excitation to complete a pattern with. Three fixes, in order:

**Sparsity.** Cortical volleys were suprathreshold (CA1->EC LII at 2.5x), so
every cell fired ~1.5 ms before feedback inhibition could arbitrate. Rescaling
each stage to just below threshold AND adding `I_e` heterogeneity gives graded
recruitment. Both were needed: subthreshold volleys with uniform `I_e` fired
nobody, and `V_m` heterogeneity alone did nothing — every initial potential
relaxes to the same rest (−70), so V_m spread is a transient, not a standing
excitability difference.

| population | before | after |
|---|---|---|
| EC LII | 87.3 % | **9.5 %** |
| EC LV | 99.9 % | **62.5 %** |
| mPFC | 100 % | **9.8 %** |
| mPFC assembly | 120/120 | **23/120** |

**E/I balance.** mPFC interneurons were at 0.00 Hz, so the winners-take-all loop
was inert and halving its weight was a no-op (2.0 % -> 2.3 %). mPFC was
excitation-starved; raising EC LV->mPFC brought it to 9.8 % with `mpfc_int` at
0.29 Hz.

**Post-lesion priming.** After the lesion mPFC has no input at all, so the test
otherwise asks cortex to self-ignite from silence. A subthreshold tonic drive
holds cells near threshold; the pre-cue baseline is the guard that it is not
firing them itself.

Result at 1 %, 40 % cue of a 23-cell assembly, hippocampus lesioned:

| condition | completion | baseline |
|---|---|---|
| consolidated (plasticity on) | **0.214** | 0.000 |
| control (no plasticity) | 0.071 | 0.000 |
| priming 60 Hz (too weak) | 0.000 | 0.000 |

Directionally this is what systems consolidation predicts — 3x more recall when
the recurrent weights were shaped by replay, against a proper unconsolidated
control and a zero baseline.

**It is not yet evidence.** Those fractions are **3 cells versus 1 cell**, from a
single seed. Poisson noise on counts that small is comparable to the effect, and
this is the same profile as the EC LV result in §9 that failed to replicate
across three seeds. Cortex also still shows no pattern discrimination by
identity, so even a solid positive would show *an* assembly reactivating rather
than *a specific memory* transferring.

Settling it needs 12 % scale, where mPFC is 1440 cells and an assembly ~250, so
recovered counts are ~30 vs ~10 — measurable rather than anecdotal — plus
several seeds.

## 11. The sparsity retune at 12 % — consolidation becomes selective (Job F)

The cortical sparsity retune of §10 changed EC LII/LV and mPFC weights, `I_e`
heterogeneity and E/I balance, and had only ever been run at 1 %. Job F
(`res/2026-08-17/`, `SCALE=12 DG=1 N_PATTERNS=2 N_SWR=14`) is the sanity run at
12 %. The core holds:

| | pre-retune (08-05) | post-retune (08-17) |
|---|---|---|
| replay ρ_fwd / ρ_rev | +0.70 / −0.54 | **+0.63 / −0.66** (both p<0.001) |
| DG granule active per window | 2.16 % | 1.55 % fwd, 1.60 % rev |
| CA1 PYR | ~5 Hz | 4.82 Hz |
| mPFC | 5.73 Hz (302 Hz in 08-07) | **1.19 Hz** |
| EC LII | 6.12 Hz, 12005/12005 firing | 0.40 Hz, 1847/12005 firing |
| L-LTP | 98.0 % of synapses | **7.0 %** |

The L-LTP drop looks like a regression and is the opposite. In the dense regime
*every* EC cell fired in *every* SWR window, so the PRP pool was just an event
counter — `prp_mean` tracked the event index exactly, everything crossed the
threshold of 14 together at event 14, and the final weights had CV 0.003 pinned
at the ceiling. That is the same non-selective saturation that produced the
retracted "engram" claim, seen from the consolidation side.

With a sparse cortex only ~9 % of EC cells fire per window, PRP accumulates at
0.075/event on average, and the cells that cross are the ones that reliably
participate:

```
                consolidated (862 cells)   rest (11,143)
  final PRP           24.0                     0.0        threshold 14
  weight               0.486                   0.305      1.59x
```

862 of 12 005 EC cells (7.2 %) end up consolidated, weight CV 0.170 spread over
0.29–0.74 — a differentiated trace rather than a saturated one. Consolidation is
also **all-or-none per postsynaptic cell**: consolidated cells have ~49.9 of
their ~51 incoming synapses captured. That is what STC predicts, since the PRP
pool is somatic — and it is a property the dense regime could not have revealed.

So the sparsity retune did not cost consolidation; it made consolidation
selective. Whether that 7.2 % assembly is *pattern*-selective is Test 3, which
has not yet run at 12 % (see below).

### Job D timed out — in the lesion, not the simulation

Job D (Test 3 consolidated) hit the 20 h limit, so Job E was never started. The
simulation was not the problem: all 16 epochs finished in **10 758 s (3.0 h)**,
close to the estimate. It then spent >9 h inside `lesion_hippocampus()`, which
called `nest.GetConnections(source=CA1, target=EC)`. Filtering on `source` makes
NEST scan the entire kernel connection table — ~19 M synapses at 12 % once the
Schaffer STDP set exists. `build_ec_lii()` and `build_stc_hook()` both carry
comments warning about exactly this; the lesion path was written later and
missed it.

Fixed by reusing the connection handles the STC hook already fetched (cost zero)
and falling back to `GetConnections(target=)` with numpy source-filtering, which
touches only that population's incoming slots. No parameter changes are needed —
the run fits comfortably in 20 h once the scan is gone.

## 12. Test 3 at 12 % — cortical recall does not survive the lesion (Jobs D + E)

`res/2026-08-19/`, seed 101, 16 epochs, `SCHAFFER_K=200`, `DELAY_JITTER=4.0`.
Both jobs completed: the lesion that consumed >9 h in the previous attempt now
runs from cached handles, and the post-lesion probe window is present in both
outputs. The hippocampal side is bit-identical across D and E (ρ +0.632/−0.656,
L-LTP 10.1 %, DG 1.52 %), as it must be — `NO_MPFC_ASSOC` touches only the
cortical hook — so the comparison is properly controlled.

Recall reconstructed from the saved mPFC spikes (cue at 16 200 ms, 80 ms
scoring window, 40 % of the assembly cued, baseline 16 100–16 180 ms):

| | assembly | uncued | cue_recall | completion | baseline | net |
|---|---|---|---|---|---|---|
| D consolidated | 309 | 185 | 0.992 | 0.049 (9 cells) | 0.022 (4) | **+0.027** |
| E control | 303 | 182 | 1.000 | 0.016 (3 cells) | 0.005 (1) | **+0.011** |

**This is a negative result.** The `[OK]` criterion is 0.25, which at this
assembly size means ~46 of 185 uncued cells; D reactivated 9. Both runs miss it
by roughly an order of magnitude, so the gap is not a matter of statistical
power — cortex does not reconstruct the pattern once the hippocampus is cut.

D is directionally above E, 3x on the raw counts, matching the direction of the
1 % preliminary in §10. It does not survive testing: Fisher exact on 9/185 vs
3/182 gives **p = 0.140**, from a single seed. This is the same profile as the
EC LV effect in §9 that failed to replicate across three seeds, and it should
not be reported as an effect. D against its own pre-cue baseline is p = 0.020,
but that is 9 cells against an expected 4.

**Correction.** An earlier version of this section read the mechanism off the
HDF5 `mpfc_assoc` group, reporting that "the mPFC recurrent hook barely moved —
614 of 28 800 synapses at ceiling". That group is the **feedforward EC LV→mPFC**
projection (`K_eclv_mpfc` 20, `w_init` 1.8), not the recurrent one. The
recurrent hook runs but its weights were never written to the file, so those
numbers said nothing about the cortical attractor. The recurrent weights are now
exported as a separate `mpfc_recurrent` group. The Test 3 verdict above is
unaffected — it is computed from spikes.

What can be said without those weights is structural, and it is enough. The
recurrent projection is `K_rec = 20` random inputs per cell over N = 1440, so an
uncued assembly cell receives on average

    20 x 124/1440 = 1.72

inputs from the 124-cell cue. At the initial `w_rec` 0.9 that is ~1.5 mV against
a ~20 mV rest→threshold gap; even pinning every one of those synapses at a 2.4
ceiling reaches only ~4.1 mV. **Test 3 cannot pass at `K_rec = 20` however well
the learning works** — clearing threshold needs ~8 ceiling-weight inputs from
the cue, i.e. `K_rec` ≳ 97, and that already assumes synchronous arrival, which
does not hold (§10). Note this is the same `K x w` reasoning that misled the E/I
iteration, so treat it as an order-of-magnitude bound, not a prediction.

E/I balance is **not** the lever, despite the analogy to CA3 in §5. During the
post-cue window mPFC interneurons fire 6 of 288 cells at 0.26 Hz — there is
almost no inhibition to rebalance, the same trap that made an earlier attempt to
halve mPFC inhibition a no-op.

So the honest state of the loop: replay, separation, completion, tagging and
selective consolidation all work at 12 %, and the trace reaches cortex as
weights — but it is not yet strong enough to be *read out* without the
hippocampus, which is what systems consolidation requires.

## Open items

- **Cortical selectivity is unsolved.** Pattern identity is robustly encoded in
  CA3 spike timing (0.167 ± 0.022) but does not reach cortex. Neither delay
  heterogeneity (§8) nor delay-aware Schaffer STDP (§9) transmits it; the one
  apparent positive failed to replicate across three seeds. Untested factors:
  much longer training, recurrent cortical targets, larger scale.
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
