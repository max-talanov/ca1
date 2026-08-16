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
chips.

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