let dataDir = "";
const fmtJPY = (v) => (v == null ? "-" : Math.round(v).toLocaleString("ja-JP"));
const fmtPrice = (v) => (v == null ? "-" : Number(v).toFixed(2));

window.addEventListener("DOMContentLoaded", () => {

    // ✅ ストアボタンの有効/無効切り替え
    function updateStoreButtonState() {
        const dropdown = document.getElementById('seller_id');
        const manualInput = document.getElementById('manual_seller_id');
        const button = document.getElementById('openStoreBtn');
        if (!button) return;

        const dropdownValue = dropdown?.value || "";
        const manualValue = manualInput?.value || "";
        // const isDropdownValid = dropdownValue !== ""; 
        const isDropdownValid = dropdownValue !== "" || manualValue.trim() === "";
        const isManualValid = manualValue.trim() !== "";
        button.disabled = !(isDropdownValid || isManualValid);
    }

        // リージョン選択処理
        const globalRegionEl = document.getElementById("globalRegion");
        if (globalRegionEl) {
            // リージョン変更時にセラーリストを更新
            globalRegionEl.addEventListener("change", function () {
                const region = this.value;
                loadSellerList(region);
                updateStoreButtonState();
            });

            // 初期ロード時にセラーリストとボタン状態をセット
            if (globalRegionEl.value) {
                loadSellerList(globalRegionEl.value);
                updateStoreButtonState();
            }
        }    
        
    document.getElementById("seller_id").addEventListener("change", updateStoreButtonState);
    document.getElementById("manual_seller_id").addEventListener("input", updateStoreButtonState);

    updateStoreButtonState();

    console.log("✅ DOMContentLoaded 発火チェック");

    // ✅ ASIN抽出ボタンのイベント委譲（再描画されても有効）
    document.addEventListener("click", function(e) {
        if (e.target && e.target.id === "asinExtractBtn") {
            extractASINFromSelected();
        }
    });
    // ✅ リロード後に seller_id を復元
    const index = localStorage.getItem("nextSellerIndex");
    if (index !== null) {
        const select = document.getElementById("seller_id");
        if (select && select.options.length > index) {
            select.selectedIndex = index;
        }
        localStorage.removeItem("nextSellerIndex");
    }

    // ✅ regionごとの config を取得
    const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase(); 

    fetch(`/amazon/load_config?region=${region}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                const lastUsed = data.last_used || {};
                configData = lastUsed;

                dataDir = data.data_dir || "data";  // ✅ data_dir に修正

                // ✅ マーケットプレイスはプルダウンの値をそのまま使う
                if (globalRegionEl) {
                    globalRegionEl.value = region.toUpperCase();
                }

                // ✅ セラーリストをロードしてから選択復元
                loadSellerList(region);
                updateStoreButtonState();

                // その他の値を復元（DBから取る項目は空にしておく）
                document.getElementById("manual_seller_id").value = "";
                document.getElementById("remarks").value = ""; 
                document.getElementById("hidden").checked = false; 
                document.getElementById("brand").value = lastUsed.brand || "";
                document.getElementById("min_price").value = lastUsed.min_price || "";
                document.getElementById("max_price").value = lastUsed.max_price || "";
                document.getElementById("step_price").value = lastUsed.step_price || "";

                // ✅ 出力フォルダ表示もプルダウン基準
                updateOutputFolderDisplay(region);
            }
        })
        .catch(error => {
            console.error("load_configエラー:", error);
        });

    // 🔁 セレクトボックス変更時にも出力フォルダ表示を更新
    if (globalRegionEl) {
        globalRegionEl.addEventListener("change", () => {
            updateOutputFolderDisplay(globalRegionEl.value);
        });
    }


    // ✅ URLパラメータ取得
    function getParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    // ✅ 数値バリデーション関数（価格チェックなどで使用）
    function isValidNumberInput(value) {
        return value.trim() === "" || !isNaN(parseFloat(value));
    }

    // ✅ 最大ページ数バリデーション関数（1～20の整数 or 空欄OK）
    function isValidPageCount(value) {
        if (value.trim() === "") return true;
        const num = parseInt(value.trim(), 10);
        return !isNaN(num) && num >= 1 && num <= 20;
    }

    // ✅ ストアを開く処理
    function openStore() {
        const minPrice = document.getElementById('min_price').value;
        const maxPrice = document.getElementById('max_price').value;
        if (!isValidNumberInput(minPrice)) {
            alert("最低価格は数値で入力してください。");
            return;
        }
        if (!isValidNumberInput(maxPrice)) {
            alert("最高価格は数値で入力してください。");
            return;
        }
        const manualInput = document.getElementById("manual_seller_id").value.trim();
        const dropdownValue = document.getElementById("seller_id").value.trim();
        const sellerId = manualInput !== "" ? manualInput : dropdownValue;
        const region = document.getElementById("globalRegion").value.toLowerCase();
        //const baseUrl = region === "au" ? "https://www.amazon.com.au/sp?seller=" : "https://www.amazon.com/sp?seller=";
        let baseUrl = "";
        if (region === "au") {
            baseUrl = "https://www.amazon.com.au/sp?seller=";
        } else if (region === "us") {
            baseUrl = "https://www.amazon.com/sp?seller=";
        } else if (region === "sg") {
            baseUrl = "https://www.amazon.sg/sp?seller=";
        } else if (region === "ca") {
            baseUrl = "https://www.amazon.ca/sp?seller=";
        }                   

        window.open(baseUrl + sellerId, '_blank');
    }

    function updateOutputFolderDisplay(region) {
        if (!region || !dataDir) return;  // ✅ 念のためチェック
        const fullPath = dataDir + "\\" + region.toLowerCase();  // ✅ 修正済み
        document.getElementById("output_folder").value = fullPath;
    } 

    // ✅ セラーID抽出：実行ボタン処理
    document.getElementById("sellerExtractBtn").addEventListener("click", function () {
        const region = document.getElementById("globalRegion").value;
        const btn = document.getElementById("sellerExtractBtn");  
        const originalLabel = btn.textContent;
        btn.disabled = true;  
        btn.textContent = "抽出中…";   
        
        document.getElementById("sellerCsvInput").click();

        document.getElementById("sellerCsvInput").addEventListener("change", function () {
            const files = Array.from(this.files);
            if (files.length === 0) {  
                btn.disabled = false; 
                btn.textContent = originalLabel; 
                return;
            }

            const formData = new FormData();
            formData.append("region", region);
            files.forEach(file => formData.append("files", file));

            fetch("/amazon/extract_seller_ids", {
                method: "POST",
                body: formData
            })

            .then(async (response) => { 
                if (response.status === 423) {
                    const data = await response.json().catch(() => ({}));
                    alert(data.message || "抽出処理がすでに実行中です。");
                    throw new Error("locked");        
                }
                return response.json();
            })

            .then(data => {
                if (data.status === "success") { 
                    const n = data.count ?? data.extracted ?? data.extracted_count ?? 0; 
                    alert(`抽出が完了しました（${n}件）。`);
                } else {
                    alert(`❌ エラー: ${data.message || "処理に失敗しました"}`);  
                }
            })
            .catch(error => {
                if (error.message !== "locked") {  
                    alert("通信エラー: " + error);
                }
            })
            .finally(() => {    
                btn.disabled = false;                   
                btn.textContent = originalLabel;                    
                this.value = "";  
            });  
        }, { once: true });
    });

    // ✅ 実行ボタンの処理
    function runExtraction() {
        const region = document.getElementById("globalRegion").value.toLowerCase();
        const sellerSelect = document.getElementById("seller_id").value.trim();
        const manualInput = document.getElementById("manual_seller_id").value.trim();
        const sellerId = manualInput || sellerSelect; 

        const remarks = document.getElementById("remarks").value.trim();
        const brand = document.getElementById("brand").value.trim();
        const minPrice = document.getElementById("min_price").value.trim();
        const maxPrice = document.getElementById("max_price").value.trim();
        const stepPrice = document.getElementById("step_price").value.trim();
        const outputFolder = document.getElementById("output_folder").value.trim();
        const confirmWait = document.getElementById("confirm_wait").value.trim();

        // ✅ config 保存（修正なし）
        fetch("/amazon/save_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                region, seller_id: sellerId, brand, min_price: minPrice,
                max_price: maxPrice, step_price: stepPrice,
                output_folder: outputFolder, confirm_wait: confirmWait, remarks
            })
        })
        .then(response => {
            if (!response.ok) throw new Error("ネットワークエラー");
            return response.json();
        })
        .then(data => {
            console.log("✅ config保存成功:", data);

            // ✅ ここを修正: URLパラメータではなく fetch本体にregionを含めるPOST一本化
            return fetch("/amazon/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    region,
                    seller_id: sellerId,                     
                    manual_seller_id: manualInput,          
                    brand, min_price: minPrice,
                    max_price: maxPrice, step_price: stepPrice,
                    output_folder: outputFolder,
                    confirm_wait: confirmWait, remarks
                })
            });
        })
        .then(response => {
            if (!response.ok) throw new Error("処理リクエスト失敗");

            // ✅ タブ遷移をリロードではなくJSで切り替える
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

            const researchTab = document.querySelector('[data-tab="research"]');
            if (researchTab) researchTab.classList.add("active");

            const researchContent = document.getElementById("research");
            if (researchContent) researchContent.classList.add("active");
        })
        .catch(error => {
            console.error("❌ エラー:", error);
            alert("実行中にエラーが発生しました");
        });
    }

    // ✅ 初期化・イベントバインド
    fetch("https://ipinfo.io/json") 
        .then(res => res.json())
        .then(data => {
            const ipBox = document.getElementById("ip-location");
            const logBox = document.getElementById("log-box");

            if (ipBox && data.city && data.country) {
                const locationText = `Location: ${data.city}, ${data.country}`;
                ipBox.textContent = locationText;

                // ✅ 最終ログを Flask から取得して結合表示
                fetch("/amazon/get_latest_log")
                    .then(res => res.text())
                    .then(latestLog => {
                        if (logBox) {
                            logBox.textContent = `${latestLog}（${locationText}）`;
                        }
                    })
                    .catch(err => {
                        console.warn("ログ取得エラー:", err);
                    });
            }
        })
        .catch(err => {
            console.warn("IP取得エラー:", err);
        });
        
    const runBtn = document.getElementById("runBtn");
    if (runBtn) {
        runBtn.addEventListener("click", (event) => {
            event.preventDefault();
            runExtraction();
        });
    }

    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');
    const targetTab = getParam("tab");
    
    if (targetTab) {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            const activeTab = document.querySelector(`.tab[data-tab="${targetTab}"]`);
            const activeContent = document.getElementById(targetTab);
            if (activeTab && activeContent) {
                activeTab.classList.add('active');
                activeContent.classList.add('active');
            }
        }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.getAttribute('data-tab');
            console.log("✅ タブクリック:", targetId); 
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(targetId).classList.add('active');
        });
    });

        const btn = document.getElementById('openStoreBtn');
        const dropdown = document.getElementById('seller_id');
        const manualInput = document.getElementById('manual_seller_id');

        if (btn) btn.addEventListener('click', openStore);

        if (dropdown) {
            dropdown.addEventListener("change", function () {
                updateStoreButtonState();

                const selectedSeller = this.value;
                const region = document.getElementById("globalRegion").value.toLowerCase();

                // ✅ fetch直書きを削除して共通関数を呼ぶ
                get_seller_info(region, selectedSeller);
            });
        }

        if (manualInput) manualInput.addEventListener('input', updateStoreButtonState);
        updateStoreButtonState();

        document.querySelectorAll('input[name="region"]').forEach(el => {
            el.addEventListener('change', function () {
                const region = this.value;
                const activeTab = document.querySelector('.tab.active')?.getAttribute('data-tab') || 'top';
                window.location.href = `/amazon/?region=${region}&tab=${activeTab}`;
            });
        });

        const saveBtn = document.getElementById("saveSellerBtn");
        if (saveBtn) {
            saveBtn.addEventListener("click", function () {
                const region = document.getElementById("globalRegion").value.toLowerCase();
                const sellerId = document.getElementById("seller_id").value;
                const manualSellerId = document.getElementById("manual_seller_id").value;
                const shopName = document.getElementById("shop_name").value.trim(); 

                if (!sellerId && !manualSellerId) {
                    alert("セラーIDを選択するか、手入力してください。");
                    return;
                }

                if (shopName === "") {
                    alert("⚠ ショップ名が空白になっています。");
                    // 保存は続行 → 保存禁止にしない
                }                

                const usedSellerId = manualSellerId.trim() || sellerId.trim(); 
                const remarks = document.getElementById("remarks").value.trim();
                const hidden = document.getElementById("hidden").checked ? "TRUE" : "";

                const formData = new URLSearchParams();
                formData.append("region", region);
                formData.append("seller_id", usedSellerId);
                formData.append("manual_seller_id", manualSellerId);
                formData.append("shop_name", shopName); // ★追加
                formData.append("remarks", remarks);
                formData.append("hidden", hidden);

                fetch("/amazon/save_seller_info", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: formData.toString(),
                })
                .catch(error => {
                    alert("通信エラー: " + error);
                });
            });
        }

        // ✅ ページロード時にセラーリストを初期ロード
        window.addEventListener("load", function () {
            const region = (document.querySelector('input[name="region"]:checked')?.value || "us").toLowerCase();
            console.log("初期ロード region:", region);
            loadSellerList(region);
        });  

        // ✅ トグル切替時にリストを再ロード
        document.getElementById("toggleHiddenSeller")?.addEventListener("change", function () {
            const region = (document.querySelector('input[name="region"]:checked')?.value || "us").toLowerCase();
            loadSellerList(region);
        });

        // DHL 遠隔地郵便番号：展開 → 表示
        async function convertDHLRemote() {
        const ta = document.getElementById("dhlInput");
        const out = document.getElementById("dhlOutput");
        const count = document.getElementById("dhlCount");
        if (!ta || !out || !count) return;

        const text = ta.value || "";
        if (!text.trim()) {
            out.textContent = "";
            count.textContent = "";
            return;
        }

        try {
            const resp = await fetch("/tools/dhl/remote_expand", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ text })
            });
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            const data = await resp.json();
            const codes = data.codes || [];
            out.textContent = codes.join("\n");
            count.textContent = `件数：${codes.length.toLocaleString()}`;
        } catch (e) {
            console.error("DHL convert error:", e);
            out.textContent = "変換エラー";
            count.textContent = "";
        }
        }

        // DHL：CSVダウンロード
        async function downloadDHLRemoteCSV() {
        const ta = document.getElementById("dhlInput");
        const text = (ta && ta.value) ? ta.value : "";
        try {
            const resp = await fetch("/tools/dhl/remote_export", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ text })
            });
            if (!resp.ok) throw new Error("HTTP " + resp.status);

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "dhl_remote_codes.csv";
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error("DHL download error:", e);
            alert("CSVのダウンロードに失敗しました。");
        }
        }

        // ボタンにバインド
        document.getElementById("dhlConvertBtn")?.addEventListener("click", convertDHLRemote);
        document.getElementById("dhlDownloadBtn")?.addEventListener("click", downloadDHLRemoteCSV);
        document.getElementById("dhlClearBtn")?.addEventListener("click", clearDHLFields); 
        
        async function splitPdfChunks() {
        const fi = document.getElementById("pdfFileInput"); 
        const perEl = document.getElementById("pdfSplitPer");
        if (!fi || !fi.files || fi.files.length === 0) {
            alert("PDFファイルを選択してください。");
            return;
        }
        let per = parseInt(perEl?.value || "60", 10);
        if (!Number.isInteger(per) || per <= 0) per = 60;

        const fd = new FormData();
        fd.append("file", fi.files[0]);
        fd.append("per", String(per));

        const resp = await fetch("/tools/pdf/split_chunks", { method: "POST", body: fd });
        if (!resp.ok) {
            alert("分割に失敗しました。");
            return;
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "pdf_splits.zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        }

        document.getElementById("pdfSplitBtn")?.addEventListener("click", splitPdfChunks);

        // 入力と結果をクリア
        function clearDHLFields() {
            const ta = document.getElementById("dhlInput");
            const out = document.getElementById("dhlOutput");
            const count = document.getElementById("dhlCount");
            if (ta) ta.value = "";
            if (out) out.textContent = "";
            if (count) count.textContent = "";
        }
        // ✅ PDFファイル選択処理 ←★ここに追加
        const pdfFileInput = document.getElementById("pdfFileInput");
        const pdfFileName = document.getElementById("pdfFileName");

        if (pdfFileName && pdfFileInput) {
            pdfFileName.addEventListener("click", () => pdfFileInput.click());
        }

        if (pdfFileInput) {
            pdfFileInput.addEventListener("change", () => {
                if (pdfFileInput.files.length > 0) {
                    pdfFileName.value = pdfFileInput.files[0].name;
                }
            });
        }
    });

    async function loadAccountConfig() {
    try {
        const res = await fetch("/amazon/account/load"); 
        const json = await res.json();
        if (json.status !== "ok") throw new Error(json.message || "load error");
        console.log("✅ /get_config_account:", json.data);

        document.getElementById("accJP_seller").value  = (json.data.account?.JP?.seller_id || "");
        document.getElementById("accJP_refresh").value = (json.data.account?.JP?.refresh_token || "");
        document.getElementById("accUS_seller").value  = (json.data.account?.US?.seller_id || "");
        document.getElementById("accUS_refresh").value = (json.data.account?.US?.refresh_token || "");
        document.getElementById("accAU_seller").value  = (json.data.account?.AU?.seller_id || "");
        document.getElementById("accAU_refresh").value = (json.data.account?.AU?.refresh_token || "");
        document.getElementById("accSG_seller").value  = (json.data.account?.SG?.seller_id || "");
        document.getElementById("accSG_refresh").value = (json.data.account?.SG?.refresh_token || "");
        document.getElementById("accUK_seller").value  = (json.data.account?.UK?.seller_id || "");
        document.getElementById("accUK_refresh").value = (json.data.account?.UK?.refresh_token || "");
        document.getElementById("accCA_seller").value  = (json.data.account?.CA?.seller_id || "");
        document.getElementById("accCA_refresh").value = (json.data.account?.CA?.refresh_token || "");        
    } catch (e) {
        console.error("loadAccountConfig error:", e);
    }
    }

    // ✅ セラー情報取得（共通関数）
    async function get_seller_info(region, seller_id = "") {
        try {
            let url = `/amazon/get_seller_info?region=${region}`;
            if (seller_id) {
                url += `&seller_id=${encodeURIComponent(seller_id)}`;
            }

            const res = await fetch(url);
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();

            // 🔽 プルダウン選択状態を反映
            const dropdown = document.getElementById("seller_id");
            if (dropdown && data.seller_id && seller_id !== "") { 
                let found = false;
                for (let opt of dropdown.options) {
                    if (opt.value === data.seller_id) {
                        dropdown.value = opt.value;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    const opt = document.createElement("option");
                    opt.value = data.seller_id;
                    opt.text = data.shop_name 
                        ? `${data.shop_name} (${data.seller_id})`
                        : data.seller_id;
                    dropdown.appendChild(opt);
                    dropdown.value = data.seller_id;
                    console.warn("[WARN] seller_id を追加しました:", data.seller_id);
                }

            }            

            // 🔽 入力欄に反映
            const shopInput    = document.getElementById("shop_name");
            const remarksInput = document.getElementById("remarks");

            if (shopInput)    shopInput.value    = data.shop_name || "";
            if (remarksInput) remarksInput.value = data.remarks || "";

        } catch (err) {
            console.error("get_seller_info error:", err);
        }
    }

    function initAccountForm() {
    const regions = ["JP", "US", "AU", "SG", "UK"];
    const el = (id) => document.getElementById(id);

    // 1) 起動時
    fetch("/amazon/api/account")
        .then(r => r.json())
        .then(res => {
            if (res?.status !== "ok") return;

            const acc = res.account || {};
            
            regions.forEach(rgn => {
                const s = el(`acc${rgn}_seller`);
                const t = el(`acc${rgn}_refresh`);
                if (s) s.value = acc?.[rgn]?.seller_id || "";
                if (t) t.value = acc?.[rgn]?.refresh_token || "";
            });
        })
        .catch(e => console.warn("GET /amazon/api/account failed:", e));

    // 2) 保存ボタン  ✅ 管理者ID：account格納 (将来ユーザーID：user_accountに統一)
    const saveBtn = el("accountSaveBtn");
    if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
        const payload = { account: {} };
        regions.forEach(rgn => {
            const s = el(`acc${rgn}_seller`);
            const t = el(`acc${rgn}_refresh`);
            if (s || t) {
            payload.account[rgn] = {
                seller_id: s ? s.value : "",
                refresh_token: t ? t.value : ""
            };
            }
        });

        try {
            const resp = await fetch("/amazon/api/account", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (data.status === "ok") {
            alert("アカウント情報を保存しました。");
            } else {
            alert("保存に失敗しました: " + (data.message || "unknown"));
            }
        } catch (err) {
            alert("通信エラー: " + err.message);
        }
        });
    }
    }

    document.addEventListener("DOMContentLoaded", () => {         
        const typeSel   = document.getElementById("bl-type");                                  
        const keyInput  = document.getElementById("bl-key");                                   
        const memoInput = document.getElementById("bl-reason");                              
        const submitBtn = document.getElementById("bl-submit");                             
        const resetBtn  = document.getElementById("bl-reset");                              
        const listBox   = document.getElementById("bl-list-placeholder");                    
        const hasBL = !!(typeSel && keyInput && memoInput && submitBtn && resetBtn && listBox); 

        // ✅ サイドバー切替処理
        document.querySelectorAll(".sidebar-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".sidebar-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");

                document.querySelectorAll(".subtab-content").forEach(pane => pane.hidden = true);
                const targetId = btn.getAttribute("data-target");
                document.getElementById(targetId).hidden = false;
            });
        });

        // ✅ サイドバー折りたたみ処理
        const collapseHandle = document.getElementById("sidebar-collapse");
        if (collapseHandle) {
            collapseHandle.addEventListener("click", () => {
                const sidebar = document.getElementById("sidebar");
                sidebar.classList.toggle("collapsed");

                // ＜ と ＞ を切替
                collapseHandle.textContent = sidebar.classList.contains("collapsed") ? "＞" : "＜";
            });
        }

        // ブラックリスト処理       
        if (hasBL) {
            const asinRe = /^[A-Z0-9]{10}$/;                                                     
            const currentRegion = document.querySelector('input[name="region"]:checked')?.value || "au"; 

            const validate = () => { 
                const type = typeSel.value;
                const key  = keyInput.value.trim();
                if (!key) { submitBtn.disabled = true; return; }
                if (type === "asin") submitBtn.disabled = !asinRe.test(key.toUpperCase());
                else submitBtn.disabled = key.length < 1 || key.length > 100;
            };                                                                                   

            typeSel.addEventListener("change", validate);                                         
            keyInput.addEventListener("input", validate);                                          
            resetBtn.addEventListener("click", () => {                                             
                keyInput.value = ""; memoInput.value = ""; validate(); keyInput.focus();
            });                                                                                    

            async function loadList(view="asin") {                                                 
                const res = await fetch(`/blacklist/${currentRegion}?type=${view}`);
                const data = await res.json();
                const rows = Array.isArray(data.rows) ? data.rows : [];
                listBox.innerHTML = `
                <div style="display:flex; gap:8px; margin-bottom:8px;">
                    <button data-view="asin"  class="btn-blue">ASIN一覧</button>
                    <button data-view="brand" class="btn-blue">ブランド一覧</button>
                </div>
                <table style="width:100%; border-collapse: collapse; background:#fff;">
                    <thead>
                    <tr>
                        <th style="text-align:left; padding:6px; border-bottom:1px solid #ddd;">タイプ</th>
                        <th style="text-align:left; padding:6px; border-bottom:1px solid #ddd;">キー</th>
                        <th style="text-align:left; padding:6px; border-bottom:1px solid #ddd;">メモ</th>
                        <th style="text-align:left; padding:6px; border-bottom:1px solid #ddd;">操作</th>
                    </tr>
                    </thead>
                    <tbody>
                    ${rows.map((r)=>`
                        <tr>
                        <td style="padding:6px; border-bottom:1px solid #f0f0f0;">${r.type}</td>
                        <td style="padding:6px; border-bottom:1px solid #f0f0f0;">${r.key}</td>
                        <td style="padding:6px; border-bottom:1px solid #f0f0f0;">${r.reason||""}</td>
                        <td style="padding:6px; border-bottom:1px solid #f0f0f0;">
                            <button class="btn-blue" data-del="${r.type}:${r.key}">削除</button>
                        </td>
                        </tr>`).join("")}
                    </tbody>
                </table>
                `;
                listBox.querySelectorAll("button[data-view]").forEach(btn=>{
                    btn.addEventListener("click",()=> loadList(btn.dataset.view));
                });
                listBox.querySelectorAll("button[data-del]").forEach(btn=>{
                    btn.addEventListener("click", async ()=>{
                        const [type, rawKey] = btn.dataset.del.split(":");
                        const key = type === "asin" ? rawKey.toUpperCase() : rawKey;
                        await fetch(`/blacklist/${currentRegion}`, {
                            method:"DELETE",
                            headers:{ "Content-Type":"application/json" },
                            body: JSON.stringify({ type, key })
                        });
                        loadList(type);
                    });
                });
            }                                                                                      

            submitBtn.addEventListener("click", async (e) => {                                     
                e.preventDefault();
                const type = typeSel.value;
                const key  = type === "asin" ? keyInput.value.trim().toUpperCase() : keyInput.value.trim();
                const reason = memoInput.value.trim();
                await fetch(`/blacklist/${currentRegion}`, {
                    method:"POST",
                    headers:{ "Content-Type":"application/json" },
                    body: JSON.stringify({ type, key, reason })
                });
                resetBtn.click();
                loadList(type);
            });

            validate(); 
            loadList("asin");
        }

        // 商品情報タブ：ASIN検索処理
        const asinBtn = document.getElementById("asinFetchBtn");
        if (asinBtn) {
        asinBtn.addEventListener("click", async () => {
            console.log("検索ボタン押された");

            const asin = document.getElementById("asinInput").value.trim();
            const region = document.getElementById("globalRegion").value;

            console.log("fetch先:", "/product_info", "asin:", asin, "region:", region);

            try {
            const res = await fetch("/amazon/product_info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ asin, region })
            });

            if (!res.ok) {
            console.error("product_info error:", res.status);
            return;
            }
            const resp = await res.json(); // ← ここ一回だけ！

            // 海外側（参考）への反映（上側のままでOK）
            (document.getElementById('asinEcho')      || {}).textContent = resp.asin || "";
            (document.getElementById('eanLabel')      || {}).textContent = resp.ean || "";
            (document.getElementById('categoryLabel') || {}).textContent = resp.category || "";
            (document.getElementById('imgThumb')      || {}).src         = resp.image_url || "";

            // ↓↓↓ ここから下で使う data は resp をそのまま再利用 ↓↓↓
            const data = resp;
            console.log("商品情報APIレス:", data);

            // package優先の整形
            const hasPkgCM  = typeof data.jp_pkg_len_cm === "number";
            const pkgHasDim = data.package_dimensions && ["length","width","height"]
            .some(k => typeof data.package_dimensions[k] === "number");

            const useDim = hasPkgCM
            ? { length: data.jp_pkg_len_cm, width: data.jp_pkg_wid_cm, height: data.jp_pkg_hei_cm, unit: "centimeters" }
            : (pkgHasDim ? { ...data.package_dimensions, unit: "centimeters" } : data.item_dimensions);
            data.item_dimensions = useDim;

            const useW = (typeof data.jp_pkg_wt_kg === "number")
            ? { value: data.jp_pkg_wt_kg, unit: "kilograms" }
            : (data.package_weight && typeof data.package_weight.value === "number"
                ? { ...data.package_weight, unit: "kilograms" }
                : data.item_weight);
            data.item_weight = useW;

            // ＪＰ側
            const dimStr = ["length","width","height"].map(k => {
            const v = useDim[k];
            return (typeof v === "number") ? v.toFixed(1) : "−";
            }).join(" × ");
            const wStr = (typeof useW.value === "number") ? useW.value.toFixed(3) : "−";
            const elDim = document.getElementById("jp_dim");    if (elDim) elDim.textContent = dimStr;
            const elW   = document.getElementById("jp_weight"); if (elW)   elW.textContent   = wStr;

            if (data.status === "ok") {
            document.getElementById("jpTitleLabel").textContent = data.title || "";
            document.getElementById("jpBrandLabel").textContent = data.brand || "";
            document.getElementById("jpManufacturerLabel").textContent = data.manufacturer || "";
            document.getElementById("jpEanLabel").textContent = data.ean || "";
            document.getElementById("jpPriceLabel").textContent = data.jp_price || "";
            document.getElementById("jpCartPriceLabel").textContent  = data.price_cart_jpy != null ? fmtJPY(data.price_cart_jpy) : "--";
            document.getElementById("jpLowestNewLabel").textContent  =
                data.price_lowest_new_jpy != null
                ? fmtJPY(data.price_lowest_new_jpy) + " (" + (data.price_lowest_new_channel || "-") + ")"
                : "--";
            document.getElementById("jpLowestUsedLabel").textContent = data.price_lowest_used_jpy != null ? fmtJPY(data.price_lowest_used_jpy) : "--";
            document.getElementById("pkgLLabel").textContent = data.length || "";
            document.getElementById("pkgWLabel").textContent = data.width || "";
            document.getElementById("pkgHLabel").textContent = data.height || "";
            document.getElementById("pkgWeightLabel").textContent = data.weight || "";

            document.getElementById("jpCategoryLabel").textContent = data.jp_category || "--";
            document.getElementById("jpRankLabel").textContent = data.jp_rank || "--";
            document.getElementById("jpCartSellerLabel").textContent = data.jp_cart_seller || "--";
           
            // 海外側（fg_ 系）
            document.getElementById("fgTitleLabel").textContent = data.fg_title || "";
            document.getElementById("fgBrandLabel").textContent = data.fg_brand || "";
            document.getElementById("fgManufacturerLabel").textContent = data.fg_manufacturer || "";
            document.getElementById("fgEanLabel").textContent = data.fg_ean || "";
            document.getElementById("fgPriceLabel").textContent = data.fg_price || "";
            document.getElementById("fgCartPriceLabel").textContent =
                data.price_cart_foreign != null ? fmtPrice(data.price_cart_foreign) : "--";
            document.getElementById("fgLowestNewLabel").textContent =
                data.price_lowest_new_foreign != null
                    ? fmtPrice(data.price_lowest_new_foreign) + " (" + (data.price_lowest_new_channel_foreign || "-") + ")"
                    : "--";
            document.getElementById("fgLowestUsedLabel").textContent =
                data.price_lowest_used_foreign != null ? fmtPrice(data.price_lowest_used_foreign) : "--";
            document.getElementById("fgPkgLLabel").textContent      = data.fg_pkg_len_cm || "";
            document.getElementById("fgPkgWLabel").textContent      = data.fg_pkg_wid_cm || "";
            document.getElementById("fgPkgHLabel").textContent      = data.fg_pkg_hei_cm || "";
            document.getElementById("fgPkgWeightLabel").textContent = data.fg_pkg_wt_kg  || "";   
            
            document.getElementById('fgCategoryLabel').textContent = (data.fg_category ?? '--'); 
            document.getElementById('fgRankLabel').textContent     = (data.fg_rank ?? '--');  
            document.getElementById("fgCartSellerLabel").textContent = data.fg_cart_seller || "--"; 

            updateShippingPanel(data);
            } else {
            alert("商品情報が取得できませんでした: " + (data.message || "不明なエラー"));
            }
            } catch (err) {
            console.error("商品情報取得エラー:", err);
            alert("商品情報の取得に失敗しました");
            }
        });
        }       
/*        
        // ---- ブランドゲート：最小配線 ----
        const bgc = {
        els: {
            asins: document.getElementById('bgc-asins'),                  
            run: document.getElementById('bgc-run'),                      
            clear: document.getElementById('bgc-clear'),                  
            sample: document.getElementById('bgc-sample'),                
            regionAU: document.getElementById('bgc-region-au'),           
            regionUS: document.getElementById('bgc-region-us'),           
            regionSG: document.getElementById('bgc-region-sg'),           
            tableBody: document.querySelector('#bgc-table tbody'),        
            summary: document.getElementById('bgc-summary'),              
            exportCsv: document.getElementById('bgc-export-csv'),         
        },
        parseAsins() {                                                  
            if (!this.els.asins) return [];                               
            return this.els.asins.value                                   
            .split(/\r?\n/)                                             
            .map(v => v.trim())                                         
            .filter(v => v);                                            
        },                                                              

        render(rows) {
            if (!this.els.tableBody) return;
            this.els.tableBody.innerHTML = '';

            rows.forEach((r) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${r.asin}</td>
                    <td>${r.brand_jp ?? ''}</td>
                    <td>${r.status ?? '—'}</td>
                    <td>${r.note ?? ''}</td>
                `;
                this.els.tableBody.appendChild(tr);
            });
            
        if (this.els.summary) {
            this.els.summary.textContent = `${rows.length}件を表示（未判定）`; // ここはそのまま
        }
        },                                                          
        toCsv(rows) {      
            console.log("rows sample for CSV:", rows.slice(0,3));          
                                               
            const header = ['ASIN','Brand(JP)','AU','US','SG'];            
            const body = rows.map((r,i)=>[r.asin, r.brand??'', r.AU??'', r.US??'', r.SG??'']); 
            return [header, ...body].map(a=>a.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\r\n');  
        }                                                        
        };                                                                

        // クリック配線（最小）                                   
        if (bgc.els.run) {                                               
            bgc.els.run.addEventListener('click', () => {
                const asins = bgc.parseAsins();
                const payload = {
                asins,
                region: window.globalRegion?.value || window.globalRegion || ""
                };

                const overlay = document.getElementById("loadingOverlay");
                const message = document.getElementById("loadingMessage");
                if (overlay) {
                    //if (message) message.textContent = "ブランドゲートを判定しています…";  // ✅ メッセージ付き
                    overlay.style.display = "flex";   // ✅ スピナー表示
                }

                if (bgc.els.summary) bgc.els.summary.textContent = '判定中…';
                if (bgc.els.run) bgc.els.run.disabled = true;

                fetch('/amazon/api/brand_gate_check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
                })
                .then(res => res.json())
                .then(data => {
                    if (data?.status !== 'ok') throw new Error(data?.message || 'API error');
                    const rows = (data.items || []).map(it => ({
                        asin: it.asin,
                        brand: it.brand_jp ?? '',     // CSV用
                        brand_jp: it.brand_jp ?? '',  // UI用
                        region: window.globalRegion,
                        status: it.status ?? '—',      
                        note: it.note ?? ''           
                    }));

                    bgc.render(rows);
                    if (bgc.els.summary) bgc.els.summary.textContent = `${rows.length}件を表示（API判定）`;
                })
                .catch(err => {
                    console.error('brand_gate_check error:', err);
                    if (bgc.els.summary) bgc.els.summary.textContent = 'エラー：判定に失敗しました';
                    alert('ブランドゲート判定に失敗しました：' + err.message);
                })
                .finally(() => {
                    const overlay = document.getElementById("loadingOverlay");
                    if (overlay) overlay.style.display = "none";    

                    if (bgc.els.run) bgc.els.run.disabled = false;
                });                                                
            });                                                            
        }                                                                 

        if (bgc.els.clear) {                                             
        bgc.els.clear.addEventListener('click', () => {                
            if (bgc.els.asins) bgc.els.asins.value = '';                 
            bgc.render([]);                                              
            if (bgc.els.summary) bgc.els.summary.textContent = '未実行'; 
        });                                                            
        }                                                                 

        if (bgc.els.sample) {                                            
        bgc.els.sample.addEventListener('click', () => {               
            if (!bgc.els.asins) return;                                  
            bgc.els.asins.value = ['B0046EC9ZK','B000TEST02','B000TEST03'].join('\n'); 
        });                                                            
        }                                                                 

        if (bgc.els.exportCsv) {                                         
        bgc.els.exportCsv.addEventListener('click', () => {            
            // いま表示中テーブルをCSVに（簡易：DOM→配列再構築）       
            const rows = Array.from(document.querySelectorAll('#bgc-table tbody tr')).map((tr, i) => { 
            const tds = tr.querySelectorAll('td');                     
            return {                                                   
                asin:     tds[0]?.textContent?.trim() || '', 
                brand:    tds[1]?.textContent?.trim() || '',   // ★追加（CSV用）
                brand_jp: tds[1]?.textContent?.trim() || '',   // UI用も残す             
                AU:       tds[2]?.textContent?.trim() || '',                   
                US:       tds[3]?.textContent?.trim() || '',                   
                SG:       tds[4]?.textContent?.trim() || ''              
            };                                                         
            });                                                          
            const csv = bgc.toCsv(rows);                                 
            const blob = new Blob(["\uFEFF" + csv], { type: 'text/csv;charset=utf-8;' });  
            const a = document.createElement('a');                       
            a.href = URL.createObjectURL(blob);                          
            a.download = 'brand_gate_check.csv';                         
            document.body.appendChild(a);                                
            a.click();                                                   
            a.remove();                                                  
        });                                                            
        }                                                                 

        // ブランドゲートのタブ配線を強制で追加
        const brandGateTab =
        document.querySelector('a[href="#brand-gate"]') ||
        document.querySelector('[data-target="brand-gate"]') ||
        document.getElementById('tab-brand-gate');

        if (brandGateTab) {
        brandGateTab.addEventListener('click', (e) => {
            e.preventDefault();
            // すべてのタブを隠す
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            // ブランドゲートを表示
            const view = document.getElementById('brand-gate');
            if (view) view.style.display = 'block';

            // タブの選択状態（アクティブ見た目）も更新
            document.querySelectorAll('.tab-nav a').forEach(a => a.classList.remove('active'));
            brandGateTab.classList.add('active');
        });
        }        
*/

        // ロック解除ボタン
        const unlockBtn = document.getElementById("unlockSellerIdsBtn");
        if (unlockBtn) {
            unlockBtn.addEventListener("click", function () {
                // const region = document.querySelector("input[name='seller_region']:checked")?.value;
                const region = document.getElementById("globalRegion").value;  
                if (!region) {
                    alert("マーケットプレイスを選択してください。");
                    return;
                }

                fetch("/amazon/unlock_seller_ids", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ region: region })
                })
                .then(res => res.json())
                .then(data => {
                    alert(data.message);
                })
                .catch(err => {
                    alert("解除リクエスト失敗: " + err);
                });
            });
        }

        // Debug モード ON/OFF スイッチ
        const debugToggle = document.querySelector("#debugToggle");
        if (debugToggle) {
            fetch("/amazon/api/get_debug")
                .then(res => res.ok ? res.json() : {debug: false})
                .then(data => {
                    debugToggle.checked = !!data.debug;
                })
                .catch(err => {
                    console.error("get_debug failed:", err);
                });

            debugToggle.addEventListener("change", async (e) => {
                const newValue = e.target.checked;
                try {
                    const res = await fetch("/amazon/api/set_debug", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ debug: newValue })
                    });
                    const data = await res.json();
                    console.debug("set_debug response:", data);
                } catch (err) {
                    console.error("set_debug failed:", err);
                }
            });
        }        

        // 初期表示で DB の last_used=1 を反映させる
        const region = document.querySelector("#globalRegion")?.value || "US";

        loadSellerList(region, () => {
            get_seller_info(region).then(() => {
                updateStoreButtonState();   // ✅ ここで呼ぶ
            });
        });

        initAccountForm(); 

        const globalRegionEl = document.getElementById("globalRegion");
        if (globalRegionEl) {
            globalRegionEl.addEventListener("change", function () {
                const region = this.value;

                loadSellerList(region, () => {
                    get_seller_info(region).then(() => {
                        updateStoreButtonState();   // リージョン切替時も有効化判定
                    });
                });
            });
        }
    });

    // 三本メニュー
    (function initAccountMenu(){
    const btn  = document.getElementById('menu-btn'); 
    const menu = document.getElementById('user-dropdown');

    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.hidden = !menu.hidden;
        btn.setAttribute('aria-expanded', String(!menu.hidden));
    });

    document.addEventListener('click', ()=>{ menu.hidden = true; });

    menu.addEventListener('click', (e)=>{
        e.stopPropagation();  
        const a = e.target.closest('.menuitem');
        if (!a) return;
        const act = a.dataset.action;

        if (act === 'open-account') {
        showView('account'); 
        } else if (act === 'open-manual') {
        // TODO: マニュアルURLに遷移
        } else if (act === 'logout') {
        // TODO: ログアウト実装
        }
        menu.hidden = true;
    });

    document.addEventListener('keydown', (e)=>{
        if (e.key === 'Escape') menu.hidden = true;
    });
    })(); 

    function showView(name){
      const targetId = (name === 'account') ? 'view-account' : name;
      const target = document.getElementById(targetId); 
      if (!target) { console.warn(`${targetId} not found`); return; } 

      // すべてのパネルを非表示（.tab-content と data-view を両方ケア）
      document.querySelectorAll('.tab-content, [data-view]').forEach(p => {
        p.classList.remove('active');
        p.setAttribute('hidden',''); 
      });  

      // 対象のみ表示
      target.removeAttribute('hidden');
      target.classList.add('active'); 

      // タブの active 切替（data-tab に "account" / 通常名 が入っている前提）
      document.querySelectorAll('.tab').forEach(b => {
        const key = b.getAttribute('data-tab');
        b.classList.toggle('active', key === (name === 'account' ? 'account' : name));  
      });   

      try { history.replaceState(null, '', `#${targetId}`); } catch {} 
    }                                                                       

    // ID記録表示
    async function loadIdConfig() {
        try {
            const res = await fetch("/api/idconfig", { method: "GET" }); 
            if (!res.ok) return;  

            const data = await res.json();  

            // サーバー実装差に強くする: {status:"ok", config:{...}} でも {...} だけでも拾う
            const cfg = (data && (data.config || (data.status ? null : data))) || null;
            if (!cfg) return; 
            
            const setVal = (sel, val) => { const el = document.querySelector(sel); if (el) el.value = val ?? ""; };

            setVal("#seller_id", cfg.seller_id);          
            setVal("#client_id", cfg.client_id);          
            setVal("#client_secret", cfg.client_secret);  
            setVal("#refresh_token", cfg.refresh_token);  

        } catch (e) {
            console.debug("idconfig load error:", e); 
        }
    }

    // ✅ ASIN抽出処理（CSV統合）ボタンの処理
    function extractASINFromSelected() {  
        console.log("✅ 抽出処理開始");
        const region = document.getElementById("globalRegion").value
        const checkboxes = document.querySelectorAll('#asin-file-list input[type="checkbox"]:checked');
        const selectedFiles = Array.from(checkboxes)
            .map(cb => cb.value)
            .filter(v => v && v !== "on");  // ✅ "on" を除外！

        if (selectedFiles.length === 0) {
            alert("ASINを抽出するCSVファイルを選択してください。");
            return;
        }

        console.log("送信データ", {
            region: region,
            files: selectedFiles
        });

        fetch("/amazon/extract_asin_list", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                region: region, 
                files: selectedFiles
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log("⬅ サーバーからのレスポンス", data); 
            if (data.status === "success") {

                // ✅ 統合直後に必ず更新
                try {
                    loadAsinFileList(region);
                } catch (e) {
                    console.error("❌ ファイル一覧再読み込みでエラー:", e);
                }

                const confirmed = confirm(
                `✅ ASINの統合が完了しました。
                保存場所: ${data.saved_path}

                ✅ OKを選択すると元のファイルは専用ごみ箱
                ✅ キャンセルを選択すると元のファイルは削除されません。`
                );

                if (confirmed) {
                    console.log("✅ 削除する選択をしました");

                    fetch("/amazon/move_to_trash", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ files: data.original_files, region: region })
                    })
                    .then(res => res.json())
                    .then(result => {
                        console.log("🗑️ ごみ箱移動成功:", result);
                        // ここで再更新してもOK（任意）
                        loadAsinFileList(region);
                    })  
                    .catch(error => {
                        console.error("🛑 ごみ箱移動失敗:", error);
                        alert("ファイルの削除に失敗しました。");
                    });

                } else {
                    console.log("❌ 削除しない選択をしました");
                }
            } else {
                alert("ASIN抽出に失敗しました：" + data.message);
            }
        })
    }

    function loadAsinFileList(region) {
        fetch(`/amazon/get_asin_file_list/${region}`)
            .then(r => r.json())
            .then(data => {
                const container = document.getElementById("asin-file-list");
                const asinExtractBtn = document.getElementById("asinExtractBtn");
                if (!container || !asinExtractBtn) return;

                container.innerHTML = "";

                // すべて選択
                const selectAllDiv = document.createElement("div");
                selectAllDiv.style.marginBottom = "4px";
                selectAllDiv.innerHTML = `
                    <input type="checkbox" id="select-all-asins" />
                    <label for="select-all-asins">すべて選択</label>
                `;
                container.appendChild(selectAllDiv);

                // ファイル一覧
                data.files.forEach(file => {
                    console.log("📂 file.name:", file.name, "📎 file.url:", file.url);
                    const div = document.createElement("div");
                    div.innerHTML = `
                        <input type="checkbox" value="${file.name}">
                        <a href="${file.url}" target="_blank">${file.name}</a>
                    `;
                    container.appendChild(div);
                });

                // 状態更新（選択数だけで決定）
                const updateExtractBtnState = () => {
                    const anyChecked = container.querySelectorAll('input[type="checkbox"][value]:checked').length > 0;
                    asinExtractBtn.disabled = !anyChecked;
                };

                // すべて選択
                selectAllDiv.querySelector("#select-all-asins").addEventListener("change", function () {
                    const targets = container.querySelectorAll('input[type="checkbox"][value]');
                    targets.forEach(cb => cb.checked = this.checked);
                    updateExtractBtnState();
                });

                // 個別チェック（change/input 両方で拾う）
                const delegate = e => {
                    if (e.target.matches('input[type="checkbox"][value]')) updateExtractBtnState();
                };
                container.addEventListener("change", delegate);
                container.addEventListener("input", delegate);

                // 初期確定
                updateExtractBtnState();
            })
            .catch(err => console.error("❌ ファイル一覧取得失敗:", err));
    }

    // ✅ セラーID抽出処理：選択したregionに応じてセラーID一覧を取得・プルダウン更新
    function loadSellerList(region) {
        const includeHidden = document.getElementById("toggleHiddenSeller")?.checked ? 1 : 0;

        fetch(`/amazon/get_seller_list?region=${region}&include_hidden=${includeHidden}`)
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById("seller_id");
                select.innerHTML = "";

                // ▼ セラー選択なし（全体検索）を追加
                const allOption = document.createElement("option");
                allOption.value = "";
                allOption.text = "セラー選択なし（全体検索）";
                select.appendChild(allOption);                

                const sellers = data.seller_list || [];
                sellers.forEach(seller => {
                    const option = document.createElement("option");
                    option.value = seller.seller_id;
                    option.text  = seller.seller_name 
                                ? `${seller.seller_name} (${seller.seller_id})`
                                : seller.seller_id;
                    select.appendChild(option);
                });

                // ✅ リスト更新後に last_used を反映
                // get_seller_info(region);
                if (select.value !== "") { // ここを修正
                    get_seller_info(region); // ここを修正
                }                
            })
            .catch(err => console.error("❌ get_seller_list error:", err));
    }

    // ✅ ファイル一覧を読み込んで表示する関数（チェックボックス付き）
    function loadFileList() {
        const region = 
            document.getElementById("globalRegion")?.value ||                  // プルダウン対応（新仕様）
            document.querySelector('input[name="asin_file_region"]:checked')?.value || 
            document.querySelector('input[name="file_region"]:checked')?.value || 
            "au";  // デフォルト値

        const displayArea =
            document.getElementById("asin-file-list") ||
            document.getElementById("file_list_area"); 

        fetch(`/amazon/get_asin_file_list/${region}`)
            .then(response => response.json())
            .then(data => {
                displayArea.innerHTML = "";

                if (data.status === "success" && data.files.length > 0) {
                    // ✅ 一括チェックボックス
                    const selectAll = document.createElement("input");
                    selectAll.type = "checkbox";
                    selectAll.id = "select_all_files";
                    selectAll.addEventListener("change", function () {
                        const checkboxes = displayArea.querySelectorAll(".file-checkbox");
                        checkboxes.forEach(cb => cb.checked = selectAll.checked);
                    });

                    const label = document.createElement("label");
                    label.textContent = " すべて選択";
                    label.htmlFor = "select_all_files";

                    const header = document.createElement("div");
                    header.appendChild(selectAll);
                    header.appendChild(label);
                    header.style.marginBottom = "10px";
                    displayArea.appendChild(header);

                    // ✅ ファイル一覧をチェックボックス付きで表示
                    const ul = document.createElement("ul");
                    ul.id = "file_list";  // 後で取得できるようにID付ける

                    data.files.forEach(file => {
                        const li = document.createElement("li");

                        const checkbox = document.createElement("input");
                        checkbox.type = "checkbox";
                        checkbox.className = "file-checkbox";
                        checkbox.value = file.name;

                        const link = document.createElement("a");
                        link.href = file.url;
                        link.textContent = file.name;
                        link.download = file.name;
                        link.className = "text-blue-600 hover:underline";
                        link.style.marginLeft = "8px";

                        li.appendChild(checkbox);
                        li.appendChild(link);
                        ul.appendChild(li);
                    });

                    displayArea.appendChild(ul);
                } else {
                    displayArea.innerHTML = "<li>ファイルが見つかりませんでした。</li>";
                }
            })
            .catch(error => {
                console.error("エラー:", error);
                displayArea.innerHTML = "<li>読み込みエラーが発生しました。</li>";
            });
    }

    // 専用ごみ箱モーダルを開く
    function openTrashModal() {
    // 既存モーダルを消す
    const old = document.getElementById("trash-modal-overlay");
    if (old) old.remove();

    // オーバーレイ
    const overlay = document.createElement("div");
    overlay.id = "trash-modal-overlay";
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.background = "rgba(0,0,0,.4)";
    overlay.style.zIndex = "9999";
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.remove();
    });

    // モーダル本体
    const modal = document.createElement("div");
    modal.style.width = "640px";
    modal.style.maxWidth = "90vw";
    modal.style.maxHeight = "80vh";
    modal.style.overflow = "auto";
    modal.style.margin = "8vh auto";
    modal.style.background = "#fff";
    modal.style.borderRadius = "12px";
    modal.style.boxShadow = "0 10px 30px rgba(0,0,0,.2)";
    modal.style.padding = "16px 20px";

    // ヘッダ
    const h = document.createElement("h2");
    h.textContent = "専用ごみ箱（C:\\ZSSS_Tool_Trash）";
    h.style.fontSize = "18px";
    h.style.margin = "0 0 12px";

    // 情報行（容量/件数）
    const info = document.createElement("div");
    info.id = "trash-info";
    info.style.marginBottom = "10px";
    info.textContent = "読み込み中…";

    // すべて選択
    const masterWrap = document.createElement("div");
    masterWrap.style.margin = "6px 0 10px";
    const master = document.createElement("input");
    master.type = "checkbox";
    master.id = "trash-select-all";
    const masterLabel = document.createElement("label");
    masterLabel.htmlFor = "trash-select-all";
    masterLabel.textContent = " すべて選択";
    masterWrap.appendChild(master);
    masterWrap.appendChild(masterLabel);

    // 一覧
    const list = document.createElement("ul");
    list.id = "trash-list";
    list.style.listStyle = "none";
    list.style.padding = "0";
    list.style.margin = "0";
    list.style.maxHeight = "46vh";
    list.style.overflow = "auto";
    list.style.border = "1px solid #eee";
    list.style.borderRadius = "8px";

    // ボタン行
    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "8px";
    actions.style.justifyContent = "flex-end";
    actions.style.marginTop = "12px";

    const delBtn = document.createElement("button");
    delBtn.textContent = "削除";
    delBtn.style.background = "#dc2626";
    delBtn.style.color = "#fff";
    delBtn.style.border = "none";
    delBtn.style.padding = "8px 14px";
    delBtn.style.borderRadius = "8px";
    delBtn.style.cursor = "pointer";

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "閉じる";
    closeBtn.style.padding = "8px 14px";
    closeBtn.style.borderRadius = "8px";
    closeBtn.addEventListener("click", () => overlay.remove());

    actions.appendChild(delBtn);
    actions.appendChild(closeBtn);

    modal.appendChild(h);
    modal.appendChild(info);
    modal.appendChild(masterWrap);
    modal.appendChild(list);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // 一覧読み込み
    loadTrashList({ info, list, master, delBtn });
    }

    // 専用ごみ箱の一覧を取得して描画
    function loadTrashList(ctx) {
    const { info, list, master, delBtn } = ctx;

    fetch("/amazon/trash_info")
        .then((r) => r.json())
        .then((data) => {
        const bytesToMB = (b) => (b / 1024 / 1024).toFixed(1);
        info.textContent = `容量: ${bytesToMB(data.bytes)} MB / 件数: ${data.count}`;

        // 一覧初期化
        list.innerHTML = "";
        master.checked = false;
        master.indeterminate = false;

        if (!data.files || !data.files.length) {
            const empty = document.createElement("div");
            empty.textContent = "ごみ箱は空です。";
            empty.style.padding = "12px";
            list.appendChild(empty);
            delBtn.disabled = true;
            return;
        }
        delBtn.disabled = false;

        // 各行
        data.files.forEach((f) => {
            const li = document.createElement("li");
            li.style.display = "flex";
            li.style.alignItems = "center";
            li.style.gap = "8px";
            li.style.padding = "8px 10px";
            li.style.borderBottom = "1px solid #f3f4f6";

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "trash-cb";
            cb.value = f.name;

            const name = document.createElement("span");
            name.textContent = f.name;
            name.style.flex = "1 1 auto";
            name.style.wordBreak = "break-all";

            const meta = document.createElement("span");
            const mb = (f.size / 1024 / 1024).toFixed(2);
            const dt = new Date(f.mtime * 1000).toLocaleString();
            meta.textContent = `${mb} MB / ${dt}`;
            meta.style.color = "#6b7280";
            meta.style.fontSize = "12px";

            li.appendChild(cb);
            li.appendChild(name);
            li.appendChild(meta);
            list.appendChild(li);
        });

        // すべて選択の連動
        const syncMaster = () => {
            const cbs = Array.from(list.querySelectorAll(".trash-cb"));
            const checked = cbs.filter((x) => x.checked).length;
            master.checked = checked === cbs.length;
            master.indeterminate = checked > 0 && checked < cbs.length;
        };
        master.onchange = () => {
            list.querySelectorAll(".trash-cb").forEach((x) => (x.checked = master.checked));
            syncMaster();
        };
        list.addEventListener("change", (e) => {
            if (e.target && e.target.classList.contains("trash-cb")) syncMaster();
        });

        // 削除ボタン
        delBtn.onclick = async () => {
            const selected = Array.from(list.querySelectorAll(".trash-cb:checked")).map((x) => x.value);
            if (!selected.length) {
            alert("削除するファイルを選択してください。");
            return;
            }
            const totalBytes = data.files
            .filter((f) => selected.includes(f.name))
            .reduce((s, f) => s + (f.size || 0), 0);
            const ok = confirm(
            `選択した ${selected.length} 件（合計 ${(totalBytes / 1024 / 1024).toFixed(1)} MB）を完全に削除します。\nOK＝削除 / キャンセル＝中止`
            );
            if (!ok) return;

            delBtn.disabled = true;
            try {
            const resp = await fetch("/amazon/trash_delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ files: selected }),
            });
            const res = await resp.json();
            const del = (res.deleted || []).length;
            const err = (res.errors || []).length;
            if (err) {
                alert(`削除: ${del} 件 / 失敗: ${err} 件`);
            }
            // 再読込
            loadTrashList(ctx);
            } catch (e) {
            alert("削除に失敗しました。");
            } finally {
            delBtn.disabled = false;
            }
        };
        })
        .catch(() => {
        info.textContent = "ごみ箱情報の取得に失敗しました。";
        list.innerHTML = "";
        delBtn.disabled = true;
        });
    }

    // === 送料計算表示ヘルパー（config反映） ===
    function updateShippingPanel(resp) {
    const s = resp && resp.shipping ? resp.shipping : null;
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    const fmt = (v, d=2) => (typeof v === "number" && isFinite(v)) ? v.toFixed(d) : "--";

    if (!s) {
        setText("ship-billable-rounded", "--");
        setText("ship-volumetric", "--");
        setText("ship-actual", "--");
        setText("ship-dims", "--");
        return;
    }
    setText("ship-billable-rounded", fmt(s.billable_weight_kg_rounded, 2) + " kg");
    setText("ship-volumetric", fmt(s.volumetric_weight_kg, 3) + " kg");
    setText("ship-actual", fmt(s.actual_weight_with_pack_kg, 3) + " kg");
    if (s.dims_cm) {
        const L = fmt(s.dims_cm.L, 1), W = fmt(s.dims_cm.W, 1), H = fmt(s.dims_cm.H, 1);
        setText("ship-dims", `${L} × ${W} × ${H}`);
    } else {
        setText("ship-dims", "--");
    }
    }

    // ✅ ASINクリックでコピー
    document.addEventListener("click", function (e) {
        if (e.target && e.target.classList.contains("asin-cell")) {
            const asin = e.target.textContent.trim();
            if (!asin) return;

            navigator.clipboard.writeText(asin).then(() => {
                showCopyNotification("コピーしました", e.target);
            }).catch(err => {
                console.error("コピー失敗:", err);
            });
        }
    });

    // ✅ 通知表示処理（右上にフェードアウト）
    function showCopyNotification(message, targetEl) {
        const rect = targetEl.getBoundingClientRect();

        const notif = document.createElement("div");
        notif.textContent = message;
        notif.style.position = "absolute";
        notif.style.left = (rect.left + window.scrollX) + "px";
        notif.style.top = (rect.top + window.scrollY - 28) + "px"; // 少し上
        notif.style.background = "rgba(23, 162, 184, 0.95)"; // 水色系
        notif.style.color = "#fff";              // 白文字
        notif.style.padding = "4px 8px";
        notif.style.borderRadius = "4px";
        notif.style.fontSize = "12px";
        notif.style.pointerEvents = "none";
        notif.style.opacity = "1";
        notif.style.transition = "opacity 1.5s ease"; // ゆっくり消える
        notif.style.zIndex = "9999";

        document.body.appendChild(notif);

        setTimeout(() => {
            notif.style.opacity = "0";           // フェードアウト開始
            setTimeout(() => notif.remove(), 800);
        }, 600); // 1秒後に消え始める
    }

    // 起動時に「専用ごみ箱」ボタンを追加（配置先が無ければ一覧の上に置く）
    window.addEventListener("DOMContentLoaded", () => {
        const btn = document.createElement("button");
        btn.id = "open-trash-btn";
        btn.textContent = "専用ごみ箱";  
        btn.addEventListener("click", openTrashModal);

    // 置き場所の候補（存在する方に付ける）
    const headerCandidates = [
        document.getElementById("asin-file-controls"),
        document.getElementById("asin-file-list")?.parentElement,
        document.getElementById("file_list_area")?.parentElement,
        document.body
    ].filter(Boolean);

    const host = headerCandidates[0];

    // ▼色・見た目を既存ボタンに合わせる
    const sampleBtn = host?.querySelector("button");                            
    if (sampleBtn) btn.className = sampleBtn.className;                         
    btn.style.marginLeft = "8px";     

    if (host) {
        // 既に同ボタンがあれば重複追加しない
        if (!document.getElementById("open-trash-btn")) {
        host.insertBefore(btn, host.firstChild);
        }
    }
    loadIdConfig();  
    
    
    // アカウント画面のタブ切り替え処理
    const tabHeaders = document.querySelectorAll(".account-tabs .tab-header li");
    const tabPanes = document.querySelectorAll("#view-account .tab-pane");

    tabHeaders.forEach(header => {
    header.addEventListener("click", function () {
        tabHeaders.forEach(h => h.classList.remove("active"));
        this.classList.add("active");

        const targetId = this.getAttribute("data-tab");
        tabPanes.forEach(pane => {
        if (pane.id === targetId) {
            pane.style.display = "block";
            pane.classList.add("active");
        } else {
            pane.style.display = "none";
            pane.classList.remove("active");
        }
        });
    });
    });
});

