# amazon 寸法・重量取得
from typing import Dict, Any
from datetime import datetime
from .base_adapter import CatalogAdapter
from utils.spapi_client import get_item_dimensions
from utils.config_loader import cfg, get_debug_mode

class AmazonCatalogAdapter(CatalogAdapter):
    def get_dimensions(self, asin: str, region: str) -> Dict[str, Any]:
        """
        Amazon SP-API (Catalog Items 2022-04-01) を利用して寸法・重量を返す。
        region: "US" / "JP" / "AU" / "SG" など
        """
        try:
            data = get_item_dimensions(asin=asin, region=region)
            return {
                "itemDimensions": data.get("itemDimensions"),
                "packageDimensions": data.get("packageDimensions"),
                "itemWeight": data.get("itemWeight"),
                "packageWeight": data.get("packageWeight"),
                "as_of": datetime.utcnow().isoformat() + "Z",
                "status": "ok",
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = str(e)
            reason = "api_error_invalid_grant" if "invalid_grant" in msg else "api_error"
            return {
                "itemDimensions": None,
                "packageDimensions": None,
                "itemWeight": None,
                "packageWeight": None,
                "as_of": datetime.utcnow().isoformat() + "Z",
                "status": "error",
                "reason": reason,      # ← これを追加
                "message": msg,
            }