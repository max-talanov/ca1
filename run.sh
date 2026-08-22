#!/bin/bash -l
#SBATCH --job-name=HIPPO_NEST
#SBATCH --output=Nest_replay_%A_%a.slurmout
#SBATCH --error=Nest_replay_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --time=20:00:00
#SBATCH --partition=gp_bsccs

# Standard Phase 2+3 run (default)
#  sbatch --export=ALL,SCALE=12,N_SWR=14 run.sh

# Phase 3 only (no STC consolidation, fast run for testing the loop)
#  sbatch --export=ALL,SCALE=12,N_SWR=1,NO_STC=1 run.sh

# Phase 5 falsification with Phase 3
#  sbatch --export=ALL,SCALE=12,N_SWR=14,PRP_THRESHOLD=999 run.sh

# Phase 4 single-alpha homeostasis
#  sbatch --export=ALL,SCALE=25,N_SWR=14,PRP_THRESHOLD=3.5,HOMEOSTASIS=1,HOMEO_ALPHA=0.75 run.sh

# Phase 4 alpha-sweep (3 alphas in one job, ~5h vs ~15h for 3 separate jobs)
#  sbatch --export=ALL,SCALE=25,N_SWR=14,PRP_THRESHOLD=3.5,HOMEOSTASIS=1,ALPHA_SWEEP=0.50,0.75,0.90 run.sh

# ---- Phase 6.2 validation at 12% (three new capabilities) -------------------
# JOB A — bidirectional replay + DG pattern separation, no consolidation stack
#   (isolates the two so-far-1%-only results at scale; fastest, cleanest read)
#  sbatch --export=ALL,SCALE=12,DG=1,NO_STC=1,EC_LII=0,EC_LV=0,MPFC=0 run.sh
#
# JOB B — CA3 pattern completion probe (separate run mode; ignores STC/cortex)
#  sbatch --export=ALL,SCALE=12,PATTERN_COMPLETION=1 run.sh
#
# JOB C — full integrated stack WITH the real DG (run only after A+B look good)
#  sbatch --export=ALL,SCALE=12,DG=1,N_SWR=14 run.sh

# ---- Test 3 at 12% : hippocampus-independent cortical recall ---------------
# The 1% result (consolidated 0.214 vs control 0.071) is 3 cells vs 1 cell on
# one seed -- too small to trust. At 12% mPFC is 1440 cells and an assembly
# ~250, so recovered counts are ~30 vs ~10.
#
# JOB F — sanity after the cortical sparsity retune.  DONE, PASSED (2026-08-17):
#   replay +0.63/-0.66, DG 1.55%, mPFC 1.19 Hz, and consolidation is now
#   SELECTIVE (862/12005 EC cells, weight CV 0.17) instead of saturated at 98%.
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,N_SWR=14 run.sh
#
# JOB D — Test 3, consolidated (repeat for SEED=101,202,303)
#   The 2026-08-17 attempt hit the 20 h wall AFTER finishing all 16 epochs in
#   3.0 h: >9 h went into lesion_hippocampus()'s GetConnections(source=,target=),
#   a whole-kernel scan over ~19M synapses. Fixed (the lesion now reuses the STC
#   hook's handles), so these settings are unchanged and now fit in ~4 h.
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,TRAIN_PATTERN=0,N_SWR=16,\
#SCHAFFER_K=200,DELAY_JITTER=4.0,SCHAFFER_STDP=1,CORTICAL_RECALL=1,SEED=101 run.sh
#
# JOB E — Test 3 control, no cortical plasticity (same seeds as D)
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,TRAIN_PATTERN=0,N_SWR=16,\
#SCHAFFER_K=200,DELAY_JITTER=4.0,SCHAFFER_STDP=1,CORTICAL_RECALL=1,NO_MPFC_ASSOC=1,SEED=101 run.sh
#
# ---- JOB H : does heterogeneity make DG SELECTIVE? (the engram question) ----
# Background (RESULTS.md §13): the model has no engram because DG is sparse but
# NOT selective -- over 7 epochs replaying the SAME pattern, 83% of granule
# cells fire in exactly 1 of 7 windows and none in all 7. Cause: the only
# pattern-carrying input (EC LII perforant path) supplies 0.6% of granule drive,
# the other 99.4% being a Poisson residual resampled every window. Raising the
# perforant weight was blocked by a synchrony ceiling -- with scalar weights and
# delays a granule cell's K=50 inputs land in one instant, so K*w must stay
# under the 20 mV gap.
#
# --het gives every cell and every synapse a distribution, which lifts that
# ceiling. H1 tests heterogeneity alone; H2 additionally spends the headroom on
# the perforant path. Compare both against JOB F (homogeneous, same settings).
#
# NOT rate-matched: five attempts to calibrate --het-wcomp at 1% each uncovered
# a different failure mode, and the 1% homogeneous baseline cannot anchor the
# comparison anyway (rho_rev -0.079 there vs -0.656 at 12%). Read H1/H2 for
# whether DG becomes SELECTIVE, and treat rate differences as expected.
#
# JOB H1 — heterogeneity alone
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,N_SWR=14,HET=0.30,HET_WCOMP=2.3 run.sh
#
# JOB H2 — heterogeneity + perforant path through the door
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,N_SWR=14,HET=0.30,HET_WCOMP=2.3,\
#W_EC_DG=1.2,PP_RESIDUAL=0.5,DG_DELAY_JITTER=4.0 run.sh
#
# JOB H3 — H2 rerun after the DG background fix.  H1/H2 (2026-08-22) produced a
#   real CORE SET for the first time (64-69 granule cells firing in >=6/7
#   same-pattern windows, against 1 in the homogeneous model) but ZERO pattern
#   selectivity (Jaccard within-between -0.002). Cause: the compensated
#   mossy-cell background put DG baskets at 22.3 Hz and clamped granule cells to
#   0.45% active, so the perforant path could not influence WHICH cells fire --
#   H2's 8x perforant weight changed nothing. With GC clamped, the cells that
#   escape are the intrinsically most excitable ones, which is why the core set
#   is reproducible but identical across patterns (H1/H2 core overlap 32 cells
#   despite an 8x input difference). Now that no DG background drive is
#   compensated, DG should return to 2-4% and the perforant path gets a say.
#  sbatch --export=ALL,SCALE=12,DG=1,N_PATTERNS=2,N_SWR=14,HET=0.30,HET_WCOMP=2.3,\
#W_EC_DG=1.2,PP_RESIDUAL=0.5,DG_DELAY_JITTER=4.0,SEED=202 run.sh
#
# READ FIRST in both: DG active fraction must be 2-4%. If it is 0.00% the
# granule population has been extinguished by basket feedback (seen at 1% when
# the basket background drive was wrongly compensated) and nothing else in the
# run means anything. Then check whether granule cells develop a CORE SET --
# cells firing in >=6/7 same-pattern windows, versus 1 observed today.
#
# CHECK BEFORE BELIEVING ANY RECALL NUMBER: the printed pre-cue baseline must be
# ~0. If it is not, the priming is firing cells by itself and completion is
# meaningless -- lower CR_PRIME_RATE (120 works at 1%; 250 did not).

SCALE=${SCALE:-25}
EC_LII=${EC_LII:-1}     # 1=add EC LII/III cortical target (default on)
EC_LII_K=${EC_LII_K:-50}
N_SWR=${N_SWR:-14}
EPOCH_MS=${EPOCH_MS:-1000}
PRP_THRESHOLD=${PRP_THRESHOLD:-14.0}
EC_LV=${EC_LV:-1}      # 1=enable Phase 3 EC LV, 0=disable
MPFC=${MPFC:-1}         # 1=enable mPFC module, 0=disable
NO_STC=${NO_STC:-0}     # 1=skip STC hook (useful for Phase 3-only runs)
HOMEOSTASIS=${HOMEOSTASIS:-0}  # 1=enable Phase 4 synaptic homeostasis
HOMEO_ALPHA=${HOMEO_ALPHA:-0.75}  # downscaling factor (default 0.75)
ALPHA_SWEEP=${ALPHA_SWEEP:-}      # comma-sep list, e.g. "0.50,0.75,0.90"; overrides HOMEO_ALPHA
# ---- Phase 6.2 dentate gyrus + pattern completion ---------------------------
HET=${HET:-0}                  # model-wide heterogeneity CV: weights, delays AND
                               # per-cell a/b/c/d/I_e. 0 = the historical
                               # homogeneous model (every cell a copy).
HET_WCOMP=${HET_WCOMP:-1.0}    # excitatory-onto-principal weight scale, to offset
                               # the gain heterogeneity costs. NOT rate-matched at
                               # 12% -- see the JOB H notes in the header.
W_EC_DG=${W_EC_DG:-}           # perforant path EC LII->GC weight (default 0.15)
PP_RESIDUAL=${PP_RESIDUAL:-}   # scale on the Poisson stand-in drive to DG
DG_DELAY_JITTER=${DG_DELAY_JITTER:-}   # extra ms jitter on the DG pathway
DG=${DG:-0}                    # 1=add the real DG (Phase 6.2), replaces Poisson proxy
DG_SCALE=${DG_SCALE:-$SCALE}   # DG scale %; defaults to SCALE
PATTERN_COMPLETION=${PATTERN_COMPLETION:-0}  # 1=run the CA3 completion probe INSTEAD
PC_CUE_FRACS=${PC_CUE_FRACS:-0.1,0.2,0.3,0.5,0.7,1.0}
PC_CUE_WEIGHT=${PC_CUE_WEIGHT:-2.5}
# ---- multi-pattern / temporal-code / Test-3 knobs -------------------------
N_PATTERNS=${N_PATTERNS:-1}        # >1 splits CA3 groups into interleaved assemblies
TRAIN_PATTERN=${TRAIN_PATTERN:-}   # replay ONLY this pattern index (A-only vs B-only)
SEED=${SEED:-}                     # sets BOTH the NEST kernel and numpy seeds
SCHAFFER_K=${SCHAFFER_K:-}         # CA3->CA1 in-degree override (weights auto-scaled)
SCHAFFER_STDP=${SCHAFFER_STDP:-0}  # 1 = delay-aware STDP on CA3->CA1
DELAY_JITTER=${DELAY_JITTER:-0}    # per-synapse axonal delay jitter (ms)
NO_MPFC_ASSOC=${NO_MPFC_ASSOC:-0}  # 1 = no cortical plasticity (Test-3 control)
CORTICAL_RECALL=${CORTICAL_RECALL:-0}   # 1 = lesion + cue + measure (Test 3)
CR_CUE_FRAC=${CR_CUE_FRAC:-0.4}
CR_PRIME_RATE=${CR_PRIME_RATE:-120}     # keep subthreshold: baseline must stay ~0
CR_PRIME_WEIGHT=${CR_PRIME_WEIGHT:-1.0}
OUTDIR="results"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export HDF5_USE_FILE_LOCKING=FALSE

unset OMP_NUM_THREADS
export OMP_PROC_BIND=close
export OMP_PLACES=cores

echo "[Slurm] job=$SLURM_JOB_ID  ntasks=$SLURM_NTASKS  cpus-per-task=$SLURM_CPUS_PER_TASK"
echo "[Slurm] scale=${SCALE}%  n_swr=$N_SWR  epoch_ms=$EPOCH_MS  prp_threshold=$PRP_THRESHOLD"
echo "[Slurm] ec_lv=${EC_LV}  mpfc=${MPFC}  no_stc=${NO_STC}  homeostasis=${HOMEOSTASIS}  homeo_alpha=${HOMEO_ALPHA}  alpha_sweep=${ALPHA_SWEEP:-<none>}"
echo "[Slurm] dg=${DG}  dg_scale=${DG_SCALE}  pattern_completion=${PATTERN_COMPLETION}"
echo "[Slurm] het=${HET}  het_wcomp=${HET_WCOMP}  w_ec_dg=${W_EC_DG:-<default>}  pp_residual=${PP_RESIDUAL:-<default>}  dg_delay_jitter=${DG_DELAY_JITTER:-<default>}"

python3 - <<'PY'
import nest
ks = nest.GetKernelStatus()
mpi = ks.get("mpi_num_processes", ks.get("num_processes", ks.get("total_num_processes", 1)))
thr = ks.get("local_num_threads", ks.get("num_threads", ks.get("threads", 1)))
print(f"nest {nest.__version__}  mpi_procs={mpi}  local_threads={thr}")
PY

mkdir -p "$OUTDIR"

# ---- Pattern-completion probe: separate run mode, short-circuits here --------
# The probe builds an isolated CA3 twice (intact + sup_local-ablated), ignores
# STC / EC / homeostasis, and exits after writing its own HDF5. Runs on the
# same node config; it is lighter than the full consolidation run.
if [ "$PATTERN_COMPLETION" = "1" ]; then
  PC_OUT="${OUTDIR}/pattern_completion_${SCALE}pct.h5"
  echo "[Slurm] PATTERN COMPLETION mode → $PC_OUT"
  srun --cpu-bind=cores \
    python3 -u "replay_scaled.py" \
      --scale             "$SCALE" \
      --threads           "$SLURM_CPUS_PER_TASK" \
      --pattern-completion \
      --pc-cue-fracs      "$PC_CUE_FRACS" \
      --pc-cue-weight     "$PC_CUE_WEIGHT" \
      --out-hdf5          "$PC_OUT" \
      --no-figures
  echo "[Slurm] pattern-completion done."
  exit 0
fi

# Tag output filename with active phases
PHASE_TAG=""
[ "$DG" = "1" ] && PHASE_TAG="${PHASE_TAG}_dg"
# tag heterogeneity so H1/H2 cannot overwrite the homogeneous JOB F output
[ "$HET" != "0" ] && PHASE_TAG="${PHASE_TAG}_het${HET}"
[ -n "$W_EC_DG" ] && PHASE_TAG="${PHASE_TAG}_pp${W_EC_DG}"
[ "$EC_LV" = "1" ]  && PHASE_TAG="${PHASE_TAG}_lv"
[ "$MPFC"  = "1" ]  && PHASE_TAG="${PHASE_TAG}_mpfc"
[ "${PRP_THRESHOLD%.*}" -gt 100 ] 2>/dev/null && PHASE_TAG="${PHASE_TAG}_ph5"
if [ "$HOMEOSTASIS" = "1" ]; then
  if [ -n "$ALPHA_SWEEP" ]; then
    # Sweep mode: tag with #alphas and a hash of the list (e.g. _ph4sw3_050075090)
    SWEEP_HASH=$(echo "$ALPHA_SWEEP" | tr -d '.,' | tr ' ' '_')
    SWEEP_N=$(echo "$ALPHA_SWEEP" | tr ',' '\n' | grep -c .)
    PHASE_TAG="${PHASE_TAG}_ph4sw${SWEEP_N}_${SWEEP_HASH}"
  else
    PHASE_TAG="${PHASE_TAG}_ph4_a${HOMEO_ALPHA//./}"
  fi
fi

[ "$SCHAFFER_STDP" = "1" ]  && PHASE_TAG="${PHASE_TAG}_stdp"
[ "$CORTICAL_RECALL" = "1" ] && PHASE_TAG="${PHASE_TAG}_recall"
[ "$NO_MPFC_ASSOC" = "1" ]   && PHASE_TAG="${PHASE_TAG}_noplast"
[ -n "$TRAIN_PATTERN" ]      && PHASE_TAG="${PHASE_TAG}_p${TRAIN_PATTERN}"
[ -n "$SEED" ]               && PHASE_TAG="${PHASE_TAG}_s${SEED}"
OUTFILE="${OUTDIR}/replay_${SCALE}pct_stc${PHASE_TAG}.h5"
echo "[Slurm] output → $OUTFILE"

# STC requires EC LII (the model errors otherwise) — force it on if STC is active.
[ "$NO_STC" != "1" ] && EC_LII=1

# Build optional flag list
OPTIONAL_FLAGS=""
[ "$EC_LII" = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --ec-lii --ec-lii-k $EC_LII_K"
[ "$N_PATTERNS" != "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --n-patterns $N_PATTERNS"
[ -n "$TRAIN_PATTERN" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --train-pattern $TRAIN_PATTERN"
[ -n "$SEED" ]          && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --seed $SEED"
[ -n "$SCHAFFER_K" ]    && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --schaffer-k $SCHAFFER_K"
[ "$SCHAFFER_STDP" = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --schaffer-stdp"
[ "$DELAY_JITTER" != "0" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --delay-jitter $DELAY_JITTER"
[ "$NO_MPFC_ASSOC" = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --no-mpfc-assoc"
if [ "$CORTICAL_RECALL" = "1" ]; then
  OPTIONAL_FLAGS="$OPTIONAL_FLAGS --cortical-recall --cr-cue-frac $CR_CUE_FRAC"
  OPTIONAL_FLAGS="$OPTIONAL_FLAGS --cr-prime-rate $CR_PRIME_RATE --cr-prime-weight $CR_PRIME_WEIGHT"
fi
[ "$DG"     = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --dg --dg-scale $DG_SCALE"
[ "$HET" != "0" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --het $HET --het-wcomp $HET_WCOMP"
[ -n "$W_EC_DG" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --w-ec-dg $W_EC_DG"
[ -n "$PP_RESIDUAL" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --pp-residual $PP_RESIDUAL"
[ -n "$DG_DELAY_JITTER" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --dg-delay-jitter $DG_DELAY_JITTER"
[ "$NO_STC" != "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --stc --n-swr $N_SWR --epoch-ms $EPOCH_MS --prp-threshold $PRP_THRESHOLD"
[ "$EC_LV"  = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --ec-lv"
[ "$MPFC"   = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --mpfc"
if [ "$HOMEOSTASIS" = "1" ]; then
  if [ -n "$ALPHA_SWEEP" ]; then
    OPTIONAL_FLAGS="$OPTIONAL_FLAGS --homeostasis --alpha-sweep $ALPHA_SWEEP"
  else
    OPTIONAL_FLAGS="$OPTIONAL_FLAGS --homeostasis --homeo-alpha $HOMEO_ALPHA"
  fi
fi

srun --cpu-bind=cores \
  python3 -u "replay_scaled.py" \
    --scale       "$SCALE" \
    --threads     "$SLURM_CPUS_PER_TASK" \
    --out-hdf5    "$OUTFILE" \
    $OPTIONAL_FLAGS \
    --no-figures
