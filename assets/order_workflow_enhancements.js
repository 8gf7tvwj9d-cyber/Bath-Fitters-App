(() => {
  'use strict';

  if (window.__shopflowCorporateWorkflowInstalled) return;
  window.__shopflowCorporateWorkflowInstalled = true;

  const originalFetch = window.fetch.bind(window);
  let refreshScheduled = false;

  function requestUrl(input) {
    if (typeof input === 'string') return input;
    if (input && typeof input.url === 'string') return input.url;
    return '';
  }

  function activeViewName() {
    return document.querySelector('.nav-link.active')?.dataset.view || 'purchase-orders';
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

  async function refreshPurchaseOrderWorkflow(poCount, viewName, scrollY) {
    if (refreshScheduled) return;
    refreshScheduled = true;
    window.setTimeout(async () => {
      try {
        const warehouseId = Number(document.querySelector('#warehouse-selector')?.value || 0);
        if (typeof window.loadApp === 'function') {
          await window.loadApp(warehouseId || undefined);
        }
        restoreView(viewName || 'purchase-orders', scrollY);
        const countText = poCount > 0 ? `${poCount} purchase order${poCount === 1 ? '' : 's'} are` : 'The purchase orders are';
        window.alert(
          `Corporate forms generated. ${countText} now Email Pending.\n\nSend the generated form(s) to purchasing, then click Email Sent on each order. That confirmation moves the parts to Waiting for Part.`,
        );
      } catch (error) {
        console.error('Unable to refresh the corporate order workflow.', error);
      } finally {
        refreshScheduled = false;
      }
    }, 350);
  }

  window.fetch = async function shopflowWorkflowFetch(input, init) {
    const url = requestUrl(input);
    const isCorporateGeneration = url.includes('/api/order-forms/generate');
    const viewName = isCorporateGeneration ? activeViewName() : '';
    const scrollY = isCorporateGeneration ? window.scrollY : 0;

    const response = await originalFetch(input, init);
    if (isCorporateGeneration && response.ok) {
      const poCount = Number(response.headers.get('X-Created-Purchase-Orders') || 0);
      refreshPurchaseOrderWorkflow(poCount, viewName, scrollY);
    }
    return response;
  };

  function addWorkflowGuide() {
    const poList = document.querySelector('#po-list');
    if (!poList || document.querySelector('#corporate-order-workflow-guide')) return;
    const panel = poList.closest('.panel');
    if (!panel) return;
    const guide = document.createElement('div');
    guide.id = 'corporate-order-workflow-guide';
    guide.className = 'subtle';
    guide.style.marginBottom = '12px';
    guide.innerHTML = '<strong>Ordering workflow:</strong> Generate Corporate Forms → send the email → click <strong>Email Sent</strong> → check parts in when they arrive.';
    poList.before(guide);
  }

  new MutationObserver(addWorkflowGuide).observe(document.documentElement, { childList: true, subtree: true });
  addWorkflowGuide();
})();
