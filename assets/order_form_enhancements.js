(() => {
  'use strict';

  const state = { partId: null, payload: null, selectedSourceKey: '', open: false };
  const styleId = 'corporate-order-form-style';
  const modalId = 'corporate-order-modal';

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function ensureStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .corp-order-overlay{position:fixed;inset:0;background:rgba(10,12,16,.72);display:flex;align-items:center;justify-content:center;padding:20px;z-index:10000}
      .corp-order-card{width:min(680px,100%);max-height:90vh;overflow:auto;background:var(--panel,#fff);color:var(--text,#111);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.38);padding:22px;border:1px solid rgba(127,127,127,.25)}
      .corp-order-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}.corp-order-head h3{margin:0 0 5px}.corp-order-subtle{opacity:.7;font-size:.92rem;margin:0}
      .corp-order-close{border:0;background:transparent;color:inherit;font-size:1.5rem;cursor:pointer;padding:2px 8px}.corp-order-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.corp-order-grid label{display:flex;flex-direction:column;gap:6px;font-weight:600}
      .corp-order-grid input,.corp-order-grid select,.corp-order-grid textarea{font:inherit;padding:10px 12px;border-radius:10px;border:1px solid rgba(127,127,127,.4);background:var(--surface,#fff);color:inherit}.corp-order-full{grid-column:1/-1}.corp-order-source-note{margin-top:6px;font-size:.88rem;opacity:.72}
      .corp-order-warning{margin-top:16px;padding:14px;border-radius:12px;border:1px solid #d29a22;background:rgba(210,154,34,.12)}.corp-order-warning strong{display:block;margin-bottom:7px}.corp-order-warning ul{margin:6px 0 10px 20px;padding:0}
      .corp-order-ack{display:flex;gap:9px;align-items:flex-start;font-weight:600}.corp-order-ack input{margin-top:3px}.corp-order-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}.corp-order-actions button{font:inherit;border-radius:10px;padding:10px 15px;cursor:pointer}
      .corp-order-primary{border:0;background:#2474d2;color:#fff;font-weight:700}.corp-order-primary:disabled{opacity:.45;cursor:not-allowed}.corp-order-secondary{border:1px solid rgba(127,127,127,.4);background:transparent;color:inherit}.corp-order-error{margin-top:12px;padding:11px;border-radius:10px;background:rgba(190,40,40,.12);border:1px solid rgba(190,40,40,.4)}.hidden{display:none!important}
      @media(max-width:620px){.corp-order-grid{grid-template-columns:1fr}.corp-order-full{grid-column:1}.corp-order-card{padding:17px}}
    `;
    document.head.appendChild(style);
  }

  function currentWarehouseId() {
    const selector = document.querySelector('#warehouse-selector');
    const value = Number(selector?.value || 0);
    return Number.isFinite(value) ? value : 0;
  }

  function selectedSource() {
    return state.payload?.sources?.find((source) => source.sourceKey === state.selectedSourceKey) || null;
  }

  function activeViewName() {
    return document.querySelector('.nav-link.active')?.dataset.view || 'inventory';
  }

  function restoreView(viewName, scrollY) {
    if (typeof window.setActiveView === 'function') {
      window.setActiveView(viewName);
    } else {
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      document.querySelector(`.nav-link[data-view="${viewName}"]`)?.classList.add('active');
      document.querySelector(`#${viewName}-view`)?.classList.add('active');
    }
    window.requestAnimationFrame(() => window.scrollTo({ top: scrollY, behavior: 'auto' }));
  }

  async function refreshWithoutLeaving(viewName, scrollY) {
    if (typeof window.loadApp === 'function') {
      await window.loadApp(currentWarehouseId());
    }
    restoreView(viewName, scrollY);
  }

  function closeModal() {
    document.getElementById(modalId)?.remove();
    state.partId = null;
    state.payload = null;
    state.selectedSourceKey = '';
    state.open = false;
  }

  function updateSubmitState() {
    const source = selectedSource();
    const submit = document.querySelector('#corp-order-submit');
    const quantity = Number(document.querySelector('#corp-order-quantity')?.value || 0);
    if (!submit || !source) return;
    const restrictions = Array.isArray(source.restrictions) ? source.restrictions : [];
    const acknowledged = !restrictions.length || Boolean(document.querySelector('#corp-order-acknowledge')?.checked);
    submit.disabled = !Number.isInteger(quantity) || quantity <= 0 || !acknowledged;
  }

  function updateRestrictionPanel() {
    const source = selectedSource();
    const warning = document.querySelector('#corp-order-warning');
    const meta = document.querySelector('#corp-order-source-meta');
    if (!source || !warning || !meta) return;

    meta.innerHTML = [
      source.templateName ? `<strong>${escapeHtml(source.templateName)}</strong>` : '',
      source.vendorItemNumber ? `Vendor item: ${escapeHtml(source.vendorItemNumber)}` : '',
      source.packCount ? `Pack: ${escapeHtml(source.packCount)}` : '',
      source.requestPer ? `Request per: ${escapeHtml(source.requestPer)}` : '',
    ].filter(Boolean).join(' &nbsp;|&nbsp; ');

    const restrictions = Array.isArray(source.restrictions) ? source.restrictions : [];
    if (restrictions.length) {
      warning.classList.remove('hidden');
      warning.innerHTML = `
        <strong>Ordering requirement</strong>
        <ul>${restrictions.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        <label class="corp-order-ack"><input id="corp-order-acknowledge" type="checkbox"> <span>I understand these ordering requirements and want to continue.</span></label>`;
      document.querySelector('#corp-order-acknowledge')?.addEventListener('change', updateSubmitState);
    } else {
      warning.classList.add('hidden');
      warning.innerHTML = '<input id="corp-order-acknowledge" type="checkbox" checked>';
    }
    updateSubmitState();
  }

  function renderModal() {
    ensureStyle();
    document.getElementById(modalId)?.remove();
    const payload = state.payload;
    if (!payload) return;
    const sources = payload.sources || [];
    if (!sources.length) {
      window.alert(`No corporate order form is mapped to ${payload.part?.partNumber || 'this item'} yet.`);
      closeModal();
      return;
    }

    state.selectedSourceKey = state.selectedSourceKey || sources[0].sourceKey;
    const overlay = document.createElement('div');
    overlay.id = modalId;
    overlay.className = 'corp-order-overlay';
    overlay.innerHTML = `
      <div class="corp-order-card" role="dialog" aria-modal="true" aria-labelledby="corp-order-title">
        <div class="corp-order-head">
          <div><h3 id="corp-order-title">Add to Corporate Order</h3><p class="corp-order-subtle">Office ${escapeHtml(payload.officeNumber)} - ${escapeHtml(payload.location)}</p></div>
          <button type="button" class="corp-order-close" aria-label="Close">×</button>
        </div>
        <div><strong>${escapeHtml(payload.part.partNumber)}</strong><p class="corp-order-subtle">${escapeHtml(payload.part.description)}</p></div>
        <div class="corp-order-grid">
          <label>Quantity<input id="corp-order-quantity" type="number" min="1" step="1" value="${Number(payload.suggestedQuantity || 1)}"></label>
          <label>Vendor / Order Form<select id="corp-order-source-select">${sources.map((source) => `<option value="${escapeHtml(source.sourceKey)}" ${source.sourceKey === state.selectedSourceKey ? 'selected' : ''}>${escapeHtml(source.vendor)}${source.templateName ? ` - ${escapeHtml(source.templateName)}` : ''}</option>`).join('')}</select></label>
          <div id="corp-order-source-meta" class="corp-order-full corp-order-source-note"></div>
          <label class="corp-order-full">Notes (optional)<textarea id="corp-order-notes" rows="2" placeholder="Anything purchasing should know"></textarea></label>
        </div>
        <div id="corp-order-warning" class="corp-order-warning hidden"></div>
        <div id="corp-order-error" class="corp-order-error hidden"></div>
        <div class="corp-order-actions">
          <button type="button" class="corp-order-secondary" id="corp-order-cancel">Cancel</button>
          <button type="button" class="corp-order-primary" id="corp-order-submit">Add to Order</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);
    state.open = true;
    overlay.addEventListener('click', (event) => { if (event.target === overlay) closeModal(); });
    overlay.querySelector('.corp-order-close')?.addEventListener('click', closeModal);
    overlay.querySelector('#corp-order-cancel')?.addEventListener('click', closeModal);
    overlay.querySelector('#corp-order-source-select')?.addEventListener('change', (event) => {
      state.selectedSourceKey = event.target.value;
      updateRestrictionPanel();
    });
    overlay.querySelector('#corp-order-quantity')?.addEventListener('input', updateSubmitState);
    overlay.querySelector('#corp-order-submit')?.addEventListener('click', submitOrder);
    updateRestrictionPanel();
    overlay.querySelector('#corp-order-quantity')?.focus();
  }

  async function openOrderDialog(partId) {
    if (state.open) return;
    const warehouseId = currentWarehouseId();
    if (!warehouseId) return window.alert('Choose a warehouse first.');
    try {
      const response = await fetch(`/api/order-sources/${Number(partId)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load corporate ordering options.');
      state.partId = Number(partId);
      state.payload = data;
      const preferred = (data.sources || []).find((source) => source.matchesCurrentVendor) || data.sources?.[0];
      state.selectedSourceKey = preferred?.sourceKey || '';
      renderModal();
    } catch (error) {
      window.alert(error.message || 'Unable to load corporate ordering options.');
      closeModal();
    }
  }

  async function submitOrder() {
    const source = selectedSource();
    const quantity = Number(document.querySelector('#corp-order-quantity')?.value || 0);
    const notes = document.querySelector('#corp-order-notes')?.value?.trim() || '';
    const errorBox = document.querySelector('#corp-order-error');
    const submit = document.querySelector('#corp-order-submit');
    if (!source || !Number.isInteger(quantity) || quantity <= 0) return;

    const restrictions = Array.isArray(source.restrictions) ? source.restrictions : [];
    const acknowledged = !restrictions.length || Boolean(document.querySelector('#corp-order-acknowledge')?.checked);
    if (restrictions.length && !acknowledged) return updateSubmitState();

    if (submit) { submit.disabled = true; submit.textContent = 'Adding...'; }
    if (errorBox) errorBox.classList.add('hidden');

    const viewName = activeViewName();
    const scrollY = window.scrollY;

    try {
      const response = await fetch('/api/order-list-v2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          warehouseId: currentWarehouseId(),
          partId: state.partId,
          quantity,
          sourceKey: source.sourceKey,
          acknowledgedRestrictions: acknowledged,
          notes,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to add this item to the order list.');

      closeModal();
      window.alert(`${data.partNumber} added to the ${data.vendor} order form.`);
      await refreshWithoutLeaving(viewName, scrollY);
    } catch (error) {
      if (errorBox) {
        errorBox.textContent = error.message || 'Unable to add this item to the order list.';
        errorBox.classList.remove('hidden');
      }
      if (submit) {
        submit.textContent = 'Add to Order';
        updateSubmitState();
      }
    }
  }

  async function generateCorporateForms(button) {
    const warehouseId = currentWarehouseId();
    if (!warehouseId) return window.alert('Choose a warehouse first.');
    const originalText = button?.textContent || '';
    if (button) { button.disabled = true; button.textContent = 'Generating Forms...'; }
    try {
      const response = await fetch('/api/order-forms/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ warehouseId }),
      });
      if (!response.ok) {
        let message = 'Unable to generate corporate order forms.';
        try {
          const data = await response.json();
          message = data.error || message;
          if (Array.isArray(data.unmappedParts) && data.unmappedParts.length) {
            message += `\n\nRe-add these items with a corporate form selected: ${data.unmappedParts.join(', ')}`;
          }
        } catch (_error) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || 'Office_93_Order_Forms.zip';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1500);
    } catch (error) {
      window.alert(error.message || 'Unable to generate corporate order forms.');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = originalText || 'Generate Corporate Forms';
      }
    }
  }

  function relabelGenerateButton() {
    const button = document.querySelector('#order-list-generate');
    if (button && !button.dataset.corporateOrderRelabeled) {
      button.textContent = 'Generate Corporate Forms';
      button.dataset.corporateOrderRelabeled = '1';
    }
  }

  document.addEventListener('click', (event) => {
    const orderButton = event.target.closest('[data-add-to-order-list], [data-inventory-scan-add-to-order]');
    if (orderButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const partId = orderButton.dataset.addToOrderList || orderButton.dataset.inventoryScanAddToOrder;
      openOrderDialog(partId);
      return;
    }
    const generateButton = event.target.closest('#order-list-generate');
    if (generateButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
      generateCorporateForms(generateButton);
    }
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.open) closeModal();
  });

  new MutationObserver(relabelGenerateButton).observe(document.documentElement, { childList: true, subtree: true });
  relabelGenerateButton();
})();
