# Amazon API（Amazon固有の実装。ASINを product_id として扱う）
from typing import Optional, Dict, Any
from .base_adapter import BaseMarketplaceAdapter
import os, json, requests
from .base_adapter import PricingAdapter
from datetime import datetime 
from utils.spapi_client import real_signed_request
from utils.config_loader import cfg, get_debug_mode

REGION_CFG = {
    "US": {"locale": "en_US", "host": "https://sellingpartnerapi-na.amazon.com"},
    "AU": {"locale": "en_AU", "host": "https://sellingpartnerapi-fe.amazon.com"},
    "SG": {"locale": "en_US", "host": "https://sellingpartnerapi-fe.amazon.com"},
    "JP": {"locale": "ja_JP", "host": "https://sellingpartnerapi-fe.amazon.com"},
}

class AmazonAdapter(BaseMarketplaceAdapter):
    """
    Amazon用Adapter。product_id は ASIN とみなす（当面）。
    後で Listings Prices API などの実呼び出しを内部で実装する。
    """

    def __init__(self, cfg: Dict[str, Any]):
        # cfg にはリージョン別クレデンシャル/LWA/keys などを想定
        self.cfg = cfg

    def update_price(
        self,
        product_id: str,
        price: float,
        currency: str,
        region: Optional[str] = None,
        marketplace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        region または marketplace_id を元に MarketplaceId を解決
        """
        if not marketplace_id and region:
            marketplace_id = (self.cfg.get("marketplace") or {}).get(region.upper())

        return {
            "status": "not_implemented",
            "op": "update_price",
            "product_id": product_id,
            "price": price,
            "currency": currency,
            "region": region,
            "marketplace_id": marketplace_id,
        }

    def get_product_info(
        self,
        asin: str,
        region: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        現時点は分離のための“空実装”。routes側で従来処理にフォールバックする。
        """
        marketplace_id = (self.cfg.get("marketplace") or {}).get(region.upper())
        return {
            "status": "not_implemented",
            "asin": asin,
            "region": region,
            "marketplace_id": marketplace_id,
        }


    def get_catalog_item(self, asin: str, source_region: str = "JP"):
        region_key = (source_region or "JP").upper() 
        """
        Catalog Items (2022-04-01) の取得（リージョン可変対応）。
        """
        try:
            region_key = (source_region or "JP").upper()    

            # config.json 読み込み（adapters からは 3 階層 up）
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "config.json",
            )
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # LWA 認証情報
            lwa_block = config.get("lwa", {})
            lwa = lwa_block.get(region_key) or lwa_block.get(region_key.lower()) or {}
            client_id = lwa.get("client_id", "")
            client_secret = lwa.get("client_secret", "")

            acct_block = config.get("account", {})
            acct = acct_block.get(region_key) or acct_block.get(region_key.lower()) or {}
            refresh_token = acct.get("refresh_token", "")

            if not (client_id and client_secret and refresh_token):
                return {"status": "error", "message": f"{region_key}クレデンシャル不足"} 

            # Refresh Token → Access Token
            token_url = "https://api.amazon.com/auth/o2/token"
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            token_res = requests.post(token_url, data=payload, headers=headers)
            token_json = token_res.json()
            if "access_token" not in token_json:
                return {"status": "error", "message": "access_token取得失敗", "detail": token_json}

            access_token = token_json["access_token"]

            # --- SigV4署名 → Catalog GET（リージョン可変）
            host = REGION_CFG.get(region_key, {}).get("host")
            locale = REGION_CFG.get(region_key, {}).get("locale")


            mpid_entry = (self.cfg.get("marketplace") or {}).get(region_key.upper())
            mpid = (mpid_entry or {}).get("marketplace_id") if isinstance(mpid_entry, dict) else mpid_entry
            if not mpid:
                return {"status": "error", "message": f"MarketplaceId not found for region={region_key}"}

            path = f"/catalog/2022-04-01/items/{asin}"

            params = {
                "marketplaceIds": [mpid],
                "includedData": "attributes,dimensions,summaries,images,productTypes,salesRanks,relationships,identifiers",
                "locale": locale,
            }

            r = real_signed_request("GET", path, params, host, config)
            resp = r
            if r is None:
                return {"status": "error", "message": "catalog request failed", "detail": "real_signed_request returned None"}

            # tuple (resp, ...) 形式に対応
            if isinstance(r, tuple) and len(r) > 0:
                resp = r[0]

            # dict {"response": resp, ...} 形式に対応
            elif isinstance(r, dict) and "response" in r:
                resp = r["response"]

            if isinstance(resp, dict):
                j = resp
                status = j.get("statusCode") or None
            else:
                status = getattr(resp, "status_code", None)
                try:
                    j = resp.json()
                except Exception:
                    body_preview = getattr(resp, "text", "")
                    if isinstance(body_preview, str) and len(body_preview) > 300:
                        body_preview = body_preview[:300] + "...(trunc)"
                    j = {"raw": body_preview}

            if isinstance(j, dict) and "errors" in j:
                return {"status": "error", "message": "catalog errors", "detail": j}
            
            if not isinstance(j, dict) or not j:
                j = {"status": "error", "message": "catalog empty response", "detail": {"status": status}}

            catalog_json = j      
            return catalog_json      
            
        except Exception as e:
            return {"status": "error", "message": f"adapter get_catalog_item init error: {e.__class__.__name__}: {e}"}

class AmazonPricingAdapter(PricingAdapter):
    def get_item_offers(self, asin: str, region: str) -> dict:
        """
        SP-API Product Pricing (v2022-05-01) から実売価格を取得して返す。
        返却：
            {
              "price_cart_jpy": float | None,
              "price_lowest_new_jpy": float | None,
              "price_lowest_used_jpy": float | None
            }
        失敗時は None を入れる（呼び出し側で表示可否を制御）
        """
        # 循環参照を避けるためローカルimport
        from utils.spapi_client import load_config, get_access_token

        cfg = load_config()
        mpid = (cfg.get("marketplace") or {}).get(region.upper())
        if not mpid:
            return {"status": "error", "message": f"MarketplaceId not found for region={region}"}

        def _money_to_float(x):
            # Money 形多対応
            if x is None:
                return None
            if isinstance(x, (int, float)):
                return float(x)
            if isinstance(x, str):
                try:
                    return float(x)
                except Exception:
                    return None
            if isinstance(x, dict):
                for k in ("Amount", "amount", "value", "Price", "price"):
                    if k in x and x[k] is not None:
                        try:
                            return float(x[k])
                        except Exception:
                            pass
            return None

        def _parse_offers_payload(payload):
            """
            sp-api の Products.get_item_offers().payload を解析して
            - cart（BuyBox価格）
            - lowest（その ItemCondition 側の最安）
            を返す。
            可能性のある形：
            - {"Summary":{"BuyBoxPrices":[{"ListingPrice":{"Amount":...},"LandedPrice":...}], "LowestPrices":[...]}}
            - {"Offers":[{"IsBuyBoxWinner":true,"ListingPrice":{"Amount":...}, ...}]}
            """
            out = {"cart": None, "lowest": None}
            try:
                p = payload or {}
                # --- BuyBox（優先：Summary.BuyBoxPrices -> Offers[IsBuyBoxWinner]） ---
                bb_price = None

                # 1) Summary.BuyBoxPrices
                summary = p.get("Summary") or p.get("summary") or {}
                bb_list = summary.get("BuyBoxPrices") or summary.get("buyBoxPrices") or []
                for bb in bb_list:
                    # ListingPrice が無ければ LandedPrice でも可
                    lp = bb.get("ListingPrice") or bb.get("listingPrice") or bb.get("LandedPrice") or bb.get("landedPrice")
                    bb_price = _money_to_float(lp)
                    if bb_price is not None:
                        break

                # 2) Offers[].IsBuyBoxWinner
                if bb_price is None:
                    offers = p.get("Offers") or p.get("offers") or []
                    for of in offers:
                        if of.get("IsBuyBoxWinner") or of.get("isBuyBoxWinner"):
                            lp = (of.get("ListingPrice") or of.get("listingPrice") or
                                  of.get("Price") or of.get("price") or
                                  of.get("LandedPrice") or of.get("landedPrice"))
                            bb_price = _money_to_float(lp)
                            if bb_price is not None:
                                break

                out["cart"] = bb_price

                # --- Lowest（Summary.LowestPrices の最小を拾う） ---
                lowest = None
                low_list = summary.get("LowestPrices") or summary.get("lowestPrices") or []
                mins = []
                for it in low_list:
                    lp = (it.get("ListingPrice") or it.get("listingPrice") or
                          it.get("LandedPrice") or it.get("landedPrice") or
                          it.get("Price") or it.get("price"))
                    amt = _money_to_float(lp)
                    if amt is not None:
                        mins.append(amt)
                lowest = min(mins) if mins else None

                # 3) フォールバック：Offers から最小 ListingPrice を拾う
                if lowest is None:
                    offers = p.get("Offers") or p.get("offers") or []
                    mins = []
                    for of in offers:
                        lp = (of.get("ListingPrice") or of.get("listingPrice") or
                              of.get("Price") or of.get("price") or
                              of.get("LandedPrice") or of.get("landedPrice"))
                        amt = _money_to_float(lp)
                        if amt is not None:
                            mins.append(amt)
                    lowest = min(mins) if mins else None

                out["lowest"] = lowest

            except Exception:
                pass
            return out

        # ---- API 呼び出し ----
        try:
            cfg = load_config()

            # --- 認証情報の取得（account優先） ---
            lwa_entry = (cfg.get("lwa", {}).get(region) or cfg.get("lwa", {}).get(region.lower()) or {})
            acct_entry = (cfg.get("account", {}).get(region) or cfg.get("account", {}).get(region.lower()) or {})

            client_id = lwa_entry.get("client_id", "")
            client_secret = lwa_entry.get("client_secret", "")
            refresh_token = acct_entry.get("refresh_token", "")

            if not (client_id and client_secret and refresh_token):
                raise RuntimeError(f"{region} クレデンシャル不足")

            access_token = get_access_token(client_id, client_secret, refresh_token)
            credentials = {
                "lwa_app_id": client_id,
                "lwa_client_secret": client_secret,
                "lwa_refresh_token": refresh_token,
                "access_token": access_token,
            }

            # sp-api 呼び出し
            from sp_api.api import Products
            pp = Products(credentials=credentials)

            cfg = load_config()
            mpid = (cfg.get("marketplace") or {}).get(region.upper())
            if not mpid:
                return {"status": "error", "message": f"MarketplaceId not found for region={region}"}

            res_new  = pp.get_item_offers(asin=asin, ItemCondition="New",  MarketplaceId=mpid)
            res_used = pp.get_item_offers(asin=asin, ItemCondition="Used", MarketplaceId=mpid)

            # payload 正規化（dict以外が来た場合に備える）
            j_new  = getattr(res_new, "payload",  res_new)
            j_used = getattr(res_used, "payload", res_used)

            if isinstance(j_new, (list, tuple)):
                j_new = (j_new[0] if j_new else {})
            if isinstance(j_used, (list, tuple)):
                j_used = (j_used[0] if j_used else {})

            if not isinstance(j_new, dict):
                j_new = {}
            if not isinstance(j_used, dict):
                j_used = {}

        except Exception as e:
            msg = str(e)
            if "invalid_grant" in msg:
                reason = "api_error_invalid_grant"
            elif "Throttled" in msg or "Too Many Requests" in msg or "429" in msg:
                reason = "api_error_throttled"
            else:
                reason = "api_error"

            return {
                "price_cart_jpy": None,
                "price_lowest_new_jpy": None,
                "price_lowest_used_jpy": None,
                "cart_reason": reason,
                "as_of": datetime.utcnow().isoformat() + "Z",
            }

        # ---- 解析 ----
        parsed_new  = _parse_offers_payload(j_new)  if isinstance(j_new, dict)  else {"cart": None, "lowest": None}
        parsed_used = _parse_offers_payload(j_used) if isinstance(j_used, dict) else {"cart": None, "lowest": None}

        cart_val = parsed_new.get("cart")
        reason = "ok" if cart_val is not None else "no_buybox"

        # New側のBuyBoxを「カート価格」とみなし、lowestは New/Used で分離して返す
        return {
            "price_cart_jpy":        cart_val,
            "price_lowest_new_jpy":  parsed_new.get("lowest"),
            "price_lowest_used_jpy": parsed_used.get("lowest"),
            "cart_reason": reason,
            "as_of": datetime.utcnow().isoformat() + "Z",
        }

    def get_pricing_summary(
        self,
        asin: str,
        region: str,
        config: dict | None = None,
    ) -> dict:
        """既存の get_pricing_summary_raw + parse_pricing_summary を安全にラップして返す。
        常に as_of / status / reason を付与。
        """
        try:
            if config is None:
                from amazon.routes import load_config as _load_config
                config = _load_config()

            from amazon.routes import get_pricing_summary_raw, parse_pricing_summary

            mpid = ((config.get("marketplace") or {}).get(region.upper()) or {}).get("marketplace_id")
            if not mpid:
                return {
                    "status": "error",
                    "reason": "marketplace_not_found",
                    "message": f"MarketplaceId not found for region={region}",
                    "as_of": datetime.utcnow().isoformat() + "Z",
                }

            raw = get_pricing_summary_raw(asin, region, config) 
            summary = parse_pricing_summary(raw) or {}

            cart_seller_name = None 

            # ★ BuyBox Winner のセラー名を raw から拾う
            try:
                offers = (raw.get("payload") or {}).get("Offers") or []
                for o in offers:
                    if o.get("IsBuyBoxWinner"):
                        cart_seller_name = o.get("SellerName") or o.get("SellerId")
                        break
            except Exception:
                pass            

            return {
                "list_price":         summary.get("list_price"),
                "buybox":             summary.get("buybox"),
                "lowest_new":         summary.get("lowest_new"),
                "lowest_used":        summary.get("lowest_used"),
                "lowest_new_channel": summary.get("lowest_new_channel"),
                "cart_seller_name":   summary.get("cart_seller_name") or cart_seller_name,
                "as_of":              datetime.utcnow().isoformat() + "Z",
                "status":             "ok",
                "reason":             "ok",
            }

        except Exception as e:
            msg = str(e)
            if "invalid_grant" in msg:
                reason = "api_error_invalid_grant"
            elif "Throttled" in msg or "Too Many Requests" in msg or "429" in msg:
                reason = "api_error_throttled"
            else:
                reason = "api_error"

            return {
                "list_price":         None,
                "buybox":             None,
                "lowest_new":         None,
                "lowest_used":        None,
                "lowest_new_channel": None,
                "cart_seller_name":   None, 
                "as_of":              datetime.utcnow().isoformat() + "Z",
                "status":             "error",
                "reason":             reason,
                "message":            msg,
            }