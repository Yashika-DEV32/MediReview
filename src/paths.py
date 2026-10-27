from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = ROOT / "data" / "raw"
PROCESSED_DATA = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
for folder in (RAW_DATA, PROCESSED_DATA, ARTIFACTS, MODELS, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)
