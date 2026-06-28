from typing import Dict, Any, Optional, List
from sp_api.base import Marketplaces, SellingApiException
from sp_api.api import CatalogItems
import json, os
import time
import hmac, hashlib, base64
from urllib.parse import urlencode
import logging
from urllib.parse import urlencode
import requests
import inspect 

from amazon.auth.token_manager import get_access_token
import os
from utils.config_loader import cfg, get_debug_mode

def _get_mpid(region: str, cfg: dict) -> str:
    mp = (cfg.get("marketplace") or {})
    mp_entry = mp.get((region or "").upper())
    if not mp_entry:
        raise ValueError(f"MarketplaceId not configured for region={region}")
    return mp_entry.get("marketplace_id")

def real_signed_request(method, path, params, host, cfg):
    """
    本番用：必ず SP-API に投げる（LWA取得 + SigV4署名 + GET）
    - params['marketplaceId'] を前提に、対象リージョンの LWA refresh_token を選ぶ
    - AWSアクセスキーは環境変数（AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN）から取得
    - 成功時は dict(JSON) を返す（既存シグネチャ互換）
    """
    import os, datetime, hmac, hashlib, requests
    from urllib.parse import urlencode
    from amazon.auth.token_manager import get_access_token

    need_mp = not (path or "").startswith("/sellers/") 
    if (not isinstance(params, dict)) or (need_mp and not params.get("marketplaceIds")):
        raise RuntimeError("real_signed_request: params['marketplaceIds'] が必須")

    mpids = params.get("marketplaceIds") or []       
    marketplace_id = (mpids[0] if (mpids and isinstance(mpids, (list, tuple))) else (mpids or None))
    params.pop("marketplaceId", None)   

    # marketplaceId から region キーを逆引き
    def _region_key_from_mp(mp_):
        for reg, mid in (cfg.get("marketplace") or {}).items():
            if mp_ == mid.get("marketplace_id"): 
                return reg.upper() 
        return None

    region_key = _region_key_from_mp(marketplace_id)

    # --- LWA クレデンシャル＆refresh_token を config から取得 ---
    lwa = cfg.get("lwa") or {}
    rk = (region_key or "").upper()   # ←必ず大文字キーに統一

    region_lwa = lwa.get(rk) or {}
    client_id = region_lwa.get("client_id") or lwa.get("client_id")
    client_secret = region_lwa.get("client_secret") or lwa.get("client_secret")

    if not client_id or not client_secret:
        raise RuntimeError(f"LWA client_id/secret 未設定: region={rk}")

    # refresh_token は account セクションから取得（大文字キーで統一）
    acct_entry = (cfg.get("account") or {}).get(rk) or {}
    refresh_token = acct_entry.get("refresh_token")
    if not refresh_token:
        raise RuntimeError(f"refresh_token 未設定: region={rk}")

    # ③ LWA アクセストークン
    access_token = get_access_token(client_id, client_secret, refresh_token)

    #LWA通過状況確認用
    if get_debug_mode():
        print(f"[DBG] LWA token ok len={len(access_token or '')}", flush=True)


    # URL とベースヘッダ
    query = urlencode(params or {}, doseq=True)
    url = f"{host}{path}" + (f"?{query}" if query else "")
    headers = {
        "accept": "application/json",
        "x-amz-access-token": access_token,
    }

    # AWS 認証情報（環境変数から）
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID") or (cfg.get("aws") or {}).get("base_access_key_id")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or (cfg.get("aws") or {}).get("base_secret_access_key")
    aws_session    = os.getenv("AWS_SESSION_TOKEN")  # 任意
    if not aws_access_key or not aws_secret_key:
        raise RuntimeError("AWS クレデンシャル未設定（AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY）")

    # エンドポイントから署名リージョンを推定
    if "-na." in host:
        aws_region = "us-east-1"
    elif "-eu." in host:
        aws_region = "eu-west-1"
    else:  # -fe.
        aws_region = "us-west-2"

    # ---- SigV4 署名（GETは空ボディ） ----
    def _hmac(key, msg): return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    service = "execute-api"

    scheme_sep = "://"
    host_and_path = url.split(scheme_sep, 1)[-1]
    host_only = host_and_path.split("/", 1)[0]
    path_and_q = host_and_path[len(host_only):] or "/"
    path_only, qs = (path_and_q.split("?", 1) + [""])[:2]

    headers["host"] = host_only
    headers["x-amz-date"] = amz_date
    if aws_session:
        headers["x-amz-security-token"] = aws_session

    signed_headers_list = ["host", "x-amz-date"] + (["x-amz-security-token"] if aws_session else [])
    signed_headers = ";".join(signed_headers_list)
    canonical_headers = "".join(f"{h}:{headers[h]}\n" for h in signed_headers_list)
    canonical_q = "&".join(sorted(qs.split("&"))) if qs else ""
    payload_hash = hashlib.sha256(b"").hexdigest()

    canonical_request = "\n".join([
        method,
        path_only if path_only.startswith("/") else "/" + path_only,
        canonical_q,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{aws_region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        algorithm,
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    kDate = _hmac(("AWS4" + aws_secret_key).encode("utf-8"), date_stamp)
    kRegion = hmac.new(kDate, aws_region.encode("utf-8"), hashlib.sha256).digest()
    kService = hmac.new(kRegion, service.encode("utf-8"), hashlib.sha256).digest()
    kSigning = hmac.new(kService, b"aws4_request", hashlib.sha256).digest()
    signature = hmac.new(kSigning, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers["Authorization"] = (
        f"{algorithm} Credential={aws_access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    # ---- 署名ここまで ----
    resp = requests.request(method, url, headers=headers, timeout=30)

    if get_debug_mode():
        print("[SP-API] RequestId:", resp.headers.get("x-amzn-RequestId"), flush=True)

    if resp.status_code >= 400:  
        if get_debug_mode():
            print(f"[SP-API][ERR] {resp.status_code} body={resp.text[:500]}")

        if resp.status_code == 404:
            # ASINが存在しない場合はJSONそのまま返す
            return resp.json()

        resp.raise_for_status()

    return resp.json()

# リージョン→MarketplaceId
def get_marketplace_id(region: str, cfg: dict) -> str:
    return _get_mpid(region, cfg)

def load_config() -> dict:
    """
    config/config.json を読み込む
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))  # /zsss_web
    config_path = os.path.join(base_dir, "config", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _included_data() -> List[str]:
    return ["dimensions"]

def get_catalog_item_direct(asin: str, region: str, cfg: dict):
    path = f"/catalog/2022-04-01/items/{asin}"

    mpid = _get_mpid(region, cfg)
    locale_map = {
        "US": "en_US",
        "JP": "ja_JP",
        "AU": "en_AU",
        "SG": "en_SG",
    }
    locale_str = locale_map.get(region.upper(), "en_US")

    params = {
        "marketplaceIds": [mpid],
        "includedData": "attributes,dimensions,summaries,images,productTypes,salesRanks",
        "locale": locale_str,
    }

    cfg = load_config()
    host = get_host_for_region(region)
    resp = real_signed_request("GET", path, params, host, cfg)

    if hasattr(resp, "json"):
        data = resp.json()
    else:
        data = resp
    return data

def get_catalog_item(asin: str, region: str) -> dict:
    cfg = load_config()

    rk_lwa  = region.upper()
    rk_acct = region.upper()

    lwa_entry = (cfg.get("lwa") or {}).get(rk_lwa, {})
    acct_entry = (cfg.get("account") or {}).get(rk_acct, {})

    client_id = (
        lwa_entry.get("client_id")
        or lwa_entry.get("clientId")
        or lwa_entry.get("app_id")
        or lwa_entry.get("lwa_app_id")
    )
    client_secret = (
        lwa_entry.get("client_secret")
        or lwa_entry.get("clientSecret")
        or lwa_entry.get("secret")
        or lwa_entry.get("lwa_client_secret")
    )
    refresh_token = acct_entry.get("refresh_token")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError(f"LWA/refresh_token 未設定: region={region}")

    mpid = _get_mpid(region, cfg)
    locale_map = {"US": "en_US", "JP": "ja_JP", "AU": "en_AU", "SG": "en_US"}
    locale_str = locale_map.get(region.upper(), "en_US")

    params = {
        "marketplaceIds": [mpid],
        "includedData": "attributes,dimensions,summaries,images,productTypes,salesRanks",
        "locale": locale_str,
    }

    host = get_host_for_region(region)
    resp = real_signed_request("GET", f"/catalog/2022-04-01/items/{asin}", params, host, cfg)

    data = resp.json() if hasattr(resp, "json") else resp
    return data

# --- amazonサイズ情報抽出 ---
def get_item_dimensions(asin: str, region: str) -> Dict[str, Any]:
    """
    ASIN と リージョン（US/AU/SG/JP）を受け取り、寸法・重量を返す
    """
    cfg = load_config()
    region = (region or "").upper()

    mp_cfg = (cfg.get("marketplace") or {}).get(region)

    if not mp_cfg:
        raise ValueError(f"Unsupported region: {region}. Use one of {list((cfg.get('marketplace') or {}).keys())}")

    marketplace_id = mp_cfg.get("marketplace_id")

    # config から LWA 情報と Refresh Token を取得
    config = load_config()
    client_id = config["lwa"][region]["client_id"]
    client_secret = config["lwa"][region]["client_secret"]
    
    acct_entry = (config.get("account") or {}).get(region)
    if not acct_entry or not acct_entry.get("refresh_token"):
        raise KeyError(f"config.account[{region}] の refresh_token が未設定です")

    refresh_token = acct_entry["refresh_token"]

    access_token = get_access_token(client_id, client_secret, refresh_token)

    aws = (config.get("aws") or {})
    ak = os.getenv("AWS_ACCESS_KEY_ID") or aws.get("base_access_key_id") or aws.get("aws_access_key_id") or aws.get("aws_access_key")
    sk = os.getenv("AWS_SECRET_ACCESS_KEY") or aws.get("base_secret_access_key") or aws.get("aws_secret_access_key") or aws.get("secret_access_key")
    tk = os.getenv("AWS_SESSION_TOKEN") or aws.get("session_token")

    # --- 署名前にヘッダをまとめる ---
    _req_headers = (headers or {}).copy()
    _req_headers["x-amz-access-token"] = access_token
    if tk:
        _req_headers["x-amz-security-token"] = tk

    # --- AWSRequestを生成 ---
    req = AWSRequest(method=method, url=url, data=body, params=params, headers=_req_headers)

    # --- 署名（STS tkも渡す）---
    SigV4Auth(Credentials(ak, sk, tk), "execute-api", aws_region).add_auth(req)

    # --- デバッグ出力 ---
    auth_header = req.headers.get("Authorization", "")
    sh = ""
    if "SignedHeaders=" in auth_header:
        sh = auth_header.split("SignedHeaders=")[1].split(",")[0]

    credentials = {
        "lwa_app_id": client_id,
        "lwa_client_secret": client_secret,
        "lwa_refresh_token": refresh_token, 
        "aws_access_key": ak,             
        "aws_secret_key": sk,             
        #"aws_session_token": tk,          
    }


    try:
        mpid = _get_mpid(region, cfg)                           
        api_region = "na" if region.upper() == "US" else _resolve_api_region(region, cfg)
        host = "https://sellingpartnerapi-na.amazon.com" if region.upper() == "US" else None
        client = CatalogItems(
            marketplace=mpid,
            region=api_region,
            **({} if host is None else {"host": host}),
            **credentials
        )

        res_obj = client.get_catalog_item(
            asin=asin,
            marketplaceIds=[mpid],
            includedData="attributes,dimensions,summaries,images,productTypes,salesRanks,relationships,identifiers",
        )

        res = res_obj.payload or {}

    except SellingApiException as e:
        raise RuntimeError(f"SP-API get_catalog_item failed: {e}") from e


    # payload から dimensions を抽出
    dims = res.get("dimensions")
    item_dims = item_wt = pkg_dims = pkg_wt = None
    category = None 
    image_url = None

    # --- カテゴリ & 画像 取得（堅牢版） ---  
    summaries = (res.get("summaries") or [])
    images_top = None
    if summaries:
        s = summaries[0]
        # 画像（summaries配下）
        imgs = (s.get("images") or [])
        if imgs:
            images_top = imgs[0]
            image_url = images_top.get("link")  # この行を修正（値があれば更新）
        # カテゴリ（summaries配下の候補）
        category = category or s.get("productType")  
        if not category:
            bn = s.get("browseNode") or {}
            category = bn.get("displayName")  

    # productTypes（トップ階層）も見る
    pts = (res.get("productTypes") or [])  
    if not category and pts:
        pt0 = pts[0] or {}
        category = pt0.get("productType")  

    # attributes 側の item_type_name も最後のフォールバックに
    attrs = res.get("attributes") or {}  
    if not category:
        itn = attrs.get("item_type_name") or []
        if itn and isinstance(itn, list) and isinstance(itn[0], dict):
            category = itn[0].get("value")  

    # 画像が summaries に無いケース用：images（トップ階層）を見る
    if not image_url:
        img_arr = res.get("images") or []
        if img_arr and isinstance(img_arr, list) and isinstance(img_arr[0], dict):
            image_url = img_arr[0].get("link")  


    def _pick_hwL(src: dict) -> dict:
        if not isinstance(src, dict):
            return {}
        out = {}
        for k in ("height", "length", "width"):
            if k in src:
                out[k] = src[k]
        return out

    if isinstance(dims, dict):
        if any(k in dims for k in ("itemDimensions", "packageDimensions")):
            item_dims = dims.get("itemDimensions")
            item_wt   = dims.get("itemWeight")
            pkg_dims  = dims.get("packageDimensions")
            pkg_wt    = dims.get("packageWeight")
        else:
            item     = dims.get("item") or {}
            package  = dims.get("package") or {}
            item_dims = _pick_hwL(item)
            pkg_dims  = _pick_hwL(package)
            item_wt   = item.get("weight")
            pkg_wt    = package.get("weight")

    elif isinstance(dims, list):
        match = next((d for d in dims if d.get("marketplaceId") == marketplace_id), dims[0] if dims else None)

        if isinstance(match, dict):
            if any(k in match for k in ("itemDimensions", "packageDimensions")):
                item_dims = match.get("itemDimensions")
                item_wt   = match.get("itemWeight")
                pkg_dims  = match.get("packageDimensions")
                pkg_wt    = match.get("packageWeight")
            else:
                item     = match.get("item") or {}
                package  = match.get("package") or {}
                item_dims = _pick_hwL(item)
                pkg_dims  = _pick_hwL(package)
                item_wt   = item.get("weight")
                pkg_wt    = package.get("weight")


    # --- ランキング抽出（salesRanks 新スキーマ対応） ---
    rank_category = "--"
    rank_value = "--"

    sr = res.get("salesRanks") or []
    sr0 = next((x for x in sr if x.get("marketplaceId") == marketplace_id), (sr[0] if sr else None))

    if isinstance(sr0, dict):
        ranks = sr0.get("classificationRanks") or sr0.get("displayGroupRanks") or []
        if isinstance(ranks, list) and ranks:
            top = sorted(ranks, key=lambda r: (r.get("rank") or 10**12))[0]
            rank_category = top.get("title") or rank_category
            rv = top.get("rank")
            rank_value = str(rv) if rv is not None else "--"

    return {
        "itemDimensions": item_dims,
        "itemWeight": item_wt,
        "packageDimensions": pkg_dims,
        "packageWeight": pkg_wt,
        "category": category,
        "image_url": image_url,
        "rank_category": rank_category,
        "rank_value": rank_value, 
        "raw": res,
    }

# --- amazon価格情報抽出 ---
def get_pricing_summary(asin: str, region: str, cfg: dict):
    """
    Product Pricing API から価格サマリを取得
    - Buy Box / Lowest(新品/中古) / ListPrice を raw JSON で返す
    """
    path = "/products/pricing/v0/price"
    mpid = _get_mpid(region, cfg)
    params = {
        "MarketplaceId": mpid,
        "Asins": [asin],
        "ItemType": "Asin",
    }

    # host 解決（restrictions で使っている分岐と同じロジック）
    if region.upper() in ("US", "CA", "MX"):
        host = "https://sellingpartnerapi-na.amazon.com"
    elif region.upper() in ("AU", "SG", "IN", "JP"):
        host = "https://sellingpartnerapi-fe.amazon.com"
    else:  # EU 他
        host = "https://sellingpartnerapi-eu.amazon.com"

    resp = real_signed_request("GET", path, params=params, host=host, cfg=cfg)
    return resp  # raw を返す（routes 側で必要分だけ抜く）

# リージョン→SP-API Host マップ
REGION_HOST_MAP = {
    "US": "https://sellingpartnerapi-na.amazon.com",
    "CA": "https://sellingpartnerapi-na.amazon.com",
    "MX": "https://sellingpartnerapi-na.amazon.com",
    "JP": "https://sellingpartnerapi-fe.amazon.com",
    "AU": "https://sellingpartnerapi-fe.amazon.com",
    "SG": "https://sellingpartnerapi-fe.amazon.com",
    # EU各国 → https://sellingpartnerapi-eu.amazon.com
}

def get_host_for_region(region: str) -> str:
    REGION_HOST_MAP = {
        "US": "https://sellingpartnerapi-na.amazon.com",
        "CA": "https://sellingpartnerapi-na.amazon.com",
        "MX": "https://sellingpartnerapi-na.amazon.com",
        "JP": "https://sellingpartnerapi-fe.amazon.com",
        "AU": "https://sellingpartnerapi-fe.amazon.com",
        "SG": "https://sellingpartnerapi-fe.amazon.com",
        # EU各国 → デフォルトに寄せる
    }
    return REGION_HOST_MAP.get(region.upper(), "https://sellingpartnerapi-eu.amazon.com")

def _resolve_refresh_token(region: str, config: dict) -> str:
    """
    config から region ごとの refresh_token を取得する。
    無ければ例外で落とし、間違ったトークン流用を絶対にしない。
    """
    try:
        # account.* に優先して保存している場合はこちらから
        token = (config.get("account", {}).get(region.upper(), {}) or {}).get("refresh_token")
        if token: 
            return token

        raise ValueError(f"refresh_token 未設定: account[{region.upper()}]")
    except Exception as e:
        raise ValueError(f"refresh_token 取得失敗: {e}")

def check_asin_restrictions(asin: str, region: str, lwa_client_id: str, lwa_client_secret: str, config: dict) -> dict:
    """
    Listings Restrictions API を“正しいホスト＆その国のリフレッシュトークン”で叩く。
    返り値: {'asin':..., 'marketplaceId':..., 'status': 'OK|NeedsApproval|NotAllowed', 'reason_codes': [...], 'debug': 'host=... mp=...'}
    """
    import requests
    from amazon.auth.token_manager import get_access_token

    host = get_host_for_region(region)
    marketplace_id = _get_mpid(region, config)

    refresh_token = _resolve_refresh_token(region, config)

    access_token = get_access_token(lwa_client_id, lwa_client_secret, refresh_token)

    url = f"{host}/listings/2021-08-01/restrictions"
    params = {"asin": asin, "marketplaceIds": [marketplace_id], "conditionType": "new_new"} 
    headers = {"x-amz-access-token": access_token, "content-type": "application/json"}

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    data = resp.json() if resp.content else {}
    reasons = []
    status = "OK"

    arr = data.get("restrictions", [])
    for r in arr:
        for rs in r.get("reasons", []):
            rc = rs.get("reasonCode")
            if rc:
                reasons.append(rc)
    if any(rc == "NOT_LISTABLE" for rc in reasons):
        status = "NotAllowed"
    elif any("NEEDS_APPROVAL" in rc for rc in reasons):
        status = "NeedsApproval"

    debug = f"host={host} mp={marketplace_id} asin={asin} reasons={reasons}"
    return {"asin": asin, "marketplaceId": marketplace_id, "status": status, "reason_codes": reasons, "debug": debug}



