let dataDir = "";

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

    // ✅ regionごとの config を取得
    const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase(); 

    fetch(`/amazon/load_config?region=${region}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {

                dataDir = data.data_dir || "data";  // ✅ data_dir に修正

                // ✅ マーケットプレイスはプルダウンの値をそのまま使う
                if (globalRegionEl) {
                    globalRegionEl.value = region.toUpperCase();
                }

                // ✅ セラーリストをロードしてから選択復元
                loadSellerList(region);
                updateStoreButtonState();

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

        // 保存
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

        // 削除
        const deleteBtn = document.getElementById("deleteSellerBtn");
        if (deleteBtn) {
            deleteBtn.addEventListener("click", async function () {

                const sellerId = document.getElementById("manual_seller_id").value.trim();

                if (!sellerId) {
                    alert("削除するセラーを選択してください。");
                    return;
                }

                if (!confirm("このセラーを削除しますか？")) {
                    return;
                }

                const region = document.getElementById("globalRegion").value.toLowerCase();

                const formData = new URLSearchParams();
                formData.append("region", region);
                formData.append("seller_id", sellerId);

                fetch("/amazon/delete_seller", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    body: formData.toString()
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === "success") {

                        loadSellerList(region);

                        document.getElementById("seller_id").value = "";
                        document.getElementById("manual_seller_id").value = "";
                        document.getElementById("shop_name").value = "";
                        document.getElementById("remarks").value = "";
                        document.getElementById("hidden").checked = false;

                        updateStoreButtonState();

                        // alert("削除しました。");

                    } else {
                        alert(data.message || "削除に失敗しました。");
                    }
                })
                .catch(error => {
                    alert("通信エラー: " + error);
                });

            });
        }        
        // ✅ ページロード時にセラーリストを初期ロード
        window.addEventListener("load", function () {
            const region = document.getElementById("globalRegion").value.toLowerCase();
            console.log("初期ロード region:", region);
            loadSellerList(region);
        });  

        // ✅ トグル切替時にリストを再ロード
        document.getElementById("toggleHiddenSeller")?.addEventListener("change", function () {
            const region = document.getElementById("globalRegion").value.toLowerCase();
            loadSellerList(region);
        });
    });

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
            if (dropdown && data.seller_id) {
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
            const sellerIdInput = document.getElementById("manual_seller_id");
            const shopInput     = document.getElementById("shop_name");
            const remarksInput  = document.getElementById("remarks");
            const hiddenCheck   = document.getElementById("hidden");

            if (sellerIdInput) sellerIdInput.value = data.seller_id || "";
            if (shopInput)     shopInput.value     = data.shop_name || "";
            if (remarksInput)  remarksInput.value  = data.remarks || "";
            if (hiddenCheck)   hiddenCheck.checked = (data.hidden === "TRUE");

        } catch (err) {
            console.error("get_seller_info error:", err);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {         

        // 初期表示で DB の last_used=1 を反映させる
        const region = document.querySelector("#globalRegion")?.value || "US";

        loadSellerList(region, () => {
            get_seller_info(region).then(() => {
                updateStoreButtonState();   // ✅ ここで呼ぶ
            });
        });

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
                    const mark = seller.hidden ? "🚫 " : "";
                    option.text  = seller.seller_name 
                                ? `${mark}${seller.seller_name} (${seller.seller_id})`
                                : `${mark}${seller.seller_id}`;
                    select.appendChild(option);
                });

                // ✅ リスト更新後に last_used を反映
                get_seller_info(region);
                // }                
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
    h.textContent = "専用ごみ箱（C:\\Research_Tool_Trash）";
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
});

