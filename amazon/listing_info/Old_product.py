# このセクションは新規追加
from amazon.db import get_conn

def build_product_block(asin, region, catalog_jp, catalog_rg):
    """
    brand / title を抽出して DB 更新し、結果を返す
    """
    def _extract_brand_title(catalog):
        brand, title = None, None
        if isinstance(catalog, dict):
            sums  = (catalog.get("summaries") or [{}])[0]
            attrs = (catalog.get("attributes") or {})

            # brand
            brand = sums.get("brand")
            if not brand:
                v = attrs.get("brand")
                if isinstance(v, list) and v:
                    head = v[0]
                    brand = head.get("value") if isinstance(head, dict) else head

            # title
            title = sums.get("itemName")
            if not title:
                v = attrs.get("item_name")
                if isinstance(v, list) and v:
                    head = v[0]
                    title = head.get("value") if isinstance(head, dict) else head
        return brand, title

    region_brand, region_title = _extract_brand_title(catalog_rg)
    jp_brand, jp_title         = _extract_brand_title(catalog_jp)

    # ---- DB 更新（空は上書きせず、既存値を保持）----
    conn = get_conn(f"a_{region.lower()}_listed_items.db")
    cur = conn.cursor()
    cur.execute("""
        UPDATE listed_items
           SET jp_brand     = COALESCE(?, jp_brand),
               jp_title     = COALESCE(?, jp_title),
               region_brand = COALESCE(?, region_brand),
               region_title = COALESCE(?, region_title)
         WHERE asin = ?
    """, (jp_brand, jp_title, region_brand, region_title, asin))
    conn.commit()
    conn.close()

    return {
        "region_brand": region_brand,
        "region_title": region_title,
        "jp_brand": jp_brand,
        "jp_title": jp_title,
    }
