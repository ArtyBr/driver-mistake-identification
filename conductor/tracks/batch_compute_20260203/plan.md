# Implementation Plan - Batch Computation Offloading

## Phase 1: Infrastructure & Dependencies [checkpoint: 17a9309]

- [x] Task: Add `paramiko` to `web_application/backend/requirements.txt` 27ff65e
    - [x] Create `tests/test_deps.py` to verify `paramiko` installation (if needed, or just relying on pip install).
    - [x] Update `requirements.txt`.
- [x] Task: Create `BatchService` Skeleton d9ec120
    - [x] Create `web_application/backend/app/services/batch_service.py`.
    - [x] Define `submit_job`, `check_status` methods.
    - [x] Write unit tests in `web_application/backend/tests/test_batch_service.py` mocking SSH connections.

## Phase 2: SLURM Script Generation & Submission

- [x] Task: Implement SLURM Script Generation a48e275
    - [x] Update `BatchService` to generate a valid `.sbatch` string based on job parameters.
    - [x] Template should include resource requests (GPU if available/needed, time limits) and environment activation.
    - [x] Test generation against expected string output.
- [ ] Task: Implement SSH Submission Logic
    - [ ] Implement `paramiko` logic to connect via Jump Host.
    - [ ] Implement `sbatch` command execution.
    - [ ] Parse Job ID from `sbatch` output.
    - [ ] Write integration tests (mocked) for the submission flow.

## Phase 3: Integration with Job Workflow

- [ ] Task: Update `AnalysisService` to use `BatchService`
    - [ ] Modify `start_analysis` in `web_application/backend/app/services/analysis_service.py`.
    - [ ] Instead of `subprocess.Popen` locally, call `batch_service.submit_job`.
- [ ] Task: Conductor - User Manual Verification 'Batch Computation Offloading' (Protocol in workflow.md)
