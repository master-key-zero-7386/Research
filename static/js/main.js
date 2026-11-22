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
                loadCategoryList(region);
                loadBrandList(region);
                loadGenreCategoryList(region);
                updateStoreButtonState();
            });

            // 初期ロード時にセラーリストとボタン状態をセット
            if (globalRegionEl.value) {
                loadSellerList(globalRegionEl.value);
                loadCategoryList(globalRegionEl.value);
                loadBrandList(globalRegionEl.value);
                loadGenreCategoryList(globalRegionEl.value);
                updateStoreButtonState();
            }
        }
        
    document.getElementById("seller_id").addEventListener("change", updateStoreButtonState);
    document.getElementById("manual_seller_id").addEventListener("input", updateStoreButtonState);

    updateStoreButtonState();

    // ✅ 「カテゴリー（大分類）」を選ぶと、カテゴリーノードID欄に自動で入力する
    document.getElementById("genre_category_select")?.addEventListener("change", function () {
        const nodeIdInput = document.getElementById("category_node_id_manual");
        if (nodeIdInput && this.value) {
            nodeIdInput.value = this.value;
        }
    });

    // ✅ カテゴリーノードIDの手動指定を確認する（この時点ではまだ保存しない）
    function verifyCategoryNodeId() {
        const idInput = document.getElementById("category_node_id_manual");
        const resultEl = document.getElementById("category_node_id_verify_result");
        const confirmRow = document.getElementById("category_node_id_confirm_row");
        const confirmNameInput = document.getElementById("category_node_id_confirm_name");

        const idValue = idInput.value.trim();
        const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();

        confirmRow.style.display = "none";

        if (!idValue) {
            resultEl.textContent = "IDを入力してください";
            resultEl.style.color = "#c0392b";
            return;
        }

        resultEl.textContent = "確認中...";
        resultEl.style.color = "#666";

        fetch(`/amazon/lookup_category_name?region=${region}&node_id=${encodeURIComponent(idValue)}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    resultEl.textContent = "↓内容を確認して、正しければ保存してください";
                    resultEl.style.color = "#666";
                    confirmNameInput.value = data.name;
                    confirmRow.style.display = "";
                } else {
                    resultEl.textContent = `❌ ${data.message || "確認できませんでした"}`;
                    resultEl.style.color = "#c0392b";
                }
            })
            .catch(err => {
                resultEl.textContent = "❌ 通信エラー";
                resultEl.style.color = "#c0392b";
                console.error("❌ lookup_category_name error:", err);
            });
    }

    // ✅ ユーザーが内容を確認・修正したうえで、実際にDBへ保存する
    function saveCategoryNodeId() {
        const idInput = document.getElementById("category_node_id_manual");
        const resultEl = document.getElementById("category_node_id_verify_result");
        const confirmRow = document.getElementById("category_node_id_confirm_row");
        const confirmNameInput = document.getElementById("category_node_id_confirm_name");

        const idValue = idInput.value.trim();
        const nameValue = confirmNameInput.value.trim();
        const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();

        if (!nameValue) {
            resultEl.textContent = "名前を入力してください";
            resultEl.style.color = "#c0392b";
            return;
        }

        fetch("/amazon/save_category_name", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ region, node_id: idValue, name: nameValue })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    resultEl.textContent = `✅ 「${data.name}」として保存しました`;
                    resultEl.style.color = "#2e7d32";
                    confirmRow.style.display = "none";
                    loadCategoryList(region);  // ✅ 保存直後にカテゴリー名候補一覧を再取得して反映する
                } else {
                    resultEl.textContent = `❌ ${data.message || "保存できませんでした"}`;
                    resultEl.style.color = "#c0392b";
                }
            })
            .catch(err => {
                resultEl.textContent = "❌ 通信エラー";
                resultEl.style.color = "#c0392b";
                console.error("❌ save_category_name error:", err);
            });
    }

    document.getElementById("verifyCategoryNodeIdBtn")?.addEventListener("click", verifyCategoryNodeId);
    document.getElementById("saveCategoryNodeIdBtn")?.addEventListener("click", saveCategoryNodeId);

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
                loadCategoryList(region);
                loadBrandList(region);
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
        } else if (region === "jp") {
            baseUrl = "https://www.amazon.co.jp/sp?seller=";
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
        const category = (document.getElementById("category")?.value || "").trim();
        const categoryNodeIdManual = (document.getElementById("category_node_id_manual")?.value || "").trim();
        const minPrice = document.getElementById("min_price").value.trim();
        const maxPrice = document.getElementById("max_price").value.trim();
        const stepPrice = document.getElementById("step_price").value.trim();
        const outputFolder = document.getElementById("output_folder").value.trim();
        // 「自動開始時間」は廃止（常に手動確認バナーを使うため
        // const confirmWait = document.getElementById("confirm_wait").value.trim();

        // ✅ config 保存（修正なし）
        fetch("/amazon/save_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                region, seller_id: sellerId, brand, category, min_price: minPrice,
                max_price: maxPrice, step_price: stepPrice,
                output_folder: outputFolder, remarks,
                category_node_id_manual: categoryNodeIdManual
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
                    brand, category, min_price: minPrice,
                    max_price: maxPrice, step_price: stepPrice,
                    output_folder: outputFolder,
                    remarks,
                    category_node_id_manual: categoryNodeIdManual
                })
            });
        })
        .then(response => {
            if (!response.ok) {
                return response.json()
                    .catch(() => ({}))
                    .then(err => { throw new Error(err.message || "処理リクエスト失敗"); });
            }
        })
        .catch(error => {
            console.error("❌ エラー:", error);
            alert(error.message || "実行中にエラーが発生しました");
        });
    }

    const runBtn = document.getElementById("runBtn");
    if (runBtn) {
        runBtn.addEventListener("click", (event) => {
            event.preventDefault();
            runExtraction();
        });
    }

    // ✅ 停止ボタン（実行中プロセスを強制終了する）
    const stopScrapeBtn = document.getElementById("stopScrapeBtn");
    if (stopScrapeBtn) {
        stopScrapeBtn.addEventListener("click", () => {
            const region = document.getElementById("globalRegion").value.toLowerCase();
            if (!confirm("実行中の取得を停止しますか？")) return;

            stopScrapeBtn.disabled = true;
            fetch("/amazon/stop_scrape", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ region })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== "success") {
                    alert(data.message || "停止に失敗しました。");
                }
                pollScrapeStatus();
            })
            .catch(error => {
                console.error("❌ 停止失敗:", error);
                alert("停止に失敗しました。");
            });
        });
    }

    // ✅ 「リサーチ」「詳細リサーチ」はdiv切替ではなく、同一DOM内の
    //    advanced-only要素を隠す/見せるモード切替（body.mode-simple）
    const modeTabs = document.querySelectorAll('.tab[data-mode]');

    modeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const mode = tab.getAttribute('data-mode');
            modeTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.body.classList.toggle('mode-simple', mode === 'simple');

            // simpleモードに切り替えた時、advanced-onlyなサブタブが選択中なら
            // 表示できるサブタブ（詳細設定）に戻す
            if (mode === 'simple') {
                const activeSubtab = document.querySelector('.subtab.active');
                if (activeSubtab && activeSubtab.classList.contains('advanced-only')) {
                    const fallback = document.querySelector('.subtab[data-subtab="detail-settings"]');
                    if (fallback) fallback.click();
                }
            }
        });
    });

    // ✅ サブタブ切替（詳細設定／ASIN抽出／ブランド一覧）
    const subtabs = document.querySelectorAll('.subtab');
    const subcontents = document.querySelectorAll('.subtab-content');

    subtabs.forEach(subtab => {
        subtab.addEventListener('click', () => {
            const targetId = subtab.getAttribute('data-subtab');
            subtabs.forEach(t => t.classList.remove('active'));
            subcontents.forEach(c => c.classList.remove('active'));
            subtab.classList.add('active');
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
                // ✅ get_seller_info()が manual_seller_id 欄を書き換え終わるのを待ってから
                //    履歴を再取得する（先に呼ぶと、書き換え前の古いセラーIDで検索してしまう）
                get_seller_info(region, selectedSeller).then(() => {
                    refreshGenreHistory();
                });
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
                .then(res => res.json())
                .then(data => {
                    if (data.status === "success") {
                        // ✅ 保存直後にプルダウンを更新し、保存したセラーを選択状態にする
                        // （loadSellerListだとlast_usedの情報で入力欄が上書きされてしまうため使わない）
                        refreshSellerDropdown(region).then(() => {
                            const dropdown = document.getElementById("seller_id");
                            if (dropdown) dropdown.value = usedSellerId;
                            updateStoreButtonState();
                        });
                    } else {
                        alert(data.message || "保存に失敗しました。");
                    }
                })
                .catch(error => {
                    alert("通信エラー: " + error);
                });
            });
        }

        // クリア
        const clearBtn = document.getElementById("clearSellerBtn");
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                document.getElementById("seller_id").value = "";
                document.getElementById("manual_seller_id").value = "";
                document.getElementById("shop_name").value = "";
                document.getElementById("remarks").value = "";
                document.getElementById("hidden").checked = false;
                updateStoreButtonState();
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
                refreshGenreHistory();
            });
        });

        const globalRegionEl = document.getElementById("globalRegion");
        if (globalRegionEl) {
            globalRegionEl.addEventListener("change", function () {
                const region = this.value;

                loadSellerList(region, () => {
                    get_seller_info(region).then(() => {
                        updateStoreButtonState();   // リージョン切替時も有効化判定
                        refreshGenreHistory();
                    });
                });
            });
        }

        // ✅ セラープルダウンの履歴更新は上の get_seller_info().then() 側に統一したので、ここでは呼ばない
        //   （同時に呼ぶと get_seller_info が manual_seller_id を書き換える前に走り、1つ前のセラーの
        //   　履歴が表示されたままになる競合バグがあった）
        document.getElementById("manual_seller_id")?.addEventListener("change", refreshGenreHistory);
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

    // ✅ 選択したファイルを専用ごみ箱へ移動（ダウンロード後の削除用）
        document.addEventListener("click", function (e) {
            if (e.target && e.target.id === "asinDeleteBtn") {
                const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();
                const container = document.getElementById("asin-file-list");
                const checked = Array.from(container.querySelectorAll('input[type="checkbox"][value]:checked'))
                    .map(cb => cb.value);

                if (checked.length === 0) return;

                if (!confirm(`選択した${checked.length}件を専用ごみ箱に移動します。よろしいですか？`)) return;

                fetch("/amazon/move_to_trash", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ region: region, files: checked })
                })
                .then(r => r.json())
                .then(data => {
                    loadAsinFileList(region);
                })
                .catch(err => {
                    console.error("❌ 削除失敗:", err);
                    alert("削除に失敗しました。");
                });
            }
        });

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
                const asinDeleteBtn = document.getElementById("asinDeleteBtn");
                const updateExtractBtnState = () => {
                    const anyChecked = container.querySelectorAll('input[type="checkbox"][value]:checked').length > 0;
                    asinExtractBtn.disabled = !anyChecked;
                    if (asinDeleteBtn) asinDeleteBtn.disabled = !anyChecked;
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

                // Shift/Ctrl(Cmd)クリックでの範囲選択・複数選択に対応
                let lastAsinCheckbox = null;
                container.addEventListener("click", function (e) {
                    const target = e.target;
                    if (!target.matches('input[type="checkbox"][value]')) return;

                    if (e.shiftKey && lastAsinCheckbox && lastAsinCheckbox !== target) {
                        const boxes = Array.from(container.querySelectorAll('input[type="checkbox"][value]'));
                        const start = boxes.indexOf(lastAsinCheckbox);
                        const end = boxes.indexOf(target);
                        if (start !== -1 && end !== -1) {
                            const [from, to] = start < end ? [start, end] : [end, start];
                            const state = target.checked;
                            for (let i = from; i <= to; i++) {
                                boxes[i].checked = state;
                            }
                        }
                    }

                    // Ctrl/Cmd+クリックは個別トグル（既定動作のまま、他の選択は維持）
                    lastAsinCheckbox = target;
                    updateExtractBtnState();
                });

                // 初期確定
                updateExtractBtnState();
            })
            .catch(err => console.error("❌ ファイル一覧取得失敗:", err));
    }

    // ✅ セラーID一覧を取得してプルダウンの選択肢だけを更新（入力欄には触れない）
    function refreshSellerDropdown(region) {
        const includeHidden = document.getElementById("toggleHiddenSeller")?.checked ? 1 : 0;

        return fetch(`/amazon/get_seller_list?region=${region}&include_hidden=${includeHidden}`)
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
            })
            .catch(err => console.error("❌ get_seller_list error:", err));
    }

    // ✅ セラーID抽出処理：選択したregionに応じてセラーID一覧を取得・プルダウン更新
    function loadSellerList(region) {
        refreshSellerDropdown(region).then(() => {
            // ✅ リスト更新後に last_used を反映
            get_seller_info(region);
        });
    }

    // ✅ カテゴリー名候補：選択したregionに応じてDB保存済みカテゴリー一覧を取得・プルダウン更新
    function loadCategoryList(region) {
        fetch(`/amazon/get_category_list?region=${region}`)
            .then(response => response.json())
            .then(data => {
                const datalist = document.getElementById("category_options");
                if (!datalist) return;
                datalist.innerHTML = "";
                (data.category_list || []).forEach(name => {
                    const opt = document.createElement("option");
                    opt.value = name;
                    datalist.appendChild(opt);
                });
            })
            .catch(err => console.error("❌ get_category_list error:", err));
    }

    // ✅ ブランド名候補：選択したregionに応じてDB保存済みブランド一覧を取得・プルダウン更新
    function loadBrandList(region) {
        fetch(`/amazon/get_brand_list?region=${region}`)
            .then(response => response.json())
            .then(data => {
                const datalist = document.getElementById("brand_options");
                if (!datalist) return;
                datalist.innerHTML = "";
                (data.brand_list || []).forEach(name => {
                    const opt = document.createElement("option");
                    opt.value = name;
                    datalist.appendChild(opt);
                });
            })
            .catch(err => console.error("❌ get_brand_list error:", err));
    }

    // ✅ カテゴリー（大分類）候補：ジャンル分析が自動検出した大分類一覧を取得・プルダウン更新
    //    選択するとカテゴリーノードID欄に自動で入力される（category_masterとは別のgenre_master.db）
    function loadGenreCategoryList(region) {
        fetch(`/amazon/get_genre_list?region=${region}`)
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById("genre_category_select");
                if (!select) return;
                select.innerHTML = '<option value="">-- ジャンル分析で検出した大分類から選択（任意） --</option>';
                (data.genre_list || []).forEach(genre => {
                    const opt = document.createElement("option");
                    opt.value = genre.node_id;
                    opt.textContent = genre.name;
                    select.appendChild(opt);
                });
            })
            .catch(err => console.error("❌ get_genre_list error:", err));
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
    h.textContent = "専用ごみ箱";
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

    const restoreBtn = document.createElement("button");
    restoreBtn.textContent = "元に戻す";
    restoreBtn.style.background = "#2563eb";
    restoreBtn.style.color = "#fff";
    restoreBtn.style.border = "none";
    restoreBtn.style.padding = "8px 14px";
    restoreBtn.style.borderRadius = "8px";
    restoreBtn.style.cursor = "pointer";    

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "閉じる";
    closeBtn.style.padding = "8px 14px";
    closeBtn.style.borderRadius = "8px";
    closeBtn.addEventListener("click", () => overlay.remove());

    actions.appendChild(restoreBtn);
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
    loadTrashList({ info, list, master, delBtn, restoreBtn });
    }

    // 専用ごみ箱の一覧を取得して描画
    function loadTrashList(ctx) {
    const { info, list, master, delBtn, restoreBtn } = ctx;

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
                    restoreBtn.disabled = true;
                    return;
                }
                delBtn.disabled = false;
                restoreBtn.disabled = false;

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

        // 元に戻すボタン
        restoreBtn.onclick = async () => {
            const selected = Array.from(list.querySelectorAll(".trash-cb:checked")).map((x) => x.value);
            if (!selected.length) {
                alert("元に戻すファイルを選択してください。");
                return;
            }
            const ok = confirm(`選択した ${selected.length} 件を元の場所に戻します。よろしいですか？`);
            if (!ok) return;

            restoreBtn.disabled = true;
            try {
                const resp = await fetch("/amazon/restore_from_trash", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ files: selected }),
                });
                const result = await resp.json();
                if (result.errors && result.errors.length) {
                    alert("一部のファイルを復元できませんでした。詳しくはコンソールを確認してください。");
                    console.error("復元エラー:", result.errors);
                }
                loadTrashList(ctx);
            } catch (e) {
                alert("復元に失敗しました。");
                console.error(e);
            } finally {
                restoreBtn.disabled = false;
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

// ✅ 価格帯ごとの取得状況（20ページ上限で頭打ちになった価格帯）をResearch画面に表示する
function renderScrapeStatus(data) {
    const el = document.getElementById("scrapeStatusList");

    const stopBtn = document.getElementById("stopScrapeBtn");
    if (stopBtn) stopBtn.disabled = !data.running;

    if (!el) return;

    const bands = data.bands || [];
    if (bands.length === 0) {
        el.textContent = data.running ? "実行中…（結果はまだありません）" : "まだ実行していません";
        return;
    }

    const rows = bands.map(b => {
        const label = `$${b.range}`;
        const state = b.capped
            ? `<span style="color:#c0392b; font-weight:bold;">オーバー（${b.count}件）</span>`
            : `<span style="color:#555;">-（${b.count}件）</span>`;
        return `<div>${label}　${state}</div>`;
    }).join("");

    let footer = "";
    if (data.running) {
        footer = `<div style="margin-top:6px; color:#888;">実行中…</div>`;
    } else if (data.stopped_by_user) {
        footer = `<div style="margin-top:6px; color:#c0392b;">ユーザーにより停止されました</div>`;
    }

    el.innerHTML = rows + footer;
}

function pollScrapeStatus() {
    const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();
    fetch(`/amazon/scrape_status?region=${region}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") renderScrapeStatus(data);
        })
        .catch(err => console.error("❌ scrape_status取得失敗:", err));
}

window.addEventListener("DOMContentLoaded", () => {
    pollScrapeStatus();
    setInterval(pollScrapeStatus, 5000);

    document.getElementById("globalRegion")?.addEventListener("change", pollScrapeStatus);
});

// ✅ 自分用：ジャンル分析（セラーIDだけを入力に、出品ジャンルと件数を調べる）
function runGenreSummary() {
    const region = document.getElementById("globalRegion").value.toLowerCase();
    const manualInput = document.getElementById("manual_seller_id").value.trim();
    const dropdownValue = document.getElementById("seller_id").value.trim();
    const sellerId = manualInput || dropdownValue;

    if (!sellerId) {
        alert("セラーIDを指定してください。");
        return;
    }

    fetch("/amazon/run_genre_summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region, seller_id: sellerId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status !== "success") {
            alert(data.message || "開始に失敗しました。");
            return;
        }
        pollGenreSummaryStatus();
    })
    .catch(err => {
        console.error("❌ ジャンル分析開始失敗:", err);
        alert("開始に失敗しました。");
    });
}

function renderGenreSummary(data) {
    const el = document.getElementById("genre-summary-result");
    const runBtn = document.getElementById("genreSummaryRunBtn");
    const stopBtn = document.getElementById("genreSummaryStopBtn");
    if (runBtn) runBtn.disabled = !!data.running;
    if (stopBtn) stopBtn.disabled = !data.running;
    if (!el) return;

    if (data.error) {
        el.innerHTML = `<div style="color:#c0392b;">❌ ${data.error}</div>`;
        return;
    }

    const genres = data.genres || [];
    if (genres.length === 0) {
        el.textContent = data.running ? "実行中…（結果はまだありません）" : "まだ実行していません";
        return;
    }

    let html = "";
    if (typeof data.total_count === "number") {
        html += `<div style="margin-bottom:6px;">全体件数（目安）: ${data.total_count.toLocaleString()}件</div>`;
    }
    html += `<table style="border-collapse:collapse;">`;
    html += `<tr><th style="text-align:left; border-bottom:1px solid #ccc; padding:2px 10px 2px 0;">ジャンル</th><th style="text-align:right; border-bottom:1px solid #ccc; padding:2px 0;">件数</th></tr>`;
    genres.forEach(g => {
        html += `<tr><td style="padding:2px 10px 2px 0;">${g.name}</td><td style="text-align:right; padding:2px 0;">${g.count}</td></tr>`;
    });
    html += `</table>`;

    if (data.running) {
        html += `<div style="margin-top:6px; color:#888;">実行中…</div>`;
    } else if (data.stopped_by_user) {
        html += `<div style="margin-top:6px; color:#c0392b;">ユーザーにより停止されました</div>`;
    } else if (data.saved_path) {
        html += `<div style="margin-top:6px;">保存先: ${data.saved_path}</div>`;
    }

    el.innerHTML = html;

    // ✅ 分析が完了したら、左側の「ジャンル分析 履歴」パネルも最新化する
    if (!data.running) {
        refreshGenreHistory();
    }
}

// ✅ 自分用：選択中のセラーに対する「ジャンル分析」実行履歴（セラー情報ブロック右側に表示）
function getCurrentSellerId() {
    const manualInput = document.getElementById("manual_seller_id")?.value.trim() || "";
    const dropdownValue = document.getElementById("seller_id")?.value.trim() || "";
    return manualInput || dropdownValue;
}

function renderGenreHistory(history) {
    const el = document.getElementById("genre-history-panel");
    if (!el) return;

    if (!history || history.length === 0) {
        el.textContent = "履歴はまだありません";
        return;
    }

    let html = "";
    history.forEach(run => {
        html += `<div style="margin-bottom:12px;">`;
        html += `<div style="font-weight:600; color:#555; margin-bottom:2px;">${run.run_at}</div>`;
        html += `<table style="border-collapse:collapse; width:100%;">`;
        run.genres.forEach(g => {
            html += `<tr><td style="padding:1px 8px 1px 0;">${g.name}</td><td style="text-align:right; padding:1px 0;">${g.count}</td></tr>`;
        });
        html += `</table></div>`;
    });

    el.innerHTML = html;
}

function loadGenreHistory(region, sellerId) {
    const el = document.getElementById("genre-history-panel");
    if (!el) return;

    if (!sellerId) {
        el.textContent = "セラーを選択してください";
        return;
    }

    fetch(`/amazon/get_genre_history?region=${region}&seller_id=${encodeURIComponent(sellerId)}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") renderGenreHistory(data.history);
        })
        .catch(err => console.error("❌ get_genre_history error:", err));
}

function refreshGenreHistory() {
    if (!document.getElementById("genre-history-panel")) return; // 配布版には存在しない
    const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();
    loadGenreHistory(region, getCurrentSellerId());
}

function pollGenreSummaryStatus() {
    const region = (document.getElementById("globalRegion")?.value || "US").toLowerCase();
    fetch(`/amazon/genre_summary_status?region=${region}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") renderGenreSummary(data);
        })
        .catch(err => console.error("❌ genre_summary_status取得失敗:", err));
}

window.addEventListener("DOMContentLoaded", () => {
    const runBtn = document.getElementById("genreSummaryRunBtn");
    if (runBtn) runBtn.addEventListener("click", runGenreSummary);

    const stopBtn = document.getElementById("genreSummaryStopBtn");
    if (stopBtn) {
        stopBtn.addEventListener("click", () => {
            const region = document.getElementById("globalRegion").value.toLowerCase();
            if (!confirm("実行中のジャンル分析を停止しますか？")) return;
            stopBtn.disabled = true;
            fetch("/amazon/stop_genre_summary", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ region })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== "success") alert(data.message || "停止に失敗しました。");
                pollGenreSummaryStatus();
            })
            .catch(() => alert("停止に失敗しました。"));
        });
    }

    pollGenreSummaryStatus();
    setInterval(pollGenreSummaryStatus, 5000);
    document.getElementById("globalRegion")?.addEventListener("change", pollGenreSummaryStatus);
});

// ✅ データのエクスポート/インポート（バックアップ・他PCへの移行用）
function getSelectedDataIORegions() {
    return Array.from(document.querySelectorAll(".dataio-region:checked")).map(el => el.value);
}

function getSelectedDataIODatasets() {
    // offsetParent !== null で「配布版 or 簡易モードで非表示」のチェックボックスは対象から除外する
    return Array.from(document.querySelectorAll(".dataio-dataset"))
        .filter(el => el.checked && el.offsetParent !== null)
        .map(el => el.value);
}

function refreshDataIOCounts() {
    const regions = getSelectedDataIORegions();
    const params = regions.length ? `?regions=${regions.join(",")}` : "";

    fetch(`/amazon/data_io_summary${params}`)
        .then(res => res.json())
        .then(data => {
            if (data.status !== "success") return;
            const counts = data.counts || {};
            document.querySelectorAll(".dataio-count").forEach(span => {
                const key = span.dataset.key;
                if (key === "genre_master") {
                    span.textContent = `（大分類${counts.genre_master ?? 0}件／履歴${counts.genre_history ?? 0}件）`;
                } else if (key in counts) {
                    span.textContent = `（${counts[key]}件）`;
                }
            });
        })
        .catch(err => console.error("❌ data_io_summary取得失敗:", err));
}

window.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("dataIOModal");
    const openBtn = document.getElementById("dataIOOpenBtn");
    const closeBtn = document.getElementById("dataIOCloseBtn");
    const exportBtn = document.getElementById("dataIOExportBtn");
    const importBtn = document.getElementById("dataIOImportBtn");
    const importFile = document.getElementById("dataIOImportFile");
    const resultEl = document.getElementById("dataIOResult");

    if (!modal || !openBtn) return;

    openBtn.addEventListener("click", () => {
        resultEl.textContent = "";
        modal.style.display = "flex";
        refreshDataIOCounts();
    });

    closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
    });

    document.querySelectorAll(".dataio-region").forEach(cb => {
        cb.addEventListener("change", refreshDataIOCounts);
    });

    exportBtn.addEventListener("click", () => {
        const datasets = getSelectedDataIODatasets();
        const regions = getSelectedDataIORegions();

        if (datasets.length === 0) {
            alert("エクスポートするデータを選択してください。");
            return;
        }

        const params = new URLSearchParams();
        params.set("datasets", datasets.join(","));
        if (regions.length) params.set("regions", regions.join(","));

        window.location.href = `/amazon/export_data?${params.toString()}`;
    });

    importBtn.addEventListener("click", () => {
        const file = importFile.files[0];
        if (!file) {
            alert("インポートするファイルを選択してください。");
            return;
        }
        if (!confirm("インポートすると、同じキー（セラーID・ブランド名等）の既存データは上書きされます。続けますか？")) {
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        resultEl.textContent = "インポート中…";
        resultEl.style.color = "#666";
        importBtn.disabled = true;

        fetch("/amazon/import_data", { method: "POST", body: formData })
            .then(res => res.json())
            .then(data => {
                importBtn.disabled = false;

                if (data.status !== "success") {
                    resultEl.textContent = data.message || "インポートに失敗しました。";
                    resultEl.style.color = "#c0392b";
                    return;
                }

                const r = data.result || {};
                const parts = [];
                if ("seller_list" in r) parts.push(`セラー一覧 ${r.seller_list}件`);
                if ("brand_master" in r) parts.push(`ブランドマスタ ${r.brand_master}件`);
                if ("category_master" in r) parts.push(`カテゴリーマスタ ${r.category_master}件`);
                if ("genre_master" in r) parts.push(`ジャンル分析（大分類）${r.genre_master}件`);
                if ("genre_history" in r) parts.push(`ジャンル分析（履歴・新規分のみ）${r.genre_history}件`);

                resultEl.textContent = `インポート完了: ${parts.join(" / ")}　※画面を更新します…`;
                resultEl.style.color = "#2e7d32";

                // ✅ セラー一覧・各種プルダウン・履歴パネルなどを確実に最新化するため、
                //    結果表示を一瞬見せてからページを再読み込みする
                setTimeout(() => window.location.reload(), 1200);
            })
            .catch(err => {
                importBtn.disabled = false;
                resultEl.textContent = "インポートに失敗しました。";
                resultEl.style.color = "#c0392b";
                console.error("❌ import_data error:", err);
            });
    });
});

