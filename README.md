# Employee Leave Management System

A simple Flask + SQLite app with a full CI/CD pipeline on GitHub Actions → Google Cloud Run.

---

## Run Locally (Windows PowerShell)

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app (DB file is created automatically as leave.db)
python app.py
```

Open http://localhost:5000  
Login with: `asha / asha123`, `vikram / vikram123`, or `manager / manager123`

Health check: http://localhost:5000/health

---

## Run with Docker

```powershell
docker build -t elms .
docker run -p 8080:8080 elms
```

Open http://localhost:8080  
Health check: http://localhost:8080/health

---

## One-Time GCP Setup

Run these once in Cloud Shell or with the `gcloud` CLI installed locally.

```bash
# Replace YOUR_PROJECT_ID with your real GCP project ID
PROJECT_ID=YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  --project $PROJECT_ID

# Create Artifact Registry repository in asia-south1
gcloud artifacts repositories create elms-repo \
  --repository-format=docker --location=asia-south1 --project $PROJECT_ID

# Create a service account for GitHub Actions
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions SA" --project $PROJECT_ID

SA=github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/iam.serviceAccountUser"

# Create and download the JSON key
gcloud iam service-accounts keys create key.json --iam-account=$SA
```

---

## GitHub Secrets to Add

In your GitHub repository → Settings → Secrets and variables → Actions, add:

| Secret name      | Value                                      |
|------------------|--------------------------------------------|
| `GCP_PROJECT_ID` | Your GCP project ID (e.g. `my-project-123`) |
| `GCP_SA_KEY`     | Full contents of `key.json` (paste as-is)  |

> **Important:** Do not commit `key.json` to git. It is in `.gitignore`.

---

## Cloud Monitoring Uptime Check

1. Open [Cloud Monitoring → Uptime checks](https://console.cloud.google.com/monitoring/uptime)
2. Click **Create uptime check**
3. Set:
   - **Target:** HTTPS, hostname = your Cloud Run URL (from `gcloud run services describe leave-management --region asia-south1 --format 'value(status.url)'`), path = `/health`
   - **Check frequency:** 1 minute
   - **Response:** Status code 200, response body contains `healthy`
4. Create an alert policy to notify you when the check fails

---

## Failure & Recovery Demo

```bash
# 1. Inject failure – health check starts returning 503
gcloud run services update leave-management \
  --region asia-south1 \
  --update-env-vars SIMULATE_FAILURE=true

# 2. Verify it is unhealthy
curl $(gcloud run services describe leave-management \
  --region asia-south1 --format 'value(status.url)')/health
# → {"status":"unhealthy"}

# 3. Recover – health check returns 200 again
gcloud run services update leave-management \
  --region asia-south1 \
  --update-env-vars SIMULATE_FAILURE=false

curl .../health
# → {"status":"healthy"}
```
