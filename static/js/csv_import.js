document.addEventListener("DOMContentLoaded", () => {
    const uploadBtn = document.getElementById("csvUploadBtn");
    const fileInput = document.getElementById("csvFileInput");
    const fileNameBox = document.getElementById("csvFileName");
    const resultArea = document.getElementById("csvResultArea");

    // 枠をクリックしたら file input を開く
    if (fileNameBox) {
        fileNameBox.addEventListener("click", () => {
            fileInput.click();
        });
    }

    // ファイル選択したら枠にファイル名を表示
    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            const fileName = e.target.files.length ? e.target.files[0].name : "";
            fileNameBox.value = fileName;
        });
    }

    // 「アップロード」ボタン処理
    if (uploadBtn) {
        uploadBtn.addEventListener("click", () => {
            if (!fileInput.files.length) {
                alert("CSVファイルを選択してください");
                return;
            }

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            formData.append("region", document.getElementById("globalRegion").value);

            const overlay = document.getElementById("loadingOverlay");
            const message = document.getElementById("loadingMessage");
            if (overlay) {
                //message.textContent = "CSVを読み込んでいます…";
                overlay.style.display = "flex";
            }            

            fetch("/amazon/csv_import", {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log("CSV Import Response:", data);
                if (data.total_count) {
                    message.textContent = `${data.total_count} 件のASINリストを読み込んでいます…`;
                }

                if (data.status === "success") {
                    // ▼ テーブルをクリア
                    let okTable = $('#csvOkTable').DataTable();
                    let listedTable = $('#csvListedTable').DataTable();
                    let blacklistTable = $('#csvBlacklistTable').DataTable();

                    okTable.clear();
                    listedTable.clear();
                    blacklistTable.clear();

                    // ▼ 出品可能（ok）
                    data.ok.forEach(item => {
                        okTable.row.add(item);
                    });

                    // ▼ 出品済み（listed）
                    data.listed.forEach(item => {
                        listedTable.row.add(item);
                    });

                    // ▼ ブラックリスト（blacklist）
                    data.blacklist.forEach(item => {
                        blacklistTable.row.add(item);
                    });

                    // ▼ 再描画
                    okTable.draw();
                    listedTable.draw();
                    blacklistTable.draw();

                } else {
                    // エラー時のみアラート表示
                    alert(data.message);
                }
            })
            .catch(err => {
                alert("エラー: " + err);
            })
            .finally(() => {
                if (overlay) overlay.style.display = "none";
            });
        });
    }

    // DataTables 初期化
    $('#csvOkTable').DataTable({
        pageLength: 10,
        lengthChange: false,
        searching: false,
        info: false,
        columns: [
            { data: "asin", title: "ASIN" },
            { data: "sku",  title: "SKU" }
        ],
        language: {
            paginate: {
                previous: "前へ",
                next: "次へ"
            },
            info: "全 _TOTAL_ 件中 _START_ から _END_ を表示",
            infoEmpty: "0 件中 0 から 0 を表示",
            emptyTable: "データがありません"
        }
    }); 

    $('#csvListedTable').DataTable({
        pageLength: 10,
        lengthChange: false,
        searching: false,
        info: false,
        columns: [
            { data: "asin", title: "ASIN" },
            { data: "sku",  title: "" }
        ],
        language: {
            paginate: {
                previous: "前へ",
                next: "次へ"
            },
            info: "全 _TOTAL_ 件中 _START_ から _END_ を表示",
            infoEmpty: "0 件中 0 から 0 を表示",
            emptyTable: "データがありません"
        }
    }); 

    $('#csvBlacklistTable').DataTable({
        pageLength: 10,
        lengthChange: false,
        searching: false,
        info: false,
        columns: [
            { data: "asin", title: "ASIN" },
            { data: "sku",  title: "" }
        ],
        language: {
            paginate: {
                previous: "前へ",
                next: "次へ"
            },
            info: "全 _TOTAL_ 件中 _START_ から _END_ を表示",
            infoEmpty: "0 件中 0 から 0 を表示",
            emptyTable: "データがありません"
        }
    }); 

});

