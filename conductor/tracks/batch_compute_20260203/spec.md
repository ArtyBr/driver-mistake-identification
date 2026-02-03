# Specification: Batch Computation Offloading

## Goal
Offload heavy video analysis tasks from the web server (`wagtail`) to the compute cluster (`kudu-taught`) using SLURM batch jobs (`sbatch`). This ensures the web server remains responsive and utilizes appropriate hardware for intensive CV tasks.

## Architecture

### 1. Job Submission Flow
1.  **User uploads video** to Frontend -> Backend (`wagtail`).
2.  **Backend saves video** to shared storage `/dcs/large/safedrive_cs310_2526/`.
3.  **Backend generates an SLURM script** (`.sbatch`) specific to the job.
4.  **Backend connects via SSH** to `kudu-taught` (jumping through `remote-49`).
5.  **Backend submits job** using `sbatch <script>`.
6.  **Backend records Job ID** returned by SLURM.

### 2. Job Status Monitoring
-   Backend polls `kudu-taught` via SSH (e.g., `squeue -j <job_id>`) to check status.
-   Alternatively, the SLURM script can make a callback (webhook) to the backend upon completion, but polling is more robust for a first iteration.

### 3. Result Retrieval
-   The `run_headless.py` script on `kudu-taught` writes results (JSON) to the same shared storage.
-   Backend reads the result file from storage once the job is complete.

## Components

### Backend (`web_application/backend/`)
-   **`services/batch_service.py`**:
    -   Handles SSH connections (using `paramiko`).
    -   Generates `.sbatch` file content.
    -   Submits jobs and checks status.
-   **Dependencies**: Add `paramiko` to `requirements.txt`.

### SLURM Script Template
-   Needs to activate the environment on `kudu-taught`.
-   Needs to execute `combined_analysis/run_headless.py` with correct paths.

## Configuration
-   **Host:** `kudu-taught.dcs.warwick.ac.uk`
-   **Jump Host:** `remote-49.dcs.warwick.ac.uk`
-   **User:** Configurable (env var), defaulting to project user.
-   **Storage Path:** `/dcs/large/safedrive_cs310_2526/`
