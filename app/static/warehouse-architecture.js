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
    .wh-evidence{font-size:12px;line-height:1.75;color:#566174;word-break:break-word}
    .wh-drawer-mask{position:fixed;inset:58px 0 0 0;background:rgba(15,23,42,.22);z-index:1200;opacity:0;visibility:hidden;transition:opacity .18s ease,visibility .18s ease}
    .wh-drawer-mask.open{opacity:1;visibility:visible}
    .wh-drawer{position:absolute;top:0;right:0;width:min(560px,calc(100vw - 260px));height:100%;background:#fff;box-shadow:-12px 0 36px rgba(15,23,42,.16);transform:translateX(100%);transition:transform .22s ease;display:flex;flex-direction:column}
    .wh-drawer-mask.open .wh-drawer{transform:translateX(0)}
    .wh-drawer-head{height:62px;flex:none;border-bottom:1px solid #e9edf2;display:flex;align-items:center;gap:10px;padding:0 18px}
    .wh-drawer-title{min-width:0;flex:1}.wh-drawer-title b{display:block;font-size:15px;color:#202635;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wh-drawer-title small{display:block;margin-top:4px;color:#8a94a4;font-size:10px}
    .wh-drawer-close{width:32px;height:32px;border:0;background:#f4f6f9;border-radius:8px;color:#697386;font-size:20px;line-height:1;cursor:pointer}.wh-drawer-close:hover{background:#e9edf4;color:#1f2937}
    .wh-drawer-body{flex:1;overflow:auto;padding:16px 18px 24px}
    .wh-drawer-kv{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
    .wh-drawer-kv>div{background:#f8f9fc;border:1px solid #edf0f4;border-radius:9px;padding:11px}.wh-drawer-kv small{display:block;color:#8a94a4;font-size:9px}.wh-drawer-kv b{display:block;font-size:13px;margin-top:5px}
    .wh-block{margin-top:16px}.wh-block-title{font-size:12px;font-weight:700;color:#283244;margin-bottom:8px}
    .wh-info-box{border:1px solid #e8ecf2;background:#fbfcfe;border-radius:9px;padding:12px}
    .wh-lineage-list{display:flex;flex-wrap:wrap;gap:6px}.wh-lineage-chip{max-width:100%;padding:5px 8px;border-radius:6px;background:#f1f4fb;color:#4d5d76;font-size:10px;word-break:break-all}
    .wh-direction{display:grid;grid-template-columns:1fr 1fr;gap:10px}.wh-direction-col{min-width:0}
    .wh-loading{padding:48px 18px;text-align:center;color:#8791a2;font-size:12px}
    @media(max-width:1300px){.wh-layer-grid{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:760px){.wh-drawer{width:100%;max-width:100%}.wh-direction{grid-template-columns:1fr}.wh-drawer-kv{grid-template-columns:1fr}.wh-drawer-mask{inset:58px 0 0 0}}
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
        </div>
      </div>`;
  }

  const drawerMask = document.createElement('div');
  drawerMask.className = 'wh-drawer-mask';
  drawerMask.id = 'whDrawerMask';
  drawerMask.innerHTML = `
    <aside class="wh-drawer" role="dialog" aria-modal="true" aria-label="数仓模型详情">
      <div class="wh-drawer-head">
        <div class="wh-drawer-title"><b id="whDrawerTitle">模型详情</b><small id="whDrawerSubtitle">Warehouse Model</small></div>
        <span class="tag" id="whDrawerLayer">-</span>
        <button class="wh-drawer-close" id="whDrawerClose" aria-label="关闭">×</button>
      </div>
      <div class="wh-drawer-body" id="whDrawerBody"><div class="wh-loading">正在加载模型详情...</div></div>
    </aside>`;
  document.body.appendChild(drawerMask);

  const closeDrawer = () => drawerMask.classList.remove('open');
  document.getElementById('whDrawerClose').onclick = closeDrawer;
  drawerMask.onclick = e => { if (e.target === drawerMask) closeDrawer(); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

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

  function renderChips(items, emptyText='无') {
    const rows = [...new Set((items || []).filter(Boolean))];
    if (!rows.length) return `<span class="muted">${emptyText}</span>`;
    return `<div class="wh-lineage-list">${rows.map(x=>`<span class="wh-lineage-chip">${esc(x)}</span>`).join('')}</div>`;
  }

  async function openWarehouseModel(id) {
    drawerMask.classList.add('open');
    document.getElementById('whDrawerTitle').textContent = '模型详情';
    document.getElementById('whDrawerSubtitle').textContent = '正在加载...';
    document.getElementById('whDrawerLayer').textContent = '-';
    document.getElementById('whDrawerBody').innerHTML = '<div class="wh-loading">正在加载模型详情...</div>';

    try {
      let payload;
      try {
        payload = await api('/api/warehouse/models/' + id + '/detail');
      } catch (_) {
        const model = await api('/api/warehouse/models/' + id);
        const lineage = await api('/api/warehouse/lineage?table=' + encodeURIComponent(model.qualified_name));
        payload = {model, lineage};
      }

      const model = payload.model || {};
      const lineage = payload.lineage || {};
      const evidence = model.evidence || {};
      const edges = lineage.edges || [];
      const upstream = [...new Set(edges.filter(e=>e.target===model.qualified_name || e.target===model.table).map(e=>e.source))];
      const downstream = [...new Set(edges.filter(e=>e.source===model.qualified_name || e.source===model.table).map(e=>e.target))];

      document.getElementById('whDrawerTitle').textContent = model.qualified_name || model.table || '模型详情';
      document.getElementById('whDrawerSubtitle').textContent = `${model.domain || '待识别'} / ${model.subject || '待识别主题'}`;
      document.getElementById('whDrawerLayer').textContent = model.layer || '-';
      document.getElementById('whDrawerBody').innerHTML = `
        <div class="wh-drawer-kv">
          <div><small>主题域</small><b>${esc(model.domain || '-')}</b></div>
          <div><small>主题</small><b>${esc(model.subject || '-')}</b></div>
          <div><small>综合置信度</small><b class="wh-confidence ${confidenceClass(model.confidence || 0)}">${((model.confidence||0)*100).toFixed(0)}%</b></div>
        </div>

        <div class="wh-block">
          <div class="wh-block-title">识别依据</div>
          <div class="wh-info-box wh-evidence">
            <b>分层</b>：${esc((evidence.layer||[]).join('；') || '无')}<br>
            <b>主题域</b>：${esc((evidence.domain||[]).join('；') || '无')}<br>
            <b>主题</b>：${esc((evidence.subject||[]).join('；') || '无')}
          </div>
        </div>

        <div class="wh-block">
          <div class="wh-block-title">关联 DolphinScheduler 任务</div>
          <div class="wh-info-box">${renderChips(evidence.task_names || [], '暂无关联任务')}</div>
        </div>

        <div class="wh-block">
          <div class="wh-block-title">上下游关系</div>
          <div class="wh-direction">
            <div class="wh-direction-col">
              <div class="muted" style="margin-bottom:7px">上游 · ${upstream.length}</div>
              <div class="wh-info-box">${renderChips(upstream, '无上游')}</div>
            </div>
            <div class="wh-direction-col">
              <div class="muted" style="margin-bottom:7px">下游 · ${downstream.length}</div>
              <div class="wh-info-box">${renderChips(downstream, '无下游')}</div>
            </div>
          </div>
        </div>

        <div class="wh-block">
          <div class="wh-block-title">任务引用</div>
          <div class="wh-info-box wh-evidence">产生任务数：<b>${model.produced_by_count ?? 0}</b>　使用任务数：<b>${model.consumed_by_count ?? 0}</b></div>
        </div>`;
    } catch (e) {
      document.getElementById('whDrawerBody').innerHTML = `<div class="empty">详情加载失败<br><span class="muted">${esc(e.message)}</span></div>`;
      toast(e.message);
    }
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
      closeDrawer();
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
