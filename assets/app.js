let state = {
  warehouses: [],
  activeWarehouses: [],
  selectedWarehouseId: null,
  selectedWarehouse: null,
  vendors: [],
  orderFormTemplates: [],
  parts: [],
  jobs: [],
  jobRequirements: [],
  orderListItems: [],
  purchaseOrders: [],
  completedJobs: [],
  receivingLogs: [],
  usageLogs: []
};
const verifiedReceipts = new Set();
const inlineEditors = {
  partId: null,
  vendorId: null,
  orderFormTemplateId: null,
  warehouseId: null
};
const collapsedCategories = new Set();
const knownInventoryCategories = new Set();
const collapsedJobs = new Set();
let jobRequirementRowSeed = 0;
let dashboardUsageExpanded = false;
let editingJobId = null;
let jobEditDirty = false;
let jobPartModalJobId = null;
let jobPartModalSearch = "";
let jobPartModalSelectedPartId = null;
const jobPartModalFilters = {
  status: "all",
  vendor: "all",
  category: "all"
};
const collapsedJobPartCategories = new Set();
const knownJobPartCategories = new Set();
const inventoryFilters = {
  status: "all",
  vendor: "all",
  category: "all"
};

const partPhotoLibrary = {
  "Drain Assemblies": "https://loremflickr.com/80/80/drain,plumbing?lock=1",
  "Valves": "https://loremflickr.com/80/80/valve,plumbing?lock=2",
  "Sealants": "https://loremflickr.com/80/80/caulk,sealant?lock=3",
  "Supply Lines": "https://loremflickr.com/80/80/plumbing,hose?lock=4",
  "Trim Kits": "https://loremflickr.com/80/80/shower,bathroom?lock=5",
  "Faucets": "https://loremflickr.com/80/80/faucet,bathroom?lock=6",
  "Install Kits": "https://loremflickr.com/80/80/tools,install?lock=7",
  "Shower Hardware": "https://loremflickr.com/80/80/showerhead,bathroom?lock=8",
  "Toilet Parts": "https://loremflickr.com/80/80/toilet,plumbing?lock=9",
  "P-Traps": "https://loremflickr.com/80/80/pipe,plumbing?lock=10"
};

const formPanels = {
  part: "part-form-panel",
  po: "po-form-panel",
  job: "job-form-panel",
  warehouse: "warehouse-form-panel",
  vendor: "vendor-form-panel",
  orderForm: "order-form-panel"
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

function orderFormTemplateByRowId(templateRowId) {
  return state.orderFormTemplates.find((template) => Number(template.id) === Number(templateRowId));
}

function orderFormTemplateName(templateId) {
  return state.orderFormTemplates.find((template) => String(template.template_id) === String(templateId))?.name || "Not linked";
}

function orderFormTemplateOptionsMarkup(selectedTemplateId = "") {
  const blank = `<option value="">No linked form</option>`;
  return blank + state.orderFormTemplates.map((template) => `<option value="${template.template_id}" ${String(template.template_id) === String(selectedTemplateId) ? "selected" : ""}>${template.name}</option>`).join("");
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

function findOrderListEntryForPart(partId) {
  return state.orderListItems.find((item) => Number(item.part_id) === Number(partId));
}

function partHasOpenPurchaseOrder(partId) {
  return state.purchaseOrders.some((po) => po.status !== "Received" && (po.lines || []).some((line) => Number(line.part_id) === Number(partId)));
}

function latestOpenPurchaseOrderForPart(partId) {
  return state.purchaseOrders
    .filter((po) => po.status !== "Received" && (po.lines || []).some((line) => Number(line.part_id) === Number(partId)))
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at))[0];
}

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0);
}

function flashToast(message, tone = "success") {
  let toast = document.querySelector("#app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.className = "app-toast hidden";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = `app-toast ${tone}`;
  window.clearTimeout(flashToast.timeoutId);
  flashToast.timeoutId = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 2200);
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
  if (inlineEditors.orderFormTemplateId && !state.orderFormTemplates.some((template) => Number(template.id) === Number(inlineEditors.orderFormTemplateId))) {
    inlineEditors.orderFormTemplateId = null;
  }
  if (inlineEditors.warehouseId && !state.warehouses.some((warehouse) => Number(warehouse.id) === Number(inlineEditors.warehouseId))) {
    inlineEditors.warehouseId = null;
  }
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function inventoryStatus(part) {
  const stagedOrder = findOrderListEntryForPart(part.id);
  const openPo = latestOpenPurchaseOrderForPart(part.id);
  if (openPo?.status === "Waiting for Part" || openPo?.status === "Partial Received") return { label: "Order Processed", className: "status-info" };
  if (openPo?.status === "Email Pending") return { label: "Order In Process", className: "status-info" };
  if (stagedOrder) return { label: "Order Staged", className: "status-info" };
  if (part.stock === 0) return { label: "Out of Stock", className: "status-danger" };
  if (part.stock <= part.reorder_point) return { label: "Low Stock", className: "status-warn" };
  return { label: "Healthy", className: "status-ok" };
}

function needsAttention(part) {
  return part.stock <= part.reorder_point && !findOrderListEntryForPart(part.id) && !partHasOpenPurchaseOrder(part.id);
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

function filteredInventoryParts() {
  const search = document.querySelector("#inventory-search")?.value.trim().toLowerCase() || "";
  return state.parts.filter((part) => {
    const status = inventoryStatus(part).label;
    const matchesSearch = [part.part_number, part.description, part.category, vendorName(part.vendor_id)].join(" ").toLowerCase().includes(search);
    const matchesStatus = inventoryFilters.status === "all" || status === inventoryFilters.status;
    const matchesVendor = inventoryFilters.vendor === "all" || String(part.vendor_id) === inventoryFilters.vendor;
    const matchesCategory = inventoryFilters.category === "all" || (part.category || "Uncategorized") === inventoryFilters.category;
    return matchesSearch && matchesStatus && matchesVendor && matchesCategory;
  });
}

function renderInventoryFilters() {
  const statusSelect = document.querySelector("#inventory-status-filter");
  const vendorSelect = document.querySelector("#inventory-vendor-filter");
  const categorySelect = document.querySelector("#inventory-category-filter");
  if (!statusSelect || !vendorSelect || !categorySelect) return;

  const statuses = ["Healthy", "Low Stock", "Order In Process", "Order Processed", "Out of Stock"];
  statusSelect.innerHTML = `<option value="all">All Statuses</option>${statuses.map((status) => `<option value="${status}">${status}</option>`).join("")}`;
  statusSelect.value = inventoryFilters.status;

  vendorSelect.innerHTML = `<option value="all">All Vendors</option>${state.vendors.map((vendor) => `<option value="${vendor.id}">${vendor.name}</option>`).join("")}`;
  vendorSelect.value = inventoryFilters.vendor;

  const categories = [...new Set(state.parts.map((part) => part.category || "Uncategorized"))].sort((left, right) => left.localeCompare(right));
  categorySelect.innerHTML = `<option value="all">All Categories</option>${categories.map((category) => `<option value="${category}">${category}</option>`).join("")}`;
  categorySelect.value = inventoryFilters.category;
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

function collapseAllInventoryCategories() {
  const categories = [...new Set(state.parts.map((part) => part.category || "Uncategorized"))];
  collapsedCategories.clear();
  categories.forEach((category) => collapsedCategories.add(category));
}

function collapseAllJobs() {
  const jobIds = state.jobs.map((job) => Number(job.id));
  collapsedJobs.clear();
  jobIds.forEach((jobId) => collapsedJobs.add(jobId));
}

function resetExpandableUiState() {
  collapseAllInventoryCategories();
  collapseAllJobs();
  dashboardUsageExpanded = false;
  inlineEditors.partId = null;
  inlineEditors.vendorId = null;
  inlineEditors.warehouseId = null;
  closeJobPartModal(true);
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
      <td colspan="6">
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
      <td colspan="7">
        <form class="inline-editor-grid compact" data-inline-vendor-form="${vendor.id}">
          <input type="hidden" name="id" value="${vendor.id}">
          <label>Vendor Name<input name="name" type="text" value="${vendor.name}" required></label>
          <label>Contact<input name="contact" type="text" value="${vendor.contact}" required></label>
          <label>Email<input name="email" type="email" value="${vendor.email}" required></label>
          <label>Phone<input name="phone" type="text" value="${vendor.phone}" required></label>
          <label class="field-small">Lead Time<input name="leadTimeDays" type="number" min="0" value="${vendor.lead_time_days}" required></label>
          <label>Linked Order Form<select name="linkedTemplateId">${orderFormTemplateOptionsMarkup(vendor.linked_template_id)}</select></label>
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

function renderInlineOrderFormTemplateEditor(template) {
  return `
    <tr class="inline-editor-row">
      <td colspan="5">
        <form class="inline-editor-grid compact" data-inline-order-form-template-form="${template.id}">
          <input type="hidden" name="id" value="${template.id}">
          <label>Template ID<input name="templateId" type="text" value="${template.template_id}" required></label>
          <label>Template Name<input name="name" type="text" value="${template.name}" required></label>
          <label>Form Style<select name="formVariant"><option value="aquaflow" ${template.form_variant === "aquaflow" ? "selected" : ""}>AquaFlow Style</option><option value="bathbuild" ${template.form_variant === "bathbuild" ? "selected" : ""}>BathBuild Style</option></select></label>
          <label>Notes<input name="notes" type="text" value="${template.notes || ""}"></label>
          <div class="form-actions inline-actions">
            <button type="submit" class="primary">Save</button>
            <button type="button" class="ghost" data-inline-cancel="order-form-template">Cancel</button>
            <button type="button" class="ghost" data-inline-delete-order-form-template="${template.id}">Delete</button>
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
    activeJobs: state.jobs.length,
    readyJobs: state.jobs.filter((job) => job.status === "Ready to Go").length
  };
}

function weeklyUsageEntries() {
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);
  return [...state.usageLogs
    .filter((log) => new Date(log.created_at) >= weekStart)
    .reduce((totals, log) => {
      const current = totals.get(log.part_id) || { quantity: 0, part: partById(log.part_id) };
      current.quantity += log.quantity;
      totals.set(log.part_id, current);
      return totals;
    }, new Map())
    .values()]
    .filter((entry) => entry.part)
    .sort((left, right) => right.quantity - left.quantity);
}

function readyJobsList() {
  return state.jobs
    .filter((job) => job.status === "Ready to Go")
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
}

function makePartThumbnail(part) {
  return partPhotoLibrary[part.category] || "https://commons.wikimedia.org/wiki/Special:FilePath/PVC_pipe_Example.jpg";
}

function renderWarehouseSelector() {
  const select = document.querySelector("#warehouse-selector");
  const summary = document.querySelector("#warehouse-summary");
  if (!select || !summary) return;
  const options = state.activeWarehouses.length ? state.activeWarehouses : state.warehouses;
  select.innerHTML = options.map((warehouse) => `
    <option value="${warehouse.id}">${warehouse.name} (${warehouse.code})</option>
  `).join("");
  const selectedId = state.selectedWarehouseId || options[0]?.id || "";
  select.value = String(selectedId);
  summary.textContent = state.selectedWarehouse
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
  const openPoCount = state.purchaseOrders.filter((po) => po.status !== "Received").length + state.orderListItems.length;
  badge.textContent = String(openPoCount);
  badge.classList.toggle("hidden", openPoCount === 0);
}

function renderJobsAttentionBadge() {
  const badge = document.querySelector("#jobs-attention-badge");
  if (!badge) return;
  const activeJobIdsNeedingParts = new Set(
    state.jobRequirements
      .filter((requirement) => Number(requirement.pulled_quantity) < Number(requirement.required_quantity))
      .map((requirement) => Number(requirement.job_id))
  );
  const count = activeJobIdsNeedingParts.size;
  badge.textContent = String(count);
  badge.classList.toggle("hidden", count === 0);
}

function renderDashboard() {
  const root = document.querySelector("#dashboard-view");
  const metrics = dashboardMetrics();
  const usageEntries = weeklyUsageEntries();
  const displayedUsage = dashboardUsageExpanded ? usageEntries : usageEntries.slice(0, 5);
  const openOrders = state.purchaseOrders.filter((po) => po.status !== "Received");
  const warehouseLabel = state.selectedWarehouse ? state.selectedWarehouse.name : "Current Warehouse";
  const readyJobs = readyJobsList();

  root.innerHTML = `
    <div class="metrics">
      <article class="metric-card"><p class="eyebrow">${warehouseLabel}</p><strong>${state.selectedWarehouse ? state.selectedWarehouse.code : "--"}</strong><p class="subtle">Warehouse currently in view</p></article>
      <article class="metric-card"><p class="eyebrow">Low Stock Alerts</p><strong>${metrics.lowStock}</strong><p class="subtle">Parts still needing action</p></article>
      <article class="metric-card"><p class="eyebrow">Open Jobs</p><strong>${metrics.activeJobs}</strong><p class="subtle">Jobs currently active at this warehouse</p></article>
      <article class="metric-card"><p class="eyebrow">Ready To Go</p><strong>${metrics.readyJobs}</strong><p class="subtle">Jobs with every required part pulled</p></article>
    </div>
    <div class="dashboard-grid">
      <div class="stack">
        <article class="panel">
          <div class="table-header">
            <div>
              <h4>Parts used this week</h4>
              <p class="subtle">Top five by default, open the full list when you need detail.</p>
            </div>
            ${usageEntries.length > 5 ? `<button type="button" class="ghost dashboard-toggle" data-toggle-weekly-usage="true">${dashboardUsageExpanded ? "Show Top 5" : "Show All"}</button>` : ""}
          </div>
          <div class="activity-list compact-list">
            ${displayedUsage.length ? displayedUsage.map((entry) => `
              <div class="activity-card usage-card">
                <strong><span class="part-number-link">${entry.part.part_number}</span> - ${entry.part.description}</strong>
                <p class="subtle">${entry.quantity} used this week</p>
              </div>`).join("") : emptyState()}
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="panel">
          <h4>Jobs ready to go</h4>
          <div class="activity-list compact-list">
            ${readyJobs.length ? readyJobs.map((job) => `
              <div class="activity-card job-ready-card">
                <strong>${job.job_number}</strong>
                <p class="subtle">${job.customer_name || "No customer listed"}</p>
                <p class="subtle">${job.address || "No address listed"}</p>
              </div>`).join("") : emptyState()}
          </div>
        </article>
        <article class="panel">
          <h4>Open purchase orders</h4>
          <div class="activity-list compact-list">
            ${openOrders.length ? openOrders.map((po) => `<div class="activity-card"><strong class="po-number-link">${po.po_number}</strong><p class="subtle">${po.vendor_name} - <span class="part-number-link">${po.part_number}</span></p><p class="subtle">${po.status} | Qty ${po.quantity}</p></div>`).join("") : emptyState()}
          </div>
        </article>
      </div>
    </div>
  `;
}

function renderInventoryTable() {
  const filteredParts = filteredInventoryParts();
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) => left[0].localeCompare(right[0]));
  const rows = groups.map(([category, parts]) => {
    const isCollapsed = collapsedCategories.has(category);
    const attentionCount = parts.filter(needsAttention).length;
    const categoryRow = `
      <tr class="category-row" data-category-toggle="${category}">
        <td colspan="6">
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
      return `<tr>
        <td class="part-meta"><strong class="part-number-link">${part.part_number}</strong><span class="subtle">${part.description}</span></td>
        <td><img class="part-thumb" src="${makePartThumbnail(part)}" alt="${part.part_number} thumbnail"></td>
        <td>${part.stock}</td>
        <td>${vendorName(part.vendor_id)}</td>
        <td><span class="status-pill ${status.className}">${status.label}</span></td>
        <td><button class="tiny-action" data-add-to-order-list="${part.id}">Add to Order List</button> <button class="tiny-action" data-edit-part="${part.id}">Edit</button></td>
      </tr>`;
    }).join("");
    return `${categoryRow}${partRows}`;
  }).join("");
  document.querySelector("#inventory-table").innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;
}

function renderVendorTable() {
  const rows = state.vendors.map((vendor) => {
    if (Number(inlineEditors.vendorId) === Number(vendor.id)) {
      return renderInlineVendorEditor(vendor);
    }
    const linkedForm = vendor.linked_template_name || orderFormTemplateName(vendor.linked_template_id);
    const rowMarkup = `<tr><td><strong>${vendor.name}</strong></td><td>${vendor.contact}</td><td>${vendor.email}</td><td>${vendor.phone}</td><td>${vendor.lead_time_days} days</td><td>${linkedForm || "Not linked"}</td><td><button class="tiny-action" data-edit-vendor="${vendor.id}">Edit</button></td></tr>`;
    return rowMarkup;
  }).join("");
  document.querySelector("#vendor-table").innerHTML = rows || `<tr><td colspan="7">${emptyState()}</td></tr>`;
}

function renderOrderFormTemplateTable() {
  const rows = state.orderFormTemplates.map((template) => {
    if (Number(inlineEditors.orderFormTemplateId) === Number(template.id)) {
      return renderInlineOrderFormTemplateEditor(template);
    }
    return `<tr><td><strong>${template.template_id}</strong></td><td>${template.name}</td><td>${template.form_variant}</td><td>${template.notes || ""}</td><td><button class="tiny-action" data-edit-order-form-template="${template.id}">Edit</button></td></tr>`;
  }).join("");
  document.querySelector("#order-form-template-table").innerHTML = rows || `<tr><td colspan="5">${emptyState()}</td></tr>`;
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

function renderJobCards(jobs, rootSelector, options = {}) {
  const root = document.querySelector(rootSelector);
  if (!root) return;
  const showActions = options.showActions !== false;
  const visibleJobs = showActions && editingJobId ? jobs.filter((job) => Number(job.id) === Number(editingJobId)) : jobs;
  const sortedJobs = [...visibleJobs].sort((left, right) => {
    const leftReady = left.status === "Ready to Go" ? 1 : 0;
    const rightReady = right.status === "Ready to Go" ? 1 : 0;
    if (leftReady !== rightReady) {
      return rightReady - leftReady;
    }
    return new Date(right.created_at) - new Date(left.created_at);
  });

  root.innerHTML = sortedJobs.length ? sortedJobs.map((job) => {
    const requirements = jobRequirementsFor(job.id);
    const readyToGo = job.status === "Ready to Go";
    const isCollapsed = showActions && !editingJobId ? collapsedJobs.has(Number(job.id)) : false;
    const totalRequired = requirements.reduce((sum, requirement) => sum + requirement.required_quantity, 0);
    const totalPulled = requirements.reduce((sum, requirement) => sum + requirement.pulled_quantity, 0);
    const requirementRows = requirements.length ? requirements.map((requirement) => {
      const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
      const part = partById(requirement.part_id);
      return `
        <div class="job-part-row">
          <div class="job-part-copy">
            <strong><span class="part-number-link">${part ? part.part_number : "Unknown"}</span>${part ? ` <span class="subtle">- ${part.description}</span>` : ""}</strong>
            <p class="subtle">Required ${requirement.required_quantity} | Pulled ${requirement.pulled_quantity} | In Inventory ${part ? part.stock : 0}</p>
          </div>
          <div class="job-part-actions ${showActions ? "" : "job-part-actions-static"}">
            ${showActions ? `<button class="tiny-action" data-return-job-part="${requirement.id}" ${requirement.pulled_quantity === 0 ? "disabled" : ""}>Return</button><button class="tiny-action" data-pull-job-part="${requirement.id}" ${remaining === 0 ? "disabled" : ""}>Pull</button>` : ""}
          </div>
        </div>
      `;
    }).join("") : emptyState();

    return `
      <div class="activity-card job-card ${readyToGo ? "job-card-ready" : ""}">
        <div class="category-row-inner job-row-header" data-job-toggle="${job.id}">
          <div class="category-title-wrap">
            ${showActions && !editingJobId ? `<button type="button" class="category-toggle" data-job-toggle="${job.id}">${isCollapsed ? ">" : "v"}</button>` : ""}
            <div class="job-identity-block">
              <div class="job-title-line">
                <strong>${job.job_number}</strong>
                <span class="subtle">${job.title}</span>
              </div>
              <div class="job-meta-grid">
                <span><strong>Customer:</strong> ${job.customer_name || "Not set"}</span>
                <span><strong>Address:</strong> ${job.address || "Not set"}</span>
                <span><strong>Team:</strong> ${job.technician}</span>
                <span><strong>Scheduled:</strong> ${job.scheduled_for ? formatDate(job.scheduled_for) : "Not set"}</span>
              </div>
            </div>
          </div>
          <div class="job-header-side">
            ${job.status === "Completed" ? '<span class="status-pill status-ok">Completed</span>' : readyToGo ? '<span class="status-pill status-ok">Ready To Go</span>' : '<span class="status-pill status-warn">Needs Parts</span>'}
            <p class="subtle">${totalPulled} pulled of ${totalRequired}</p>
          </div>
        </div>
        ${isCollapsed ? "" : `
          <div class="job-detail-block">
            ${showActions ? `<div class="job-detail-toolbar"><button class="tiny-action" data-edit-job="${job.id}">Edit Job</button><button class="tiny-action" data-open-job-part-modal="${job.id}">Add Part</button><button class="tiny-action" data-complete-job="${job.id}" ${readyToGo ? "" : "disabled"}>Complete Job</button></div>` : ""}
            <div class="job-notes-card">
              <div class="table-header compact-header">
                <h4>Notes</h4>
              </div>
              <textarea class="job-notes-input" rows="3" ${showActions ? "readonly" : "readonly"}>${job.notes || ""}</textarea>
            </div>
            <div class="job-parts-list">${requirementRows}</div>
          </div>
        `}
      </div>
    `;
  }).join("") : emptyState();
}

function renderJobsList() {
  renderJobCards(state.jobs, "#jobs-list", { showActions: true });
}

function renderCompletedJobsList() {
  renderJobCards(state.completedJobs || [], "#completed-jobs-list", { showActions: false });
}

function renderJobEditOverlay() {
  const overlay = document.querySelector("#job-edit-overlay");
  const form = document.querySelector("#job-edit-modal-form");
  const title = document.querySelector("#job-edit-title");
  if (!overlay || !form || !title) return;
  if (!editingJobId) {
    overlay.classList.add("hidden");
    form.innerHTML = "";
    return;
  }

  const job = jobById(editingJobId);
  if (!job) {
    overlay.classList.add("hidden");
    form.innerHTML = "";
    return;
  }

  title.textContent = `${job.job_number} details`;
  const requirements = jobRequirementsFor(job.id);
  const requirementRows = requirements.length ? requirements.map((requirement) => {
    const part = partById(requirement.part_id);
    return `
      <div class="job-part-row">
        <div class="job-part-copy">
          <strong><span class="part-number-link">${part ? part.part_number : "Unknown"}</span>${part ? ` <span class="subtle">- ${part.description}</span>` : ""}</strong>
          <p class="subtle">Pulled ${requirement.pulled_quantity} | In Inventory ${part ? part.stock : 0}</p>
        </div>
        <div class="job-part-actions">
          <label class="field-small compact-field">Required Qty<input type="number" min="${Math.max(requirement.pulled_quantity, 1)}" value="${requirement.required_quantity}" data-job-part-qty="${requirement.id}"></label>
          <button type="button" class="tiny-action" data-delete-job-part="${requirement.id}" ${requirement.pulled_quantity > 0 ? "disabled" : ""}>Remove</button>
        </div>
      </div>
    `;
  }).join("") : emptyState();

  form.innerHTML = `
    <div class="job-edit-modal-layout">
      <div class="job-edit-modal-fields">
        <label>Job / Work Order<input name="jobNumber" type="text" value="${job.job_number}" required></label>
        <label>Customer Name<input name="customerName" type="text" value="${job.customer_name || ""}" required></label>
        <label>Address<input name="address" type="text" value="${job.address || ""}" required></label>
        <label>Job Title<input name="title" type="text" value="${job.title}" required></label>
        <label>Technician / Team<input name="technician" type="text" value="${job.technician}" required></label>
        <label>Scheduled Date<input name="scheduledFor" type="date" value="${job.scheduled_for || ""}" required></label>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Notes</h4></div>
        <textarea name="notes" class="job-notes-input" rows="4">${job.notes || ""}</textarea>
      </div>
      <div class="job-edit-parts-card">
        <div class="table-header compact-header"><h4>Parts Needed</h4><button type="button" class="tiny-action" data-open-job-part-modal="${job.id}">Add Part</button></div>
        <div class="job-parts-list">${requirementRows}</div>
      </div>
      <div class="form-actions job-edit-modal-actions">
        <button type="submit" class="primary">Save Job Changes</button>
      </div>
    </div>
  `;
  overlay.classList.remove("hidden");
}

function renderOrderList() {
  const summary = document.querySelector("#order-list-summary");
  const table = document.querySelector("#order-list-table");
  if (!summary || !table) return;

  const rows = state.orderListItems.map((item) => `
    <tr>
      <td><span class="part-number-link">${item.part_number}</span> - ${item.description}</td>
      <td>${item.vendor_name}</td>
      <td><input class="compact-field order-list-qty-input" type="number" min="1" value="${item.quantity_requested}" data-order-list-qty="${item.id}"></td>
      <td>${item.template_id || "Standard"}</td>
      <td><input class="compact-field order-list-notes-input" type="text" value="${item.notes || ""}" data-order-list-notes="${item.id}"></td>
      <td><div class="action-stack"><button class="tiny-action" data-order-list-save="${item.id}">Save</button><button class="tiny-action" data-order-list-delete="${item.id}">Remove</button></div></td>
    </tr>
  `).join("");
  table.innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;

  const groupedCount = new Set(state.orderListItems.map((item) => `${item.vendor_id}|${item.template_id}|${item.warehouse_id}`)).size;
  summary.classList.toggle("hidden", state.orderListItems.length === 0);
  summary.textContent = state.orderListItems.length ? `${state.orderListItems.length} staged item(s) will create ${groupedCount} grouped purchase order(s).` : "";
}

function renderPurchaseOrders() {
  renderOrderList();
  const root = document.querySelector("#po-list");
  if (!root) return;
  const activePurchaseOrders = state.purchaseOrders.filter((po) => po.status !== "Received");
  const vendorGroups = activePurchaseOrders.reduce((groups, po) => {
    const key = po.vendor_name || "Unassigned Vendor";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(po);
    return groups;
  }, new Map());

  root.innerHTML = activePurchaseOrders.length ? [...vendorGroups.entries()].map(([vendorName, orders]) => `
    <section class="vendor-po-group">
      <div class="table-header compact-header">
        <div><h4>${vendorName}</h4><p class="subtle">${orders.length} open order(s)</p></div>

      </div>
      ${orders.map((po) => {
        const statusClass = po.status === "Email Pending" ? "status-danger" : po.status === "Partial Received" ? "status-info" : "status-warn";
        const isVerified = verifiedReceipts.has(Number(po.id));
        const lineRows = (po.lines || []).map((line) => {
          const outstanding = Math.max(Number(line.quantity_ordered) - Number(line.quantity_received), 0);
          return `
            <tr>
              <td><span class="part-number-link">${line.part_number}</span><div class="subtle">${line.description}</div></td>
              <td>${line.quantity_ordered}</td>
              <td>${line.quantity_received}</td>
              <td>${outstanding}</td>
              <td><input class="compact-field po-line-receive-input" type="number" min="0" value="${outstanding}" data-po-line-receive="${po.id}:${line.id}"></td>
            </tr>
          `;
        }).join("");
        return `
          <article class="activity-card po-card-detail">
            <div class="job-card-header">
              <div>
                <strong class="po-number-link">${po.po_number}</strong>
                <p class="subtle">${po.vendor_name} | ${po.line_count} line item(s) | ETA ${po.eta ? formatDate(po.eta) : "TBD"}</p>
              </div>
              <span class="status-pill ${statusClass}">${po.status}</span>
            </div>
            <div class="po-card-meta">
              <p><strong>Outstanding:</strong> ${po.outstanding_quantity}</p>
              <p><strong>Notes:</strong> ${po.notes || "No notes"}</p>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Part</th><th>Ordered</th><th>Received</th><th>Outstanding</th><th>Check In Now</th></tr></thead>
                <tbody>${lineRows}</tbody>
              </table>
            </div>
            <div class="po-card-actions">
              <a class="tiny-action" href="/purchase-orders/${po.id}/form" target="_blank" rel="noreferrer">Open Form</a>
              ${po.status === "Email Pending" ? `<button class="tiny-action" data-po-status="${po.id}" data-status-value="Waiting for Part">Email Sent</button>` : ""}
              ${po.status === "Waiting for Part" || po.status === "Partial Received" ? `<label class="verification-check"><input type="checkbox" data-po-verified="${po.id}" ${isVerified ? "checked" : ""}>Visually counted and verified</label><button class="tiny-action" data-po-receive="${po.id}" ${isVerified ? "" : "disabled"}>Check In</button>` : ""}
            </div>
          </article>
        `;
      }).join("")}
    </section>
  `).join("") : emptyState();
}


function renderReceivingLog() {
  const logs = state.receivingLogs.slice(0, 8);
  document.querySelector("#receiving-log").innerHTML = logs.length ? logs.map((log) => `<div class="activity-card"><strong class="po-number-link">${log.po_number || "Manual receipt"}</strong><p><span class="part-number-link">${log.part_number || "Unknown Part"}</span></p><p class="subtle">${log.quantity} received by ${log.received_by}</p><p class="subtle">${log.notes || "No notes"} - ${formatDate(log.created_at)}</p></div>`).join("") : emptyState();
}

function renderUsageLog() {
  const logs = state.usageLogs.slice(0, 12);
  document.querySelector("#usage-log").innerHTML = logs.length ? logs.map((log) => `<div class="activity-card"><strong>${log.job_number}</strong><p class="subtle">${log.technician} used ${log.quantity} of <span class="part-number-link">${log.part_number}</span> - ${log.description}</p><p class="subtle">${log.notes || "No notes"} - ${formatDate(log.created_at)}</p></div>`).join("") : emptyState();
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
  const vendorSelects = [document.querySelector("#part-vendor")];
  vendorSelects.forEach((select) => fillSelect(select, state.vendors, (vendor) => vendor.name));

  const vendorTemplateSelect = document.querySelector("#vendor-template");
  if (vendorTemplateSelect) {
    vendorTemplateSelect.innerHTML = orderFormTemplateOptionsMarkup();
  }
}

function safeRender(label, renderFn) {
  try {
    renderFn();
  } catch (error) {
    console.error(`Render failed for ${label}`, error);
  }
}

function renderAll() {
  safeRender("warehouse selector", renderWarehouseSelector);
  safeRender("inventory attention badge", renderInventoryAttentionBadge);
  safeRender("purchase order attention badge", renderPoAttentionBadge);
  safeRender("jobs attention badge", renderJobsAttentionBadge);
  safeRender("inventory category init", initializeCollapsedCategories);
  safeRender("jobs init", initializeCollapsedJobs);
  safeRender("selects", renderSelects);
  safeRender("inventory filters", renderInventoryFilters);
  safeRender("dashboard", renderDashboard);
  safeRender("inventory table", renderInventoryTable);
  safeRender("vendor table", renderVendorTable);
  safeRender("order form table", renderOrderFormTemplateTable);
  safeRender("warehouse table", renderWarehouseTable);
  safeRender("purchase orders", renderPurchaseOrders);
  safeRender("receiving log", renderReceivingLog);
  safeRender("jobs list", renderJobsList);
  safeRender("completed jobs", renderCompletedJobsList);
  safeRender("job edit overlay", renderJobEditOverlay);
  safeRender("job part modal", renderJobPartModal);
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
  const form = document.querySelector("#part-form");
  if (form) {
    form.reset();
  }
  hideForm(formPanels.part);
}

function closeJobPartModal(resetFilters = false) {
  jobPartModalJobId = null;
  jobPartModalSelectedPartId = null;
  if (resetFilters) {
    jobPartModalSearch = "";
    jobPartModalFilters.status = "all";
    jobPartModalFilters.vendor = "all";
    jobPartModalFilters.category = "all";
    collapsedJobPartCategories.clear();
    knownJobPartCategories.clear();
  }
  const quantityInput = document.querySelector("#job-part-modal-quantity");
  if (quantityInput) {
    quantityInput.value = "1";
  }
  renderJobPartModal();
}

function filteredJobModalParts() {
  const search = jobPartModalSearch.trim().toLowerCase();
  return state.parts.filter((part) => {
    const status = inventoryStatus(part).label;
    const matchesSearch = [part.part_number, part.description, part.category, vendorName(part.vendor_id)].join(" ").toLowerCase().includes(search);
    const matchesStatus = jobPartModalFilters.status === "all" || status === jobPartModalFilters.status;
    const matchesVendor = jobPartModalFilters.vendor === "all" || String(part.vendor_id) === jobPartModalFilters.vendor;
    const matchesCategory = jobPartModalFilters.category === "all" || (part.category || "Uncategorized") === jobPartModalFilters.category;
    return matchesSearch && matchesStatus && matchesVendor && matchesCategory;
  });
}

function initializeCollapsedJobModalCategories(parts) {
  const categories = [...new Set(parts.map((part) => part.category || "Uncategorized"))];
  categories.forEach((category) => {
    if (!knownJobPartCategories.has(category)) {
      knownJobPartCategories.add(category);
      collapsedJobPartCategories.add(category);
    }
  });
  [...knownJobPartCategories].forEach((category) => {
    if (!categories.includes(category)) {
      knownJobPartCategories.delete(category);
      collapsedJobPartCategories.delete(category);
    }
  });
}

function renderJobPartModal() {
  const overlay = document.querySelector("#job-part-modal");
  const table = document.querySelector("#job-part-modal-table");
  const title = document.querySelector("#job-part-modal-title");
  const searchInput = document.querySelector("#job-part-modal-search");
  const statusSelect = document.querySelector("#job-part-modal-status-filter");
  const vendorSelect = document.querySelector("#job-part-modal-vendor-filter");
  const categorySelect = document.querySelector("#job-part-modal-category-filter");
  const selectedLabel = document.querySelector("#job-part-modal-selected");
  const confirmButton = document.querySelector("#job-part-modal-confirm");
  if (!overlay || !table || !title || !searchInput || !statusSelect || !vendorSelect || !categorySelect || !selectedLabel || !confirmButton) return;

  if (!jobPartModalJobId) {
    overlay.classList.add("hidden");
    searchInput.value = "";
    table.innerHTML = "";
    return;
  }

  const job = jobById(jobPartModalJobId);
  title.textContent = job ? `Add part to ${job.job_number}` : "Select a part";
  searchInput.value = jobPartModalSearch;

  const statuses = ["Healthy", "Low Stock", "Order In Process", "Order Processed", "Order Staged", "Out of Stock"];
  statusSelect.innerHTML = `<option value="all">All Statuses</option>${statuses.map((status) => `<option value="${status}">${status}</option>`).join("")}`;
  statusSelect.value = jobPartModalFilters.status;
  vendorSelect.innerHTML = `<option value="all">All Vendors</option>${state.vendors.map((vendor) => `<option value="${vendor.id}">${vendor.name}</option>`).join("")}`;
  vendorSelect.value = jobPartModalFilters.vendor;
  const categories = [...new Set(state.parts.map((part) => part.category || "Uncategorized"))].sort((left, right) => left.localeCompare(right));
  categorySelect.innerHTML = `<option value="all">All Categories</option>${categories.map((category) => `<option value="${category}">${category}</option>`).join("")}`;
  categorySelect.value = jobPartModalFilters.category;

  const filteredParts = filteredJobModalParts();
  initializeCollapsedJobModalCategories(filteredParts);
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) => left[0].localeCompare(right[0]));
  const rows = groups.map(([category, parts]) => {
    const isCollapsed = collapsedJobPartCategories.has(category);
    const header = `
      <tr class="category-row" data-job-modal-category-toggle="${category}">
        <td colspan="6">
          <div class="category-row-inner">
            <div class="category-title-wrap">
              <button type="button" class="category-toggle" data-job-modal-category-toggle="${category}">${isCollapsed ? ">" : "v"}</button>
              <strong>${category}</strong>
              <span class="subtle">${parts.length} parts</span>
            </div>
          </div>
        </td>
      </tr>
    `;
    if (isCollapsed) return header;
    const partRows = parts.map((part) => {
      const status = inventoryStatus(part);
      const isSelected = Number(jobPartModalSelectedPartId) === Number(part.id);
      return `
        <tr class="${isSelected ? "selected-modal-row" : ""}">
          <td class="part-meta"><strong class="part-number-link">${part.part_number}</strong><span class="subtle">${part.description}</span></td>
          <td><img class="part-thumb" src="${makePartThumbnail(part)}" alt="${part.part_number} thumbnail"></td>
          <td>${part.stock}</td>
          <td>${vendorName(part.vendor_id)}</td>
          <td><span class="status-pill ${status.className}">${status.label}</span></td>
          <td><button type="button" class="tiny-action" data-select-job-modal-part="${part.id}">${isSelected ? "Selected" : "Select"}</button></td>
        </tr>
      `;
    }).join("");
    return `${header}${partRows}`;
  }).join("");
  table.innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;

  const selectedPart = partById(jobPartModalSelectedPartId);
  selectedLabel.textContent = selectedPart ? `Selected: ${selectedPart.part_number} - ${selectedPart.description}` : "Choose a part from the list below.";
  confirmButton.disabled = !selectedPart;
  overlay.classList.remove("hidden");
}

function clearReorderForm() {
  return;
}


function clearVendorForm() {
  document.querySelector("#vendor-form").reset();
  const templateSelect = document.querySelector("#vendor-template");
  if (templateSelect) templateSelect.value = "";
  hideForm(formPanels.vendor);
}

function clearOrderFormTemplateForm() {
  document.querySelector("#order-form-template-form").reset();
  document.querySelector("#order-form-template-variant").value = "aquaflow";
  hideForm(formPanels.orderForm);
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
      if (editingJobId && button.dataset.view !== "jobs") {
        window.alert("Save the current job before leaving the edit view.");
        return;
      }
      const currentView = document.querySelector(".nav-link.active")?.dataset.view;
      if (currentView && currentView !== button.dataset.view) {
        resetExpandableUiState();
        renderAll();
      }
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
      leadTimeDays: Number(document.querySelector("#vendor-lead-time").value),
      linkedTemplateId: document.querySelector("#vendor-template").value
    }).then(clearVendorForm).catch((error) => window.alert(error.message));
  });

  document.querySelector("#order-form-template-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/order-form-templates", {
      warehouseId: currentWarehouseId(),
      templateId: document.querySelector("#order-form-template-id").value.trim(),
      name: document.querySelector("#order-form-template-name").value.trim(),
      formVariant: document.querySelector("#order-form-template-variant").value,
      notes: document.querySelector("#order-form-template-notes").value.trim()
    }).then(clearOrderFormTemplateForm).catch((error) => window.alert(error.message));
  });

  document.querySelector("#warehouse-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJson("/api/warehouses", {
      name: document.querySelector("#warehouse-name").value.trim(),
      code: document.querySelector("#warehouse-code").value.trim()
    }).then(clearWarehouseForm).catch((error) => window.alert(error.message));
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
      customerName: document.querySelector("#job-customer").value.trim(),
      address: document.querySelector("#job-address").value.trim(),
      title: document.querySelector("#job-title").value.trim(),
      technician: document.querySelector("#job-tech").value.trim(),
      scheduledFor: document.querySelector("#job-scheduled-for").value,
      notes: document.querySelector("#job-notes").value.trim(),
      requirements
    }).then(() => {
      resetJobForm();
    }).catch((error) => window.alert(error.message));
  });
}

function bindActions() {
  document.querySelector("#inventory-search").addEventListener("input", renderInventoryTable);
  ["#inventory-status-filter", "#inventory-vendor-filter", "#inventory-category-filter"].forEach((selector) => {
    document.querySelector(selector).addEventListener("change", (event) => {
      if (selector === "#inventory-status-filter") inventoryFilters.status = event.target.value;
      if (selector === "#inventory-vendor-filter") inventoryFilters.vendor = event.target.value;
      if (selector === "#inventory-category-filter") inventoryFilters.category = event.target.value;
      renderInventoryTable();
    });
  });
  document.querySelector("#part-form-clear").addEventListener("click", clearPartForm);
  document.querySelector("#vendor-form-clear").addEventListener("click", clearVendorForm);
  document.querySelector("#order-form-template-clear").addEventListener("click", clearOrderFormTemplateForm);
  document.querySelector("#warehouse-form-clear").addEventListener("click", clearWarehouseForm);
  document.querySelector("#job-add-part-row").addEventListener("click", () => addJobRequirementRow());
  document.querySelector("#order-list-clear")?.addEventListener("click", async () => {
    await postAction("/api/order-list/clear", { warehouseId: currentWarehouseId() }, "Clear the entire order list?").catch((error) => window.alert(error.message));
  });
  document.querySelector("#order-list-generate")?.addEventListener("click", async () => {
    const response = await fetch("/api/order-list/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ warehouseId: currentWarehouseId() })
    });
    const data = await response.json();
    if (!response.ok) {
      window.alert(data.error || "Request failed.");
      return;
    }
    state = data.state;
    pruneVerifiedReceipts();
    pruneInlineEditors();
    renderAll();
    const created = data.createdPurchaseOrders || [];
    if (created.length) {
      const summary = created.map((po) => `${po.poNumber} (${po.vendorName})`).join(", ");
      window.alert(`Created ${created.length} grouped purchase order(s): ${summary}`);
    }
  });
  document.querySelector("#job-part-modal-close").addEventListener("click", () => closeJobPartModal(true));
  document.querySelector("#job-part-modal-search").addEventListener("input", (event) => {
    jobPartModalSearch = event.target.value;
    renderJobPartModal();
  });
  document.querySelector("#job-part-modal-status-filter").addEventListener("change", (event) => {
    jobPartModalFilters.status = event.target.value;
    renderJobPartModal();
  });
  document.querySelector("#job-part-modal-vendor-filter").addEventListener("change", (event) => {
    jobPartModalFilters.vendor = event.target.value;
    renderJobPartModal();
  });
  document.querySelector("#job-part-modal-category-filter").addEventListener("change", (event) => {
    jobPartModalFilters.category = event.target.value;
    renderJobPartModal();
  });
  document.querySelector("#job-part-modal-confirm").addEventListener("click", async () => {
    const quantity = Number(document.querySelector("#job-part-modal-quantity")?.value || 0);
    if (!jobPartModalSelectedPartId) {
      window.alert("Select a part first.");
      return;
    }
    if (!Number.isInteger(quantity) || quantity <= 0) {
      window.alert("Enter a whole number greater than 0.");
      return;
    }
    const jobId = Number(jobPartModalJobId);
    await postJson(`/api/jobs/${jobId}/parts`, {
      warehouseId: currentWarehouseId(),
      partId: Number(jobPartModalSelectedPartId),
      requiredQuantity: quantity
    }).then(() => {
      jobEditDirty = true;
      closeJobPartModal();
      renderJobEditOverlay();
      flashToast("Part added to job.");
    }).catch((error) => window.alert(error.message));
  });
  document.querySelector("#job-edit-modal-form").addEventListener("input", () => {
    if (editingJobId) jobEditDirty = true;
  });
  document.querySelectorAll(".form-toggle").forEach((button) => {
    updateToggleButton(button.dataset.formTarget);
    button.addEventListener("click", () => toggleForm(button.dataset.formTarget));
  });

  document.querySelector("#warehouse-selector").addEventListener("change", async (event) => {
    if (editingJobId) {
      window.alert("Save the current job before switching warehouses.");
      event.target.value = String(currentWarehouseId());
      return;
    }
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

    const jobModalCategoryToggle = event.target.closest("[data-job-modal-category-toggle]");
    if (jobModalCategoryToggle) {
      const category = jobModalCategoryToggle.dataset.jobModalCategoryToggle;
      if (collapsedJobPartCategories.has(category)) {
        collapsedJobPartCategories.delete(category);
      } else {
        collapsedJobPartCategories.add(category);
      }
      renderJobPartModal();
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

    const weeklyUsageToggle = event.target.closest("[data-toggle-weekly-usage]");
    if (weeklyUsageToggle) {
      dashboardUsageExpanded = !dashboardUsageExpanded;
      renderDashboard();
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

    const orderListSaveButton = event.target.closest("[data-order-list-save]");
    if (orderListSaveButton) {
      const itemId = Number(orderListSaveButton.dataset.orderListSave);
      const quantity = Number(document.querySelector(`[data-order-list-qty="${itemId}"]`)?.value || 0);
      const notes = document.querySelector(`[data-order-list-notes="${itemId}"]`)?.value || "";
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert("Enter a whole number greater than 0.");
        return;
      }
      await postJson(`/api/order-list/${itemId}`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes
      }).catch((error) => window.alert(error.message));
      return;
    }

    const orderListDeleteButton = event.target.closest("[data-order-list-delete]");
    if (orderListDeleteButton) {
      await postAction(
        `/api/order-list/${orderListDeleteButton.dataset.orderListDelete}/delete`,
        { warehouseId: currentWarehouseId() },
        "Remove this item from the order list?"
      ).catch((error) => window.alert(error.message));
      return;
    }

    const openJobPartModalButton = event.target.closest("[data-open-job-part-modal]");
    if (openJobPartModalButton) {
      const jobId = Number(openJobPartModalButton.dataset.openJobPartModal);
      jobPartModalJobId = jobId;
      jobPartModalSelectedPartId = null;
      jobPartModalSearch = "";
      jobPartModalFilters.status = "all";
      jobPartModalFilters.vendor = "all";
      jobPartModalFilters.category = "all";
      collapsedJobPartCategories.clear();
      collapsedJobs.delete(jobId);
      renderJobPartModal();
      return;
    }

    const completeJobButton = event.target.closest("[data-complete-job]");
    if (completeJobButton) {
      await postAction(
        `/api/jobs/${completeJobButton.dataset.completeJob}/complete`,
        { warehouseId: currentWarehouseId() },
        "Mark this job as completed?"
      ).catch((error) => window.alert(error.message));
      return;
    }

    const selectJobModalPartButton = event.target.closest("[data-select-job-modal-part]");
    if (selectJobModalPartButton) {
      jobPartModalSelectedPartId = Number(selectJobModalPartButton.dataset.selectJobModalPart);
      renderJobPartModal();
      return;
    }

    const editJobButton = event.target.closest("[data-edit-job]");
    if (editJobButton) {
      const jobId = Number(editJobButton.dataset.editJob);
      editingJobId = jobId;
      jobEditDirty = false;
      collapsedJobs.delete(jobId);
      document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      document.querySelector('[data-view="jobs"]')?.classList.add("active");
      document.querySelector("#jobs-view")?.classList.add("active");
      renderAll();
      return;
    }


    const saveJobNotesButton = event.target.closest("[data-save-job-notes]");
    if (saveJobNotesButton) {
      const jobId = Number(saveJobNotesButton.dataset.saveJobNotes);
      const notes = document.querySelector(`[data-job-notes-input="${jobId}"]`)?.value || "";
      collapsedJobs.delete(jobId);
      await postJson(`/api/jobs/${jobId}/notes`, {
        warehouseId: currentWarehouseId(),
        notes
      }).then(() => {
        collapsedJobs.delete(jobId);
        renderJobsList();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const deleteJobPartButton = event.target.closest("[data-delete-job-part]");
    if (deleteJobPartButton) {
      const requirementId = Number(deleteJobPartButton.dataset.deleteJobPart);
      const requirement = state.jobRequirements.find((item) => Number(item.id) === requirementId);
      if (!window.confirm("Remove this part from the job?")) {
        return;
      }
      if (requirement) {
        collapsedJobs.delete(Number(requirement.job_id));
      }
      await postJson(`/api/job-parts/${requirementId}/delete`, {
        warehouseId: currentWarehouseId()
      }).then(() => {
        if (requirement) collapsedJobs.delete(Number(requirement.job_id));
        renderJobsList();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const returnJobPartButton = event.target.closest("[data-return-job-part]");
    if (returnJobPartButton) {
      const requirement = state.jobRequirements.find((item) => Number(item.id) === Number(returnJobPartButton.dataset.returnJobPart));
      if (!requirement) return;
      const part = partById(requirement.part_id);
      const requested = window.prompt(`How many of ${part ? part.part_number : "this part"} do you want to return to inventory?`, String(requirement.pulled_quantity));
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert("Enter a whole number greater than 0.");
        return;
      }
      collapsedJobs.delete(Number(requirement.job_id));
      await postJson(`/api/job-parts/${requirement.id}/return`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: "Returned from job card"
      }).then(() => {
        collapsedJobs.delete(Number(requirement.job_id));
        renderJobsList();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const poReceiveButton = event.target.closest("[data-po-receive]");
    if (poReceiveButton) {
      const poId = Number(poReceiveButton.dataset.poReceive);
      if (!verifiedReceipts.has(poId)) {
        window.alert("Check the counted and verified box before marking this order received.");
        return;
      }
      const lineInputs = [...document.querySelectorAll(`[data-po-line-receive^="${poId}:"]`)];
      const lineReceipts = Object.fromEntries(lineInputs.map((input) => [input.dataset.poLineReceive.split(":")[1], Number(input.value || 0)]));
      const requestedTotal = Object.values(lineReceipts).reduce((sum, value) => sum + Number(value || 0), 0);
      if (requestedTotal <= 0) {
        window.alert("Enter the quantities that arrived before checking this order in.");
        return;
      }
      if (!window.confirm(`Check in ${requestedTotal} item(s) across this purchase order?`)) {
        return;
      }
      await postJson(`/api/purchase-orders/${poId}/receive`, {
        warehouseId: currentWarehouseId(),
        lineReceipts,
        receivedBy: "Inventory",
        notes: "Checked in from PO tab",
        verifiedCount: true
      }).then(() => {
        verifiedReceipts.delete(poId);
        renderPurchaseOrders();
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
      collapsedJobs.delete(Number(requirement.job_id));
      await postJson(`/api/job-parts/${requirement.id}/pull`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: "Pulled from job card"
      }).then(() => {
        collapsedJobs.delete(Number(requirement.job_id));
        renderJobsList();
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

    const addToOrderListButton = event.target.closest("[data-add-to-order-list]");
    if (addToOrderListButton) {
      const part = partById(addToOrderListButton.dataset.addToOrderList);
      if (!part) return;
      const suggested = Math.max(part.reorder_point * 2 - part.stock, 1);
      const requested = window.prompt(`How many of ${part.part_number} do you want to stage for ordering?`, String(suggested));
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert("Enter a whole number greater than 0.");
        return;
      }
      postJson("/api/order-list", {
        warehouseId: currentWarehouseId(),
        partId: part.id,
        quantity,
        notes: `Low stock reorder for ${part.part_number}`
      }).catch((error) => window.alert(error.message));
      return;
    }

    const vendorButton = event.target.closest("[data-edit-vendor]");
    if (vendorButton) {
      inlineEditors.vendorId = Number(inlineEditors.vendorId) === Number(vendorButton.dataset.editVendor) ? null : Number(vendorButton.dataset.editVendor);
      renderVendorTable();
      return;
    }

    const orderFormTemplateButton = event.target.closest("[data-edit-order-form-template]");
    if (orderFormTemplateButton) {
      inlineEditors.orderFormTemplateId = Number(inlineEditors.orderFormTemplateId) === Number(orderFormTemplateButton.dataset.editOrderFormTemplate) ? null : Number(orderFormTemplateButton.dataset.editOrderFormTemplate);
      renderOrderFormTemplateTable();
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
      } else if (kind === "order-form-template") {
        inlineEditors.orderFormTemplateId = null;
        renderOrderFormTemplateTable();
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
    const jobEditForm = event.target.closest("#job-edit-modal-form");
    if (jobEditForm) {
      event.preventDefault();
      const formData = new FormData(jobEditForm);
      const jobId = Number(editingJobId);
      const requirementInputs = [...jobEditForm.querySelectorAll("[data-job-part-qty]")];
      const requirementQuantities = requirementInputs.map((input) => ({
        requirementId: Number(input.dataset.jobPartQty),
        requiredQuantity: Number(input.value || 0)
      }));
      const invalidRequirement = requirementQuantities.find((item) => !Number.isInteger(item.requiredQuantity) || item.requiredQuantity <= 0);
      if (invalidRequirement) {
        window.alert("Enter a whole number greater than 0 for every required quantity.");
        return;
      }
      const submitButton = jobEditForm.querySelector('button[type="submit"]');
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Saving...";
      }
      await postJson(`/api/jobs/${jobId}`, {
        warehouseId: currentWarehouseId(),
        jobNumber: String(formData.get("jobNumber")).trim(),
        customerName: String(formData.get("customerName")).trim(),
        address: String(formData.get("address")).trim(),
        title: String(formData.get("title")).trim(),
        technician: String(formData.get("technician")).trim(),
        scheduledFor: String(formData.get("scheduledFor")).trim(),
        notes: String(formData.get("notes")).trim(),
        requirementQuantities
      }).then(() => {
        jobEditDirty = false;
        collapsedJobs.delete(jobId);
        editingJobId = null;
        renderAll();
        flashToast("Job changes saved.");
      }).catch((error) => window.alert(error.message)).finally(() => {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = "Save Job Changes";
        }
      });
      return;
    }

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
        leadTimeDays: Number(formData.get("leadTimeDays")),
        linkedTemplateId: String(formData.get("linkedTemplateId") || "").trim()
      }).then(() => {
        inlineEditors.vendorId = null;
        renderVendorTable();
      }).catch((error) => window.alert(error.message));
      return;
    }

    const orderFormTemplateForm = event.target.closest("[data-inline-order-form-template-form]");
    if (orderFormTemplateForm) {
      event.preventDefault();
      const formData = new FormData(orderFormTemplateForm);
      await postJson("/api/order-form-templates", {
        id: Number(formData.get("id")),
        warehouseId: currentWarehouseId(),
        templateId: String(formData.get("templateId")).trim(),
        name: String(formData.get("name")).trim(),
        formVariant: String(formData.get("formVariant")).trim(),
        notes: String(formData.get("notes") || "").trim()
      }).then(() => {
        inlineEditors.orderFormTemplateId = null;
        renderOrderFormTemplateTable();
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

    const deleteOrderFormTemplateButton = event.target.closest("[data-inline-delete-order-form-template]");
    if (deleteOrderFormTemplateButton) {
      await postAction(
        `/api/order-form-templates/${deleteOrderFormTemplateButton.dataset.inlineDeleteOrderFormTemplate}/delete`,
        { warehouseId: currentWarehouseId() },
        "Delete this order form template? This only works if nothing is using it."
      ).then(() => {
        inlineEditors.orderFormTemplateId = null;
        renderOrderFormTemplateTable();
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
    if (editingJobId) {
      window.alert("Save the current job before resetting demo data.");
      return;
    }
    await postJson("/api/reset", { warehouseId: currentWarehouseId() }).then(() => {
      clearPartForm();
      clearVendorForm();
      clearWarehouseForm();
    }).catch((error) => window.alert(error.message));
  });

  document.querySelector("#export-data").addEventListener("click", () => {
    if (editingJobId) {
      window.alert("Save the current job before leaving the edit view.");
      return;
    }
    window.location.href = `/api/export?warehouseId=${currentWarehouseId()}`;
  });
}

window.addEventListener("beforeunload", (event) => {
  if (!editingJobId) return;
  event.preventDefault();
  event.returnValue = "";
});

bindNavigation();
bindForms();
bindActions();
loadApp();
