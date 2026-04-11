let state = {
  warehouses: [],
  activeWarehouses: [],
  selectedWarehouseId: null,
  selectedWarehouse: null,
  vendors: [],
  parts: [],
  jobs: [],
  jobRequirements: [],
  purchaseOrders: [],
  receivingLogs: [],
  usageLogs: []
};
const verifiedReceipts = new Set();
const inlineEditors = {
  partId: null,
  vendorId: null,
  warehouseId: null
};
const collapsedCategories = new Set();
const knownInventoryCategories = new Set();
const collapsedJobs = new Set();
let jobRequirementRowSeed = 0;

const formPanels = {
  part: "part-form-panel",
  po: "po-form-panel",
  job: "job-form-panel",
  warehouse: "warehouse-form-panel",
  vendor: "vendor-form-panel"
};

function currentWarehouseId() {
  return Number(state.selectedWarehouseId);
}

function warehouseById(id) {
  return state.warehouses.find((warehouse) => Number(warehouse.id) === Number(id));
}

function vendorName(vendorId) {
  return state.vendors.find((vendor) => Number(vendor.id) === Number(vendorId))?.name || "Unassigned";
}

function partById(partId) {
  return state.parts.find((part) => Number(part.id) === Number(partId));
}

function jobById(jobId) {
  return state.jobs.find((job) => Number(job.id) === Number(jobId));
}

function jobRequirementsFor(jobId) {
  return state.jobRequirements.filter((requirement) => Number(requirement.job_id) === Number(jobId));
}

function partHasOpenPurchaseOrder(partId) {
  return state.purchaseOrders.some((po) => Number(po.part_id) === Number(partId) && po.status !== "Received");
}

function latestOpenPurchaseOrderForPart(partId) {
  return state.purchaseOrders
    .filter((po) => Number(po.part_id) === Number(partId) && po.status !== "Received")
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at))[0];
}

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0);
}

function pruneVerifiedReceipts() {
  const poIds = new Set(state.purchaseOrders.map((po) => Number(po.id)));
  [...verifiedReceipts].forEach((poId) => {
    if (!poIds.has(Number(poId))) {
      verifiedReceipts.delete(Number(poId));
    }
  });
}

function pruneInlineEditors() {
  if (inlineEditors.partId && !state.parts.some((part) => Number(part.id) === Number(inlineEditors.partId))) {
    inlineEditors.partId = null;
  }
  if (inlineEditors.vendorId && !state.vendors.some((vendor) => Number(vendor.id) === Number(inlineEditors.vendorId))) {
    inlineEditors.vendorId = null;
  }
  if (inlineEditors.warehouseId && !state.warehouses.some((warehouse) => Number(warehouse.id) === Number(inlineEditors.warehouseId))) {
    inlineEditors.warehouseId = null;
  }
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function inventoryStatus(part) {
  const openPo = latestOpenPurchaseOrderForPart(part.id);
  if (openPo?.status === "Waiting for Part") return { label: "Order Processed", className: "status-info" };
  if (openPo) return { label: "Order In Process", className: "status-info" };
  if (part.stock === 0) return { label: "Out of Stock", className: "status-danger" };
  if (part.stock <= part.reorder_point) return { label: "Low Stock", className: "status-warn" };
  return { label: "Healthy", className: "status-ok" };
}

function needsAttention(part) {
  return part.stock <= part.reorder_point && !partHasOpenPurchaseOrder(part.id);
}

function partCategoryGroups(filteredParts = state.parts) {
  return filteredParts.reduce((groups, part) => {
    const category = part.category || "Uncategorized";
    if (!groups.has(category)) {
      groups.set(category, []);
    }
    groups.get(category).push(part);
    return groups;
  }, new Map());
}

function initializeCollapsedCategories() {
  const categories = [...new Set(state.parts.map((part) => part.category || "Uncategorized"))];
  categories.forEach((category) => {
    if (!knownInventoryCategories.has(category)) {
      knownInventoryCategories.add(category);
      collapsedCategories.add(category);
    }
  });
  [...knownInventoryCategories].forEach((category) => {
    if (!categories.includes(category)) {
      knownInventoryCategories.delete(category);
      collapsedCategories.delete(category);
    }
  });
}

function initializeCollapsedJobs() {
  const jobIds = state.jobs.map((job) => Number(job.id));
  jobIds.forEach((jobId) => {
    if (!collapsedJobs.has(jobId)) {
      collapsedJobs.add(jobId);
    }
  });
  [...collapsedJobs].forEach((jobId) => {
    if (!jobIds.includes(Number(jobId))) {
      collapsedJobs.delete(jobId);
    }
  });
}

function vendorOptionsMarkup(selectedVendorId) {
  return state.vendors.map((vendor) => `<option value="${vendor.id}" ${Number(vendor.id) === Number(selectedVendorId) ? "selected" : ""}>${vendor.name}</option>`).join("");
}

function renderInlinePartEditor(part) {
  return `
    <tr class="inline-editor-row">
      <td colspan="5">
        <form class="inline-editor-grid inline-editor-grid-part" data-inline-part-form="${part.id}">
          <input type="hidden" name="id" value="${part.id}">
          <label>Part Number<input name="partNumber" type="text" value="${part.part_number}" required></label>
          <label>Description<input name="description" type="text" value="${part.description}" required></label>
          <label>Category<input name="category" type="text" value="${part.category}" required></label>
          <label class="field-small">Stock<input name="stock" type="number" min="0" value="${part.stock}" required></label>
          <label>Vendor<select name="vendorId">${vendorOptionsMarkup(part.vendor_id)}</select></label>
          <label class="field-small">Reorder<input name="reorderPoint" type="number" min="0" value="${part.reorder_point}" required></label>
          <label class="field-small">Unit Cost<input name="unitCost" type="number" min="0" step="0.01" value="${part.unit_cost}" required></label>
          <div class="form-actions inline-actions">
            <button type="submit" class="primary">Save</button>
            <button type="button" class="ghost" data-inline-cancel="part">Cancel</button>
            <button type="button" class="ghost" data-inline-delete-part="${part.id}">Delete</button>
          </div>
        </form>
      </td>
    </tr>
  `;
}

function renderInlineVendorEditor(vendor) {
  return `
    <tr class="inline-editor-row">
      <td colspan="6">
        <form class="inline-editor-grid compact" data-inline-vendor-form="${vendor.id}">
          <input type="hidden" name="id" value="${vendor.id}">
          <label>Vendor Name<input name="name" type="text" value="${vendor.name}" required></label>
          <label>Contact<input name="contact" type="text" value="${vendor.contact}" required></label>
          <label>Email<input name="email" type="email" value="${vendor.email}" required></label>
          <label>Phone<input name="phone" type="text" value="${vendor.phone}" required></label>
          <label class="field-small">Lead Time<input name="leadTimeDays" type="number" min="0" value="${vendor.lead_time_days}" required></label>
          <div class="form-actions inline-actions">
            <button type="submit" class="primary">Save</button>
            <button type="button" class="ghost" data-inline-cancel="vendor">Cancel</button>
            <button type="button" class="ghost" data-inline-delete-vendor="${vendor.id}">Delete</button>
          </div>
        </form>
      </td>
    </tr>
  `;
}

function renderInlineWarehouseEditor(warehouse) {
  return `
    <tr class="inline-editor-row">
      <td colspan="4">
        <form class="inline-editor-grid compact" data-inline-warehouse-form="${warehouse.id}">
          <input type="hidden" name="id" value="${warehouse.id}">
          <label>Warehouse Name<input name="name" type="text" value="${warehouse.name}" required></label>
          <label class="field-small">Code<input name="code" type="text" maxlength="10" value="${warehouse.code}" required></label>
          <div class="form-actions inline-actions">
            <button type="submit" class="primary">Save</button>
            <button type="button" class="ghost" data-inline-cancel="warehouse">Cancel</button>
            <button type="button" class="ghost" data-inline-archive-warehouse="${warehouse.id}">${warehouse.is_active ? "Archive" : "Restore"}</button>
          </div>
        </form>
      </td>
    </tr>
  `;
}

function emptyState() {
  return document.querySelector("#empty-state-template").innerHTML;
}

function dashboardMetrics() {
  return {
    lowStock: state.parts.filter(needsAttention).length,
    openOrders: state.purchaseOrders.filter((po) => po.status !== "Received").length,
    inventoryValue: state.parts.reduce((sum, part) => sum + (part.stock * part.unit_cost), 0),
    usageToday: state.usageLogs.filter((log) => new Date(log.created_at).toDateString() === new Date().toDateString()).length
  };
}

function renderWarehouseSelector() {
  const select = document.querySelector("#warehouse-selector");
  const options = state.activeWarehouses.length ? state.activeWarehouses : state.warehouses;
  select.innerHTML = options.map((warehouse) => `
    <option value="${warehouse.id}">${warehouse.name} (${warehouse.code})</option>
  `).join("");
  select.value = String(state.selectedWarehouseId || "");
  document.querySelector("#warehouse-summary").textContent = state.selectedWarehouse
    ? `Showing inventory for ${state.selectedWarehouse.name}.`
    : "Showing one location at a time.";
}

function renderInventoryAttentionBadge() {
  const badge = document.querySelector("#inventory-attention-badge");
  if (!badge) return;
  const lowStockCount = state.parts.filter(needsAttention).length;
  badge.textContent = String(lowStockCount);
  badge.classList.toggle("hidden", lowStockCount === 0);
}

function renderPoAttentionBadge() {
  const badge = document.querySelector("#po-attention-badge");
  if (!badge) return;
  const openPoCount = state.purchaseOrders.filter((po) => po.status !== "Received").length;
  badge.textContent = String(openPoCount);
  badge.classList.toggle("hidden", openPoCount === 0);
}

function renderDashboard() {
  const root = document.querySelector("#dashboard-view");
  const metrics = dashboardMetrics();
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);
  const weeklyUsage = state.usageLogs
    .filter((log) => new Date(log.created_at) >= weekStart)
    .reduce((totals, log) => {
      const current = totals.get(log.part_id) || { quantity: 0, part: partById(log.part_id) };
      current.quantity += log.quantity;
      totals.set(log.part_id, current);
      return totals;
    }, new Map());
  const mostUsedParts = [...weeklyUsage.values()]
    .filter((entry) => entry.part)
    .sort((left, right) => right.quantity - left.quantity)
    .slice(0, 5);
  const openOrders = state.purchaseOrders.filter((po) => po.status !== "Received");
  const warehouseLabel = state.selectedWarehouse ? state.selectedWarehouse.name : "Current Warehouse";

  root.innerHTML = `
    <div class="metrics">
      <article class="metric-card"><p class="eyebrow">${warehouseLabel}</p><strong>${state.selectedWarehouse ? state.selectedWarehouse.code : "--"}</strong><p class="subtle">Warehouse currently in view</p></article>
      <article class="metric-card"><p class="eyebrow">Low Stock Alerts</p><strong>${metrics.lowStock}</strong><p class="subtle">Parts at or below reorder point</p></article>
      <article class="metric-card"><p class="eyebrow">Open POs</p><strong>${metrics.openOrders}</strong><p class="subtle">Orders awaiting receipt</p></article>
      <article class="metric-card"><p class="eyebrow">Inventory Value</p><strong>${money(metrics.inventoryValue)}</strong><p class="subtle">Based on current on-hand quantity</p></article>
    </div>
    <div class="dashboard-grid">
      <div class="stack">
        <article class="panel">
          <h4>Top 5 most used parts this week</h4>
          <div class="activity-list">
            ${mostUsedParts.length ? mostUsedParts.map((entry) => `
              <div class="activity-card">
                <strong>${entry.part.part_number} - ${entry.part.description}</strong>
                <p class="subtle">${entry.quantity} used this week</p>
              </div>`).join("") : emptyState()}
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="panel">
          <h4>Open purchase orders</h4>
          <div class="activity-list">
            ${openOrders.length ? openOrders.map((po) => `<div class="activity-card"><strong>${po.po_number}</strong><p class="subtle">${po.vendor_name} - ${po.part_number} - Remaining ${po.quantity - po.received_quantity}</p><p class="subtle">ETA ${formatDate(po.eta)} - ${po.notes || "No notes"}</p></div>`).join("") : emptyState()}
          </div>
        </article>
        <article class="panel">
          <h4>Quick view</h4>
          <div class="activity-list">
            <div class="activity-card"><strong>Warehouse management</strong><p class="subtle">You can now add and edit warehouse records directly in the app.</p></div>
            <div class="activity-card"><strong>Job pulling</strong><p class="subtle">Create jobs, assign required parts, and pull inventory straight from the job card.</p></div>
          </div>
        </article>
      </div>
    </div>`;
}

function renderInventoryTable() {
  const search = document.querySelector("#inventory-search").value.trim().toLowerCase();
  const filteredParts = state.parts.filter((part) => [part.part_number, part.description, part.category, vendorName(part.vendor_id)].join(" ").toLowerCase().includes(search));
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) => left[0].localeCompare(right[0]));
  const rows = groups.map(([category, parts]) => {
    const isCollapsed = collapsedCategories.has(category);
    const attentionCount = parts.filter(needsAttention).length;
    const categoryRow = `
      <tr class="category-row" data-category-toggle="${category}">
        <td colspan="5">
          <div class="category-row-inner">
            <div class="category-title-wrap">
              <button type="button" class="category-toggle" data-category-toggle="${category}">${isCollapsed ? "▸" : "▾"}</button>
              <strong>${category}</strong>
              <span class="subtle">${parts.length} parts</span>
            </div>
            ${attentionCount ? `<span class="status-pill status-warn">${attentionCount} need attention</span>` : ""}
          </div>
        </td>
      </tr>
    `;
    if (isCollapsed) {
      return categoryRow;
    }
    const partRows = parts.map((part) => {
      const status = inventoryStatus(part);
      if (Number(inlineEditors.partId) === Number(part.id)) {
        return renderInlinePartEditor(part);
      }
      return `<tr><td class="part-meta"><strong>${part.part_number}</strong><span class="subtle">${part.description}</span></td><td>${part.stock}</td><td>${vendorName(part.vendor_id)}</td><td><span class="status-pill ${status.className}">${status.label}</span></td><td><button class="tiny-action" data-order-more="${part.id}">Order More</button> <button class="tiny-action" data-edit-part="${part.id}">Edit</button></td></tr>`;
    }).join("");
    return `${categoryRow}${partRows}`;
  }).join("");
  document.querySelector("#inventory-table").innerHTML = rows || `<tr><td colspan="5">${emptyState()}</td></tr>`;
}

function renderVendorTable() {
  const rows = state.vendors.map((vendor) => {
    if (Number(inlineEditors.vendorId) === Number(vendor.id)) {
      return renderInlineVendorEditor(vendor);
    }
    const rowMarkup = `<tr><td><strong>${vendor.name}</strong></td><td>${vendor.contact}</td><td>${vendor.email}</td><td>${vendor.phone}</td><td>${vendor.lead_time_days} days</td><td><button class="tiny-action" data-edit-vendor="${vendor.id}">Edit</button></td></tr>`;
    return rowMarkup;
  }).join("");
  document.querySelector("#vendor-table").innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;
}

function renderWarehouseTable() {
  const rows = state.warehouses.map((warehouse) => {
    if (Number(inlineEditors.warehouseId) === Number(warehouse.id)) {
      return renderInlineWarehouseEditor(warehouse);
    }
    const rowMarkup = `<tr><td><strong>${warehouse.name}</strong></td><td>${warehouse.code}</td><td>${warehouse.is_active ? "Active" : "Archived"}</td><td><button class="tiny-action" data-edit-warehouse="${warehouse.id}">Edit</button></td></tr>`;
    return rowMarkup;
  }).join("");
  document.querySelector("#warehouse-table").innerHTML = rows || `<tr><td colspan="4">${emptyState()}</td></tr>`;
}

function renderJobsList() {
  const root = document.querySelector("#jobs-list");
  if (!root) return;
  const jobs = [...state.jobs].sort((left, right) => {
    const leftReady = left.status === "Ready to Go" ? 1 : 0;
    const rightReady = right.status === "Ready to Go" ? 1 : 0;
    if (leftReady !== rightReady) {
      return rightReady - leftReady;
    }
    return new Date(right.created_at) - new Date(left.created_at);
  });
  root.innerHTML = jobs.length ? jobs.map((job) => {
    const requirements = jobRequirementsFor(job.id);
    const readyToGo = job.status === "Ready to Go";
    const isCollapsed = collapsedJobs.has(Number(job.id));
    const totalRequired = requirements.reduce((sum, requirement) => sum + requirement.required_quantity, 0);
    const totalPulled = requirements.reduce((sum, requirement) => sum + requirement.pulled_quantity, 0);
    const requirementRows = requirements.length ? requirements.map((requirement) => {
      const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
      const part = partById(requirement.part_id);
      return `
        <div class="job-part-row">
          <div>
            <strong>${part ? `${part.part_number} - ${part.description}` : "Unknown Part"}</strong>
            <p class="subtle">Required ${requirement.required_quantity} | Pulled ${requirement.pulled_quantity} | In Inventory ${part ? part.stock : 0}</p>
          </div>
          <button class="tiny-action" data-pull-job-part="${requirement.id}" ${remaining === 0 ? "disabled" : ""}>Pull Parts</button>
        </div>
      `;
    }).join("") : emptyState();
    return `
      <div class="activity-card job-card">
        <div class="category-row-inner job-row-header" data-job-toggle="${job.id}">
          <div class="category-title-wrap">
            <button type="button" class="category-toggle" data-job-toggle="${job.id}">${isCollapsed ? ">" : "v"}</button>
            <div>
              <strong>${job.job_number} - ${job.title}</strong>
              <p class="subtle">${job.technician} | ${totalPulled} pulled of ${totalRequired}</p>
            </div>
          </div>
          ${readyToGo ? '<span class="status-pill status-info">Ready To Go</span>' : '<span class="status-pill status-warn">Needs Pulling</span>'}
        </div>
        ${isCollapsed ? "" : `
          <p class="subtle">${job.notes || "No notes"} | ${formatDate(job.created_at)}</p>
          <div class="job-parts-list">${requirementRows}</div>
        `}
      </div>
    `;
  }).join("") : emptyState();
}

function renderPurchaseOrders() {
  const activePurchaseOrders = state.purchaseOrders.filter((po) => po.status !== "Received");
  const rows = activePurchaseOrders.map((po) => {
    const statusClass = po.status === "Received" ? "status-ok" : "status-warn";
    const isVerified = verifiedReceipts.has(Number(po.id));
    let actions = `<div class="action-stack"><a class="tiny-action" href="/purchase-orders/${po.id}/form" target="_blank" rel="noreferrer">Open Form</a>`;
    if (po.status === "Email Pending") {
      actions += `<button class="tiny-action" data-po-status="${po.id}" data-status-value="Waiting for Part">Email Sent</button>`;
    } else if (po.status === "Waiting for Part") {
      actions += `
        <label class="verification-check">
          <input type="checkbox" data-po-verified="${po.id}" ${isVerified ? "checked" : ""}>
          Visually counted and verified
        </label>
        <button class="tiny-action" data-po-receive="${po.id}" ${isVerified ? "" : "disabled"}>Order Received</button>
      `;
    }
    actions += "</div>";
    return `<tr><td><strong>${po.po_number}</strong></td><td>${po.vendor_name}</td><td>${po.part_number} - ${po.description}</td><td>${po.quantity}</td><td>${formatDate(po.eta)}</td><td><span class="status-pill ${statusClass}">${po.status}</span></td><td>${po.notes || "No notes"}</td><td>${actions}</td></tr>`;
  }).join("");
  document.querySelector("#po-table").innerHTML = rows || `<tr><td colspan="8">${emptyState()}</td></tr>`;
}

function renderReceivingLog() {
  const logs = state.receivingLogs.slice(0, 8);
  document.querySelector("#receiving-log").innerHTML = logs.length ? logs.map((log) => `<div class="activity-card"><strong>${log.po_number || "Manual receipt"} - ${log.part_number || "Unknown Part"}</strong><p class="subtle">${log.quantity} received by ${log.received_by}</p><p class="subtle">${log.notes || "No notes"} - ${formatDate(log.created_at)}</p></div>`).join("") : emptyState();
}

function renderUsageLog() {
  const logs = state.usageLogs.slice(0, 12);
  document.querySelector("#usage-log").innerHTML = logs.length ? logs.map((log) => `<div class="activity-card"><strong>${log.job_number}</strong><p class="subtle">${log.technician} used ${log.quantity} of ${log.part_number} - ${log.description}</p><p class="subtle">${log.notes || "No notes"} - ${formatDate(log.created_at)}</p></div>`).join("") : emptyState();
}

function renderTransferLog() {
  const logs = state.transferLogs.slice(0, 12);
  document.querySelector("#transfer-log").innerHTML = logs.length ? logs.map((log) => `
    <div class="activity-card">
      <strong>${log.part_number} - ${log.quantity} moved</strong>
      <p class="subtle">${log.from_warehouse_code} to ${log.to_warehouse_code} by ${log.transferred_by}</p>
      <p class="subtle">${log.notes || "No notes"} - ${formatDate(log.created_at)}</p>
    </div>
  `).join("") : emptyState();
}

function renderTransferPreview() {
  const root = document.querySelector("#transfer-preview");
  const fromWarehouseId = Number(document.querySelector("#transfer-from").value || currentWarehouseId());
  const toWarehouseId = Number(document.querySelector("#transfer-to").value || 0);
  const quantity = Number(document.querySelector("#transfer-quantity").value || 0);
  const part = partById(document.querySelector("#transfer-part").value);
  const fromWarehouse = warehouseById(fromWarehouseId);
  const toWarehouse = warehouseById(toWarehouseId);

  if (!part || !fromWarehouse || !toWarehouse || !quantity) {
    root.innerHTML = `<div class="activity-card"><strong>Waiting for transfer details</strong><p class="subtle">Pick a source, destination, part, and quantity to preview the move.</p></div>`;
    return;
  }

  root.innerHTML = `
    <div class="activity-card">
      <strong>${part.part_number} - ${part.description}</strong>
      <p class="subtle">From ${fromWarehouse.code} to ${toWarehouse.code}</p>
      <p class="subtle">${quantity} will move. Source stock goes from ${part.stock} to ${part.stock - quantity}.</p>
    </div>
  `;
}

function fillSelect(select, options, formatter) {
  if (!select) return;
  if (!options.length) {
    select.innerHTML = `<option value="">No options yet</option>`;
    return;
  }
  select.innerHTML = options.map((option) => `<option value="${option.id}">${formatter(option)}</option>`).join("");
}

function renderSelects() {
  const vendorSelects = [document.querySelector("#part-vendor"), document.querySelector("#po-vendor")];
  vendorSelects.forEach((select) => fillSelect(select, state.vendors, (vendor) => vendor.name));

  const partSelects = [document.querySelector("#po-part")];
  partSelects.forEach((select) => fillSelect(select, state.parts, (part) => `${part.part_number} - ${part.description}`));
}

function renderAll() {
  renderWarehouseSelector();
  renderInventoryAttentionBadge();
  renderPoAttentionBadge();
  initializeCollapsedCategories();
  initializeCollapsedJobs();
  renderSelects();
  renderDashboard();
  renderInventoryTable();
  renderVendorTable();
  renderWarehouseTable();
  renderPurchaseOrders();
  renderReceivingLog();
  renderJobsList();
}

function updateToggleButton(panelId) {
  const button = document.querySelector(`.form-toggle[data-form-target="${panelId}"]`);
  const panel = document.querySelector(`#${panelId}`);
  if (!button || !panel) return;
  button.textContent = panel.classList.contains("hidden") ? button.dataset.openLabel : button.dataset.closeLabel;
}

function showForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.remove("hidden");
  updateToggleButton(panelId);
}

function hideForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.add("hidden");
  updateToggleButton(panelId);
}

function toggleForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.toggle("hidden");
  updateToggleButton(panelId);
}

function clearPartForm() {
  document.querySelector("#part-form").reset();
  hideForm(formPanels.part);
}

function clearReorderForm() {
  return;
}

function clearVendorForm() {
  document.querySelector("#vendor-form").reset();
  hideForm(formPanels.vendor);
}

function clearWarehouseForm() {
  document.querySelector("#warehouse-form").reset();
  hideForm(formPanels.warehouse);
}

function jobPartOptionsMarkup(selectedPartId = "") {
  return state.parts.map((part) => `<option value="${part.id}" ${Number(selectedPartId) === Number(part.id) ? "selected" : ""}>${part.part_number} - ${part.description}</option>`).join("");
}

function addJobRequirementRow(selectedPartId = "", quantity = 1) {
  const container = document.querySelector("#job-required-parts");
  if (!container) return;
  jobRequirementRowSeed += 1;
  const row = document.createElement("div");
  row.className = "job-required-row";
  row.dataset.rowId = String(jobRequirementRowSeed);
  row.innerHTML = `
    <label>Part<select name="jobRequiredPart">${jobPartOptionsMarkup(selectedPartId)}</select></label>
    <label class="field-small">Required Qty<input name="jobRequiredQuantity" type="number" min="1" value="${quantity}" required></label>
    <button type="button" class="ghost" data-remove-job-row="${jobRequirementRowSeed}">Remove</button>
  `;
  container.appendChild(row);
}

function resetJobForm() {
  const form = document.querySelector("#job-form");
  if (form) {
    form.reset();
  }
  const container = document.querySelector("#job-required-parts");
  if (container) {
    container.innerHTML = "";
  }
  addJobRequirementRow();
  hideForm(formPanels.job);
}

function bindNavigation() {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.view}-view`).classList.add("active");
    });
  });
}

function bindFormToggles() {
  document.querySelectorAll(".form-toggle").forEach((button) => {
    updateToggleButton(button.dataset.formTarget);
    button.addEventListener("click", () => toggleForm(button.dataset.formTarget));
  });
}

async function loadApp(warehouseId = state.selectedWarehouseId) {
  const suffix = warehouseId ? `?warehouseId=${warehouseId}` : "";
  const response = await fetch(`/api/bootstrap${suffix}`);
  state = await response.json();
  pruneVerifiedReceipts();
  pruneInlineEditors();
  renderAll();
  if (!document.querySelector("#job-required-parts .job-required-row")) {
    addJobRequirementRow();
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  state = data;
  pruneVerifiedReceipts();
  pruneInlineEditors();
  renderAll();
}

async function postReorder(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  state = data.state;
  pruneVerifiedReceipts();
  pruneInlineEditors();
  renderAll();
  return data.createdReorderId;
}

async function postCreatedPurchaseOrder(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  state = data.state;
  pruneVerifiedReceipts();
  pruneInlineEditors();
  renderAll();
  return data.createdPoId;
}

async function postAction(url, payload, confirmationMessage = "") {
  if (confirmationMessage && !window.confirm(confirmationMessage)) {
    return;
  }
  await postJson(url, payload);
}

function bindForms() {
  document.querySelector("#part-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/parts", {
      warehouseId: currentWarehouseId(),
      partNumber: document.querySelector("#part-number").value.trim(),
      description: document.querySelector("#part-description").value.trim(),
      category: document.querySelector("#part-category").value.trim(),
      stock: Number(document.querySelector("#part-stock").value),
      reorderPoint: Number(document.querySelector("#part-reorder").value),
      vendorId: Number(document.querySelector("#part-vendor").value),
      unitCost: Number(document.querySelector("#part-cost").value)
    }).then(clearPartForm).catch((error) => window.alert(error.message));
  });

  document.querySelector("#vendor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/vendors", {
      warehouseId: currentWarehouseId(),
      name: document.querySelector("#vendor-name").value.trim(),
      contact: document.querySelector("#vendor-contact").value.trim(),
      email: document.querySelector("#vendor-email").value.trim(),
      phone: document.querySelector("#vendor-phone").value.trim(),
      leadTimeDays: Number(document.querySelector("#vendor-lead-time").value)
    }).then(clearVendorForm).catch((error) => window.alert(error.message));
  });

  document.querySelector("#warehouse-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/warehouses", {
      name: document.querySelector("#warehouse-name").value.trim(),
      code: document.querySelector("#warehouse-code").value.trim()
    }).then(clearWarehouseForm).catch((error) => window.alert(error.message));
  });

  document.querySelector("#po-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/purchase-orders", {
      warehouseId: currentWarehouseId(),
      vendorId: Number(document.querySelector("#po-vendor").value),
      partId: Number(document.querySelector("#po-part").value),
      quantity: Number(document.querySelector("#po-quantity").value),
      eta: document.querySelector("#po-eta").value,
      notes: document.querySelector("#po-notes").value.trim()
    }).then(() => {
      event.target.reset();
      hideForm(formPanels.po);
    }).catch((error) => window.alert(error.message));
  });

  document.querySelector("#job-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const requirements = [...document.querySelectorAll("#job-required-parts .job-required-row")].map((row) => ({
      partId: Number(row.querySelector('[name="jobRequiredPart"]').value),
      requiredQuantity: Number(row.querySelector('[name="jobRequiredQuantity"]').value)
    })).filter((item) => item.partId && item.requiredQuantity > 0);
    await postJson("/api/jobs", {
      warehouseId: currentWarehouseId(),
      jobNumber: document.querySelector("#job-number").value.trim(),
      title: document.querySelector("#job-title").value.trim(),
      technician: document.querySelector("#job-tech").value.trim(),
      notes: document.querySelector("#job-notes").value.trim(),
      requirements
    }).then(() => {
      resetJobForm();
    }).catch((error) => window.alert(error.message));
  });
}

function bindActions() {
  document.querySelector("#inventory-search").addEventListener("input", renderInventoryTable);
  document.querySelector("#part-form-clear").addEventListener("click", clearPartForm);
  document.querySelector("#vendor-form-clear").addEventListener("click", clearVendorForm);
  document.querySelector("#warehouse-form-clear").addEventListener("click", clearWarehouseForm);
  document.querySelector("#job-add-part-row").addEventListener("click", () => addJobRequirementRow());
  document.querySelectorAll(".form-toggle").forEach((button) => {
    updateToggleButton(button.dataset.formTarget);
    button.addEventListener("click", () => toggleForm(button.dataset.formTarget));
  });

  document.querySelector("#warehouse-selector").addEventListener("change", async (event) => {
    await loadApp(Number(event.target.value));
    clearPartForm();
    clearVendorForm();
    clearWarehouseForm();
    resetJobForm();
  });

  document.body.addEventListener("click", async (event) => {
    const categoryToggle = event.target.closest("[data-category-toggle]");
    if (categoryToggle) {
      const category = categoryToggle.dataset.categoryToggle;
      if (collapsedCategories.has(category)) {
        collapsedCategories.delete(category);
      } else {
        collapsedCategories.add(category);
      }
      renderInventoryTable();
      return;
    }

    const jobToggle = event.target.closest("[data-job-toggle]");
    if (jobToggle) {
      const jobId = Number(jobToggle.dataset.jobToggle);
      if (collapsedJobs.has(jobId)) {
        collapsedJobs.delete(jobId);
      } else {
        collapsedJobs.add(jobId);
      }
      renderJobsList();
      return;
    }

    const poStatusButton = event.target.closest("[data-po-status]");
    if (poStatusButton) {
      await postAction(
        `/api/purchase-orders/${poStatusButton.dataset.poStatus}/status`,
        { warehouseId: currentWarehouseId(), status: poStatusButton.dataset.statusValue },
        `Mark this order as ${poStatusButton.dataset.statusValue}?`
      ).catch((error) => window.alert(error.message));
      return;
    }

    const poReceiveButton = event.target.closest("[data-po-receive]");
    if (poReceiveButton) {
      const poId = Number(poReceiveButton.dataset.poReceive);
      if (!verifiedReceipts.has(poId)) {
        window.alert("Check the counted and verified box before marking this order received.");
        return;
      }
      if (!window.confirm("Mark this PO as received and add the quantity into inventory?")) {
        return;
      }
      await postJson(`/api/purchase-orders/${poReceiveButton.dataset.poReceive}/receive`, {
        warehouseId: currentWarehouseId(),
        receivedBy: "Inventory",
        notes: "Received from PO tab",
        verifiedCount: true
      }).then(() => {
        verifiedReceipts.delete(poId);
      }).catch((error) => window.alert(error.message));
      return;
    }

    const pullJobPartButton = event.target.closest("[data-pull-job-part]");
    if (pullJobPartButton) {
      const requirement = state.jobRequirements.find((item) => Number(item.id) === Number(pullJobPartButton.dataset.pullJobPart));
      if (!requirement) return;
      const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
      const part = partById(requirement.part_id);
      const requested = window.prompt(`How many of ${part ? part.part_number : "this part"} do you want to mark as pulled?`, String(remaining));
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert("Enter a whole number greater than 0.");
        return;
      }
      await postJson(`/api/job-parts/${requirement.id}/pull`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: "Pulled from job card"
      }).catch((error) => window.alert(error.message));
      return;
    }
  });

  document.body.addEventListener("change", (event) => {
    const verifyBox = event.target.closest("[data-po-verified]");
    if (!verifyBox) return;
    const poId = Number(verifyBox.dataset.poVerified);
    if (verifyBox.checked) {
      verifiedReceipts.add(poId);
    } else {
      verifiedReceipts.delete(poId);
    }
    renderPurchaseOrders();
  });

  document.body.addEventListener("click", (event) => {
    const partButton = event.target.closest("[data-edit-part]");
    if (partButton) {
      inlineEditors.partId = Number(inlineEditors.partId) === Number(partButton.dataset.editPart) ? null : Number(partButton.dataset.editPart);
      renderInventoryTable();
      return;
    }

    const orderMoreButton = event.target.closest("[data-order-more]");
    if (orderMoreButton) {
      const part = partById(orderMoreButton.dataset.orderMore);
      if (!part) return;
      const suggested = Math.max(part.reorder_point * 2 - part.stock, 1);
      const requested = window.prompt(`How many of ${part.part_number} do you want to order?`, String(suggested));
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert("Enter a whole number greater than 0.");
        return;
      }
      postCreatedPurchaseOrder("/api/purchase-orders/order-more", {
        warehouseId: currentWarehouseId(),
        partId: part.id,
        quantity,
        notes: `Low stock reorder for ${part.part_number}`
      }).then((createdPoId) => {
        if (!createdPoId) return;
        window.open(`/purchase-orders/${createdPoId}/form`, "_blank", "noopener,noreferrer");
      }).catch((error) => window.alert(error.message));
    }

    const vendorButton = event.target.closest("[data-edit-vendor]");
    if (vendorButton) {
      inlineEditors.vendorId = Number(inlineEditors.vendorId) === Number(vendorButton.dataset.editVendor) ? null : Number(vendorButton.dataset.editVendor);
      renderVendorTable();
      return;
    }

    const warehouseButton = event.target.closest("[data-edit-warehouse]");
    if (warehouseButton) {
      inlineEditors.warehouseId = Number(inlineEditors.warehouseId) === Number(warehouseButton.dataset.editWarehouse) ? null : Number(warehouseButton.dataset.editWarehouse);
      renderWarehouseTable();
      return;
    }

    const cancelButton = event.target.closest("[data-inline-cancel]");
    if (cancelButton) {
      const kind = cancelButton.dataset.inlineCancel;
      if (kind === "part") {
        inlineEditors.partId = null;
        renderInventoryTable();
      } else if (kind === "vendor") {
        inlineEditors.vendorId = null;
        renderVendorTable();
      } else if (kind === "warehouse") {
        inlineEditors.warehouseId = null;
        renderWarehouseTable();
      }
      return;
    }

    const removeJobRowButton = event.target.closest("[data-remove-job-row]");
    if (removeJobRowButton) {
      removeJobRowButton.closest(".job-required-row")?.remove();
      if (!document.querySelector("#job-required-parts .job-required-row")) {
        addJobRequirementRow();
      }
      return;
    }
  });

  document.body.addEventListener("submit", async (event) => {
    const partForm = event.target.closest("[data-inline-part-form]");
    if (partForm) {
      event.preventDefault();
      const formData = new FormData(partForm);
      await postJson("/api/parts", {
        id: Number(formData.get("id")),
        warehouseId: currentWarehouseId(),
        partNumber: String(formData.get("partNumber")).trim(),
        description: String(formData.get("description")).trim(),
        category: String(formData.get("category")).trim(),
        stock: Number(formData.get("stock")),
        reorderPoint: Number(formData.get("reorderPoint")),
        vendorId: Number(formData.get("vendorId")),
        unitCost: Number(formData.get("unitCost"))
      }).then(() => {
        inlineEditors.partId = null;
        renderInventoryTable();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const vendorForm = event.target.closest("[data-inline-vendor-form]");
    if (vendorForm) {
      event.preventDefault();
      const formData = new FormData(vendorForm);
      await postJson("/api/vendors", {
        id: Number(formData.get("id")),
        warehouseId: currentWarehouseId(),
        name: String(formData.get("name")).trim(),
        contact: String(formData.get("contact")).trim(),
        email: String(formData.get("email")).trim(),
        phone: String(formData.get("phone")).trim(),
        leadTimeDays: Number(formData.get("leadTimeDays"))
      }).then(() => {
        inlineEditors.vendorId = null;
        renderVendorTable();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const warehouseForm = event.target.closest("[data-inline-warehouse-form]");
    if (warehouseForm) {
      event.preventDefault();
      const formData = new FormData(warehouseForm);
      await postJson("/api/warehouses", {
        id: Number(formData.get("id")),
        name: String(formData.get("name")).trim(),
        code: String(formData.get("code")).trim()
      }).then(() => {
        inlineEditors.warehouseId = null;
        renderWarehouseTable();
      }).catch((error) => window.alert(error.message));
    }
  });

  document.body.addEventListener("click", async (event) => {
    const deletePartButton = event.target.closest("[data-inline-delete-part]");
    if (deletePartButton) {
      await postAction(
        `/api/parts/${deletePartButton.dataset.inlineDeletePart}/delete`,
        { warehouseId: currentWarehouseId() },
        "Delete this part? This only works if it has no history."
      ).then(() => {
        inlineEditors.partId = null;
        renderInventoryTable();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const deleteVendorButton = event.target.closest("[data-inline-delete-vendor]");
    if (deleteVendorButton) {
      await postAction(
        `/api/vendors/${deleteVendorButton.dataset.inlineDeleteVendor}/delete`,
        { warehouseId: currentWarehouseId() },
        "Delete this vendor? This only works if nothing is using it."
      ).then(() => {
        inlineEditors.vendorId = null;
        renderVendorTable();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const archiveWarehouseButton = event.target.closest("[data-inline-archive-warehouse]");
    if (archiveWarehouseButton) {
      await postAction(
        `/api/warehouses/${archiveWarehouseButton.dataset.inlineArchiveWarehouse}/archive`,
        { warehouseId: currentWarehouseId() },
        "Toggle archive status for this warehouse?"
      ).then(() => {
        inlineEditors.warehouseId = null;
        renderWarehouseTable();
      }).catch((error) => window.alert(error.message));
    }
  });

  document.querySelector("#reset-demo").addEventListener("click", async () => {
    await postJson("/api/reset", { warehouseId: currentWarehouseId() }).then(() => {
      clearPartForm();
      clearVendorForm();
      clearWarehouseForm();
    }).catch((error) => window.alert(error.message));
  });

  document.querySelector("#export-data").addEventListener("click", () => {
    window.location.href = `/api/export?warehouseId=${currentWarehouseId()}`;
  });
}

function renderInventoryTable() {
  const search = document.querySelector("#inventory-search").value.trim().toLowerCase();
  const filteredParts = state.parts.filter((part) => [part.part_number, part.description, part.category, vendorName(part.vendor_id)].join(" ").toLowerCase().includes(search));
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) => left[0].localeCompare(right[0]));
  const rows = groups.map(([category, parts]) => {
    const isCollapsed = collapsedCategories.has(category);
    const attentionCount = parts.filter(needsAttention).length;
    const categoryRow = `
      <tr class="category-row" data-category-toggle="${category}">
        <td colspan="5">
          <div class="category-row-inner">
            <div class="category-title-wrap">
              <button type="button" class="category-toggle" data-category-toggle="${category}">${isCollapsed ? ">" : "v"}</button>
              <strong>${category}</strong>
              <span class="subtle">${parts.length} parts</span>
            </div>
            ${attentionCount ? `<span class="status-pill status-warn">${attentionCount} need attention</span>` : ""}
          </div>
        </td>
      </tr>
    `;
    if (isCollapsed) {
      return categoryRow;
    }
    const partRows = parts.map((part) => {
      if (Number(inlineEditors.partId) === Number(part.id)) {
        return renderInlinePartEditor(part);
      }
      const status = inventoryStatus(part);
      return `<tr><td class="part-meta"><strong>${part.part_number}</strong><span class="subtle">${part.description}</span></td><td>${part.stock}</td><td>${vendorName(part.vendor_id)}</td><td><span class="status-pill ${status.className}">${status.label}</span></td><td><button class="tiny-action" data-order-more="${part.id}">Order More</button> <button class="tiny-action" data-edit-part="${part.id}">Edit</button></td></tr>`;
    }).join("");
    return `${categoryRow}${partRows}`;
  }).join("");
  document.querySelector("#inventory-table").innerHTML = rows || `<tr><td colspan="5">${emptyState()}</td></tr>`;
}

bindNavigation();
bindForms();
bindActions();
loadApp();
