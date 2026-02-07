import logging
import paramiko
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class BatchService:
    def __init__(self):
        self.project_root = "/dcs/project/safedrive/driver-mistake-identification"
        self.conda_env = "safedrive_env"
        self.jump_host = "remote-49.dcs.warwick.ac.uk"
        self.target_host = "kudu-taught.dcs.warwick.ac.uk"
        self.username = "u2204449"
        self.remote_project_root = "~/cs310/driver-mistake-identification"
        self.venv_path = "/dcs/large/safedrive_cs310_2526/safedrive_venv"

    def _get_ssh_client(self):
        """Creates an SSH client jumping through a proxy."""
        gateway_client = paramiko.SSHClient()
        gateway_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to jump host
        gateway_client.connect(
            self.jump_host, 
            username=self.username, 
            allow_agent=True, 
            look_for_keys=True,
            timeout=10
        )
        
        # Open tunnel to target host
        transport = gateway_client.get_transport()
        dest_addr = (self.target_host, 22)
        local_addr = ('localhost', 0)
        channel = transport.open_channel("direct-tcpip", dest_addr, local_addr, timeout=10)
        
        # Connect to target host through tunnel
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.target_host, 
            username=self.username, 
            sock=channel, 
            allow_agent=True, 
            look_for_keys=True,
            timeout=10
        )
        
        return client

    def _get_latest_slurm_log_local(self, job_dir: str) -> Optional[str]:
        """Finds the most recent slurm log file in the job directory locally."""
        try:
            path = Path(job_dir)
            logs = sorted(path.glob("slurm_*.log"))
            if not logs:
                return None
            return str(logs[-1])
        except Exception as e:
            logger.error(f"Error finding slurm log locally: {e}")
            return None

    def get_job_progress(self, job_id: str, job_dir: str) -> Optional[int]:
        """Parses the latest SLURM log for tqdm progress using local file access."""
        try:
            log_file = self._get_latest_slurm_log_local(job_dir)
            if not log_file:
                return None
                
            # Read the last few kilobytes of the file to find the latest progress
            with open(log_file, 'rb') as f:
                # Seek to end and read last 4096 bytes
                try:
                    f.seek(-4096, 2)
                except OSError:
                    # File smaller than 4096 bytes
                    pass
                output = f.read().decode(errors='ignore')

            # Regex for tqdm: " 45%|" or "45%|####"
            # Look for the last occurrence of a percentage followed by % and |
            matches = re.findall(r'(\d+)%\s*\|', output)
            if matches:
                return int(matches[-1])
            
            return None
        except Exception as e:
            logger.error(f"Error reading progress locally for {job_id}: {e}")
            return None

    def get_job_error(self, job_id: str, job_dir: str) -> Optional[str]:
        """Reads the tail of the SLURM log locally to capture errors."""
        try:
            log_file = self._get_latest_slurm_log_local(job_dir)
            if not log_file:
                return "Log file not found."
                
            with open(log_file, 'r') as f:
                lines = f.readlines()
                return "".join(lines[-20:])
        except Exception as e:
            logger.error(f"Error reading error log locally for {job_id}: {e}")
            return f"Failed to read log file: {e}"

    def read_results_local(self, output_path: str) -> Optional[str]:
        """Reads the results.json file locally."""
        try:
            path = Path(output_path)
            if not path.exists():
                return None
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading results locally: {e}")
            return None

    def _generate_sbatch_script(self, job_name: str, road_path: str, face_path: str, output_path: str, road_meta: str = None, face_meta: str = None) -> str:
        cmd = f"python combined_analysis/run_headless.py \\\n    --road {road_path} \\\n    --face {face_path} \\\n    --output {output_path}"
        
        if road_meta:
            # Escape double quotes for shell
            escaped_road_meta = road_meta.replace('"', '\\"')
            cmd += f" \\\n    --road_meta \"{escaped_road_meta}\""
        if face_meta:
            escaped_face_meta = face_meta.replace('"', '\\"')
            cmd += f" \\\n    --face_meta \"{escaped_face_meta}\""

        # Extract job directory from output_path (which is .../results.json)
        job_dir = Path(output_path).parent

        script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=eagle
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=01:00:00
#SBATCH --output={job_dir}/slurm_%j.log

# Load environment
source {self.venv_path}/bin/activate

cd {self.remote_project_root}
{cmd}
"""
        return script

    def submit_job(self, script_content: str) -> str:
        client = self._get_ssh_client()
        try:
            stdin, stdout, stderr = client.exec_command("sbatch")
            stdin.write(script_content)
            stdin.channel.shutdown_write()
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if stdout.channel.recv_exit_status() != 0:
                logger.error(f"sbatch failed: {error}")
                raise Exception(f"Failed to submit job: {error}")
            
            # Example output: "Submitted batch job 123456"
            if "Submitted batch job" in output:
                job_id = output.split()[-1]
                return job_id
            else:
                raise Exception(f"Unexpected sbatch output: {output}")
        finally:
            client.close()

    def check_status(self, job_id: str) -> str:
        client = self._get_ssh_client()
        try:
            # First check squeue (running/pending jobs)
            stdin, stdout, stderr = client.exec_command(f"squeue -j {job_id} -h -o %T")
            output = stdout.read().decode().strip()
            
            if output:
                return output

            # If not in squeue, check sacct (finished jobs)
            # -j: job id, -n: no header, -o state: show only state, -X: no job steps
            stdin, stdout, stderr = client.exec_command(f"sacct -j {job_id} -n -o state -X")
            output = stdout.read().decode().strip()
            
            if output:
                # sacct returns states like "COMPLETED", "FAILED", "RUNNING"
                return output.split()[0]
            
            # If still nothing, it might be very new or very old
            return "UNKNOWN"
        finally:
            client.close()
