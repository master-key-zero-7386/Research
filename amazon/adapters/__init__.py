# adapters パッケージの公開インタフェースをまとめる
from .base_adapter import BaseMarketplaceAdapter
from utils.config_loader import cfg, get_debug_mode

__all__ = ["BaseMarketplaceAdapter", "AmazonAdapter"]