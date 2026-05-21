// 出品処理関連 (listing.js)

document.addEventListener("DOMContentLoaded", function () {
    // Pre-Listing テーブル初期化
    const preTable = $("#preListingTable").DataTable({
        autoWidth: false,
        paging: true,
        pageLength: 100,
        lengthChange: false,
        searching: false,
        info: true,
        scrollX: false,
        dom: '<"top"i p>rt<"bottom"i p><"clear">',
        language: {
            info: "全 _TOTAL_ 件中 _START_ から _END_ 件を表示",
            infoEmpty: "0 件中 0 から 0 件を表示",
            paginate: {
                previous: "前へ",
                next: "次へ"
            }
        },
        order: [],               // 初期ソートなし
        orderClasses: false,     // ← .sorting_1 着色を無効化
        stripeClasses: ['zsss-odd','zsss-even'], // ← 自前ストライプクラスを付与
        columns: [
            {
                data: null,
                title: '<input type="checkbox" id="toggleAllRows"> 商品情報',
                className: 'col-info',
                orderable: false,   // ← ソート無効化
                render: function (data, type, row) {
                    const checked = row.selected ? "checked" : "";
                    const content = `
                        <div>
                            <div>
                                <strong class="asin-cell" data-asin="${row.asin}"
                                    style="color:#007bff; cursor:pointer; text-decoration:underline;">
                                ${row.asin}
                                </strong>
                            </div>
                            <div style="font-size:12px;">${row.sku || ""}</div>
                            <div class="jp-title" title="${row.jp_title || ""}">${row.jp_title || ""}</div>
                            <div class="jp-brand">${row.jp_brand || ""}</div>
                        </div>
                    `;
                    return ` 
                    <span class="row-toggle-wrap">
                        <input type="checkbox" class="row-select" data-asin="${row.asin}" ${checked}
                            style="vertical-align:middle; margin-right:8px;"> <!-- この行を新規追加（行ごとのチェックボックス） -->
                        <span class="row-container">
                            ${content}
                        </span>
                    </span>
                    `;
                }
            },

            {
                data: null,
                title: '<input type="checkbox" id="toggleAllImages"> 画像',
                className: 'col-ops',
                orderable: false,   // ← ソート無効化
                render: function (_data, _type, row) {
                    const url = (row.image_url || '').replace(/"/g, '&quot;'); // 安全化
                    const checked = row.imageVisible ? "checked" : "";
                    const content = (row.imageVisible && row.image_url)
                        ? `<img src="${url}" style="max-width:80px; max-height:80px;">`
                        : "画像";
                    return `
                    <span class="img-toggle-wrap" style="display:inline-block; white-space:nowrap;">
                        <input type="checkbox" class="image-toggle" data-url="${url}" ${checked}
                            style="vertical-align:middle; margin-right:8px;">
                        <span class="image-container"
                            style="display:inline-flex; width:80px; height:80px; border:1px solid #ccc;
                                    background:#f9f9f9; align-items:center; justify-content:center;
                                    font-size:12px; color:#999; vertical-align:middle; overflow:hidden;">
                            ${content}
                        </span>
                    </span>
                    `;
                }
            },
            
            {
                data: null,
                title: "セラー・価格情報",
                orderable: false,   // ← ソート無効化
                defaultContent: ""
            }
        ]
    });

    // 全選択 / 全解除
    $(document).on("change", "#toggleAllRows", function () {
        const checked = $(this).is(":checked");
        $(".row-select").prop("checked", checked);
    });

    // 個別チェック → 他全部がONならヘッダーもONにする
    $(document).on("change", ".row-select", function () {
        const total = $(".row-select").length;
        const checkedCount = $(".row-select:checked").length;
        $("#toggleAllRows").prop("checked", total === checkedCount);
    });

    // 一括ON/OFF
    $(document).on("change", "#toggleAllImages", function () {
        const checked = $(this).is(":checked");
        $(".image-toggle").each(function () {
            $(this).prop("checked", checked).trigger("change");
        });
    });

    // 個別ON/OFF
    $("#preListingTable").on("change", ".image-toggle", function () {
        const checked = this.checked;
        const container = $(this).closest(".img-toggle-wrap").find(".image-container");
        const asin = $(this).data("asin");   // ← ASINを持たせる必要あり
        const region = (document.getElementById("globalRegion").value || "US").trim();

        if (checked) {
            const url = $(this).data("url");
            if (url) {
                container.html(`<img src="${url}" style="max-width:80px; max-height:80px;">`);
            } else {
                // ★ リトライ処理：API呼び出し
                fetch(`/amazon/retry_image?asin=${asin}&region=${region}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === "ok" && data.image_url) {
                            container.html(`<img src="${data.image_url}" style="max-width:80px; max-height:80px;">`);
                        } else {
                            container.text("取得失敗");
                        }
                    })
                    .catch(() => {
                        container.text("取得失敗");
                    });
            }
        } else {
            container.text("画像");
        }
    })

    // ✅ サイドバークリック時に Listing データをロード
    document.querySelectorAll(".sidebar-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-target");
            const region = (document.getElementById("globalRegion").value || "US").trim();

            if (target === "prelisting") {
                loadPreListing(region);
            } else if (target === "listing") {
                loadAllListing(region);
            }
        });
    });

    // グローバルで補完済みASINを保持
    window.fetchedAsins = window.fetchedAsins || new Set();

    function loadPreListing(region) {
        const overlay = document.getElementById("loadingOverlay");
        const message = document.getElementById("loadingMessage");
        if (overlay) {
            //message.textContent = `読み込んでいます…`;
            overlay.style.display = "flex";
        }

        fetch(`/amazon/get_prelisting?region=${region}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    preTable.clear();
                    (data.pre || []).forEach(item => preTable.row.add(item));
                    preTable.draw(false);

                    // ✅ 未補完かつ未処理のASINだけ
                    const asinList = data.pre.filter(item =>
                        !(item.jp_brand && item.jp_title && item.region_brand && item.region_title && item.image_url)
                        && !window.fetchedAsins.has(item.asin)
                    ).map(item => item.asin);

                    // 補完処理を Promise にまとめる
                    const tasks = asinList.map((asin, idx) => {
                        window.fetchedAsins.add(asin); // ✅ 補完済みに登録
                        return new Promise(resolve => {
                            setTimeout(() => {
                                fetch("/amazon/listing/fetch_item_info", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ asin: asin, region: region })
                                })
                                .then(res => res.json())
                                .then(updated => {
                                    if (updated.status === "ok") {
                                        const row = preTable.row((i, d) => d.asin === asin);
                                        if (row.node()) {
                                            let rowData = row.data();
                                            rowData = Object.assign({}, rowData, updated);
                                            row.data(rowData); // ← draw(false) は呼ばない
                                        }
                                    }
                                })
                                .catch(err => console.error("fetch_item_info error:", err))
                                .finally(resolve);
                            }, idx * 800);
                        });
                    });

                    // 全部終わってからオーバーレイを閉じる
                    return Promise.all(tasks);
                } else {
                    console.error("get_prelisting error:", data);
                }
            })
            .catch(err => console.error("get_prelisting fetch error:", err))
            .finally(() => {
                if (overlay) overlay.style.display = "none";
            });
    }

    // ✅ DataTable の描画完了イベントは一度だけ登録
    preTable.off("draw").on("draw", function () {
        const asins = Array.from(document.querySelectorAll("#preListingTable strong.asin-cell"))
                        .map(el => el.textContent.trim());
        console.log("ASINリスト:", asins);
        if (asins.length > 0) {
            const region = document.getElementById("globalRegion")?.value || "US";
            fetchJPBrandPool(asins, region);
        }
    });

    const commitBtn = document.getElementById("commitBtn");
    if (commitBtn) {
        commitBtn.addEventListener("click", function () {
            // DataTables からASINとSKUを全件取得
            let okTable = $('#csvOkTable').DataTable();
            const items = okTable.rows().data().toArray().map(row => {
                return { asin: row.asin, sku: row.sku };
            });

            // リージョン取得
            let region = document.querySelector('input[name="region"]:checked')?.value;
            if (!region) {
                region = document.getElementById("globalRegion")?.value;
            }

            if (items.length === 0) {
                alert("ASINリストが空です。CSVを取り込んでください。");
                return;
            }
            if (!region) {
                alert("リージョンを選択してください。");
                return;
            }

            // サーバに送信（まとめて送る）
            fetch(`/amazon/listing/add`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ items, region })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === "success") {
                    let okTable = $('#csvOkTable').DataTable();
                    let listedTable = $('#csvListedTable').DataTable();
                    let blacklistTable = $('#csvBlacklistTable').DataTable();
                    let preTable = $('#preListingTable').DataTable(); 

                    // ▼ まずリセット
                    okTable.clear().draw();
                    listedTable.clear().draw();
                    blacklistTable.clear().draw();
                    
                    // ▼ Pre-Listing再描画
                    preTable.clear().draw();  
                    (data.pre || []).forEach(item => preTable.row.add(item));
                    preTable.draw();

                    // ▼ ファイル選択欄もリセット
                    document.getElementById("csvFileName").value = "";
                    document.getElementById("csvFileInput").value = "";

                    // ※ commit 成功後は再描画しない（新規登録に残さないため）
                } else {
                    alert("エラー: 登録に失敗しました（ASINまたはSKUが重複しています）");
                    console.error("server error:", data);
                }
            })
            .catch(err => {
                console.error("commitBtn error:", err);
                alert("通信エラーが発生しました。");
            });
        });
    }

    // Pre-Listing一覧のASINリストを集めてブランド取得開始
    const asins = Array.from(document.querySelectorAll("#preListingTable strong.asin-cell"))
                    .map(el => el.textContent.trim());
    if (asins.length > 0) {
        const region = document.getElementById("globalRegion")?.value || "US";
        fetchJPBrandPool(asins, region);
    }

    // Pre-Listing API情報取得セクション　↓ ↓ ↓
    // ====== 並列ブランド取得プール ======
    const BRAND_FETCH_CONCURRENCY = 2;
    const BRAND_FETCH_RETRIES     = 6;
    const BRAND_FETCH_BASE_DELAY  = 800;

    function fetchJPBrandPool(asins, region) {
        if (!asins || asins.length === 0) return;

        asins.forEach(a => {
            const node = document.querySelector(`#preListingTable strong[data-asin="${a}"]`)
                ?.closest("div")?.parentElement?.querySelector(".jp-brand");
            if (node && !node.textContent) node.textContent = "取得中…";
        });

        let idx = 0;
        const inFlight = new Set();

        function nextJob() {
            if (idx >= asins.length) return;
            if (inFlight.size >= BRAND_FETCH_CONCURRENCY) return;

            const asin = asins[idx++];
            inFlight.add(asin);
            runOne(asin, 0).finally(() => {
                inFlight.delete(asin);
                nextJob();
                if (idx < asins.length) setTimeout(nextJob, 0);
            });

            while (inFlight.size < BRAND_FETCH_CONCURRENCY && idx < asins.length) {
                nextJob();
            }
        }

        function sleep(ms) { return new Promise(res => setTimeout(res, ms)); }

        async function runOne(asin, attempt) {
            try {
                const res = await fetch("/amazon/listing/fetch_item_info", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ asin: asin, region: region })
                });

                if (!res.ok) {
                    if ((res.status === 429 || res.status >= 500) && attempt < BRAND_FETCH_RETRIES) {
                        const delay = (BRAND_FETCH_BASE_DELAY * Math.pow(2, attempt)) + Math.floor(Math.random() * 200);
                        await sleep(delay);
                        return runOne(asin, attempt + 1);
                    }
                    console.warn("fetch_jp_brand http error:", asin, res.status);
                    return;
                }

                const data = await res.json();
                console.log("★ fetch_jp_brand response:", data);

                if (data && data.status === "ok") {
                    // JPブランド
                    if (data.jp_brand) {
                        const brandCell = document.querySelector(`#preListingTable strong[data-asin="${asin}"]`)
                            ?.closest("div")?.parentElement?.querySelector(".jp-brand");
                        if (brandCell) brandCell.textContent = data.jp_brand;
                    }
                    // JPタイトル
                    if (data.jp_title) {
                        const titleCell = document.querySelector(`#preListingTable strong[data-asin="${asin}"]`)
                            ?.closest("div")?.parentElement?.querySelector(".jp-title");
                        if (titleCell) titleCell.textContent = data.jp_title;
                    }

                    // ✅ 画像URLをDataTableに保存
                    if (data.image_url) {
                        preTable.rows().every(function () {
                            const rowData = this.data();
                            if (rowData.asin === asin) {
                                rowData.image_url = data.image_url; // 追加保持
                                this.data(rowData); // invalidate() は呼ばない
                            }
                        });
                    }                    
                }
            } catch (err) {
                if (attempt < BRAND_FETCH_RETRIES) {
                    const delay = (BRAND_FETCH_BASE_DELAY * Math.pow(2, attempt)) + Math.floor(Math.random() * 200);
                    await sleep(delay);
                    return runOne(asin, attempt + 1);
                }
                console.error("JP brand fetch error:", asin, err);
            }
        }

        nextJob();
    }


    // Pre-Listing / ALL-Listing のマーケットプレイス切り替え
    const globalRegionEl = document.getElementById("globalRegion");
    if (globalRegionEl) {
        globalRegionEl.addEventListener("change", function () {            
            const region = (this.value || "US").trim();

            // Pre-Listing ページに居るか判定
            if (document.querySelector("#preListingTable")) {
                loadPreListing(region);
            }
            // ALL-Listing ページに居るか判定
            else if (document.querySelector("#allListingTable")) {
                loadAllListing(region);
            }
        });
    }
});



