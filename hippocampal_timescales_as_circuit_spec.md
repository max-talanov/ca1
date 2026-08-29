# Hippocampal Timescales as a Circuit Specification


## 1. The timescales, compressed

Learning in this system runs on eight processes spanning nine orders of magnitude, from a single receptor gating event to a memory trace redistributing across cortex over months. What matters for hardware is not the molecular detail of each stage but three facts: which stages are fast enough to force analog/continuous-time circuitry, which are slow enough that a clocked digital design is free, and where the biological threshold behavior maps directly onto a specific circuit primitive.

![Eight consolidation stages plotted on one logarithmic time axis from 1 ms to 10 years — bar position marks onset, length marks characteristic duration, and stages visibly overlap rather than handing off in strict sequence.](timescale_axis.png)

*Fig. 1 — All eight consolidation stages on one log time axis. Full molecular detail (receptor subunits, kinase cascades, transcription factors) is in the companion consolidation-timescales document; what carries over to the hardware discussion below is just the numbers.*

| Stage | Time constant | What it forces on a circuit |
|---|---|---|
| Neurotransmission (AMPA/NMDA gating) | ~0.5–5 ms | Sets the fastest timescale in the whole system — the floor for any front-end comparator bandwidth. |
| Short-term plasticity | ~10 ms–1 s | NMDAR's slower deactivation is *why* a ±20 ms coincidence window exists at all — a real biophysical constant, not a modeling convenience. |
| Ca²⁺/kinase cascades | ~1 s–5 min | The "weight update decision" happens on this timescale; anything reading it out only needs to sample in the low-second range. |
| AMPAR trafficking / early-LTP | ~1–30 min, decays over 1–3 hr | A real, decaying analog state — this *is* the tag described below. |
| Synaptic tagging & capture | tag set in 1–2 min, decays τ≈1–4 hr | The pivot point: a local, transient, decaying signal that is either captured or lost — directly analogous to a volatile-memristor relaxation state (§2). |
| Transcription / late-LTP | onset ~30–60 min, stable by ~4–8 hr | Once captured, this state should stop decaying — a discrete regime change, not a continuous process. |
| Sharp-wave-ripple replay | ripple 100–300 ms, recurs over hours–days | Compressed replay packs sequence elements only a few milliseconds apart — this is the number that actually sizes circuit timing budgets in §4 of the companion hardware document (`neuron_model_optimization.md`). |
| Systems consolidation | days–weeks (rodent) to months–years (human) | Fully clocked-digital territory; no continuous-time requirement whatsoever. |

## 2. Tag decay and capture: a directly testable hardware analogy

The synaptic tagging-and-capture (STC) mechanism described in the hippocampal plasticity literature has a clean circuit reading: a tag is set by coincident activity, decays with a fixed time constant if nothing happens, and is *captured* — converted to a stable, non-decaying state — only if a separate signal (biologically, a plasticity-related-protein pool) crosses threshold before the tag decays. This is close to the operating description of a **volatile threshold-switching memristor**: a device that transitions to a low-resistance state on a triggering pulse and spontaneously relaxes back over an intrinsic retention time — unless something latches it into a non-volatile state first.

![Synaptic weight versus successive sharp-wave-ripple events. Before event 4 the weight jumps and partly decays each cycle. At event 4 the plasticity-related-protein pool crosses threshold, decay stops, and weight climbs in a clean staircase — normal capture. A dashed counterfactual trace shows the same jumps but with capture blocked: weight oscillates at a flat baseline and never consolidates.](weight_consolidation.png)

*Fig. 2 — The tag-decay/capture dynamic, and the falsification test it implies. Both traces receive identical STDP-driven jumps per event (replay quality is unaffected either way); they diverge only in whether the tag gets captured before it decays.*

The dashed trace is the predicted signature if capture is blocked entirely: the weight distribution should stay flat while replay quality (measured independently) stays unchanged — a clean separation of the replay mechanism from the consolidation mechanism. That separation is also, functionally, the experiment you'd want to run on a candidate memristive tagging device: drive it with the same input statistics, and check whether blocking "capture" produces the same flat, non-accumulating signature.

This section describes the tag's *time-domain* behavior — when it is set, how it decays, whether it is captured. §4.2 below extends it along a second, independent axis — the tag's *amplitude* — once the dendritic pipeline gives that amplitude somewhere to come from.

## 3. The dendritic-convolution pipeline: what's cheap and what's hard in silicon

![Reference circuit topology for the 
dendritic-convolution pipeline: per-synapse 
threshold units feed a two-level hierarchy of 
OR-gated refractory junctions (each level with 
its own 5–10 ms τ_rf), converging on a soma 
that also receives a direct, dendritic-bypass inhibitory input, followed by a fixed-delay axon stage.](dendritic_convolution.png)

The companion hardware document frames dendritic processing as a three-stage information-reduction pipeline — a postsynaptic threshold, an OR-gated refractory junction, and a somatic summation — each stage a candidate site for replacing an expensive analog circuit with a cheap thresholding one.

### 3.1 The approach: stage-by-stage feasibility verdict

| Stage | Circuit primitive | Feasibility | Main open risk |
|---|---|---|---|
| Postsynaptic threshold (dSpike) | Memristor + local comparator | High — prototype-ready | Conductance drift shifting the threshold near the decision boundary |
| Junction (OR + refractory) | Wired-OR + edge-catcher + counter FSM, or a volatile memristor | High | Volatile-memristor relaxation-time variability, if used in place of a digital counter |
| Synaptic clustering | Non-uniform crossbar floorplan / reconfigurable interconnect | Moderate — the binding constraint | Needs 3D memristive/CMOS integration to be biologically faithful; not yet a mature foundry process |
| Somatic E/I summation | Differential integrate-and-fire | High — already standard (Loihi, BrainScaleS, TrueNorth-class cores) | None specific to this proposal |

Three of four stages are close to off-the-shelf. The interesting one — both because it's the hardest and because it's where the biology and the device physics line up most directly — is the junction/tag stage, which is worth its own figure.

## 4. Implementation

This section turns the approach in §3.1 into something buildable: a block-by-block reading of the reference topology, an extension that gives stage 1 a graded rather than purely boolean output, and a concrete materials candidate already under test for the tag/capture element itself.

### 4.1 Reading the reference topology

The figure above is not schematic shorthand — it is the specific two-cluster instance the rest of this section refers to, and it is worth reading block by block.

**Excitatory side.** `Cluster1` groups six excitatory synapses (`ex_syn0`…`ex_syn4`, `ex_synN`); `Cluster2` groups three more (`ex_syn0`, `ex_syn1`, `ex_synN`) — two independent dendritic segments, sized differently, which is itself a statement that the pipeline does not assume uniform fan-in per branch. Every excitatory synapse feeds its own per-synapse `thr` unit in the leftmost, **1 ms** column — the stage-1 postsynaptic threshold from the table above, instantiated once per synapse, not shared. Within `Cluster1`, two of the six threshold outputs (`ex_syn2`, `ex_syn3`) are drawn joining on a short local wire before entering the junction; the other four converge on the same junction along separate wires. This is a wiring-topology detail, not a functional one — all six thresholded outputs feed the same first-tier junction, which is a plain wired-OR (§4.2 of the companion document): the diagram's local pairing of two wires versus four individual ones has no effect on the OR's logic, only on layout.

**Two-level junction hierarchy.** Each cluster's thresholded outputs converge on its *own* first-tier `junction th/rp`, in the first **5–10 ms** column — one junction instance per cluster, each carrying an independently-settable `τ_rf` in that range. Both first-tier junctions' outputs then converge on a single second-tier `junction th/rp`, in the second **5–10 ms** column. This is the "reusable leaf cell" point made elsewhere in the companion document made visually explicit: the same `th/rp` primitive appears three times in the excitatory path (twice at tier 1, once at tier 2) with identical internal structure and independently tunable timing, and the worst-case synapse-to-soma latency contributed by this hierarchy is on the order of two stacked `τ_rf` periods — roughly 10–20 ms for 5–10 ms per level — not one.

**Inhibitory bypass.** `Cluster3` (`in_syn0`, `in_syn1`, `in_synN`) connects directly to the `Soma th/rp` block with a single wire each, passing through no `thr` unit and no junction at all. This is the diagram's explicit statement that fast, proximal/perisomatic inhibition is architecturally exempt from the threshold-and-refractory pipeline that every excitatory input must pass through — consistent with basket-cell-type inhibition acting close to the soma rather than being integrated dendritically.

**Somatic stage and output.** The second-tier junction's output and `Cluster3`'s direct inhibitory lines both arrive at `Soma th/rp`, which is the same threshold-plus-refractory primitive again, just with a different fan-in, a different threshold, and (presumably) a different `τ_rf`, implementing the differential E/I summation from the feasibility table. Its output feeds a final `axon delay` block, drawn as a separate stage outside the soma and outside all `τ_rf`-scale circuitry — a fixed propagation delay applied only after the somatic decision has already been made, decoupling millisecond-scale dendritic computation from simple downstream routing latency.

### 4.2 Extending stage 1: a graded synaptic-potential state per segment (`V_seg`)

Every `thr` unit described above reduces its segment's synaptic drive to a single bit the instant it crosses threshold; nothing about the graded depolarization *before* that crossing survives into the junction hierarchy or into the tag/capture mechanism of §2. That is a real gap, not just a simplification: NMDA-receptor conductance is itself voltage-dependent (the Mg²⁺-block relief follows a steep, roughly sigmoidal function of local depolarization — the Jahr & Stevens 1990 unblock curve is the standard reference form), so the calcium influx that actually drives the tag-setting kinase cascade in §2 scales continuously with subthreshold depolarization, not with a single all-or-nothing spike event. Voltage-based plasticity models built on this fact — most explicitly Clopath, Büsing, Vasilaki & Gerstner (*Nat. Neurosci.* 13:344–352, 2010) — make plasticity magnitude a continuous function of postsynaptic voltage rather than of spike timing alone, and it is the same mechanistic content behind the older calcium-control hypothesis (Lisman 1989; Shouval, Bear & Cooper 2002): induction strength, not just induction occurrence, sets the outcome.

The minimum addition that closes this gap is one continuous state per dendritic segment (i.e., per `thr` unit in the diagram above, not per synapse and not per junction):

```
τ_v · dV_seg/dt = −V_seg + Σ_i w_i · s_i(t)
```

a leaky integration of the segment's synaptic input, carried *alongside* — not instead of — the existing boolean `thr` output, with `τ_v` in the same 10–30 ms range already assigned to short-term plasticity in §1's table. A sigmoid gain `g_Ca(V_seg) = 1/(1 + K·exp(−λ·V_seg))`, patterned on the NMDAR unblock curve but fit rather than copied, converts `V_seg` into a tag-induction amplitude: `tag_amplitude ∝ g_Ca(V_seg) · [dSpike fired]`. This changes nothing about §2's time-domain claims — `τ_tag`, the PRP-threshold capture gate, and the flat-weight-distribution falsification test all stand unmodified — it only makes the tag's *initial height* graded by how depolarized the segment was at induction, instead of fixed.

Two consequences follow directly from the diagram above. First, because `V_seg` is shared across all synapses on one segment (e.g. all six of `Cluster1`), several individually subthreshold synapses can jointly drive `V_seg` into the steep part of `g_Ca` without any of them — or their shared `thr` unit — ever firing a dSpike, giving the clustering argument in the feasibility table a mechanistic channel (voltage-dependent cooperativity) in addition to its wiring-based one. Second, this is implementable as one added analog block per `thr` unit — a shared leaky-integrator capacitor plus a differential-pair sigmoid stage, both standard sub-threshold-CMOS neuromorphic primitives — driving a graded-amplitude SET pulse into the same volatile threshold-switching memristor already proposed as the tag element in §2, rather than a fixed-height one. The one new open risk this introduces is empirical: whether that memristor's SET response is graded enough, over a wide enough pulse-amplitude range, to carry a useful dynamic range of tag amplitudes — a device-characterization question of the same kind already flagged for `τ_rf` variability in the junction table, just measured along the amplitude axis instead of the timing axis. It also predicts a companion falsification test to the one in §2: dose-dependent partial NMDAR blockade (reducing `g_Ca(V_seg)` without eliminating dSpike firing) should shrink captured-weight step size continuously, rather than switching captured synapses to uncaptured all-or-nothing — a quantitatively distinct, and separately checkable, signature.

### 4.3 A physical candidate for the tag element: polycrystalline copper-aspirinate memristors

Both stages above are stated at the level of circuit primitives, deliberately agnostic to the device technology. Caus, Sławek, Mazur, Zawal, Baś, Szaciłowski, Talanov & Abdi (2026, "The memristive implementation of the hippocampus: a hypothesis") report one concrete candidate for the volatile threshold-switching memristor proposed as the tag element in §2, built and electrically tested rather than only simulated. The material is polycrystalline copper(II) bis-aspirinate, [Cu₂(asp)₄], spin-coated as a thin layer on ITO and capped with a sputtered copper electrode; three axially-ligated derivatives — [Cu₂(asp)₄(py)₂] (pyridine), [Cu₂(asp)₄(bimi)₂] (benzimidazole), and [Cu₂(asp)₄(DABCO)₂] — were prepared from the same parent complex by adding an axial N-donor ligand. All but the DABCO derivative show pinched I–V hysteresis loops under cyclic voltammetry — the standard electrical signature of memristive switching — and the axial ligand acts as a single tuning parameter on two properties at once: conductivity (the pyridine and benzimidazole derivatives conduct roughly two orders of magnitude more than the unligated parent) and, more relevantly here, retention. In chronoamperometric retention testing, the unligated parent's low-resistance state decayed back to the high-resistance state within about 50 minutes — a volatile device — while the benzimidazole derivative's high- and low-resistance states were both still stable, essentially noise-free, after 6 hours — effectively non-volatile on the timescale of the experiment.

That volatile-versus-latched split, produced by changing only the axial ligand on one underlying complex, brackets the `τ_tag ≈ 1–4 hr` range in §1's table and lands on the two states the tag/capture analogy in §2 needs: a device that relaxes back on its own (parent complex, minutes-scale retention) and a device that, once switched, holds (benzimidazole derivative, hours-plus retention) — which is a materials-level demonstration of "tag decays unless captured," rather than only a circuit-level one. It does not, on its own, demonstrate the graded-amplitude SET behavior §4.2's `V_seg` extension would need (the paper's I–V and retention data characterize switching and retention, not conductance-step-versus-pulse-amplitude curves), so that remains the specific open device-characterization question flagged above. The same paper's separate methylammonium-lead-iodide perovskite devices, modified with graphene oxide, fullerenol (C₆₀(OH)), or multiwalled carbon nanotubes, show measurable STDP-like potentiation directly in the memristive response — a second, independent materials route toward stage-1's threshold-plus-plasticity behavior, alongside a random-junction stochastic-network framing (percolating Ag–Ag₂S and SWNT/Por-POM meshes) the same paper proposes as a physical analogue for the probabilistic, disordered connectivity in the clustering stage.

---

*Full technical detail: [Consolidation Cascade](https://claude.ai/code/artifact/f879468e-00e8-4ca1-9acc-348b12cc7e33) (molecular timescales) and `neuron_model_optimization.md` (hardware feasibility).*