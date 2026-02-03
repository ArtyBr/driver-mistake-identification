import logging
import paramiko

logger = logging.getLogger(__name__)

class BatchService:
    def __init__(self):
        self.project_root = "/dcs/project/safedrive/driver-mistake-identification"
        self.conda_env = "safedrive_env"
        self.jump_host = "remote-49.dcs.warwick.ac.uk"
        self.target_host = "kudu-taught.dcs.warwick.ac.uk"
        self.username = "safedrive"

    def _get_ssh_client(self):
        """Creates an SSH client jumping through a proxy."""
        gateway_client = paramiko.SSHClient()
        gateway_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to jump host
        # Note: In production, this might need key_filename or ssh-agent
        gateway_client.connect(self.jump_host, username=self.username)
        
        # Open tunnel to target host
        transport = gateway_client.get_transport()
        dest_addr = (self.target_host, 22)
        local_addr = ('localhost', 0) # Use any local port for the proxy
        channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)
        
        # Connect to target host through tunnel
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.target_host, username=self.username, sock=channel)
        
        return client

    def _generate_sbatch_script(self, job_name: str, road_path: str, face_path: str, output_path: str, road_meta: str = None, face_meta: str = None) -> str:
        cmd = f"python combined_analysis/run_headless.py \\\n    --road {road_path} \\\n    --face {face_path} \\\n    --output {output_path}"
        
        if road_meta:
            # Escape double quotes for shell
            escaped_road_meta = road_meta.replace('"', '\\"')
            cmd += f" \\\n    --road_meta \"{escaped_road_meta}\""
        if face_meta:
            escaped_face_meta = face_meta.replace('"', '\\"')
            cmd += f" \\\n    --face_meta \"{escaped_face_meta}\""

        script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=gpus
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=01:00:00
#SBATCH --output={self.project_root}/logs/batch_%j.log

# Load environment
source ~/.bashrc
conda activate {self.conda_env} || source {self.project_root}/lane_detection/lanedet/environment.yaml

cd {self.project_root}
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
            # -h: no header, -o %T: show only state
            stdin, stdout, stderr = client.exec_command(f"squeue -j {job_id} -h -o %T")
            
            output = stdout.read().decode().strip()
            
            if stdout.channel.recv_exit_status() != 0:
                # If squeue fails, it might be because the job is no longer in the queue (completed)
                # We should check if the job exists in sacct or just assume it's COMPLETED if not found
                # For now, let's return UNKNOWN if it fails
                return "UNKNOWN"
            
            if not output:
                # Often means the job is finished and gone from the queue
                return "COMPLETED"
                
            return output
        finally:
            client.close()
        # Skeleton implementation
        return "PENDING"
