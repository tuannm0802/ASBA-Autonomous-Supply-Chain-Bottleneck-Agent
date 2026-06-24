"""
Google Cloud Storage (GCS) Helper for ASBA.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handles data persistence in serverless environments. If running on GCP
(or local configured with USE_GCS=true), it syncs ML models, logistics CSVs, 
and daily reports to a GCS bucket so data persists across container restarts.
"""

import os
import sys
from pathlib import Path
from google.cloud import storage

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import DATA_DIR, REPORTS_DIR

# Configuration environment variables
USE_GCS = os.getenv("USE_GCS", "false").lower() == "true"
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET", "adroit-gravity-500216-r4-asba-data")


def get_gcs_client():
    """Initializes the GCS storage client. Returns None if disabled or failed."""
    if not USE_GCS:
        return None
    try:
        # Implicitly uses Application Default Credentials (ADC) on GCP
        return storage.Client()
    except Exception as e:
        print(f"  ⚠️  [GCS] Failed to initialize storage client (falling back to local): {e}")
        return None


def get_or_create_bucket():
    """Fetches the target GCS bucket, creating it if it doesn't exist."""
    client = get_gcs_client()
    if not client:
        return None
    
    try:
        bucket = client.lookup_bucket(GCS_BUCKET_NAME)
        if bucket:
            return bucket
            
        print(f"  ☁️  [GCS] Bucket '{GCS_BUCKET_NAME}' not found. Creating bucket...")
        # Create bucket in us-central1 default location
        bucket = client.create_bucket(GCS_BUCKET_NAME, location="us-central1")
        print(f"  ☁️  [GCS] Bucket '{GCS_BUCKET_NAME}' created successfully.")
        return bucket
    except Exception as e:
        print(f"  ⚠️  [GCS] Failed to lookup/create bucket '{GCS_BUCKET_NAME}': {e}")
        return None


def upload_to_gcs(local_file_path: Path, gcs_blob_path: str) -> bool:
    """Uploads a local file to GCS."""
    bucket = get_or_create_bucket()
    if not bucket:
        return False
        
    try:
        blob = bucket.blob(gcs_blob_path)
        blob.upload_from_filename(str(local_file_path))
        print(f"  ☁️  [GCS] Uploaded: {local_file_path.name} ➡️ gs://{GCS_BUCKET_NAME}/{gcs_blob_path}")
        return True
    except Exception as e:
        print(f"  ⚠️  [GCS] Upload failed for {local_file_path.name}: {e}")
        return False


def download_from_gcs(gcs_blob_path: str, local_file_path: Path) -> bool:
    """Downloads a GCS blob to a local file path."""
    bucket = get_or_create_bucket()
    if not bucket:
        return False
        
    try:
        blob = bucket.blob(gcs_blob_path)
        if not blob.exists():
            return False
            
        local_file_path.parent.mkdir(exist_ok=True)
        blob.download_to_filename(str(local_file_path))
        print(f"  ☁️  [GCS] Downloaded: gs://{GCS_BUCKET_NAME}/{gcs_blob_path} ➡️ {local_file_path.name}")
        return True
    except Exception as e:
        print(f"  ⚠️  [GCS] Download failed for {gcs_blob_path}: {e}")
        return False


def sync_cloud_to_local() -> bool:
    """Syncs critical files (CSV datasets, models, report jsons) from GCS to local directories."""
    client = get_gcs_client()
    if not client:
        return False
        
    bucket = get_or_create_bucket()
    if not bucket:
        return False
        
    print("  ☁️  [GCS] Syncing files from cloud storage bucket to local container...")
    success = False
    try:
        blobs = client.list_blobs(GCS_BUCKET_NAME)
        for blob in blobs:
            name = blob.name
            
            # Map GCS folder paths back to local project folders
            if name.startswith("data/"):
                local_path = DATA_DIR / name.replace("data/", "")
                download_from_gcs(name, local_path)
                success = True
            elif name.startswith("daily_reports/"):
                local_path = REPORTS_DIR / name.replace("daily_reports/", "")
                download_from_gcs(name, local_path)
                success = True
        return success
    except Exception as e:
        print(f"  ⚠️  [GCS] Cloud sync failed: {e}")
        return False


def sync_local_to_cloud() -> bool:
    """Uploads local data datasets, daily reports, and models to GCS."""
    bucket = get_or_create_bucket()
    if not bucket:
        return False
        
    print("  ☁️  [GCS] Uploading local data, models, and reports to cloud storage...")
    try:
        # Sync CSV and model files from data/
        for local_file in DATA_DIR.glob("*"):
            if local_file.is_file() and not local_file.name.startswith("."):
                upload_to_gcs(local_file, f"data/{local_file.name}")
                
        # Sync markdown and JSON reports from daily_reports/
        for local_file in REPORTS_DIR.glob("*"):
            if local_file.is_file() and not local_file.name.startswith("."):
                upload_to_gcs(local_file, f"daily_reports/{local_file.name}")
        return True
    except Exception as e:
        print(f"  ⚠️  [GCS] Local sync failed: {e}")
        return False
