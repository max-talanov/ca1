#!/bin/bash -l
#SBATCH --job-name=DG_CA3_FI_CALIB
#SBATCH --output=dg_ca3_fi_calib_%A_%a.slurmout
#SBATCH --error=dg_ca3_fi_calib_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:20:00
#SBATCH --partition=gp_bsccs

# Phase 6.1 f-I calibration (default params)
#   sbatch run.sh

# Wider/finer sweep, more repeats for tighter rheobase estimates
#   sbatch --export=ALL,N_REPEATS=16,RATE_STEP=100 run.sh

# Data-only run, no PNG (e.g. for a batch of calibration variants)
#   sbatch --export=ALL,NO_FIGURES=1 run.sh

SIM_MS=${SIM_MS:-3000}
N_REPEATS=${N_REPEATS:-8}
RATE_MAX=${RATE_MAX:-6200}
RATE_STEP=${RATE_STEP:-200}
WEIGHT=${WEIGHT:-20.0}
CRITERION_HZ=${CRITERION_HZ:-2.0}
NO_FIGURES=${NO_FIGURES:-0}
OUTDIR="calibration_output"
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
echo "[Slurm] sim_ms=$SIM_MS  n_repeats=$N_REPEATS  rate_max=$RATE_MAX  rate_step=$RATE_STEP  weight=$WEIGHT"

python3 - <<'PY'
import nest
ks = nest.GetKernelStatus()
thr = ks.get("local_num_threads", ks.get("num_threads", ks.get("threads", 1)))
print(f"nest {nest.__version__}  local_threads={thr}")
PY

mkdir -p "$OUTDIR"
OUTFILE="${OUTDIR}/dg_ca3_fi_calib.h5"
echo "[Slurm] output -> $OUTFILE"

OPTIONAL_FLAGS=""
[ "$NO_FIGURES" = "1" ] && OPTIONAL_FLAGS="$OPTIONAL_FLAGS --no-figures"

srun --cpu-bind=cores \
  python3 -u "nest_dg_ca3_fi_calibration.py" \
    --threads      "$SLURM_CPUS_PER_TASK" \
    --sim-ms       "$SIM_MS" \
    --n-repeats    "$N_REPEATS" \
    --rate-max     "$RATE_MAX" \
    --rate-step    "$RATE_STEP" \
    --weight       "$WEIGHT" \
    --criterion-hz "$CRITERION_HZ" \
    --out-hdf5     "$OUTFILE" \
    $OPTIONAL_FLAGS
