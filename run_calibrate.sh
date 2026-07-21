#!/bin/bash
#SBATCH --job-name=dg_ca3_fi_calib
#SBATCH --account=uab100
#SBATCH --qos=acc_resb
#SBATCH --partition=acc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:20:00
#SBATCH --output=dg_ca3_fi_calib_%j.out
#SBATCH --error=dg_ca3_fi_calib_%j.err
# NOTE: no --gres=gpu -- NEST 3.9.0 here is the OpenMP-only build, not
# MPI/GPU-compiled, so this job is pure CPU. If acc_resb on MN5 requires
# a nonzero --gres=gpu to be schedulable at all (BSC's ACC-partition
# accounting ties CPU allocation to GPU count on some queues), uncomment:
# #SBATCH --gres=gpu:1
# and drop --cpus-per-task to whatever your allocation's per-GPU CPU
# ratio implies -- I can't confirm this from here, please check with
# `bsc_queues` / a prior working run.sh if you have one.

set -euo pipefail

# --- environment -----------------------------------------------------------
# FILL IN: however you've been loading NEST 3.9.0 + numpy<2.0 + scipy +
# matplotlib + h5py for the other tinyHippo phases (module load line or
# conda/venv activation). Not guessing this since it's specific to your
# MN5 setup and getting it wrong silently breaks the run.
# module purge
# module load <your NEST 3.9.0 module>
# source activate <your tinyHippo env>       # or: source /path/to/venv/bin/activate

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export SRUN_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK}

cd "${SLURM_SUBMIT_DIR}"

echo ">>> Node: $(hostname)"
echo ">>> Starting DG-CA3 Phase 6.1 f-I calibration at $(date)"

python3 nest_dg_ca3_fi_calibration.py

echo ">>> Done at $(date)"
