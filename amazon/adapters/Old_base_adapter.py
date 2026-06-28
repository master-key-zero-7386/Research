# 共通 API（各プラットフォームに共通するインタフェース定義）
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from utils.config_loader import cfg, get_debug_mode

class BaseMarketplaceAdapter(ABC):
    @abstractmethod
    def update_price(
        self,
        product_id: str,
        price: float,
        currency: str,
        region: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """単品の価格を更新する。戻り値はPFごとの結果ペイロード。"""
        raise NotImplementedError

class PricingAdapter(ABC):
    @abstractmethod
    def get_item_offers(self, asin: str, region: str) -> dict:
        """
        返却形式：
        {
            "price_cart_jpy": float|None,
            "price_lowest_new_jpy": float|None,
            "price_lowest_used_jpy": float|None,
        }
        """
        raise NotImplementedError

class CatalogAdapter(ABC):
    @abstractmethod
    def get_dimensions(self, asin: str, region: str) -> Dict[str, Any]:
        """
        Catalog Items などから item/package の寸法・重量を返す。
        返却例:
        {
            "itemDimensions": {"length": float|None, "width": float|None, "height": float|None, "unit": "centimeters"},
            "packageDimensions": {"length": ..., "width": ..., "height": ..., "unit": "centimeters"},
            "itemWeight": {"value": float|None, "unit": "kilograms"},
            "packageWeight": {"value": float|None, "unit": "kilograms"},
        }
        取得失敗時は各フィールドを None にして返す（呼び出し側で制御）。
        """
        raise NotImplementedError

class BrandGateAdapter(ABC):
    @abstractmethod
    def check_brand_gate(self, asins: list[str], regions: list[str]) -> dict:
        """
        複数 ASIN × 複数リージョンのブランドゲート判定を返す。

        入力:
            asins   : ["B000...", "B001...", ...]
            regions : ["JP","US","AU","SG", ...]  # 大小文字は実装側で許容

        返却例（現行APIの形に合わせる）:
        {
            "items": [
                {
                    "asin": "B000XXXXXX",
                    "JP": "開放/申請可/申請不可 など実装側の判定文字列",
                    "US": "...",
                    "AU": "...",
                    "SG": "...",
                    "note": ""  # 追加メモ・理由コードなど
                },
                ...
            ],
            "as_of": "2025-09-03T12:34:56Z",
            "status": "ok" | "error",
            "reason": "ok | api_error | api_error_invalid_grant | throttled など"
        }
        """
        raise NotImplementedError

        