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
