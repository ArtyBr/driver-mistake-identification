# Implementation Plan - Progress Tracking and Result Loading for Batch Jobs

This plan outlines the steps to enable progress tracking for SLURM batch jobs by parsing log files and automatically ingesting results into the database upon completion.

## Phase 1: Enhanced Batch Service (Backend) [checkpoint: ba7e248]
Focus on extending `BatchService` to extract progress and error details from the remote filesystem.

- [x] Task: Extend `BatchService` with log parsing capabilities
    - [ ] Add `_get_latest_slurm_log(job_dir)` to find the most recent `slurm_*.log`.
    - [ ] Add `get_job_progress(job_id, job_dir)` to read the remote log file and parse `tqdm` progress (e.g., searching for `XX%|`).
    - [ ] Add `get_job_error(job_dir)` to capture the tail of the log file if a job fails.
- [x] Task: Add result file reading to `BatchService`
    - [x] Implement `read_remote_results(output_path)` to fetch the `results.json` content via SSH/SFTP or direct file access if shared.
- [x] Task: Write unit tests for `BatchService` enhancements
    - [x] Mock SSH/SFTP responses with sample `tqdm` log output.
    - [x] Mock successful and failed job scenarios.
- [x] Task: Conductor - User Manual Verification 'Enhanced Batch Service' (Protocol in workflow.md) ba7e248

## Phase 2: Status Polling Logic (Backend)
Update the API layer to use the new service capabilities.

- [ ] Task: Update `JobService.get_job` or `/status/{job_id}` route
    - [ ] If job status is `SUBMITTED` or `RUNNING`, call `batch_service.check_status`.
    - [ ] If SLURM status is `RUNNING`, update progress in DB by parsing logs.
    - [ ] If SLURM status indicates completion, trigger the "Finalization" logic.
- [ ] Task: Implement Job Finalization logic
    - [ ] Create `finalize_job(job_id)` in `JobService` or `AnalysisService`.
    - [ ] This should: Read `results.json`, update DB `result` column, set status to `COMPLETED`.
    - [ ] Handle error states by capturing log tails.
- [ ] Task: Verify status polling with integration tests
    - [ ] Use `test_analysis_integration.py` as a base to verify DB updates during polling.
- [ ] Task: Conductor - User Manual Verification 'Status Polling Logic' (Protocol in workflow.md)

## Phase 3: Frontend Refinement & Verification
Ensure the UI correctly reflects the backend updates.

- [ ] Task: Verify `StatusPage` and `useJobStatus` hook
    - [ ] Ensure the progress bar moves as the backend updates the `progress` column.
    - [ ] Confirm automatic redirection to `ResultPage` works when status hits `COMPLETED`.
- [ ] Task: Manual end-to-end verification
    - [ ] Upload a small video, monitor progress, and verify results load correctly.
    - [ ] Simulate a failure and verify the error message appears.
- [ ] Task: Conductor - User Manual Verification 'Frontend Refinement & Verification' (Protocol in workflow.md)
