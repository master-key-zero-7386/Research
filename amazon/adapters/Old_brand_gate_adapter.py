# amazon ブランドケート
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime

from .base_adapter import BrandGateAdapter
from utils.spapi_client import load_config
from sp_api.base import Marketplaces
from sp_api.api import Sellers
from utils.spapi_client import real_signed_request
import os
from utils.spapi_client import get_item_dimensions
from utils.spapi_client import get_catalog_item
from utils.config_loader import cfg, get_debug_mode

# SP-APIの Listings Restrictions を使う実装
# 参考: https://github.com/saleweaver/python-amazon-sp-api
from sp_api.api import ListingsRestrictions

def _resolve_key_case_insensitive(d: Dict[str, Any], region: str) -> str | None:
    """regionキーを大小文字/前後空白を無視して解決（不一致時は None を返す）"""
    if not isinstance(d, dict) or not d:
        return None
    region_norm = (region or "").strip() 
    norm_map = { (str(k or "")).strip().lower(): k for k in d.keys() } 

    for cand in (region_norm, region_norm.upper(), region_norm.lower()):
        if cand in d:
            return cand

    return norm_map.get(region_norm.lower()) 

def _resolve_marketplace_id(cfg: Dict[str, Any], region: str) -> str | None:
    """
    config.json から region に対応する marketplace_id を解決
    優先: marketplace → account
    """

    def _pick_id(x: Any) -> str | None:
        # 設定の書き方の揺れに対応：dict / str / list の全部を許容
        if isinstance(x, dict):
            return (
                x.get("marketplace_id")
                or x.get("marketplaceId")
                or x.get("id")
                or (x.get("marketplaceIds")[0] if isinstance(x.get("marketplaceIds"), (list, tuple)) and x.get("marketplaceIds") else None)
                or x.get("MP")
                or x.get("mp")
            )
        if isinstance(x, str):
            return x.strip() or None
        if isinstance(x, (list, tuple)) and x:
            return (x[0] if isinstance(x[0], str) else None)
        return None

    rk_market = _resolve_key_case_insensitive(cfg.get("marketplace", {}), region)
    if rk_market:
        mid = _pick_id((cfg.get("marketplace") or {}).get(rk_market))
        if mid:
            return mid

    rk_acct = _resolve_key_case_insensitive(cfg.get("account", {}), region)
    if rk_acct:
        mid = _pick_id((cfg.get("account") or {}).get(rk_acct))
        if mid:
            return mid

    return None

def _resolve_marketplace_host(cfg: Dict[str, Any], region: str) -> str:
    """
    config.json から region に対応する SP-API ホストを解決
    優先: marketplace → account
    見つからなければ NA を返す
    """
    def _pick_host(x: Any) -> str | None:
        if isinstance(x, dict):
            return x.get("host")
        return None

    rk_market = _resolve_key_case_insensitive(cfg.get("marketplace", {}), region)
    if rk_market:
        h = _pick_host((cfg.get("marketplace") or {}).get(rk_market))
        if h: 
            return h

    rk_acct = _resolve_key_case_insensitive(cfg.get("account", {}), region)
    if rk_acct:
        h = _pick_host((cfg.get("account") or {}).get(rk_acct))
        if h: 
            return h

    # 保険として NA を返す
    return "https://sellingpartnerapi-na.amazon.com"

def _region_bucket_from_host(host: str) -> str:
    h = (host or "").lower()
    if "sellingpartnerapi-na" in h:  # 北米
        return "na"
    if "sellingpartnerapi-fe" in h:  # 極東（JP/AU/SG/IN）
        return "fe"
    if "sellingpartnerapi-eu" in h:  # 欧州
        return "eu"
    return "na"

class AmazonBrandGateAdapter(BrandGateAdapter):
    def __init__(self, skip_sellers_check: bool = False):
        self.skip_sellers_check = skip_sellers_check
        self._cache_jp_brand: Dict[str, str] = {} 

    def check_brand_gate(self, asins: List[str], region: str) -> Dict[str, Any]:
        """複数ASIN×単一リージョンのブランドゲート判定"""

        now = datetime.utcnow().isoformat() + "Z"
        asins = [a.strip() for a in asins or [] if a and a.strip()]
        region = (region or "").strip().upper()
        items_out: List[Dict[str, Any]] = []

        try:
            cfg = load_config()

            for asin in asins:
                row: Dict[str, Any] = {"asin": asin, "note": ""}

                # --- Brand(JP) 抽出処理 ---
                if asin in self._cache_jp_brand:
                    row["brand_jp"] = self._cache_jp_brand[asin]
                else:
                    brand_jp = ""

                    try:
                        jp_mp = (cfg.get("marketplace", {}).get("JP") or {}).get("marketplace_id")

                        jp_catalog = get_catalog_item(asin=asin, region="JP") or {}
                        summaries = jp_catalog.get("summaries") or []
                        attrs = jp_catalog.get("attributes") or {}

                        if summaries and summaries[0].get("brand"):
                            brand_jp = summaries[0]["brand"]
                        elif attrs.get("brand", {}).get("values"):
                            brand_jp = attrs["brand"]["values"][0].get("value") or ""
                        elif attrs.get("brandName", {}).get("values"):
                            brand_jp = attrs["brandName"]["values"][0].get("value") or ""
                        elif attrs.get("manufacturer", {}).get("values"):
                            brand_jp = attrs["manufacturer"]["values"][0].get("value") or ""
                    except Exception as e:
                        if get_debug_mode():
                            print(f"[WARN] brand_jp resolve failed asin={asin}: {e}", flush=True)

                    self._cache_jp_brand[asin] = brand_jp
                    row["brand_jp"] = brand_jp
                # -------------------------

                    mp = _resolve_marketplace_id(cfg, region)
                    if not mp:
                        row["status"] = "未設定"
                        row["note"] = (row.get("note") or "") + f"[{region}: missing marketplace_id]"
                        items_out.append(row)
                        continue

                    rk_lwa  = _resolve_key_case_insensitive(cfg.get("lwa", {}), region)
                    rk_acct = _resolve_key_case_insensitive(cfg.get("account", {}), region)

                    lwa_entry = (cfg.get("lwa") or {}).get(rk_lwa) if rk_lwa else None
                    acct_entry = (cfg.get("account") or {}).get(rk_acct) if rk_acct else None

                    client_id = (
                        (lwa_entry or {}).get("client_id")
                        or (lwa_entry or {}).get("clientId")
                        or (lwa_entry or {}).get("app_id")
                        or (lwa_entry or {}).get("lwa_app_id")
                    )

                    client_secret = (
                        (lwa_entry or {}).get("client_secret")
                        or (lwa_entry or {}).get("clientSecret")
                        or (lwa_entry or {}).get("secret")
                        or (lwa_entry or {}).get("lwa_client_secret")
                    )

                    refresh_token = (acct_entry or {}).get("refresh_token")
                    # --- デバッグ行は削除（常時Noteに出さない）
                    #row["note"] = (row.get("note") or "") + f"[DBG region={region} rk_lwa={rk_lwa} rk_acct={rk_acct} has_lwa={isinstance(lwa_entry, dict)} has_acct={isinstance(acct_entry, dict)} cid={'Y' if client_id else 'N'} sec={'Y' if client_secret else 'N'} rt={'Y' if refresh_token else 'N'}]"

                    row.setdefault("dbg_creds", {})            
                    row["dbg_creds"][region] = {                           
                        "client_id": bool(client_id),                   
                        "client_secret": bool(client_secret),           
                        "refresh_token": bool(refresh_token)            
                    } 

                    # 必須欠如ならAPIを呼ばずにスキップ
                    if not refresh_token:
                        row["status"] = "未設定"
                        row["note"] = (row.get("note") or "") + f"[{region}: refresh_token 未設定]"
                        items_out.append(row)
                        continue

                    seller_id = (acct_entry or {}).get("seller_id")
                    if not seller_id:
                        row["status"] = "未設定"
                        row["note"] = (row.get("note") or "") + f"[{region}: missing seller_id]"
                        items_out.append(row)
                        continue                 

                    # sp-api にトークン取得を任せる（access_token は渡さない）
                    aws = (cfg.get("aws") or {})
                    aws_key = aws.get("base_access_key_id") or aws.get("aws_access_key_id") or aws.get("access_key")
                    aws_secret = aws.get("base_secret_access_key") or aws.get("aws_secret_access_key") or aws.get("secret_access_key")

                    credentials = {
                        "lwa_app_id": client_id,
                        "lwa_client_secret": client_secret,
                        # ライブラリは 'refresh_token' キー名を推奨
                        "refresh_token": refresh_token,
                    }
                    # AWS 署名キーがあるなら添える（あれば精度↑、無ければ省略でも動く場合あり）
                    if aws_key and aws_secret:
                        credentials["aws_access_key"] = aws_key
                        credentials["aws_secret_key"] = aws_secret

                    # --- legacy: 分離前と同じ直署名リクエストに戻す ---
                    # reasonLocale を旧コード通りに付ける
                    _locale_map = {"US": "en_US", "JP": "ja_JP", "AU": "en_AU", "SG": "en_US"}
                    reason_locale = _locale_map.get(region, "en_US")

                    host = _resolve_marketplace_host(cfg, region)

                    # パラメータ（sellerId は“あれば付ける”）
                    params = {
                        "asin": asin.upper(),
                        "marketplaceIds": [mp],
                        "reasonLocale": reason_locale,
                        "conditionType": "new_new",
                    }
                    if seller_id:
                        params["sellerId"] = seller_id

                    _market_enum = {"US": Marketplaces.US, "JP": Marketplaces.JP, "AU": Marketplaces.AU, "SG": Marketplaces.SG}
                    market_enum = _market_enum.get(region)

                    creds = {
                        "lwa_app_id": client_id,
                        "lwa_client_secret": client_secret,
                        "refresh_token": refresh_token,
                    }
                    if aws_key and aws_secret:
                        creds["aws_access_key"] = aws_key
                        creds["aws_secret_key"] = aws_secret

                    try:
                        if not self.skip_sellers_check and market_enum:
                            Sellers(credentials=creds, marketplace=market_enum).get_marketplace_participations()

                        lr = ListingsRestrictions(credentials=creds, marketplace=market_enum)
                        r = lr.get_listings_restrictions(
                            asin=asin.upper(),
                            conditionType="new_new",
                            sellerId=seller_id,
                            reasonLocale=reason_locale,
                            marketplaceIds=[mp],
                        )
                        payload = getattr(r, "payload", None) or (r or {})
                    except Exception as e:
                        row["status"] = "エラー"
                        row["note"] = (row.get("note") or "") + f"[{region}: {str(e)[:180]}]"
                        items_out.append(row)
                        continue

                    restrictions = payload.get("restrictions") or []

                    if not restrictions:
                        row["status"] = "〇"
                    else:
                        needs_approval = False
                        hard_block = False
                        reason_codes = []

                        for it in restrictions:
                            reasons = it.get("reasons") or []
                            for r in reasons:
                                code = (r.get("reasonCode") or r.get("code") or "").upper()
                                msg  = (r.get("message") or "").upper()
                                blob = f"{code} {msg}"
                                reason_codes.append(code or "UNKNOWN")

                                if any(k in blob for k in ["APPROVAL_REQUIRED", "REQUIRES_APPROVAL", "REQUEST_APPROVAL", "PRE_APPROVAL"]):
                                    needs_approval = True

                                if any(k in blob for k in ["RESTRICTED", "NOT_ALLOWED", "NOT_ELIGIBLE", "NOT_PERMITTED", "UNAUTHORIZED"]):
                                    hard_block = True

                        if hard_block:
                            row["status"] = "✕"
                        elif needs_approval:
                            row["status"] = "△"
                        else:
                            row["status"] = "✕"


                items_out.append(row)
            return {"items": items_out, "as_of": now, "status": "ok", "reason": "ok"}

        except Exception as e:
            msg = str(e)
            reason = (
                "api_error_invalid_grant"
                if "invalid_grant" in msg
                else ("api_error_throttled" if ("Throttled" in msg or "429" in msg) else "api_error")
            )
            return {"items": items_out, "as_of": now, "status": "error", "reason": reason, "message": msg}
