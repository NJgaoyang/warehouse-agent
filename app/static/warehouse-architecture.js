(() => {
  const page = document.getElementById('page-architecture');
  if (!page) return;

  const style = document.createElement('style');
  style.textContent = `
    .wh-layer-grid{display:grid;grid-template-columns:repeat(6,minmax(105px,1fr));gap:10px;margin-bottom:13px}
    .wh-layer-card{background:#fff;border:1px solid #e7eaf0;border-radius:10px;padding:13px;cursor:pointer}
    .wh-layer-card:hover,.wh-layer-card.active{border-color:#8798ff;box-shadow:0 0 0 2px #eef1ff}
    .wh-layer-card small{display:block;color:#8a94a4;font-size:10px}.wh-layer-card b{display:block;font-size:22px;margin-top:4px}.wh-layer-card span{font-size:10px;color:#687386}
    .wh-domain{padding:10px;border:1px solid #edf0f4;border-radius:8px;margin-bottom:7px;cursor:pointer;background:#fff}
    .wh-domain:hover,.wh-domain.active{background:#f3f5ff;border-color:#dce2ff}.wh-domain b{font-size:12px}.wh-domain .wh-meta{font-size:10px;color:#8791a2;margin-top:5px;line-height:1.5}
    .wh-confidence{font-variant-numeric:tabular-nums}.wh-confidence.high{color:#168d5b}.wh-confidence.mid{color:#b27600}.wh-confidence.low{color:#c54c4c}
    .wh-model-row{cursor:pointer}.wh-model-row:hover{background:#f8f9ff}
    .wh-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.wh-evidence{font-size:11px;line-height:1.7;color:#566174}
    @media(max-width:1300px){.wh-layer-grid{grid-template-columns:repeat(3,1fr)}}
  `;
  document.head.appendChild(style);

  const oldDomains = document.getElementById('domains');
  if (oldDomains) {
    oldDomains.className = '';
    oldDomains.innerHTML = `
      <div id="whLayerSummary" class="wh-layer-grid"></div>
      <div class="workspace">
        <div class="card">
          <div class="section-head"><span class="section-title">主题域</span><span class="muted" id="whDomainCount">0 个</span></div>
          <div class="panel"><input class="search" id="whDomainSearch" placeholder="搜索主题域 / 主题"></div>
          <div class="list" id="whDomains"></div>
        </div>
        <div>
          <div class="card">
            <div class="section-head">
              <span class="section-title">识别到的数仓模型</span>
              <div class="toolbar">
                <select id="whLayerFilter" class="btn small"><option value="">全部分层</option><option>ODS</option><option>DWD</option><option>DWS</option><option>ADS</option><option>DIM</option><option>UNKNOWN</option></select>
                <input id="whModelSearch" class="search" style="width:190px;height:28px" placeholder="搜索表名">
              </div>
            </div>
            <div id="whModels"><div class="empty">点击“重新识别数仓”开始分析真实 DS SQL</div></div>
          </div>
          <div id="whDetail" class="card section" style="display:none"></div>
        </div>
      </div>`;
  }

  let overview = null;
  let selectedDomain = '';
  let selectedLayer = '';

  function confidenceClass(v) {
    if (v >= .8) return 'high';
    if (v >= .55) return 'mid';
    return 'low';
  }

  function renderLayers(data) {
    const layers = data.layers || {};
    const labels = {ODS:'原始层',DWD:'明细层',DWS:'汇总层',ADS:'应用层',DIM:'维度层',UNKNOWN:'待识别'};
    document.getElementById('whLayerSummary').innerHTML = ['ODS','DWD','DWS','ADS','DIM','UNKNOWN'].map(layer => `
      <div class="wh-layer-card ${selectedLayer===layer?'active':''}" data-layer="${layer}">
        <small>${labels[layer]}</small><b>${layers[layer] || 0}</b><span>${layer}</span>
      </div>`).join('');
    document.querySelectorAll('.wh-layer-card').forEach(el => el.onclick = () => {
      selectedLayer = selectedLayer === el.dataset.layer ? '' : el.dataset.layer;
      document.getElementById('whLayerFilter').value = selectedLayer;
      renderLayers(overview || data);
      loadWarehouseModels();
    });
  }

  function renderDomains(data) {
    const rows = data.domains || [];
    const q = (document.getElementById('whDomainSearch').value || '').trim().toLowerCase();
    const filtered = rows.filter(x => !q || `${x.name} ${(x.subjects||[]).map(s=>s.name).join(' ')}`.toLowerCase().includes(q));
    document.getElementById('whDomainCount').textContent = `${rows.length} 个`;
    document.getElementById('whDomains').innerHTML = filtered.length ? filtered.map(x => `
      <div class="wh-domain ${selectedDomain===x.code?'active':''}" data-domain="${esc(x.code)}">
        <b>${esc(x.name)}</b><span class="tag" style="float:right">${x.table_count}</span>
        <div class="wh-meta">${(x.subjects||[]).map(s=>esc(s.name)).join(' / ') || '未识别主题'}<br>平均置信度 ${(x.avg_confidence*100).toFixed(0)}%</div>
      </div>`).join('') : '<div class="empty">暂无匹配主题域</div>';
    document.querySelectorAll('.wh-domain').forEach(el => el.onclick = () => {
      selectedDomain = selectedDomain === el.dataset.domain ? '' : el.dataset.domain;
      renderDomains(overview || data);
      loadWarehouseModels();
    });
  }

  async function loadWarehouseModels() {
    try {
      const qs = new URLSearchParams();
      const layer = document.getElementById('whLayerFilter').value || selectedLayer;
      const q = document.getElementById('whModelSearch').value.trim();
      if (layer) qs.set('layer', layer);
      if (selectedDomain) qs.set('domain', selectedDomain);
      if (q) qs.set('q', q);
      const rows = await api('/api/warehouse/models?' + qs.toString());
      document.getElementById('whModels').innerHTML = rows.length ? `<table class="table"><thead><tr><th>模型</th><th>分层</th><th>主题域</th><th>主题</th><th>上下游</th><th>置信度</th></tr></thead><tbody>${rows.map(x => `
        <tr class="wh-model-row" data-id="${x.id}">
          <td><b>${esc(x.qualified_name)}</b></td>
          <td><span class="tag">${esc(x.layer)}</span></td>
          <td>${esc(x.domain)}</td><td>${esc(x.subject)}</td>
          <td>↑ ${x.upstream_count} / ↓ ${x.downstream_count}</td>
          <td><span class="wh-confidence ${confidenceClass(x.confidence)}">${(x.confidence*100).toFixed(0)}%</span></td>
        </tr>`).join('')}</tbody></table>` : '<div class="empty">当前筛选条件下暂无模型</div>';
      document.querySelectorAll('.wh-model-row').forEach(el => el.onclick = () => openWarehouseModel(el.dataset.id));
    } catch (e) { toast(e.message); }
  }

  async function openWarehouseModel(id) {
    try {
      const model = await api('/api/warehouse/models/' + id);
      const lineage = await api('/api/warehouse/lineage?table=' + encodeURIComponent(model.qualified_name));
      const evidence = model.evidence || {};
      const edges = lineage.edges || [];
      const upstream = [...new Set(edges.filter(e=>e.target===model.qualified_name || e.target===model.table).map(e=>e.source))];
      const downstream = [...new Set(edges.filter(e=>e.source===model.qualified_name || e.source===model.table).map(e=>e.target))];
      const box = document.getElementById('whDetail');
      box.style.display = 'block';
      box.innerHTML = `<div class="section-head"><span class="section-title">${esc(model.qualified_name)}</span><span class="tag">${esc(model.layer)}</span></div>
        <div class="panel">
          <div class="kv"><div><small>主题域</small><b>${esc(model.domain)}</b></div><div><small>主题</small><b>${esc(model.subject)}</b></div><div><small>综合置信度</small><b>${(model.confidence*100).toFixed(0)}%</b></div></div>
          <div class="wh-detail-grid">
            <div><div class="section-title">识别依据</div><div class="wh-evidence section">分层：${esc((evidence.layer||[]).join('；'))}<br>主题域：${esc((evidence.domain||[]).join('；'))}<br>主题：${esc((evidence.subject||[]).join('；'))}<br>关联任务：${esc((evidence.task_names||[]).join(' / ') || '-')}</div></div>
            <div><div class="section-title">上下游</div><div class="wh-evidence section">上游：${esc(upstream.join(' / ') || '无')}<br>下游：${esc(downstream.join(' / ') || '无')}<br>产生任务数：${model.produced_by_count} · 使用任务数：${model.consumed_by_count}</div></div>
          </div>
        </div>`;
      box.scrollIntoView({behavior:'smooth', block:'nearest'});
    } catch (e) { toast(e.message); }
  }

  loadDomains = async function() {
    try {
      overview = await api('/api/warehouse/overview');
      renderLayers(overview);
      renderDomains(overview);
      await loadWarehouseModels();
    } catch (e) { toast(e.message); }
  };

  const scanButton = document.getElementById('archScan');
  if (scanButton) scanButton.onclick = async () => {
    try {
      scanButton.disabled = true;
      scanButton.textContent = '识别中...';
      const data = await api('/api/warehouse/scan', {method:'POST'});
      overview = data;
      selectedDomain = '';
      selectedLayer = '';
      renderLayers(data);
      renderDomains(data);
      await loadWarehouseModels();
      const scan = data.scan || {};
      toast(`识别完成：${scan.tables_discovered||0} 张表，${scan.lineage_edges||0} 条血缘`);
    } catch (e) { toast(e.message); }
    finally { scanButton.disabled = false; scanButton.textContent = '重新识别数仓'; }
  };

  document.getElementById('whDomainSearch').oninput = () => renderDomains(overview || {domains:[]});
  document.getElementById('whLayerFilter').onchange = e => { selectedLayer = e.target.value; if (overview) renderLayers(overview); loadWarehouseModels(); };
  document.getElementById('whModelSearch').onkeydown = e => { if (e.key === 'Enter') loadWarehouseModels(); };
})();
