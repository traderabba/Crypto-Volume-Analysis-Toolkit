import os
import threading
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage

# ==============================
# GLOBAL PATHS & STATE
# ==============================
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Default to local cwd if no other path found
REPORT_SAVE_PATH = Path.cwd()

# Global Threading State
LIVE_LOGS = []
PROGRESS = {"percent": 0, "text": "System Idle", "status": "idle"}
LOCK = threading.Lock()

# ==============================
# API KEYS & CONFIG (Defaults)
# ==============================
HTML2PDF_API_KEY = 'CONFIG_REQUIRED_HTML2PDF'
CMC_API_KEY = 'CONFIG_REQUIRED_CMC'
LIVECOINWATCH_API_KEY = 'CONFIG_REQUIRED_LCW'
COINRANKINGS_API_KEY = 'CONFIG_REQUIRED_CR'
COINALYZE_VTMR_URL = 'CONFIG_VTMR_URL'

STABLECOINS = {
    'USDT', 'USDC', 'BUSD', 'DAI', 'BSC-USD', 'USD1', 'CBBTC', 'WBNB', 'WETH',
    'UST', 'TUSD', 'USDP', 'USDD', 'FRAX', 'GUSD', 'LUSD', 'FDUSD'
}

# ==============================
# FIREBASE HELPER
# ==============================
class FirebaseHelper:
    _db = None
    _bucket = None
    _initialized = False

    @classmethod
    def initialize(cls):
        if not cls._initialized:
            try:
                cred_path = BASE_DIR / "firebase_credentials.json"
                if cred_path.exists():
                    cred = credentials.Certificate(str(cred_path))
                    # Attempt to init with storage, but don't crash if it fails later
                    try:
                        firebase_admin.initialize_app(cred, {
                            'storageBucket': 'YOUR_PROJECT_ID.appspot.com' 
                        })
                        cls._bucket = storage.bucket()
                    except Exception:
                        # Fallback for Firestore-only (No Storage)
                        if not len(firebase_admin._apps):
                            firebase_admin.initialize_app(cred)
                        cls._bucket = None
                    
                    cls._db = firestore.client()
                    cls._initialized = True
                    print("   ✅ Firebase Auth & DB Connected")
                    if cls._bucket: print("   ✅ Firebase Storage Connected")
                    else: print("   ⚠️  Firebase Storage Disabled (Local Mode)")
                else:
                    print("   ⚠️  firebase_credentials.json missing.")
            except Exception as e:
                print(f"   ❌ Firebase Init Error: {e}")
        return cls._db, cls._bucket

    @staticmethod
    def upload_report(user_id: str, local_path: Path):
        _, bucket = FirebaseHelper.initialize()
        # [MODIFICATION] If no bucket, return None immediately (Skip Upload)
        if not bucket:
            return None
            
        try:
            blob = bucket.blob(f"reports/{user_id}/{local_path.name}")
            blob.upload_from_filename(str(local_path))
            blob.make_public()
            return blob.public_url
        except Exception:
            return None

    @staticmethod
    def log_activity(user_id: str, action: str):
        db, _ = FirebaseHelper.initialize()
        if db:
            try:
                db.collection('analytics').add({
                    'uid': user_id,
                    'action': action,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
            except: pass