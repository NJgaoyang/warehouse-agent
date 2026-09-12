(() => {
  const escHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));

  const style = document.createElement('style');
  style.textContent = `
    .wh-task-ref-counts{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .wh-task-ref-btn{border:0;background:#eef3ff;color:#3f5fd6;border-radius:7px;padding:7px 10px;font-size:11px;cursor:pointer;font-weight:600}
    .wh-task-ref-btn:hover{background:#e2e9ff;color:#294bc5}
    .wh-task-ref-btn.active{background:#536df0;color:#fff}
    .wh-task-ref-btn:disabled{cursor:default;background:#f3f5f8;color:#9aa3b2}
    .wh-task-ref-panel{display:none;margin-top:10px}
    .wh-task-ref-panel.open{display:block}
    .wh-task-card{border:1px solid #e7ebf2;border-radius:9px;padding:10px 11px;background:#fff;margin-top:8px}
    .wh-task-card:first-child{margin-top:0}
    .wh-task-card-head{display:flex;gap:8px;align-items:flex-start}
    .wh-task-card-name{font-size:12px;font-weight:700;color:#253047;word-break:break-word;flex:1}
    .wh-task-card-code{font-size:9px;color:#7f8a9d;background:#f3f5f9;padding:3px 6px;border-radius:12px;white-space:nowrap}
    .wh-task-card-row{margin-top:7px;font-size:10px;line-height:1.6;color:#68758a;word-break:break-all}
    .wh-task-card-row b{color:#4a5568;font-weight:600}
    .wh-task-open-code{margin-top:8px;border:0;background:transparent;color:#4f63df;font-size:10px;padding:0;cursor:pointer}
    .wh-task-open-code:hover{text-decoration:underline}
    .wh-task-ref-empty{font-size:10px;color:#9199a7;padding:8px 2px}
    .wh-task-ref-loading{font-size:10px;color:#8791a2;padding:4px 0}
  `;
  document.head.appendChild(style);

  let activeModelId = null;
  let requestVersion = 0;

  function findTaskBlock() {
    const blocks = [...document.querySelectorAll('#whDrawerBody .wh-block')];
    return blocks.find(block => {
      const title = block.querySelector('.wh-block-title');
      return title && title.textContent.trim() === '任务引用';
    }) || null;
  }

  function renderTaskCards(tasks, emptyText) {
    if (!tasks || !tasks.length) {
      return `<div class="wh-task-ref-empty">${escHtml(emptyText)}</div>`;
    }
    return tasks.map(task => `
      <div class="wh-task-card">
        <div class="wh-task-card-head">
          <div class="wh-task-card-name">${escHtml(task.task_name || '-')}</div>
          ${task.task_code ? `<span class="wh-task-card-code">${escHtml(task.task_code)}</span>` : ''}
        </div>
        <div class="wh-task-card-row"><b>位置：</b>${escHtml(task.position || '-')}</div>
        <div class="wh-task-card-row"><b>本地 SQL：</b>${escHtml(task.file_path || '-')}</div>
        ${task.artifact_id ? `<button class="wh-task-open-code" data-artifact-id="${task.artifact_id}">在“现有代码”中查看 →</button>` : ''}
      </div>`).join('');
  }

  function bindPanelButtons(container) {
    container.querySelectorAll('.wh-task-ref-btn').forEach(button => {
      button.onclick = () => {
        if (button.disabled) return;
        const kind = button.dataset.kind;
        const panel = container.querySelector(`[data-panel="${kind}"]`);
        const wasOpen = panel && panel.classList.contains('open');
        container.querySelectorAll('.wh-task-ref-panel').forEach(x => x.classList.remove('open'));
        container.querySelectorAll('.wh-task-ref-btn').forEach(x => x.classList.remove('active'));
        if (panel && !wasOpen) {
          panel.classList.add('open');
          button.classList.add('active');
        }
      };
    });

    container.querySelectorAll('.wh-task-open-code').forEach(button => {
      button.onclick = () => {
        const artifactId = button.dataset.artifactId;
        const mask = document.getElementById('whDrawerMask');
        if (mask) mask.classList.remove('open');
        if (typeof window.showPage === 'function') window.showPage('source');
        if (typeof window.openSource === 'function') {
          setTimeout(() => window.openSource(artifactId), 80);
        }
      };
    });
  }

  async function enhanceTaskReferences(modelId) {
    const block = findTaskBlock();
    if (!block || !modelId) return;
    if (block.dataset.taskReferenceModel === String(modelId)) return;

    block.dataset.taskReferenceModel = String(modelId);
    const box = block.querySelector('.wh-info-box');
    if (!box) return;
    box.innerHTML = '<div class="wh-task-ref-loading">正在读取 DolphinScheduler 任务位置...</div>';

    const myVersion = ++requestVersion;
    try {
      const data = await window.api(`/api/warehouse/models/${modelId}/task-references`);
      if (myVersion !== requestVersion || String(activeModelId) !== String(modelId)) return;
      const producerCount = data.producer_count ?? (data.producers || []).length;
      const consumerCount = data.consumer_count ?? (data.consumers || []).length;
      box.innerHTML = `
        <div class="wh-task-ref-counts">
          <button class="wh-task-ref-btn" data-kind="producer" ${producerCount ? '' : 'disabled'}>产生任务数：${producerCount}</button>
          <button class="wh-task-ref-btn" data-kind="consumer" ${consumerCount ? '' : 'disabled'}>使用任务数：${consumerCount}</button>
        </div>
        <div class="wh-task-ref-panel" data-panel="producer">
          ${renderTaskCards(data.producers || [], '没有找到产生该模型的 DolphinScheduler 任务')}
        </div>
        <div class="wh-task-ref-panel" data-panel="consumer">
          ${renderTaskCards(data.consumers || [], '没有找到使用该模型的 DolphinScheduler 任务')}
        </div>`;
      bindPanelButtons(box);
    } catch (error) {
      if (myVersion !== requestVersion) return;
      box.innerHTML = `<div class="wh-task-ref-empty">任务位置加载失败：${escHtml(error.message || error)}</div>`;
    }
  }

  document.addEventListener('click', event => {
    const row = event.target.closest && event.target.closest('.wh-model-row');
    if (!row) return;
    activeModelId = row.dataset.id;
    requestVersion++;
    setTimeout(() => enhanceTaskReferences(activeModelId), 0);
  }, true);

  const drawerBody = document.getElementById('whDrawerBody');
  if (drawerBody) {
    const observer = new MutationObserver(() => {
      if (activeModelId) enhanceTaskReferences(activeModelId);
    });
    observer.observe(drawerBody, {childList: true, subtree: true});
  }
})();
