# Deployment Plan: Driver Mistake Identification System

## 1. Executive Summary

For a third-year university project, the primary goals for deployment are **cost-effectiveness**, **simplicity**, and **demonstrability**.

**Recommendation:**
*   **Frontend:** Deploy on **Vercel** or **Netlify** (Free Tier). These platforms are optimized for React, provide global CDNs for fast loading, and handle SSL automatically.
*   **Backend & Processing:** Deploy on a **Virtual Private Server (VPS)** (e.g., DigitalOcean Droplet or AWS EC2) using **Docker**.

**Why this approach?**
The backend performs heavy computational tasks (video processing with PyTorch/OpenCV) and requires a persistent filesystem for the SQLite database (`jobs.db`) and uploaded video files. "Serverless" or free-tier PaaS environments (like Heroku Free) often have strict timeout limits (30s), ephemeral filesystems (data is lost on restart), and low RAM, which would cause this application to fail. A VPS mimics your local environment, ensuring stability.

---

## 2. System Architecture

### High-Level Design
```mermaid
graph TD
    User[User / Browser] -->|HTTPS| Frontend[Frontend (Vercel/Netlify)]
    User -->|API Calls (Videos)| Nginx[Nginx Reverse Proxy (VPS)]
    
    subgraph VPS [Virtual Private Server]
        Nginx -->|Proxy /api| Backend[FastAPI Server]
        Backend -->|Spawns| Worker[Analysis Subprocess]
        Backend -->|Read/Write| DB[(SQLite DB)]
        Backend -->|Read/Write| Storage[Local Disk /uploads]
        Worker -->|Read/Write| Storage
    end
```

1.  **Client Layer**: React App served via CDN.
2.  **Network Layer**: Nginx acts as a "traffic controller" on the VPS. It handles SSL encryption (HTTPS) and directs API requests to the Python backend.
3.  **Application Layer**: FastAPI handles uploads and manages the SQLite database. It spawns the heavy analysis logic as a separate background subprocess (just like it does locally).
4.  **Data Layer**: A local `uploads/` directory on the VPS stores videos temporarily, and a SQLite file stores job status.

---

## 3. Data Privacy and Safety

Handling user video data requires strict adherence to privacy standards.

### 3.1 Data Minimization & Retention
*   **Current State**: Your `analysis_service.py` already implements a `keep_videos` flag.
*   **Deployment Strategy**: Ensure `keep_videos` defaults to `False`. Implement a "Cron Job" (scheduled task) on the server to purely clean up any "orphaned" files (files older than 24 hours) in case the application crashes before deletion.
    *   *Command*: `find /path/to/uploads -type f -mtime +1 -delete`
*   **Justification**: Minimizing data storage limits liability. If you don't have the data, it can't be leaked.

### 3.2 Transmission Security
*   **HTTPS**: All data in transit must be encrypted.
*   **Implementation**: Use **Certbot (Let's Encrypt)** on the Nginx server to get a free, auto-renewing SSL certificate. Vercel handles this automatically for the frontend.
*   **Justification**: Prevents "Man-in-the-Middle" attacks where an attacker could intercept the video upload stream.

### 3.3 Access Control
*   **Strategy**: For a university demo, implement **Basic Authentication** or a simple API Key mechanism if the URL is public.
*   **Justification**: Prevents unauthorized users from flooding your server with large video files, which could fill your disk space or crash the server (Denial of Service).

---

## 4. Performance & Scalability

### 4.1 Throughput Limitations
*   **Bottleneck**: The current architecture spawns a `subprocess` for every analysis. If 10 users upload videos simultaneously, the server will try to run 10 PyTorch instances. This will crash a small server (OOM - Out of Memory).
*   **Solution (Semaphore)**: In `analysis_service.py`, you should use an `asyncio.Semaphore` or a simple counter to limit concurrent analyses to **1** or **2** at a time. Other requests should wait or be rejected with "Server Busy".

### 4.2 Handling Large Files
*   **Configuration**: You must configure Nginx to accept large file uploads.
    *   `client_max_body_size 500M;`
*   **Timeout**: FastAPI and Nginx timeouts must be increased (e.g., to 300s) for slow connections, though the *analysis* runs in the background so it won't timeout the HTTP request.

---

## 5. Deployment Guide (Step-by-Step)

### Phase 1: Preparation (Dockerization)
Docker containers package your code with all its dependencies (Python, OpenCV libraries, etc.), guaranteeing it runs on the server exactly as it does on your machine.

**1. Create a `Dockerfile` in the project root:**
```dockerfile
FROM python:3.9-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement files
COPY web_application/backend/requirements.txt ./
# Add any other requirements from sub-folders if needed

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project structure to preserve relative imports
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "web_application.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Phase 2: Frontend Deployment
1.  Push your code to **GitHub**.
2.  Log in to **Vercel** (vercel.com) using GitHub.
3.  "Add New Project" -> Select your repository.
4.  **Settings**:
    *   Root Directory: `web_application/frontend`
    *   Build Command: `npm run build`
    *   Output Directory: `dist`
5.  **Environment Variables**: Set `VITE_API_URL` to your future VPS IP (e.g., `https://api.yourproject.com`).

### Phase 3: Server Deployment (The Backend)
1.  **Get a Server**:
    *   Sign up for **GitHub Student Developer Pack** (free credits for DigitalOcean/Azure).
    *   Create a "Droplet" (Virtual Machine) on DigitalOcean: **Ubuntu 22.04**, Basic Plan, **4GB RAM** (Video processing needs RAM). ~\$24/mo (covered by credits).
2.  **Setup Server**:
    *   SSH into server: `ssh root@<your-ip>`
    *   Install Docker: `snap install docker`
3.  **Deploy**:
    *   Clone your repo: `git clone https://github.com/your/repo.git`
    *   Build Docker image: `docker build -t driver-app .`
    *   Run it (mounting a volume for data persistence):
        ```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/uploads:/app/web_application/uploads \
  -v $(pwd)/jobs.db:/app/web_application/backend/jobs.db \
  --name backend_container \
  driver-app
        ```

### Phase 4: Connecting the Dots (Nginx)
Install Nginx on the VPS to make it secure and accessible.

1.  `apt install nginx`
2.  Edit config: `/etc/nginx/sites-available/default`
    ```nginx
    server {
        server_name api.your-domain.com; # Or just the IP

        client_max_body_size 500M; # Allow large videos

        location / {
            proxy_pass http://localhost:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    ```
3.  Restart Nginx: `systemctl restart nginx`

## 6. Cost Estimation (Student Optimized)

| Service | Choice | Cost | Notes |
| :--- | :--- | :--- | :--- |
| **Hosting** | DigitalOcean Droplet (4GB RAM) | \$24/mo | **Free** via GitHub Student Pack (\$200 credit). |
| **Frontend** | Vercel | \$0 | Generous free tier. |
| **Domain** | Namecheap / GitHub Pack | \$0 - \$10/yr | Free .me domain often included in Student Pack. |
| **SSL** | Let's Encrypt | \$0 | Industry standard free SSL. |

**Total Cost for Student:** **\$0** (for 12 months using credits).
