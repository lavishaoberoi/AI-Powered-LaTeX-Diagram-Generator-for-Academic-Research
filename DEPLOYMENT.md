# DiagramAI Deployment Guide
# IBM Watson Studio / IBM Cloud — Step-by-Step

# ════════════════════════════════════════════════════════════════════
# PHASE 1 — IBM Cloud Setup
# ════════════════════════════════════════════════════════════════════

## Step 1: Create an IBM Cloud account
# Visit: https://cloud.ibm.com/registration
# Complete sign-up and email verification.

## Step 2: Create an IBM Cloud API Key
# 1. Log in to https://cloud.ibm.com
# 2. Navigate to: Manage → Access (IAM) → API Keys
# 3. Click "Create an IBM Cloud API key"
# 4. Name it: diagramai-key
# 5. Copy the key — YOU CANNOT VIEW IT AGAIN
# 6. Add it to .env: IBM_CLOUD_API_KEY=<your_key>

## Step 3: Create a Watson Studio / Watsonx.ai Project
# 1. Navigate to: https://dataplatform.cloud.ibm.com
# 2. Click "Create a project" → "Create an empty project"
# 3. Name it: DiagramAI
# 4. Choose an Object Storage instance (create one if needed — Lite tier is free)
# 5. Click "Create"
# 6. From the project Settings → General, copy your Project ID
# 7. Add it to .env: WATSONX_PROJECT_ID=<your_project_id>

## Step 4: Enable Watsonx.ai and Granite Models
# 1. From your Watson Studio project, click "+ Add to project" → "Foundation model"
# 2. In IBM watsonx.ai, locate: ibm/granite-13b-instruct-v2
# 3. Ensure your IBM Cloud account has watsonx.ai access
#    (Activate at: https://dataplatform.cloud.ibm.com/wx/home)
# 4. The model endpoint is automatically managed by the ibm-watsonx-ai SDK —
#    no manual deployment needed for SaaS Granite models.
# 5. Set in .env: GRANITE_MODEL_ID=ibm/granite-13b-instruct-v2

# ════════════════════════════════════════════════════════════════════
# PHASE 2 — Local Development Setup
# ════════════════════════════════════════════════════════════════════

## Step 1: Python environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

## Step 2: Install dependencies
pip install -r requirements.txt

## Step 3: Install Tectonic (LaTeX compiler)
# Windows (via Chocolatey):
choco install tectonic
# macOS:
brew install tectonic
# Linux:
curl --proto '=https' --tlsv1.2 -fsSL https://drop.rust-lang.org/tectonic-installer.sh | sh
# Or use pdflatex instead: set LATEX_COMPILER=pdflatex in .env

## Step 4: Install Poppler (for PDF→PNG conversion)
# Windows: https://github.com/oschwartz10612/poppler-windows/releases
# macOS:   brew install poppler
# Ubuntu:  sudo apt-get install poppler-utils

## Step 5: Configure environment
cp .env.example .env
# Edit .env with your IBM_CLOUD_API_KEY, WATSONX_PROJECT_ID, etc.

## Step 6: Run locally
python app.py
# Open: http://localhost:5000

# ════════════════════════════════════════════════════════════════════
# PHASE 3 — IBM Code Engine Deployment (Recommended)
# ════════════════════════════════════════════════════════════════════

## Step 1: Install IBM Cloud CLI
# https://cloud.ibm.com/docs/cli

## Step 2: Log in
ibmcloud login --sso

## Step 3: Install Code Engine plugin
ibmcloud plugin install code-engine

## Step 4: Create Code Engine project
ibmcloud ce project create --name diagramai-project
ibmcloud ce project select --name diagramai-project

## Step 5: Create a container registry namespace (optional but recommended)
ibmcloud cr namespace-add diagramai-ns

## Step 6: Build and push Docker image
# Build:
docker build -t us.icr.io/diagramai-ns/diagramai:latest .
# Push (login to IBM Container Registry first):
ibmcloud cr login
docker push us.icr.io/diagramai-ns/diagramai:latest

## Step 7: Create Code Engine secrets for environment variables
ibmcloud ce secret create --name diagramai-env \
  --from-literal IBM_CLOUD_API_KEY=<your_key> \
  --from-literal WATSONX_PROJECT_ID=<your_project_id> \
  --from-literal FLASK_SECRET_KEY=<secure_random_string>

## Step 8: Deploy application
ibmcloud ce application create \
  --name diagramai \
  --image us.icr.io/diagramai-ns/diagramai:latest \
  --registry-secret ce-auto-icr-private-us-south \
  --env-from-secret diagramai-env \
  --env GRANITE_MODEL_ID=ibm/granite-13b-instruct-v2 \
  --env LATEX_COMPILER=tectonic \
  --env FLASK_ENV=production \
  --port 5000 \
  --min-scale 1 \
  --max-scale 3 \
  --cpu 1 \
  --memory 4G

## Step 9: Get the public URL
ibmcloud ce application get --name diagramai --output url

# ════════════════════════════════════════════════════════════════════
# PHASE 4 — Docker Setup (for containerized deployment)
# ════════════════════════════════════════════════════════════════════
# See Dockerfile in this directory for the container definition.

# ════════════════════════════════════════════════════════════════════
# PHASE 5 — Production Checklist
# ════════════════════════════════════════════════════════════════════
# [ ] Set FLASK_SECRET_KEY to a cryptographically random 32+ char string
# [ ] Set FLASK_ENV=production and FLASK_DEBUG=0
# [ ] Restrict CORS origins in app.py (replace * with your domain)
# [ ] Enable HTTPS (Code Engine provides this automatically)
# [ ] Set up IBM Cloud Object Storage for diagram file persistence
# [ ] Configure IBM Cloud Monitoring for usage tracking
# [ ] Review IBM Cloud IAM permissions — principle of least privilege
# [ ] Test all API endpoints with your IBM_CLOUD_API_KEY
