#!/usr/bin/env bash
# Download Person-3 Kaggle exports and unzip into data/kaggle_download/ (requires: pip install kaggle).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/data/kaggle_download"
mkdir -p "${DEST}"
cd "${DEST}"
if ! command -v kaggle >/dev/null 2>&1; then
  echo "Install Kaggle CLI: pip install kaggle" >&2
  exit 1
fi
kaggle datasets download -d rajatraj0502/linkedin-job-2023
kaggle datasets download -d snehaanbhawal/resume-dataset
unzip -o -q linkedin-job-2023.zip
unzip -o -q resume-dataset.zip
echo "OK: CSVs under ${DEST} (job_postings.csv, Resume/Resume.csv, companies.csv, …)"
