document.addEventListener("DOMContentLoaded", () => {
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
});