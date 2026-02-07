# Specification: Progress Tracking and Result Loading for Batch Jobs

## Overview
This track addresses the visibility of analysis progress when using the SLURM batch compute system. It ensures that the frontend correctly displays progress bars and transitions to the results screen once the batch job completes.

## Functional Requirements

### 1. On-Demand Progress Updating
-   The backend `/status/{job_id}` endpoint must be enhanced to trigger a status and progress check if the job is in a non-terminal state (e.g., `SUBMITTED`, `RUNNING`).
-   `BatchService` will be extended to:
    -   Identify the SLURM log file for a given job ID.
    -   Parse the log file to extract the current progress percentage from `tqdm` output.
    -   Detect job completion or failure from SLURM state and file existence.

### 2. Automatic Result Integration
-   When a job is detected as `COMPLETED` on the batch system:
    -   The backend must locate the `results.json` in the job's directory.
    -   The contents of `results.json` must be loaded into the `result` column of the `Job` record in the database.
    -   The job status must be updated to `COMPLETED` and progress to `100%`.

### 3. Error Reporting
-   If a job fails on the batch system (detected via SLURM status or missing result file):
    -   The backend must attempt to read the last few lines of the SLURM log file.
    -   The captured error message must be stored in the `error` column of the `Job` record.
    -   The status must be updated to `FAILED`.

### 4. Frontend Resilience
-   The `StatusPage` should handle transitions from `SUBMITTED` to `RUNNING` and eventually to `COMPLETED`.
-   The `ResultPage` must correctly render the results fetched from the database once the job is finished.

## Non-Functional Requirements
-   **Performance:** Status checks should be efficient. SSH calls should have reasonable timeouts.
-   **Reliability:** Handle cases where the SLURM log file is not yet created or the result file is delayed by file system latency.

## Acceptance Criteria
- [ ] Users see a real-time (polling-based) progress bar on the `StatusPage` after starting an analysis.
- [ ] Jobs that finish successfully automatically redirect to/enable the `ResultPage`.
- [ ] Meaningful error messages from the batch script are displayed on the frontend if the analysis fails.
- [ ] The database `result` column is populated for successful batch jobs.

## Out of Scope
-   Real-time streaming of logs via WebSockets (we are sticking to polling).
-   Re-submitting failed jobs automatically.
