import os
import datetime
import requests
from pathlib import Path
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import sync_playwright

# Import Global State
from ..state import get_user_temp_dir

# --- Shared Utilities ---

def create_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(429, 500, 502, 503, 504)) -> requests.Session:
    """Configures a requests session with automatic retry logic for resilience."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = create_session()

def short_num(n: float | int) -> str:
    """Formats large numbers into readable strings (e.g., 1.5B, 200M)."""
    try:
        n = float(n)
    except Exception:
        return str(n)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    return str(round(n))

def now_str(fmt: str = "%d-%m-%Y %H:%M:%S") -> str:
    return datetime.datetime.now().strftime(fmt)

# --- PDF Generation ---

def convert_html_to_pdf(html_content: str, user_id: str) -> Optional[Path]:
    """
    Uses Playwright (Local Chromium) to convert HTML to PDF.
    Renders exactly as defined in CSS (Scale 1.0) on US Letter paper.
    """
    print("\n   Converting to PDF (Playwright Engine)...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_name = f"{timestamp}-crypto-analysis.pdf"
    
    # Use user isolated directory
    user_dir = get_user_temp_dir(user_id)
    pdf_path = user_dir / pdf_name
        
    try:
        with sync_playwright() as p:
            # 1. Launch Browser
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 2. Load HTML
            # wait_until="networkidle" is safer to ensure styles load
            page.set_content(html_content, wait_until="networkidle")
            
            # 3. Print to PDF (US Letter, No Auto-Scaling)
            page.pdf(
                path=pdf_path,
                format="Letter",       # <--- UPDATED TO LETTER
                landscape=False,
                scale=1.0,             # <--- FORCED TO 1.0 (Exact Size)
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
            )
            browser.close()

        file_size = pdf_path.stat().st_size
        print(f"   PDF created: {pdf_name}")
        print(f"   Size: {file_size:,} bytes")
        print(f"   Location: {user_dir}")
        return pdf_path

    except Exception as e:
        print(f"   ❌ Playwright Error: {e}")
        return None

# --- File Cleanup ---

def cleanup_after_analysis(spot_file: Optional[Path], futures_file: Optional[Path]) -> int:
    """Removes source files (CSV/PDF) after successful analysis to keep the temp dir clean."""
    files_cleaned = 0
    now_date = datetime.datetime.now().date()
    
    for file_path, file_type in [(spot_file, "spot"), (futures_file, "futures PDF")]:
        if file_path and file_path.exists():
            try:
                file_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time.date() == now_date:
                    file_path.unlink()
                    print(f"   🗑️  Cleaned up {file_type} file: {file_path.name}")
                    files_cleaned += 1
            except Exception as e:
                print(f"   ⚠️  Could not remove {file_type} file: {e}")
    
    if files_cleaned > 0:
        print(f"   ✅ Cleaned up {files_cleaned} source files")
    return files_cleaned