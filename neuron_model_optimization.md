# Dendritic Convolution: Optimization Principles for Electronic Spiking Neural Networks

## 0. Scope and framing

This note extends the original *Dendritic convolution* draft into a structured
account of how the dendritic-tree processing observed in the Associative
Cortex (AC) and Hippocampal system (HS) can be read as a three-stage
information-reduction (convolution) pipeline, and it closes with a feasibility
assessment of implementing that pipeline in electronic — specifically
memristive/CMOS mixed-signal — spiking neural network (SNN) hardware, in the
context of the tinyHippo project's NEST-based CA3/CA1 model.

The word "convolution" is used here in its information-theoretic sense — a
progressive folding-down of a high-dimensional input space onto a
lower-dimensional decision variable — rather than in the discrete-signal-
processing sense (sliding kernel). Each of the three stages below performs
one such folding step, and each step is a candidate site for hardware
optimization because each step is where information is *deliberately
discarded*, i.e. where a cheaper circuit can, in principle, replace an
expensive one without loss relative to the biological baseline.

## 1. First-level convolution: the postsynaptic dendritic spike

Neurotransmitter release at an excitatory synapse depolarizes the local
postsynaptic membrane in proportion to the synaptic weight `W`. When that
local depolarization crosses a threshold, a dendritic spike (dSpike) is
triggered locally, independent of the soma.

This is a **thresholding, weight-to-boolean convolution**: a graded,
analogue quantity (`W` × presynaptic activity) is compressed to a single bit
(dSpike fired / not fired) at the site of the synapse, well before the
signal reaches the soma. Two consequences follow that matter for hardware
design:

1. The nonlinearity is *local and per-branch*, not global and per-neuron —
   each dendritic segment behaves as an independent thresholding unit with
   its own operating point, rather than the whole neuron collapsing to a
   single soma-level threshold.
2. Because the compression happens at the synapse, all downstream circuitry
   (junction, soma) only ever has to process binary dendritic-spike events,
   not analogue synaptic currents. This is the first and largest point of
   potential savings for an electronic implementation: replacing an
   analogue multiply-accumulate at every synapse with a local
   compare-to-threshold operation whose output is a single wire.

### 1.1 Neuromodulation of the synaptic weight

`W` in the description above should not be read as a fixed, purely
Hebbian-set parameter. In the biological system it is under continuous,
time-varying gain control by ascending neuromodulatory afferents, and this
gain control is a principal mechanism by which memory consolidation and
temporal (state- and salience-dependent) weight update are implemented on
top of, and largely independently of, spike-timing-dependent plasticity
(STDP) itself:

- **Dopamine (DA)** — acting largely through D1/D2-class receptors — gates
  the transition from early- to late-phase potentiation. In the
  synaptic-tagging-and-capture (STC) framework this project already uses
  for CA1→EC consolidation, DA is the most direct biological analogue of
  the plasticity-related-protein (PRP) capture signal: a synapse can be
  tagged by coincident pre/post activity, but whether that tag is
  *captured* into a stable weight change is conditioned on a
  DA-dependent permissive signal, closely mirroring the `PRP_threshold`
  gate in the existing consolidation model.
- **Serotonin (5-HT)** modulates the sign and threshold of plasticity at
  many hippocampal and cortical synapses, and interacts with network
  excitability/inhibition balance, effectively shifting where the stage-1
  threshold sits without touching `W` directly.
- **Noradrenaline (NA)**, released under arousal and novelty, transiently
  raises gain and lowers the effective threshold for potentiation,
  consistent with its role in prioritizing salient or unexpected input for
  consolidation — a time-locked, arousal-gated multiplier on the
  otherwise activity-only weight update.
- **Acetylcholine (ACh)** shifts the hippocampal circuit between
  encoding-favoring and consolidation/replay-favoring regimes (high ACh
  during active exploration suppresses recurrent/feedback transmission and
  favors afferent-driven encoding; low ACh during quiet wakefulness and
  slow-wave sleep favors the recurrent replay this project's SWR
  simulations model), and thereby indirectly gates *when* stage-1
  thresholding is allowed to translate into lasting weight change.
- **Oxytocin (Oxt)** modulates interneuron excitability and social/
  salience-tagged plasticity in hippocampal and related circuits, acting
  as a further context-dependent multiplier on effective synaptic gain
  for specific classes of input.

Functionally, each of these neuromodulators acts on a slower timescale
than the millisecond-scale dSpike threshold crossing itself, so the
correct way to model their effect at stage 1 is as a **multiplicative,
slowly-varying gain term on `W`** (or, equivalently, a slow shift of the
local threshold), rather than as an additional fast synaptic input. This
distinction matters for the network-level claim of §0: it means the
"convolution" performed by the dendritic spike is not applied to a static
weight but to a weight that itself carries a second, slower time constant
set by neuromodulatory tone — which is exactly the mechanism needed to
implement selective, state-dependent memory consolidation without
requiring every synapse to be re-evaluated by STDP timing alone.

**Optimization idea.** Implement each synapse as a two-terminal memristive
element whose conductance encodes `W`, feeding a local comparator (or a
sub-threshold CMOS integrate-and-fire node) shared by a small cluster of
synapses on the same dendritic segment. The memristor removes the need for a
digital weight register and a digital multiplier; the comparator removes the
need to route an analogue current any further than the segment boundary.
This converts an O(N) analogue fan-in problem into an O(N) local threshold
problem followed by an O(1) digital wire per segment — a substantial
reduction in wiring and in analogue-to-digital conversion (ADC) load, which
is typically the dominant area and power cost in mixed-signal neuromorphic
chips. Neuromodulation can be added to this circuit cheaply because it is
slow: rather than a per-synapse fast input, a small number of global or
regional bias lines (one per modeled neuromodulator, analogous to DA, 5-HT,
NA, ACh and Oxt) can modulate either the memristor's write-enable
threshold (gating whether a coincidence-driven SET/RESET pulse is allowed
to change the stored conductance — the direct hardware analogue of tag
capture) or the comparator's reference voltage (shifting the effective
stage-1 threshold). Both mechanisms reuse existing circuit elements and
add only a handful of shared analogue bias wires per dendritic region,
rather than new circuitry per synapse.

## 2. Second-level convolution: the dendritic junction as a temporal winner-take-all gate

A dendritic junction — the point where several dendritic branches converge
onto a parent branch or the soma — passes through only the *first* dSpike
that arrives, and then blocks further spikes from sibling branches for the
duration of that first spike's refractory period.

This is a **first-past-the-post, time-domain convolution**: among several
branches that convolved their own inputs to a boolean value in stage 1, the
junction convolves *those* booleans down to a single winning branch,
selected purely by arrival time. Two things follow:

1. The junction performs sparsification "for free," using only relative
   timing rather than an explicit comparison-of-magnitudes circuit. This is
   cheaper than a conventional winner-take-all (WTA) network, which normally
   requires lateral inhibition wired across all competing units.
2. Because the criterion is temporal precedence, not amplitude, the
   junction is intrinsically compatible with spike-timing-dependent
   information coding: whichever input arrived because it was most strongly
   or most reliably driven (highest `W`, most correlated presynaptic burst)
   tends to win, so amplitude information is implicitly translated into
   latency and preserved through the gate even though the gate itself only
   ever looks at *order*.

**Optimization idea.** A junction can be realized as a monostable
(refractory) latch per dendritic node: the first incoming digital dSpike
edge sets the latch, the latch output enables a fixed-width refractory
timer, and any dSpike arriving inside that window is simply discarded by
gating it against the latch state. This is a few-transistor digital circuit
per junction (one flip-flop, one timer), dramatically cheaper than an
analogue lateral-inhibition WTA circuit of the classical Lazzaro/Mead type,
at the cost of encoding competition in time rather than in current
amplitude. The trade-off is worth stating precisely: analogue WTA circuits
give a continuous, graded notion of "winning margin," while the
refractory-junction implementation gives a binary winner with no margin
information — this is a deliberate loss of information that mirrors the
biological original and should be treated as a modeling choice, not an
implementation artifact.

### 2.1 Clustering of synapses

Synapses onto a given neuron are not distributed at random across the
dendritic tree; morphologically, inputs that originate from correlated or
functionally related sources terminate closer together on the tree. Two
functional consequences follow directly from stages 1 and 2 above:

- Co-clustered synapses share a dendritic segment and therefore share a
  stage-1 threshold and a stage-2 junction, so correlated sources are
  convolved together more effectively than uncorrelated ones — the
  morphology itself implements a similarity-based grouping prior, before
  any learning occurs.
- Channels judged more important (by whatever developmental or activity-
  dependent criterion the biological system applies) are allocated a larger
  number of parallel projections into AC/HS, i.e. importance is encoded as
  redundancy of wiring, not as a larger weight on a single wire.

**Optimization idea.** In a crossbar-based memristive implementation, this
maps onto *deliberate non-uniform crossbar topology*: rather than a fully
connected, uniform crossbar where every input reaches every neuron with
equal wire length and equal fan-out, correlated input channels should be
routed to physically adjacent rows/columns feeding a shared local
comparator group, and important channels should be given multiple physical
memristive rows rather than one row of larger conductance. This is a
routing/floorplanning optimization more than a device-level one, and it is
the stage most constrained by fabrication (interconnect layers, crossbar
tiling), discussed further in §4.

## 3. Third-level convolution: somatic integration

The soma integrates the surviving dendritic-junction outputs together with
direct inhibitory synaptic input, and collapses the entire tree's activity
to exactly two scalar influences: net excitatory drive and net inhibitory
drive, whose difference (or ratio, depending on the modeling convention)
determines whether and when the neuron fires.

This is the **final and most aggressive convolution** in the pipeline: an
arbitrarily large dendritic tree, already reduced at stages 1 and 2, is now
reduced to two numbers. The biological cost of this aggressiveness is real —
over-compression at the soma is a plausible route to a non-functional or
pathologically synchronized network — so the soma's operating point
represents an explicit compromise between compression efficiency and the
minimum information the network needs to remain functionally expressive.

**Optimization idea.** Electronically, this argues for a two-line summing
bus per neuron (one excitatory accumulation node, one inhibitory
accumulation node) rather than per-synapse digital readout, with the
final excitatory/inhibitory comparison performed by a single differential
integrate-and-fire circuit. This is already close to how most neuromorphic
silicon neurons are built (Loihi, BrainScaleS, TrueNorth-style cores);
the contribution of the dendritic-convolution framing is to justify, from a
biological first-principles argument, *why* the two-line reduction is not
merely a hardware simplification but a computationally load-bearing
feature of the original system — which in turn argues against adding
additional somatic input channels (e.g. neuromodulatory third and fourth
lines) purely for hardware convenience without checking whether they change
network-level dynamics.

## 4. Feasibility analysis of an electronic dendritic-convolution SNN

The following assesses, stage by stage, how far current (as of this
writing) electronic device and circuit technology can realize the pipeline
above, and where the open problems are.

### 4.1 Stage 1 (synapse + local threshold): high feasibility

Two-terminal memristive devices (RRAM/HfOx, PCM, and related resistive
switching technologies) that store an analogue or multi-level conductance
and are read out by a local CMOS comparator or leaky-integrate-and-fire
node are a mature research area with working silicon demonstrations at
kilo- to mega-synapse scale. This stage is the closest to off-the-shelf:
crossbar arrays with per-row or per-column threshold circuits are routinely
fabricated in academic and some commercial neuromorphic prototypes. The
main open engineering issues are device-level, not architectural:

- **Conductance drift and cycle-to-cycle variability** in RRAM/PCM devices
  (typically single-digit to tens-of-percent variation depending on
  technology and write scheme) directly perturbs the effective dendritic
  threshold, which — because stage 1 is a hard threshold, not a graded
  readout — can flip a "spike"/"no spike" decision near the boundary. This
  is more consequential here than in a conventional analogue
  multiply-accumulate crossbar, where small conductance errors merely
  perturb a continuous sum. Threshold circuits sitting on top of memristive
  weights therefore need either wider design margins or periodic
  recalibration, both of which cost area or energy.
- **Endurance** (write-cycle lifetime) matters only insofar as the design
  intends on-chip learning (weight updates via SET/RESET pulses); a
  fixed-weight, inference-only realization of stage 1 is not endurance-
  limited.

Verdict: feasible today at prototype scale (hundreds to low thousands of
synapses per die); production-scale reliability engineering (drift
compensation, per-cell calibration) is incremental, not fundamental,
research.

### 4.2 Stage 2 (junction / refractory winner-take-all): moderate feasibility

The refractory-latch implementation proposed in §2 is circuit-trivial in
digital CMOS (a set-reset latch plus a one-shot timer is a handful of
transistors) and there is no serious feasibility obstacle to building it.
The open questions are architectural rather than device-level:

- **Fan-in topology.** Biological dendritic trees have a branching junction
  structure (many small local junctions feeding progressively fewer, larger
  junctions toward the soma). Replicating a multi-level junction hierarchy
  in silicon means routing binary dSpike wires through several logic levels
  per neuron rather than a single flat OR/priority gate, which multiplies
  the per-neuron logic footprint roughly linearly with the number of
  hierarchy levels chosen. A shallow (one- or two-level) approximation is
  cheap; a biologically faithful multi-level tree is a larger but still
  bounded digital design problem, well within reach of a standard-cell ASIC
  flow.
- **Refractory window matching.** The refractory period must be tuned
  relative to the expected inter-spike arrival jitter of competing
  branches; too short a window fails to suppress legitimate late arrivals
  from the same event, too long a window under-utilizes the junction's
  temporal bandwidth. This is a parameter-tuning problem addressable by
  simulation (e.g., against the tinyHippo NEST model's own inter-group
  timing, which in the SWR replay experiments already documented in
  `bidirectional_replay.py` runs on a millisecond scale — ~3.8 ms between
  sequence groups at 10% network scale), not an open research question.

Verdict: feasible with a straightforward digital design; the work is in
tuning the hierarchy depth and refractory constants against a target
biological timing regime rather than in inventing new devices.

### 4.3 Clustering / topology-aware routing: the binding constraint

This is the stage most likely to determine whether the overall architecture
is practical at scale. A crossbar array is, by construction, a uniform,
fully connected fabric: every row reaches every column with comparable wire
length. Deliberately clustering correlated inputs onto shared local
segments, and giving important channels redundant physical rows, works
against that uniformity and requires either:

- non-uniform, application-specific floorplanning at design time (feasible
  for a fixed, known input structure such as a specific hippocampal
  circuit model, but not reconfigurable after fabrication), or
- a reconfigurable interconnect fabric (programmable switch matrix between
  crossbar tiles) that can be set up post-fabrication to approximate
  whatever clustering the trained/biological model calls for, at the cost
  of extra silicon area and extra parasitic capacitance on every
  reconfigurable link.

Both are demonstrated techniques individually (application-specific
neuromorphic ASICs use the former; FPGA-style programmable interconnect is
the latter), but combining fine-grained, dendrite-level clustering with a
dense memristive synapse array is closer to a monolithic 3D integration
problem (multiple tiers of memristive crossbars and CMOS logic stacked and
connected by dense through-silicon vias) than to a 2D chip layout problem.
Monolithic 3D memristive/CMOS stacks exist as research demonstrations but
are not yet a mature, foundry-available process the way 2D RRAM crossbars
are.

Verdict: feasible in principle, but this is the stage where the proposal
goes from "engineering" to "applied research." A 2D approximation
(coarse, design-time clustering fixed at fabrication) is achievable now; a
fully general, dendrite-faithful clustering fabric is a 3–5 year hardware
research horizon at the time of writing, contingent on continued progress
in 3D memristive integration.

### 4.4 Stage 3 (somatic two-line summation): high feasibility

This is architecturally the least novel part of the proposal — differential
excitatory/inhibitory integrate-and-fire somas are already standard in
existing neuromorphic silicon (Loihi/Loihi 2, BrainScaleS, TrueNorth-class
designs). The contribution of this framing is conceptual (justifying the
two-line reduction from a biological information-budget argument) rather
than requiring new circuitry.

Verdict: fully feasible with existing, deployed circuit techniques.

### 4.5 System-level assessment

| Stage | Core electronic primitive | Feasibility | Dominant risk |
|---|---|---|---|
| Postsynaptic dSpike | Memristor + local comparator | High (prototype-ready) | Conductance drift shifting the threshold |
| Junction / refractory WTA | Digital latch + one-shot timer | High–moderate | Hierarchy depth vs. logic footprint trade-off |
| Synaptic clustering | Non-uniform crossbar floorplan / reconfigurable interconnect | Moderate | Requires 3D or application-specific fabric to be biologically faithful |
| Somatic E/I summation | Differential integrate-and-fire | High (already standard) | None specific to this proposal |

The net argument for building this pipeline in hardware, rather than a
conventional flat SNN core, is a *wiring and conversion* argument: stages 1
and 2 convert what would otherwise be a large analogue fan-in per neuron
into a small number of digital dSpike wires before any ADC is needed, which
is where a conventional dense crossbar chip spends most of its area and
power budget. The clustering stage is what actually captures the wiring
savings implied by that reduction, which is precisely why it is also the
hardest stage to realize faithfully — the benefit and the difficulty are
the same feature. A pragmatic path for the tinyHippo project is therefore
to validate stages 1–2 first (they map directly onto operations the
existing NEST model already performs numerically — thresholded dendritic
nonlinearity and a timing-gated update analogous to the tag-and-capture STC
mechanism already used for CA1→EC consolidation), and to treat stage-2.1
clustering as a design-time, application-specific floorplan rather than a
general reconfigurable fabric until 3D memristive integration matures
further. This keeps the electronic implementation question tractable while
still testing the network-level hypothesis — that dendrite-level
convolution reduces the information reaching the soma without collapsing
the network into non-functional over-simplification — that motivates the
whole proposal.

## 5. Continuous time as the gap between a pure digital solution and the proposed approach

Every implementation choice discussed in §§1–4 is compatible, in principle,
with a purely synchronous digital realization: quantize time into fixed
ticks, represent `W` as a multi-bit register, evaluate the stage-1
threshold once per tick, resolve the stage-2 junction with a clocked
priority encoder, and accumulate stage-3 sums in a digital adder. This is,
in fact, how most existing digital neuromorphic silicon (Loihi/Loihi 2,
TrueNorth-class cores) and the tinyHippo NEST simulation itself already
operate — NEST's default solver advances the network in fixed simulation
steps (commonly sub-millisecond, e.g. 0.1 ms) and evaluates neuron and
synapse dynamics at those steps rather than continuously. It is worth
being explicit about what is lost by that choice, because it is precisely
the gap that a continuous-time, event-driven analog or mixed-signal
realization of the dendritic-convolution pipeline is proposed to close.

### 5.1 What "continuous time" means for each stage

- **Stage 1 (threshold crossing).** The dendritic spike is triggered at
  the instant the membrane potential crosses threshold, a continuous,
  real-valued event time. A clocked digital evaluator only observes the
  membrane state at tick boundaries, so the reported crossing time is
  quantized to the tick period `Δt` and carries an expected timing error
  of up to `Δt`/2. Sub-threshold CMOS or translinear analog circuits
  (the classical Mead-style neuromorphic approach) instead implement the
  membrane state as a genuinely continuous voltage or current governed by
  an RC-like differential equation, and the comparator fires
  asynchronously, exactly when threshold is crossed, with a hardware
  latency set by transistor bandwidth (typically nanoseconds to low
  microseconds) rather than by a simulation tick.
- **Stage 2 (junction arbitration).** The "first spike wins" rule is only
  meaningful if the hardware can actually resolve which of several
  candidate spikes arrived first. In continuous time this is a
  well-posed question with probability zero of an exact tie (for
  independent, continuously distributed arrival times). Under a
  fixed-tick digital clock, two dSpikes that cross threshold within the
  same tick are indistinguishable in arrival order and require an
  arbitrary tie-breaking rule (e.g., fixed priority by row address),
  which silently and systematically biases which branch "wins" — a
  digitally-induced artifact with no biological counterpart. The finer
  the tick, the rarer this collision, but it is never eliminated by
  clocking alone; a genuinely asynchronous, self-timed (clockless)
  arbitration circuit — of the kind already used in TrueNorth's
  asynchronous crossbar fabric or in classical mutual-exclusion (metastability-
  resolving) arbiter circuits — removes the artifact by construction.
- **Stage 3 (somatic integration).** The excitatory/inhibitory balance is
  integrated over a leak time constant that is itself continuous; how
  finely a digital implementation must sample it depends on how fast that
  time constant is relative to `Δt`. This stage is the least sensitive of
  the three, because summation is a linear, low-pass operation that
  tolerates modest time-quantization without qualitative error — consistent
  with §4.4's assessment that stage 3 is already adequately served by
  existing digital/mixed-signal somatic circuits.

### 5.2 Quantifying the gap against the tinyHippo timing regime

The bidirectional-replay simulations already in this project provide a
concrete scale against which to size the required timing precision.
Sequence groups activate roughly 3.8 ms apart during an SWR at 10% network
scale, and the STDP window used for tagging is ±20 ms with a forward axonal
delay of about 3 ms. Two implications follow directly:

1. A digital tick coarser than roughly a few hundred microseconds begins
   to erode the ability to resolve which of two closely spaced sequence
   groups produced the earlier dendritic spike, which is exactly the
   ordering information the stage-2 junction is meant to preserve; a
   tick on the order of the 3.8 ms inter-group spacing (or coarser, as is
   typical of default 0.1–1 ms digital-SNN and NEST time steps once
   several tick periods of latency are added by synchronous pipeline
   stages) is adequate for network-level replay-order statistics (the
   Spearman-ρ metric already used to score replay quality) but is not
   adequate for preserving fine-grained relative timing *within* a single
   SWR event at the resolution the biological circuit appears to use.
2. The forward/reverse LTP/LTD asymmetry in the STC mechanism depends on
   the sign of a millisecond-scale timing difference (+3 ms vs. −3 ms).
   Any digital implementation whose effective tick or pipeline latency
   approaches that few-millisecond scale risks collapsing the sign
   distinction that separates consolidating from de-potentiating synapses
   — turning a designed asymmetry into noise.

In short: the network-level, statistical claims this project already
validates in simulation (replay quality, consolidation curves) are
tick-tolerant at typical digital-SNN/NEST time steps; the synapse- and
dendrite-level timing claims that motivate the dendritic-convolution
proposal in §§1–3 are not, and are the specific place where a purely
digital, clocked implementation departs furthest from the biological (and
simulated) target.

### 5.3 Cost side of the gap: why "just use a finer clock" is not free

Shrinking `Δt` to close the timing gap does not come for free in a
synchronous digital design: doubling clock frequency to halve `Δt`
roughly doubles dynamic switching power (power scales approximately
linearly with clock frequency in CMOS, all else equal) and requires every
neuron and synapse in the array to be re-evaluated on every tick whether
or not it has anything to do — an `O(N)` per-tick cost regardless of how
sparse the actual spiking activity is. This is the well-known
event-driven-vs-clocked trade-off in neuromorphic engineering: a clocked
digital design pays a fixed per-tick tax on the entire array to buy
timing resolution, while an asynchronous, continuous-time analog design
pays energy only when a threshold is actually crossed (current flows in a
comparator only around a transition) and its timing resolution is set by
device physics rather than by a clock budget. For a sparse hippocampal
replay-style workload — a small fraction of neurons active per SWR
event — this favors continuous-time, event-driven circuits on energy
grounds as well as on timing-fidelity grounds, which reinforces rather
than competes with the wiring-reduction argument made in §4.5.

### 5.4 What continuous time costs in return

The gap does not close for free on the analog side either, and it is
important to state the reciprocal cost precisely rather than treat
continuous-time analog circuits as a strictly dominant option:

- **No natural notion of a global "simulation state."** A clocked digital
  design can be paused, checkpointed, and stepped deterministically —
  useful for debugging and for reproducing the exact `bidirectional_replay.py`-
  style trace-by-trace comparisons this project already relies on.
  Continuous-time analog circuits are intrinsically real-time and
  free-running; extracting a reproducible, inspectable trace requires
  additional instrumentation (fast ADCs on monitored nodes) that
  reintroduces some of the sampling/quantization question the analog
  approach was meant to avoid, just moved to the measurement layer.
- **Device-level noise and drift are continuous too.** The same
  continuous physics that gives an analog comparator its sub-microsecond
  timing precision also lets thermal noise, flicker noise, and
  memristor conductance drift (§4.1) act continuously on the threshold,
  so timing precision in the abstract does not automatically translate
  into timing *accuracy* without calibration.
- **Verification and yield.** A digital tie-breaking rule, however
  biologically inexact, is at least fully specified and reproducible
  across chips; a self-timed arbiter's behavior near true coincidence is
  governed by circuit metastability, which is a well-understood but
  non-trivial design discipline (bounded, not eliminated, resolution
  time) and complicates functional verification relative to a
  synchronous design.

### 5.5 Recommended position

Given §§5.1–5.4, the pragmatic reading is that continuous time is not an
all-or-nothing architectural choice but a resource that should be spent
where the biological claim actually needs it. Stages 1 and 2 — where the
proposal's own argument rests on exact threshold-crossing time and
arrival order — are where a continuous-time, asynchronous analog or
mixed-signal front end earns its cost. Stage 3, and all network-level,
routing-layer logic (spike packet transport between neurons, the digital
bookkeeping already well served by existing crossbar/router architectures
in Loihi-class chips), can remain clocked digital without materially
weakening the timing claims of §§1–3, because summation over a leak time
constant is the one stage in this pipeline that is genuinely tolerant of
tick-scale quantization. This mixed strategy — continuous-time analog at
the synapse/dendrite boundary, clocked digital everywhere else — is also
the strategy already implicit in the feasibility ranking of §4.5 (stages 1
and 2 rated highest feasibility for custom analog/mixed-signal circuits;
stage 3 rated highest feasibility precisely because existing digital
somatic designs already suffice), so the continuous-time discussion in
this section sharpens, rather than revises, the conclusions reached there.