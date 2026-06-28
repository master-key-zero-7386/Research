# ファイル名：image.py

from amazon.db import get_conn

def build_image_block(asin, region, catalog_jp, catalog_rg):
    """
    image_url を抽出して DB 更新し、結果を返す
    """
    def _pick_image_url(images_list):
        if not isinstance(images_list, list):
            return None
        def scan(obj):
            if isinstance(obj, dict):
                for k in ("link","url","imageUrl","imageURL","hiRes","large","medium","small"):
                    v = obj.get(k)
                    if isinstance(v, str) and v.startswith("http"):
                        return v
                for v in obj.values():
                    r = scan(v)
                    if r: return r
            elif isinstance(obj, list):
                for v in obj:
                    r = scan(v)
                    if r: return r
            elif isinstance(obj, str):
                if obj.startswith("http"):
                    return obj
            return None

        for itm in images_list:
            r = scan(itm)
            if r: return r
        return None

    # region image
    region_image = _pick_image_url((catalog_rg or {}).get("images") or [])
    if not region_image:
        region_image = _pick_image_url(((catalog_rg.get("summaries") or [{}])[0]).get("images") or [])
    # jp image
    jp_image = _pick_image_url((catalog_jp or {}).get("images") or [])
    if not jp_image:
        jp_image = _pick_image_url(((catalog_jp.get("summaries") or [{}])[0]).get("images") or [])

    final_image = region_image or jp_image

    # ---- DB更新（image_urlだけ）----
    conn = get_conn(f"a_{region.lower()}_listed_items.db")
    cur = conn.cursor()
    cur.execute("""
        UPDATE listed_items
           SET image_url = COALESCE(?, image_url)
         WHERE asin = ?
    """, (final_image, asin))
    conn.commit()
    conn.close()

    return {"image_url": final_image}
