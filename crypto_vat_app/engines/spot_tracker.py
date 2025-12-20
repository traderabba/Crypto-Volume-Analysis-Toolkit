import time
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import config
from utils import create_session, short_num, now_str

SESSION = create_session()

def fetch_coingecko(session):
    tokens = []
    print("   Scanning CoinGecko...")
    for page in range(1, 5):
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page}
        try:
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            for t in data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                volume = float(t.get("total_volume") or 0)
                marketcap = float(t.get("market_cap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CG"})
            time.sleep(0.2)
        except: continue
    print(f"   CoinGecko: {len(tokens)} tokens")
    return tokens

def fetch_coinmarketcap(session):
    tokens = []
    print("   Scanning CoinMarketCap...")
    if not config.CMC_API_KEY or "CONFIG_REQUIRED" in config.CMC_API_KEY:
        print("   ⚠️  No CMC API key")
        return tokens
    headers = {"X-CMC_PRO_API_KEY": config.CMC_API_KEY}
    for start in range(1, 1001, 100):
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {"start": start, "limit": 100, "convert": "USD"}
        try:
            r = session.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])
            for t in data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                quote = t.get("quote", {}).get("USD", {})
                volume = float(quote.get("volume_24h") or 0)
                marketcap = float(quote.get("market_cap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CMC"})
            time.sleep(0.2)
        except: continue
    print(f"   CoinMarketCap: {len(tokens)} tokens")
    return tokens

def fetch_livecoinwatch(session):
    tokens = []
    if not config.LIVECOINWATCH_API_KEY or "CONFIG_REQUIRED" in config.LIVECOINWATCH_API_KEY:
        print("   ⚠️  No LCW API key")
        return tokens
    print("   Scanning LiveCoinWatch...")
    url = "https://api.livecoinwatch.com/coins/list"
    headers = {"content-type": "application/json", "x-api-key": config.LIVECOINWATCH_API_KEY}
    payload = {"currency": "USD", "sort": "rank", "order": "ascending", "offset": 0, "limit": 1000, "meta": True}
    try:
        r = session.post(url, json=payload, headers=headers, timeout=20)
        data = r.json()
        for t in data:
            symbol = (t.get("code") or "").upper()
            if symbol in config.STABLECOINS: continue
            volume = float(t.get("volume") or 0)
            marketcap = float(t.get("cap") or 0)
            if marketcap and volume > 0.75 * marketcap:
                tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "LCW"})
    except: pass
    print(f"   LiveCoinWatch: {len(tokens)} tokens")
    return tokens

def fetch_coinrankings(session):
    tokens = []
    print("   Scanning CoinRankings...")
    if not config.COINRANKINGS_API_KEY or "CONFIG_REQUIRED" in config.COINRANKINGS_API_KEY:
        print("   ⚠️  No CR API key")
        return tokens
    headers = {"x-access-token": config.COINRANKINGS_API_KEY}
    url = "https://api.coinranking.com/v2/coins"
    for offset in range(0, 1000, 100):
        params = {"limit": 100, "offset": offset, "orderBy": "marketCap", "orderDirection": "desc"}
        try:
            r = session.get(url, headers=headers, params=params, timeout=15)
            data = r.json().get("data", {}).get("coins", [])
            for coin in data:
                symbol = (coin.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                volume = float(coin.get("24hVolume") or 0)
                marketcap = float(coin.get("marketCap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CR"})
            time.sleep(0.2)
        except: pass
    print(f"   CoinRankings: {len(tokens)} tokens")
    return tokens

def run_spot_analysis(user_id):
    print("   📊 Starting fresh spot analysis...")
    
    # Run fetches in parallel
    sources = [fetch_coingecko, fetch_coinmarketcap, fetch_livecoinwatch, fetch_coinrankings]
    results = []
    with ThreadPoolExecutor(max_workers=4) as exe:
        futures = [exe.submit(fn, SESSION) for fn in sources]
        for f in as_completed(futures):
            try:
                res = f.result(timeout=60)
                if res: results.extend(res)
            except: continue
    
    # Process Data
    all_data = {}
    for t in results:
        sym = t.get('symbol', '').upper()
        if sym: all_data.setdefault(sym, []).append(t)
    
    verified = []
    for sym, tokens in all_data.items():
        volumes = [float(t['volume']) for t in tokens]
        mcs = [float(t['marketcap']) for t in tokens]
        if not volumes or not mcs: continue
        
        avg_vol = sum(volumes)/len(volumes)
        avg_mc = sum(mcs)/len(mcs)
        ratio = avg_vol/avg_mc if avg_mc else 0
        large_cap = any(m > 1_000_000_000 for m in mcs)

        # Logic from original
        if (len(tokens) == 1 and large_cap and ratio >= 0.50) or (len(tokens) >= 2 and ratio > 0.75):
            verified.append({
                "symbol": sym, "marketcap": avg_mc, "volume": avg_vol,
                "flipping_multiple": ratio, "source_count": len(tokens), "large_cap": large_cap
            })
    
    hot_tokens = sorted(verified, key=lambda x: x['flipping_multiple'], reverse=True)
    
    # Generate HTML
    filename = f"{user_id}_Volumed_Spot_Tokens.html"
    save_path = config.UPLOAD_FOLDER / filename
    
    html = """<h1>SPOT VOLUME REPORT</h1><table><tr><th>Rank</th><th>Ticker</th><th>MC</th><th>Vol</th><th>VTMR</th></tr>"""
    for i, t in enumerate(hot_tokens):
        html += f"<tr><td>#{i+1}</td><td>{t['symbol']}</td><td>{short_num(t['marketcap'])}</td><td>{short_num(t['volume'])}</td><td>{t['flipping_multiple']:.1f}x</td></tr>"
    html += "</table>"
    
    with open(save_path, "w", encoding="utf-8") as f: f.write(html)
    print(f"   ✅ Found {len(hot_tokens)} high-volume tokens.")