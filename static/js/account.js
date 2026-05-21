document.addEventListener("DOMContentLoaded", () => {
    // ▼ JPのアカウント情報を初期ロード
    fetch("/amazon/get_account_info?region=JP")
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                document.getElementById("jp_seller_id").value = data.seller_id || "";
                document.getElementById("jp_refresh_token").value = data.refresh_token || "";
            }
        });

    // ▼ プルダウンで選択されたマーケットプレイスをロード
    const regionSelect = document.getElementById("globalRegion");
    regionSelect.addEventListener("change", () => {
        const region = regionSelect.value;
        if (!region) return;

        fetch(`/amazon/get_account_info?region=${region}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    document.getElementById("region-title").innerText = data.display_name;
                    document.getElementById("region_seller_id").value = data.seller_id || "";
                    document.getElementById("region_refresh_token").value = data.refresh_token || "";
                }
            });
    });

    // ▼ 保存処理
    document.getElementById("saveAccountBtn").addEventListener("click", () => {
        // JP
        const jpPayload = {
            region: "JP",
            seller_id: document.getElementById("jp_seller_id").value,
            refresh_token: document.getElementById("jp_refresh_token").value
        };

        // 選択リージョン
        const region = regionSelect.value;
        const regionPayload = {
            region: region,
            seller_id: document.getElementById("region_seller_id").value,
            refresh_token: document.getElementById("region_refresh_token").value
        };

        // 2件まとめて保存
        [jpPayload, regionPayload].forEach(payload => {
            fetch("/amazon/save_account_info", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(result => {
                console.log("Save result:", result);
            });
        });

        alert("保存しました");
    });
});

