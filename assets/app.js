function createDefaultState() {
  return {
    currentUser: null,
    currentUserPermissions: {},
    users: [],
    rolePermissions: [],
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
    usageLogs: [],
    jobAttachments: [],
    jobNotes: [],
    jobTypeOptions: ['Install', 'Service', 'Warranty', 'Detail'],
    serviceFieldOptions: {
      status: [
        'New',
        'Scheduled',
        'In Progress',
        'Waiting on Parts',
        'Return Trip Needed',
        'Completed',
        'Closed',
        'Cancelled',
      ],
      serviceCode: ['Service', 'Warranty', 'Callback', 'Evaluation', 'Parts Follow-Up', 'Other'],
      probableIssueCategory: [
        'Valve / Cartridge',
        'Diverter',
        'Handle Hard To Turn',
        'Caulking',
        'Plumbing Leak',
        'Drain Issue',
        'Cosmetic',
        'Measurement / Final Check',
        'Missing / Wrong Parts',
        'Product Defect',
        'Customer Concern',
        'Other',
      ],
      serviceCategory: [
        'Valve / Cartridge',
        'Diverter',
        'Handle Hard To Turn',
        'Caulking',
        'Plumbing Leak',
        'Drain Issue',
        'Cosmetic',
        'Measurement / Final Check',
        'Missing / Wrong Parts',
        'Product Defect',
        'Customer Concern',
        'Other',
      ],
      urgency: ['Low', 'Normal', 'High', 'Urgent'],
      paymentMethod: ['No Payment Due', 'Cash', 'Credit Card', 'Check'],
      serviceFaultCategory: ['Customer', 'Installer', 'Product', 'Evaluation', 'Additional Items'],
      yesNo: ['Unknown', 'Yes', 'No'],
      detailDiscrepancyCategory: [
        'Measurement mismatch',
        'Product mismatch',
        'Accessory mismatch',
        'Plumbing / valve mismatch',
        'Color / finish mismatch',
        'Site condition issue',
        'Customer expectation mismatch',
        'Missing paperwork info',
        'Other',
      ],
    },
    featureFlags: {
      inventory: true,
      jobs: true,
      purchase_orders: true,
      receiving: true,
      insights: true,
      users: true,
    },
    emailSettings: { sendAvailable: false, fromEmail: '' },
  };
}

let state = createDefaultState();
const verifiedReceiptLines = new Set();
const poLineReceiveDrafts = new Map();
const DEFAULT_ARCHIVE_AFTER_DAYS = 30;
const ARCHIVE_CUTOFF_STORAGE_KEY = 'shopflowArchiveAfterDays';
const inlineEditors = {
  partId: null,
  vendorId: null,
  orderFormTemplateId: null,
  warehouseId: null,
};
const collapsedCategories = new Set();
const knownInventoryCategories = new Set();
const collapsedJobs = new Set();
const knownJobIds = new Set();
let jobRequirementRowSeed = 0;
let dashboardUsageExpanded = false;
let editingJobId = null;
let jobEditDirty = false;
let jobFormPartPickerMode = false;
let jobPartModalJobId = null;
let jobPartModalSearch = '';
let jobPartModalSelectedPartId = null;
let inventoryScanModalOpen = false;
let inventoryScanValue = '';
let inventoryScanMatchedPart = null;
let inventoryScanCameraEnabled = false;
let inventoryScanScannerStream = null;
let inventoryScanScannerTimer = null;
let inventoryScanInFlight = false;
let jobPullModalJobId = null;
let jobPullScanValue = '';
let jobPullMatchedPart = null;
let jobPullCameraEnabled = false;
let jobPullScannerStream = null;
let jobPullScannerTimer = null;
let jobPullScanInFlight = false;
const jobPullRecentScans = new Map();
let jobScanAddModalJobId = null;
let jobScanAddValue = '';
let jobScanAddMatchedPart = null;
let jobScanAddCameraEnabled = false;
let jobScanAddScannerStream = null;
let jobScanAddScannerTimer = null;
let jobScanAddInFlight = false;
let jobCompletionModalJobId = null;
let jobCompletionPreview = null;
let jobDraftRequirements = [];
let activeJobsWorkflow = 'install';
const archiveFilters = {
  installSearch: '',
  installSort: 'newest',
  detailSearch: '',
  detailSort: 'newest',
  serviceSearch: '',
  serviceSort: 'newest',
  poSearch: '',
  poSort: 'newest',
};
const summaryPanelState = {
  title: '',
  items: [],
};
const jobPartModalFilters = {
  status: 'all',
  partType: 'all',
  vendor: 'all',
  category: 'all',
};
const collapsedJobPartCategories = new Set();
const knownJobPartCategories = new Set();
const inventoryFilters = {
  status: 'all',
  partType: 'all',
  vendor: 'all',
  category: 'all',
};

const insightsFilters = {
  dateRange: '90',
  jobType: 'all',
  vendor: 'all',
  partCategory: 'all',
  partType: 'all',
  warehouseId: 'all',
  crew: 'all',
};
let insightsDrilldown = {
  type: 'overview',
  key: 'overview',
};
const aiInsightsCache = new Map();
const aiInsightsState = {
  loading: false,
  error: '',
  brief: null,
  answer: null,
  question: '',
  contextKey: '',
};

const partPhotoLibrary = {
  'Drain Assemblies': 'https://loremflickr.com/80/80/drain,plumbing?lock=1',
  Valves: 'https://loremflickr.com/80/80/valve,plumbing?lock=2',
  Sealants: 'https://loremflickr.com/80/80/caulk,sealant?lock=3',
  'Supply Lines': 'https://loremflickr.com/80/80/plumbing,hose?lock=4',
  'Trim Kits': 'https://loremflickr.com/80/80/shower,bathroom?lock=5',
  Faucets: 'https://loremflickr.com/80/80/faucet,bathroom?lock=6',
  'Install Kits': 'https://loremflickr.com/80/80/tools,install?lock=7',
  'Shower Hardware': 'https://loremflickr.com/80/80/showerhead,bathroom?lock=8',
  'Toilet Parts': 'https://loremflickr.com/80/80/toilet,plumbing?lock=9',
  'P-Traps': 'https://loremflickr.com/80/80/pipe,plumbing?lock=10',
};

const formPanels = {
  part: 'part-form-panel',
  po: 'po-form-panel',
  job: 'job-form-panel',
  warehouse: 'warehouse-form-panel',
  vendor: 'vendor-form-panel',
  orderForm: 'order-form-panel',
};

function currentWarehouseId() {
  return Number(state.selectedWarehouseId);
}

function currentUser() {
  return state.currentUser || null;
}

function hasPermission(permission) {
  return Boolean(state.currentUserPermissions?.[permission]);
}

function isManager() {
  return ['manager', 'admin'].includes(currentUser()?.role || '');
}

function isWorker() {
  return ['installer', 'service_tech'].includes(currentUser()?.role || '');
}

function hasGlobalJobScope() {
  return ['admin', 'manager', 'warehouse_manager', 'viewer'].includes(currentUser()?.role || '');
}

function roleLabel(role) {
  if (role === 'admin') return 'Admin';
  if (role === 'manager') return 'Manager';
  if (role === 'warehouse_manager') return 'Warehouse Manager';
  if (role === 'installer') return 'Installer';
  if (role === 'service_tech') return 'Service Tech';
  if (role === 'viewer') return 'Viewer';
  return role || 'User';
}

function warehouseById(id) {
  return state.warehouses.find((warehouse) => Number(warehouse.id) === Number(id));
}

function vendorName(vendorId) {
  return state.vendors.find((vendor) => Number(vendor.id) === Number(vendorId))?.name || 'Unassigned';
}

function assignableUsers() {
  return (state.users || []).filter((user) => ['installer', 'service_tech'].includes(user.role) && user.is_active);
}

function userById(userId) {
  return (state.users || []).find((user) => Number(user.id) === Number(userId));
}

function orderFormTemplateByRowId(templateRowId) {
  return state.orderFormTemplates.find((template) => Number(template.id) === Number(templateRowId));
}

function orderFormTemplateName(templateId) {
  return (
    state.orderFormTemplates.find((template) => String(template.template_id) === String(templateId))?.name ||
    'Not linked'
  );
}

function orderFormTemplateOptionsMarkup(selectedTemplateId = '') {
  const blank = `<option value="">No linked form</option>`;
  return (
    blank +
    state.orderFormTemplates
      .map(
        (template) =>
          `<option value="${template.template_id}" ${String(template.template_id) === String(selectedTemplateId) ? 'selected' : ''}>${template.name}</option>`,
      )
      .join('')
  );
}

function partById(partId) {
  return state.parts.find((part) => Number(part.id) === Number(partId));
}

function isNonStock(part) {
  return String(part?.item_type || 'stocked') === 'non_stock';
}

function partTypeLabel(part) {
  return isNonStock(part) ? 'Non-Stock' : 'Stocked';
}

function partTypeTag(part) {
  return isNonStock(part) ? '<span class="part-type-tag">Non-Stock</span>' : '';
}

function canonicalJobType(job) {
  const raw = String(job?.job_type || '').trim();
  if (['Install', 'Service', 'Warranty', 'Detail'].includes(raw)) return raw;
  const haystack = `${raw} ${String(job?.title || '').trim()}`.toLowerCase();
  if (['detail', 'measure', 'measurement', 'verify', 'verification'].some((keyword) => haystack.includes(keyword))) {
    return 'Detail';
  }
  if (haystack.includes('warranty')) return 'Warranty';
  if (['service', 'repair', 'follow-up', 'follow up', 'callback'].some((keyword) => haystack.includes(keyword))) {
    return 'Service';
  }
  return 'Install';
}

function isInstallRole() {
  return currentUser()?.role === 'installer';
}

function isServiceRole() {
  return currentUser()?.role === 'service_tech';
}

function isServiceJob(job) {
  return ['Service', 'Warranty'].includes(canonicalJobType(job));
}

function isDetailJob(job) {
  return canonicalJobType(job) === 'Detail';
}

function serviceFieldOptions(key) {
  return state.serviceFieldOptions?.[key] || [];
}

function selectOptionsMarkup(options, selectedValue, fallbackLabel = 'Select') {
  return [
    `<option value="">${fallbackLabel}</option>`,
    ...options.map(
      (option) =>
        `<option value="${htmlEscape(option)}" ${String(selectedValue || '') === String(option) ? 'selected' : ''}>${htmlEscape(option)}</option>`,
    ),
  ].join('');
}

function serviceFieldValue(job, key, fallback = '') {
  return String(job?.[key] || fallback || '');
}

function serviceDisplayValue(job, key, fallback = 'Not set') {
  const value = serviceFieldValue(job, key);
  return value || fallback;
}

function serviceHistoryForJob(job) {
  const contract = serviceFieldValue(job, 'contract_number').toLowerCase();
  const customer = serviceFieldValue(job, 'customer_name_primary', job.customer_name).toLowerCase();
  const address = serviceFieldValue(job, 'address_line_1', job.address).toLowerCase();
  return [...(state.completedJobs || []), ...(state.jobs || [])]
    .filter((entry) => Number(entry.id) !== Number(job.id) && isServiceJob(entry))
    .filter((entry) => {
      const entryContract = serviceFieldValue(entry, 'contract_number').toLowerCase();
      const entryCustomer = serviceFieldValue(entry, 'customer_name_primary', entry.customer_name).toLowerCase();
      const entryAddress = serviceFieldValue(entry, 'address_line_1', entry.address).toLowerCase();
      return (
        (contract && entryContract === contract) ||
        (customer && address && entryCustomer === customer && entryAddress === address) ||
        (!contract && address && entryAddress === address)
      );
    })
    .sort(
      (left, right) =>
        new Date(right.completed_at || right.created_at) - new Date(left.completed_at || left.created_at),
    );
}

function jobById(jobId) {
  return state.jobs.find((job) => Number(job.id) === Number(jobId));
}

function jobRequirementsFor(jobId) {
  return state.jobRequirements.filter((requirement) => Number(requirement.job_id) === Number(jobId));
}

function jobAttachmentsFor(jobId) {
  return (state.jobAttachments || [])
    .filter((attachment) => Number(attachment.job_id) === Number(jobId))
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
}

function jobNotesFor(jobId) {
  return (state.jobNotes || [])
    .filter((note) => Number(note.job_id) === Number(jobId))
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
}

function setActiveView(viewName) {
  document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
  document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
  document.querySelector(`.nav-link[data-view="${viewName}"]`)?.classList.add('active');
  document.querySelector(`#${viewName}-view`)?.classList.add('active');
}

function scrollToElement(selector) {
  const element = document.querySelector(selector);
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function openJobDestination(jobId, preferArchive = false) {
  collapsedJobs.delete(Number(jobId));
  renderAll();
  if (preferArchive || (state.completedJobs || []).some((job) => Number(job.id) === Number(jobId))) {
    setActiveView('archive');
    window.setTimeout(() => scrollToElement(`[data-archive-job-id="${jobId}"]`), 30);
    return;
  }
  setActiveView('jobs');
  window.setTimeout(() => scrollToElement(`[data-job-card-id="${jobId}"]`), 30);
}

function openPartDestination(partId) {
  setActiveView('inventory');
  const part = partById(partId);
  const search = document.querySelector('#inventory-search');
  if (search && part) {
    search.value = part.part_number;
  }
  if (part?.category) {
    collapsedCategories.delete(part.category);
  }
  renderInventoryTable();
  window.setTimeout(() => scrollToElement(`[data-part-row-id="${partId}"]`), 30);
}

function openPurchaseOrderDestination(poId, preferArchive = false) {
  const po = (state.purchaseOrders || []).find((entry) => Number(entry.id) === Number(poId));
  if (preferArchive || po?.status === 'Received') {
    setActiveView('archive');
    window.setTimeout(() => scrollToElement(`[data-archive-po-id="${poId}"]`), 30);
    return;
  }
  setActiveView('purchase-orders');
  window.setTimeout(() => scrollToElement(`[data-po-card-id="${poId}"]`), 30);
}

function openInsightDestination(type, key) {
  setActiveView('insights');
  insightsDrilldown = { type, key: String(key) };
  renderInsights();
  window.setTimeout(() => scrollToElement('.insight-detail-panel'), 30);
}

function closeSummaryPanel() {
  summaryPanelState.title = '';
  summaryPanelState.items = [];
  const overlay = document.querySelector('#summary-panel-modal');
  if (overlay) overlay.classList.add('hidden');
}

function openSummaryPanel(title, items) {
  summaryPanelState.title = title;
  summaryPanelState.items = items;
  renderSummaryPanel();
  document.querySelector('#summary-panel-modal')?.classList.remove('hidden');
}

function canManageJobs() {
  return hasPermission('job_access') && hasPermission('edit_records');
}

function canReceiveJobs() {
  return hasPermission('receive_jobs');
}

function canCompleteJobs() {
  return hasPermission('complete_jobs');
}

function findOrderListEntryForPart(partId) {
  return state.orderListItems.find((item) => Number(item.part_id) === Number(partId));
}

function partHasOpenPurchaseOrder(partId) {
  return state.purchaseOrders.some(
    (po) => po.status !== 'Received' && (po.lines || []).some((line) => Number(line.part_id) === Number(partId)),
  );
}

function latestOpenPurchaseOrderForPart(partId) {
  return state.purchaseOrders
    .filter(
      (po) => po.status !== 'Received' && (po.lines || []).some((line) => Number(line.part_id) === Number(partId)),
    )
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at))[0];
}

function money(value) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value || 0);
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function flashToast(message, tone = 'success') {
  let toast = document.querySelector('#app-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'app-toast';
    toast.className = 'app-toast hidden';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = `app-toast ${tone}`;
  window.clearTimeout(flashToast.timeoutId);
  flashToast.timeoutId = window.setTimeout(() => {
    toast.classList.add('hidden');
  }, 2200);
}

async function logClientError(message, error = null, context = {}, source = 'ui') {
  const payload = {
    message,
    source,
    context,
    stack: error?.stack || '',
  };
  console.error(message, error, context);
  try {
    await fetch('/api/client-errors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (_reportError) {
    // Keep client-side logging best-effort so broken logging never breaks the UI.
  }
}

function normalizeState(data) {
  const defaults = createDefaultState();
  return {
    ...defaults,
    ...(data || {}),
    currentUserPermissions: data?.currentUserPermissions || defaults.currentUserPermissions,
    users: Array.isArray(data?.users) ? data.users : defaults.users,
    rolePermissions: Array.isArray(data?.rolePermissions) ? data.rolePermissions : defaults.rolePermissions,
    warehouses: Array.isArray(data?.warehouses) ? data.warehouses : defaults.warehouses,
    activeWarehouses: Array.isArray(data?.activeWarehouses) ? data.activeWarehouses : defaults.activeWarehouses,
    vendors: Array.isArray(data?.vendors) ? data.vendors : defaults.vendors,
    orderFormTemplates: Array.isArray(data?.orderFormTemplates) ? data.orderFormTemplates : defaults.orderFormTemplates,
    parts: Array.isArray(data?.parts) ? data.parts : defaults.parts,
    jobs: Array.isArray(data?.jobs) ? data.jobs : defaults.jobs,
    jobRequirements: Array.isArray(data?.jobRequirements) ? data.jobRequirements : defaults.jobRequirements,
    orderListItems: Array.isArray(data?.orderListItems) ? data.orderListItems : defaults.orderListItems,
    purchaseOrders: Array.isArray(data?.purchaseOrders) ? data.purchaseOrders : defaults.purchaseOrders,
    completedJobs: Array.isArray(data?.completedJobs) ? data.completedJobs : defaults.completedJobs,
    receivingLogs: Array.isArray(data?.receivingLogs) ? data.receivingLogs : defaults.receivingLogs,
    usageLogs: Array.isArray(data?.usageLogs) ? data.usageLogs : defaults.usageLogs,
    jobAttachments: Array.isArray(data?.jobAttachments) ? data.jobAttachments : defaults.jobAttachments,
    jobNotes: Array.isArray(data?.jobNotes) ? data.jobNotes : defaults.jobNotes,
    jobTypeOptions:
      Array.isArray(data?.jobTypeOptions) && data.jobTypeOptions.length ? data.jobTypeOptions : defaults.jobTypeOptions,
    serviceFieldOptions: { ...defaults.serviceFieldOptions, ...(data?.serviceFieldOptions || {}) },
    featureFlags: { ...defaults.featureFlags, ...(data?.featureFlags || {}) },
    emailSettings: { ...defaults.emailSettings, ...(data?.emailSettings || {}) },
  };
}

function syncState(data) {
  state = normalizeState(data);
  pruneVerifiedReceipts();
  pruneInlineEditors();
}

function renderFeatureFallback(label) {
  const configs = {
    dashboard: [
      {
        selector: '#dashboard-view',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Dashboard unavailable</strong><p class="subtle">We hit a problem loading dashboard data. Other areas should still work.</p></div></div>`,
      },
    ],
    insights: [
      {
        selector: '#insights-page',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Insights unavailable</strong><p class="subtle">Insights could not load right now. Your jobs and inventory are still available.</p></div></div>`,
      },
    ],
    'inventory table': [
      {
        selector: '#inventory-table',
        html: `<tr><td colspan="8">${emptyState('Unable to load parts right now.')}</td></tr>`,
      },
    ],
    'vendor table': [
      {
        selector: '#vendor-table',
        html: `<tr><td colspan="5">${emptyState('Unable to load vendors right now.')}</td></tr>`,
      },
    ],
    'warehouse table': [
      {
        selector: '#warehouse-table',
        html: `<tr><td colspan="4">${emptyState('Unable to load warehouses right now.')}</td></tr>`,
      },
    ],
    'purchase orders': [
      {
        selector: '#po-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Purchase orders unavailable</strong><p class="subtle">Orders could not load right now.</p></div></div>`,
      },
    ],
    'receiving log': [
      {
        selector: '#receiving-log',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Receiving history unavailable</strong><p class="subtle">Checked-in history could not load right now.</p></div></div>`,
      },
      { selector: '#receiving-archive', html: '' },
    ],
    'jobs list': [
      {
        selector: '#jobs-install-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Jobs unavailable</strong><p class="subtle">Install jobs could not load right now. Other sections should still work.</p></div></div>`,
      },
      {
        selector: '#jobs-service-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Jobs unavailable</strong><p class="subtle">Service and warranty jobs could not load right now. Other sections should still work.</p></div></div>`,
      },
    ],
    archive: [
      {
        selector: '#archive-install-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Archive unavailable</strong><p class="subtle">Install archive could not load right now.</p></div></div>`,
      },
      {
        selector: '#archive-service-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Archive unavailable</strong><p class="subtle">Service archive could not load right now.</p></div></div>`,
      },
      {
        selector: '#archive-po-list',
        html: `<div class="alert-card feature-fallback-card"><div><strong>Archive unavailable</strong><p class="subtle">Purchase-order archive could not load right now.</p></div></div>`,
      },
    ],
    'users table': [
      {
        selector: '#users-table',
        html: `<tr><td colspan="4">${emptyState('Unable to load users right now.')}</td></tr>`,
      },
    ],
    'role permissions table': [
      {
        selector: '#role-permissions-table',
        html: `<tr><td colspan="3">${emptyState('Unable to load role permissions right now.')}</td></tr>`,
      },
    ],
  };
  (configs[label] || []).forEach((config) => {
    const element = document.querySelector(config.selector);
    if (element) element.innerHTML = config.html;
  });
}

function setJobFormMessage(message = '', tone = 'error') {
  const root = document.querySelector('#job-form-message');
  if (!root) return;
  root.textContent = message;
  root.className = `inline-form-message ${tone} ${message ? '' : 'hidden'}`.trim();
}

function pruneVerifiedReceipts() {
  const validLineKeys = new Set(
    state.purchaseOrders.flatMap((po) =>
      (po.lines || [])
        .filter((line) => Math.max(Number(line.quantity_ordered) - Number(line.quantity_received), 0) > 0)
        .map((line) => `${po.id}:${line.id}`),
    ),
  );
  [...verifiedReceiptLines].forEach((lineKey) => {
    if (!validLineKeys.has(String(lineKey))) {
      verifiedReceiptLines.delete(String(lineKey));
    }
  });
  [...poLineReceiveDrafts.keys()].forEach((lineKey) => {
    if (!validLineKeys.has(String(lineKey))) {
      poLineReceiveDrafts.delete(String(lineKey));
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
  if (
    inlineEditors.orderFormTemplateId &&
    !state.orderFormTemplates.some((template) => Number(template.id) === Number(inlineEditors.orderFormTemplateId))
  ) {
    inlineEditors.orderFormTemplateId = null;
  }
  if (
    inlineEditors.warehouseId &&
    !state.warehouses.some((warehouse) => Number(warehouse.id) === Number(inlineEditors.warehouseId))
  ) {
    inlineEditors.warehouseId = null;
  }
}

function formatDate(value) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function archiveAfterDays() {
  const stored = Number(window.localStorage.getItem(ARCHIVE_CUTOFF_STORAGE_KEY) || DEFAULT_ARCHIVE_AFTER_DAYS);
  return [14, 30, 60, 90].includes(stored) ? stored : DEFAULT_ARCHIVE_AFTER_DAYS;
}

function archiveCutoffDate() {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - archiveAfterDays());
  cutoff.setHours(0, 0, 0, 0);
  return cutoff;
}

function splitRecentAndArchived(items, dateField = 'created_at') {
  const cutoff = archiveCutoffDate();
  return items.reduce(
    (groups, item) => {
      const itemDate = new Date(item[dateField]);
      if (itemDate < cutoff) {
        groups.archived.push(item);
      } else {
        groups.recent.push(item);
      }
      return groups;
    },
    { recent: [], archived: [] },
  );
}

function archiveMonthLabel(value) {
  return new Date(value).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function groupArchiveItemsByMonth(items, dateField = 'created_at') {
  return items.reduce((groups, item) => {
    const key = new Date(item[dateField]).toISOString().slice(0, 7);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
    return groups;
  }, new Map());
}

function inventoryStatus(part) {
  const stagedOrder = findOrderListEntryForPart(part.id);
  const openPo = latestOpenPurchaseOrderForPart(part.id);
  if (openPo?.status === 'Waiting for Part' || openPo?.status === 'Partial Received')
    return { label: 'Order Processed', className: 'status-info' };
  if (openPo?.status === 'Email Pending') return { label: 'Order In Process', className: 'status-info' };
  if (stagedOrder) return { label: 'Order Staged', className: 'status-info' };
  if (isNonStock(part)) return { label: 'Non-Stock', className: 'status-neutral' };
  if (part.stock === 0) return { label: 'Out of Stock', className: 'status-danger' };
  if (part.stock <= part.reorder_point) return { label: 'Low Stock', className: 'status-warn' };
  return { label: 'Healthy', className: 'status-ok' };
}

function needsAttention(part) {
  if (isNonStock(part)) return false;
  return part.stock <= part.reorder_point && !findOrderListEntryForPart(part.id) && !partHasOpenPurchaseOrder(part.id);
}

function partCategoryGroups(filteredParts = state.parts) {
  return filteredParts.reduce((groups, part) => {
    const category = part.category || 'Uncategorized';
    if (!groups.has(category)) {
      groups.set(category, []);
    }
    groups.get(category).push(part);
    return groups;
  }, new Map());
}

function filteredInventoryParts() {
  const search = document.querySelector('#inventory-search')?.value.trim().toLowerCase() || '';
  return state.parts.filter((part) => {
    const status = inventoryStatus(part).label;
    const matchesSearch = [part.part_number, part.description, part.category, vendorName(part.vendor_id)]
      .join(' ')
      .toLowerCase()
      .includes(search);
    const matchesStatus = inventoryFilters.status === 'all' || status === inventoryFilters.status;
    const matchesPartType = inventoryFilters.partType === 'all' || partTypeLabel(part) === inventoryFilters.partType;
    const matchesVendor = inventoryFilters.vendor === 'all' || String(part.vendor_id) === inventoryFilters.vendor;
    const matchesCategory =
      inventoryFilters.category === 'all' || (part.category || 'Uncategorized') === inventoryFilters.category;
    return matchesSearch && matchesStatus && matchesPartType && matchesVendor && matchesCategory;
  });
}

function renderInventoryFilters() {
  const statusSelect = document.querySelector('#inventory-status-filter');
  const typeSelect = document.querySelector('#inventory-type-filter');
  const vendorSelect = document.querySelector('#inventory-vendor-filter');
  const categorySelect = document.querySelector('#inventory-category-filter');
  if (!statusSelect || !typeSelect || !vendorSelect || !categorySelect) return;

  const statuses = ['Healthy', 'Low Stock', 'Order In Process', 'Order Processed', 'Out of Stock', 'Non-Stock'];
  statusSelect.innerHTML = `<option value="all">All Statuses</option>${statuses.map((status) => `<option value="${status}">${status}</option>`).join('')}`;
  statusSelect.value = inventoryFilters.status;

  typeSelect.innerHTML =
    '<option value="all">All Items</option><option value="Stocked">Stocked Only</option><option value="Non-Stock">Non-Stock Only</option>';
  typeSelect.value = inventoryFilters.partType;

  vendorSelect.innerHTML = `<option value="all">All Vendors</option>${state.vendors.map((vendor) => `<option value="${vendor.id}">${vendor.name}</option>`).join('')}`;
  vendorSelect.value = inventoryFilters.vendor;

  const categories = [...new Set(state.parts.map((part) => part.category || 'Uncategorized'))].sort((left, right) =>
    left.localeCompare(right),
  );
  categorySelect.innerHTML = `<option value="all">All Categories</option>${categories.map((category) => `<option value="${category}">${category}</option>`).join('')}`;
  categorySelect.value = inventoryFilters.category;
}

function initializeCollapsedCategories() {
  const categories = [...new Set(state.parts.map((part) => part.category || 'Uncategorized'))];
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
  const categories = [...new Set(state.parts.map((part) => part.category || 'Uncategorized'))];
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
  closeJobPullModal(true);
}

function initializeCollapsedJobs() {
  const jobIds = [...(state.jobs || []), ...(state.completedJobs || [])].map((job) => Number(job.id));
  jobIds.forEach((jobId) => {
    if (!knownJobIds.has(jobId)) {
      knownJobIds.add(jobId);
      collapsedJobs.add(jobId);
    }
  });
  [...knownJobIds].forEach((jobId) => {
    if (!jobIds.includes(Number(jobId))) {
      knownJobIds.delete(jobId);
      collapsedJobs.delete(jobId);
    }
  });
}

function vendorOptionsMarkup(selectedVendorId) {
  return state.vendors
    .map(
      (vendor) =>
        `<option value="${vendor.id}" ${Number(vendor.id) === Number(selectedVendorId) ? 'selected' : ''}>${vendor.name}</option>`,
    )
    .join('');
}

function renderInlinePartEditor(part) {
  return `
    <tr class="inline-editor-row">
      <td colspan="6">
        <form class="inline-editor-grid inline-editor-grid-part" data-inline-part-form="${part.id}">
          <input type="hidden" name="id" value="${part.id}">
          <label>Part Number<input name="partNumber" type="text" value="${part.part_number}" required></label>
          <label>Scan Code<input name="scanCode" type="text" value="${part.scan_code || ''}"></label>
          <label>Description<input name="description" type="text" value="${part.description}" required></label>
          <label>Category<input name="category" type="text" value="${part.category}" required></label>
          <label>Item Type<select name="itemType"><option value="stocked" ${!isNonStock(part) ? 'selected' : ''}>Stocked</option><option value="non_stock" ${isNonStock(part) ? 'selected' : ''}>Non-Stock</option></select></label>
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
          <label>Form Style<select name="formVariant"><option value="aquaflow" ${template.form_variant === 'aquaflow' ? 'selected' : ''}>AquaFlow Style</option><option value="bathbuild" ${template.form_variant === 'bathbuild' ? 'selected' : ''}>BathBuild Style</option></select></label>
          <label>Notes<input name="notes" type="text" value="${template.notes || ''}"></label>
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
            <button type="button" class="ghost" data-inline-archive-warehouse="${warehouse.id}">${warehouse.is_active ? 'Archive' : 'Restore'}</button>
          </div>
        </form>
      </td>
    </tr>
  `;
}

function emptyState(message = '') {
  const template =
    document.querySelector('#empty-state-template')?.innerHTML || `<div class="empty-state"><p></p></div>`;
  if (!message) return template;
  return template.replace('<p>Nothing to show yet.</p>', `<p>${htmlEscape(message)}</p>`);
}

function dashboardMetrics() {
  return {
    lowStock: state.parts.filter(needsAttention).length,
    openOrders: state.purchaseOrders.filter((po) => po.status !== 'Received').length,
    inventoryValue: state.parts.reduce((sum, part) => sum + part.stock * part.unit_cost, 0),
    activeJobs: state.jobs.length,
    readyJobs: state.jobs.filter((job) => job.status === 'Ready to Go').length,
  };
}

function lowStockTone(count) {
  if (count === 0) return 'metric-good';
  if (count <= 4) return 'metric-warn';
  return 'metric-danger';
}

function weeklyUsageEntries() {
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);
  return [
    ...state.usageLogs
      .filter((log) => new Date(log.created_at) >= weekStart)
      .reduce((totals, log) => {
        const current = totals.get(log.part_id) || { quantity: 0, part: partById(log.part_id) };
        current.quantity += log.quantity;
        totals.set(log.part_id, current);
        return totals;
      }, new Map())
      .values(),
  ]
    .filter((entry) => entry.part)
    .sort((left, right) => right.quantity - left.quantity);
}

function readyJobsList() {
  return state.jobs
    .filter((job) => job.status === 'Ready to Go')
    .sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
}

function makePartThumbnail(part) {
  return partPhotoLibrary[part.category] || 'https://commons.wikimedia.org/wiki/Special:FilePath/PVC_pipe_Example.jpg';
}

function renderWarehouseSelector() {
  const select = document.querySelector('#warehouse-selector');
  const summary = document.querySelector('#warehouse-summary');
  if (!select || !summary) return;
  const options = state.activeWarehouses.length ? state.activeWarehouses : state.warehouses;
  select.innerHTML = options
    .map(
      (warehouse) => `
    <option value="${warehouse.id}">${warehouse.name} (${warehouse.code})</option>
  `,
    )
    .join('');
  const selectedId = state.selectedWarehouseId || options[0]?.id || '';
  select.value = String(selectedId);
  summary.textContent = state.selectedWarehouse
    ? `Showing inventory for ${state.selectedWarehouse.name}.`
    : 'Showing one location at a time.';
}

function renderInventoryAttentionBadge() {
  const badge = document.querySelector('#inventory-attention-badge');
  if (!badge) return;
  const lowStockCount = state.parts.filter(needsAttention).length;
  badge.textContent = String(lowStockCount);
  badge.classList.toggle('hidden', lowStockCount === 0);
}

function renderPoAttentionBadge() {
  const badge = document.querySelector('#po-attention-badge');
  if (!badge) return;
  const openPoCount =
    state.purchaseOrders.filter((po) => po.status !== 'Received').length + state.orderListItems.length;
  badge.textContent = String(openPoCount);
  badge.classList.toggle('hidden', openPoCount === 0);
}

function renderJobsAttentionBadge() {
  const badge = document.querySelector('#jobs-attention-badge');
  if (!badge) return;
  const activeJobIdsNeedingParts = new Set(
    state.jobRequirements
      .filter((requirement) => Number(requirement.pulled_quantity) < Number(requirement.required_quantity))
      .map((requirement) => Number(requirement.job_id)),
  );
  const count = activeJobIdsNeedingParts.size;
  badge.textContent = String(count);
  badge.classList.toggle('hidden', count === 0);
}

function renderSummaryPanel() {
  const title = document.querySelector('#summary-panel-title');
  const list = document.querySelector('#summary-panel-list');
  if (!title || !list) return;
  title.textContent = summaryPanelState.title || 'Items';
  list.innerHTML = summaryPanelState.items.length
    ? summaryPanelState.items
        .map(
          (item) => `
        <button type="button" class="activity-card summary-panel-item" data-summary-route="${htmlEscape(item.routeType || '')}" data-summary-key="${htmlEscape(item.routeKey || '')}" data-summary-archive="${item.preferArchive ? '1' : '0'}" ${item.routeType ? '' : 'disabled'}>
          <strong>${htmlEscape(item.title || 'Item')}</strong>
          ${item.subtitle ? `<p class="subtle">${htmlEscape(item.subtitle)}</p>` : ''}
        </button>
      `,
        )
        .join('')
    : emptyState('Nothing matched this summary box.');
}

function renderDashboard() {
  const root = document.querySelector('#dashboard-view');
  const metrics = dashboardMetrics();
  const usageEntries = weeklyUsageEntries();
  const displayedUsage = dashboardUsageExpanded ? usageEntries : usageEntries.slice(0, 5);
  const openOrders = state.purchaseOrders.filter((po) => po.status !== 'Received');
  const warehouseLabel = state.selectedWarehouse ? state.selectedWarehouse.name : 'Current Warehouse';
  const readyJobs = readyJobsList();
  const activeJobs = [...state.jobs].sort((left, right) => new Date(right.created_at) - new Date(left.created_at));

  root.innerHTML = `
    <div class="metrics metrics-dashboard">
      <article class="metric-card"><p class="eyebrow">${warehouseLabel}</p><strong>${state.selectedWarehouse ? state.selectedWarehouse.code : '--'}</strong><p class="subtle">Warehouse currently in view</p></article>
      <button type="button" class="metric-card metric-button ${lowStockTone(metrics.lowStock)}" data-summary-open="dashboard-low-stock"><p class="eyebrow">Low Stock Alerts</p><strong>${metrics.lowStock}</strong><p class="subtle">Parts still needing action</p></button>
      <button type="button" class="metric-card metric-button" data-summary-open="dashboard-active-jobs"><p class="eyebrow">Active Jobs</p><strong>${metrics.activeJobs}</strong><p class="subtle">Jobs currently in progress</p></button>
    </div>
    <div class="dashboard-grid">
      <div class="stack">
        <article class="panel">
          <div class="table-header">
            <div>
              <h4>Parts used this week</h4>
              <p class="subtle">Top five by default, open the full list when you need detail.</p>
            </div>
            ${usageEntries.length > 5 ? `<button type="button" class="ghost dashboard-toggle" data-toggle-weekly-usage="true">${dashboardUsageExpanded ? 'Show Top 5' : 'Show All'}</button>` : ''}
          </div>
          <div class="activity-list compact-list">
            ${
              displayedUsage.length
                ? displayedUsage
                    .map(
                      (entry) => `
              <div class="activity-card usage-card">
                <strong><span class="part-number-link">${entry.part.part_number}</span> - ${entry.part.description}</strong>
                <p class="subtle">${entry.quantity} used this week</p>
              </div>`,
                    )
                    .join('')
                : emptyState()
            }
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="panel">
          <h4>Jobs ready to go</h4>
          <div class="activity-list compact-list">
            ${
              readyJobs.length
                ? readyJobs
                    .map(
                      (job) => `
              <div class="activity-card job-ready-card">
                <button type="button" class="job-number-link button-link" data-summary-route="job" data-summary-key="${job.id}">${job.job_number}</button>
                <p class="subtle">${job.customer_name || 'No customer listed'}</p>
                <p class="subtle">${job.address || 'No address listed'}</p>
                <p class="subtle">${job.technician} | ${job.scheduled_for ? formatDate(job.scheduled_for) : 'Not scheduled'}</p>
              </div>`,
                    )
                    .join('')
                : emptyState()
            }
          </div>
        </article>
        <article class="panel">
          <h4>Open purchase orders</h4>
          <div class="activity-list compact-list">
            ${
              openOrders.length
                ? openOrders
                    .map(
                      (po) => `
              <div class="activity-card">
                <button type="button" class="po-number-link button-link" data-summary-route="po" data-summary-key="${po.id}">${po.po_number}</button>
                <p class="subtle">${po.vendor_name} | ${po.line_count} line item(s)</p>
                <p class="subtle">${po.status} | Outstanding ${po.outstanding_quantity}</p>
              </div>`,
                    )
                    .join('')
                : emptyState()
            }
          </div>
        </article>
      </div>
    </div>
  `;
}

function insightTable(headers, rows, emptyMessage = 'No insight data yet.') {
  if (!rows.length) {
    return `<div class="empty-state"><p>${emptyMessage}</p></div>`;
  }
  return `
    <div class="table-wrap insight-table-wrap">
      <table class="insight-table">
        <thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead>
        <tbody>${rows.join('')}</tbody>
      </table>
    </div>
  `;
}

function quantityByPartLogs(logs) {
  return logs.reduce((totals, log) => {
    const key = String(log.part_id);
    const current = totals.get(key) || {
      partId: Number(log.part_id),
      partNumber: log.part_number,
      description: log.description,
      quantity: 0,
      hits: 0,
    };
    current.quantity += Number(log.quantity || 0);
    current.hits += 1;
    totals.set(key, current);
    return totals;
  }, new Map());
}

function daysAgoDate(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date;
}

function usageLogsWithinDays(days) {
  const cutoff = daysAgoDate(days);
  return (state.usageLogs || []).filter((log) => Number(log.quantity || 0) > 0 && new Date(log.created_at) >= cutoff);
}

function monthUsageSeries() {
  const monthMap = new Map();
  (state.usageLogs || [])
    .filter((log) => Number(log.quantity || 0) > 0)
    .forEach((log) => {
      const key = new Date(log.created_at).toISOString().slice(0, 7);
      const current = monthMap.get(key) || { key, quantity: 0 };
      current.quantity += Number(log.quantity || 0);
      monthMap.set(key, current);
    });
  return [...monthMap.values()].sort((left, right) => left.key.localeCompare(right.key)).slice(-6);
}

function monthLabel(key) {
  const [year, month] = key.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

function partCategoryFor(partId) {
  return partById(partId)?.category || 'Uncategorized';
}

function phase1FilteredInsightsInputs() {
  const dateRangeDays = Number(insightsFilters.dateRange || 90);
  const cutoff = daysAgoDate(dateRangeDays);
  const completedJobs = (state.completedJobs || []).filter((job) => {
    const matchesDate = new Date(job.created_at) >= cutoff;
    const matchesType = insightsFilters.jobType === 'all' || job.title === insightsFilters.jobType;
    return matchesDate && matchesType;
  });
  const usageLogs = (state.usageLogs || []).filter((log) => {
    const matchesDate = new Date(log.created_at) >= cutoff;
    const matchesType =
      insightsFilters.jobType === 'all' ||
      (state.completedJobs || []).some(
        (job) => job.job_number === log.job_number && job.title === insightsFilters.jobType,
      );
    const matchesCategory =
      insightsFilters.partCategory === 'all' || partCategoryFor(log.part_id) === insightsFilters.partCategory;
    return matchesDate && matchesType && matchesCategory && Number(log.quantity || 0) > 0;
  });
  return { completedJobs, usageLogs, dateRangeDays };
}

function phase1CompletedJobUsage(job) {
  return jobRequirementsFor(job.id).reduce((sum, requirement) => sum + Number(requirement.pulled_quantity || 0), 0);
}

function phase1InsightsData() {
  const { completedJobs, usageLogs, dateRangeDays } = phase1FilteredInsightsInputs();
  const usage30 = usageLogsWithinDays(30).filter(
    (log) =>
      Number(log.quantity || 0) > 0 &&
      (insightsFilters.partCategory === 'all' || partCategoryFor(log.part_id) === insightsFilters.partCategory) &&
      (insightsFilters.jobType === 'all' ||
        completedJobs.some((job) => job.job_number === log.job_number && job.title === insightsFilters.jobType)),
  );
  const usage60 = usageLogsWithinDays(60).filter(
    (log) =>
      Number(log.quantity || 0) > 0 &&
      (insightsFilters.partCategory === 'all' || partCategoryFor(log.part_id) === insightsFilters.partCategory) &&
      (insightsFilters.jobType === 'all' ||
        completedJobs.some((job) => job.job_number === log.job_number && job.title === insightsFilters.jobType)),
  );
  const usage90 = usageLogsWithinDays(90).filter(
    (log) =>
      Number(log.quantity || 0) > 0 &&
      (insightsFilters.partCategory === 'all' || partCategoryFor(log.part_id) === insightsFilters.partCategory) &&
      (insightsFilters.jobType === 'all' ||
        completedJobs.some((job) => job.job_number === log.job_number && job.title === insightsFilters.jobType)),
  );

  const mostUsedParts = [...quantityByPartLogs(usageLogs).values()]
    .sort((left, right) => right.quantity - left.quantity)
    .slice(0, 8);

  const fastestMovingParts = [...quantityByPartLogs(usage30).values()]
    .map((entry) => ({ ...entry, perWeek: Number(((entry.quantity / 30) * 7).toFixed(1)) }))
    .sort((left, right) => right.perWeek - left.perWeek)
    .slice(0, 8);

  const jobTypeCounts = completedJobs.reduce((counts, job) => {
    const key = job.title || 'Uncategorized Job';
    const current = counts.get(key) || { title: key, count: 0, totalUsage: 0 };
    current.count += 1;
    current.totalUsage += completedJobUsage(job);
    counts.set(key, current);
    return counts;
  }, new Map());

  const commonJobTypes = [...jobTypeCounts.values()].sort((left, right) => right.count - left.count);
  const repeatedJobTypes = commonJobTypes.filter((entry) => entry.count > 1).slice(0, 6);

  const unusualHighUsageJobs = completedJobs
    .map((job) => {
      const totalUsage = phase1CompletedJobUsage(job);
      const titleGroup = commonJobTypes.find((entry) => entry.title === job.title);
      const averageUsage = titleGroup ? titleGroup.totalUsage / titleGroup.count : totalUsage;
      return { job, totalUsage, averageUsage };
    })
    .filter((entry) => entry.totalUsage >= entry.averageUsage + 2 && entry.totalUsage > entry.averageUsage * 1.25)
    .sort((left, right) => right.totalUsage - left.totalUsage)
    .slice(0, 6);

  const incompleteRequirements = (state.jobRequirements || []).filter((requirement) => {
    const matchesCategory =
      insightsFilters.partCategory === 'all' || partCategoryFor(requirement.part_id) === insightsFilters.partCategory;
    return Number(requirement.required_quantity || 0) > Number(requirement.pulled_quantity || 0) && matchesCategory;
  });
  const incompletePartCounts = incompleteRequirements.reduce((counts, requirement) => {
    const key = String(requirement.part_id);
    const current = counts.get(key) || {
      partNumber: requirement.part_number,
      description: requirement.description,
      count: 0,
      shortfall: 0,
    };
    current.count += 1;
    current.shortfall += Number(requirement.required_quantity || 0) - Number(requirement.pulled_quantity || 0);
    counts.set(key, current);
    return counts;
  }, new Map());

  const extraUsageParts = usageLogs.reduce((counts, log) => {
    const note = String(log.notes || '').toLowerCase();
    if (!note.includes('extra') && !note.includes('misc')) return counts;
    const key = String(log.part_id);
    const current = counts.get(key) || { partNumber: log.part_number, count: 0 };
    current.count += 1;
    counts.set(key, current);
    return counts;
  }, new Map());

  const reorderedOften = state.purchaseOrders.reduce((counts, po) => {
    (po.lines || []).forEach((line) => {
      if (insightsFilters.partCategory !== 'all' && partCategoryFor(line.part_id) !== insightsFilters.partCategory)
        return;
      const key = String(line.part_id);
      const current = counts.get(key) || { partNumber: line.part_number, count: 0 };
      current.count += 1;
      counts.set(key, current);
    });
    return counts;
  }, new Map());

  const reorderPredictions = state.parts
    .filter(
      (part) =>
        !isNonStock(part) && (insightsFilters.partCategory === 'all' || part.category === insightsFilters.partCategory),
    )
    .map((part) => {
      const used30 = usage30
        .filter((log) => Number(log.part_id) === Number(part.id))
        .reduce((sum, log) => sum + Number(log.quantity || 0), 0);
      const used60 = usage60
        .filter((log) => Number(log.part_id) === Number(part.id))
        .reduce((sum, log) => sum + Number(log.quantity || 0), 0);
      const used90 = usage90
        .filter((log) => Number(log.part_id) === Number(part.id))
        .reduce((sum, log) => sum + Number(log.quantity || 0), 0);
      const avgDaily60 = used60 / 60;
      const availableBeforeReorder = Number(part.stock || 0) - Number(part.reorder_point || 0);
      let daysUntilReorder = null;
      if (avgDaily60 > 0) {
        daysUntilReorder = availableBeforeReorder <= 0 ? 0 : Number((availableBeforeReorder / avgDaily60).toFixed(1));
      }
      return {
        partId: Number(part.id),
        partNumber: part.part_number,
        description: part.description,
        stock: Number(part.stock || 0),
        reorderPoint: Number(part.reorder_point || 0),
        used30,
        used60,
        used90,
        avgDaily60,
        daysUntilReorder,
      };
    })
    .filter((entry) => entry.used60 > 0 || entry.stock <= entry.reorderPoint)
    .sort((left, right) => {
      const leftDays = left.daysUntilReorder ?? Number.POSITIVE_INFINITY;
      const rightDays = right.daysUntilReorder ?? Number.POSITIVE_INFINITY;
      return leftDays - rightDays;
    })
    .slice(0, 8);

  const processFlags = [];
  const topIncomplete = [...incompletePartCounts.values()].sort((left, right) => right.shortfall - left.shortfall)[0];
  if (topIncomplete) {
    processFlags.push({
      tone: 'warning',
      title: 'Incomplete Job Pressure',
      body: `${topIncomplete.partNumber} is still short across ${topIncomplete.count} active job(s), with ${topIncomplete.shortfall} unit(s) left to pull.`,
    });
  }
  const topExtra = [...extraUsageParts.values()].sort((left, right) => right.count - left.count)[0];
  if (topExtra) {
    processFlags.push({
      tone: 'warning',
      title: 'Extra Material Pattern',
      body: `${topExtra.partNumber} appears in extra or miscellaneous usage notes ${topExtra.count} time(s) in the selected view.`,
    });
  }
  const topReordered = [...reorderedOften.values()].sort((left, right) => right.count - left.count)[0];
  if (topReordered && topReordered.count > 1) {
    processFlags.push({
      tone: 'info',
      title: 'Frequent Reorder Signal',
      body: `${topReordered.partNumber} appears on purchase orders ${topReordered.count} time(s), suggesting repeat reorder pressure.`,
    });
  }
  const topUnusualJob = unusualHighUsageJobs[0];
  if (topUnusualJob) {
    processFlags.push({
      tone: 'warning',
      title: 'High Usage Job',
      body: `${topUnusualJob.job.job_number} used ${topUnusualJob.totalUsage} parts for ${topUnusualJob.job.title}, versus a typical ${topUnusualJob.averageUsage.toFixed(1)}.`,
    });
  }

  const monthlyUsage = monthUsageSeries().filter((entry) => {
    const monthStart = new Date(`${entry.key}-01T00:00:00`);
    return monthStart >= daysAgoDate(Math.max(dateRangeDays, 30));
  });
  const monthlyChange =
    monthlyUsage.length >= 2
      ? ((monthlyUsage[monthlyUsage.length - 1].quantity - monthlyUsage[monthlyUsage.length - 2].quantity) /
          Math.max(monthlyUsage[monthlyUsage.length - 2].quantity || 1, 1)) *
        100
      : 0;

  const summaries = [];
  if (mostUsedParts[0]) {
    summaries.push(
      `The busiest part in this view is ${mostUsedParts[0].partNumber}, used ${mostUsedParts[0].quantity} times over the selected period.`,
    );
  }
  if (commonJobTypes[0]) {
    summaries.push(
      `${commonJobTypes[0].title} is the most common completed job type here, with ${commonJobTypes[0].count} finished jobs in the selected range.`,
    );
  }
  if (reorderPredictions[0]) {
    const topPrediction = reorderPredictions[0];
    const forecastText =
      topPrediction.daysUntilReorder === 0
        ? 'has already reached its reorder point'
        : `is on track to hit its reorder point in about ${topPrediction.daysUntilReorder} day(s)`;
    summaries.push(`${topPrediction.partNumber} ${forecastText}, based on its last 60 days of usage.`);
  }
  if (monthlyUsage.length >= 2) {
    const direction = monthlyChange >= 0 ? 'rose' : 'fell';
    summaries.push(
      `Overall usage ${direction} ${Math.abs(monthlyChange).toFixed(0)}% from ${monthLabel(monthlyUsage[monthlyUsage.length - 2].key)} to ${monthLabel(monthlyUsage[monthlyUsage.length - 1].key)}.`,
    );
  }

  return {
    dateRangeDays,
    usageLogs,
    usage30,
    usage60,
    usage90,
    mostUsedParts,
    fastestMovingParts,
    commonJobTypes,
    repeatedJobTypes,
    unusualHighUsageJobs,
    reorderPredictions,
    processFlags,
    monthlyUsage,
    summaries,
    completedJobs,
  };
}

function phase1RenderInsights() {
  const root = document.querySelector('#insights-page');
  if (!root) return;
  const data = phase1InsightsData();
  const maxMonthlyUsage = Math.max(...data.monthlyUsage.map((entry) => entry.quantity), 1);
  const jobTypes = [...new Set((state.completedJobs || []).map((job) => job.title).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
  const partCategories = [...new Set((state.parts || []).map((part) => part.category || 'Uncategorized'))].sort(
    (a, b) => a.localeCompare(b),
  );

  root.innerHTML = `
    <article class="panel insight-panel">
      <div class="table-header compact-header">
        <div>
          <h4>Insight Filters</h4>
          <p class="subtle">Narrow the view without changing the underlying reporting formulas.</p>
        </div>
      </div>
      <div class="inventory-filters insights-filters">
        <label>Date Range<select id="insights-date-range"><option value="30" ${insightsFilters.dateRange === '30' ? 'selected' : ''}>Last 30 days</option><option value="60" ${insightsFilters.dateRange === '60' ? 'selected' : ''}>Last 60 days</option><option value="90" ${insightsFilters.dateRange === '90' ? 'selected' : ''}>Last 90 days</option></select></label>
        <label>Job Type<select id="insights-job-type"><option value="all">All Job Types</option>${jobTypes.map((title) => `<option value="${title}" ${insightsFilters.jobType === title ? 'selected' : ''}>${title}</option>`).join('')}</select></label>
        <label>Part Category<select id="insights-part-category"><option value="all">All Categories</option>${partCategories.map((category) => `<option value="${category}" ${insightsFilters.partCategory === category ? 'selected' : ''}>${category}</option>`).join('')}</select></label>
      </div>
    </article>
    <div class="metrics metrics-dashboard insights-metrics">
      <article class="metric-card metric-warn"><p class="eyebrow">Reorder Watch</p><strong>${data.reorderPredictions[0]?.daysUntilReorder === 0 ? 'Now' : (data.reorderPredictions[0]?.daysUntilReorder ?? '--')}</strong><p class="subtle">Closest estimated days to reorder in the current view</p></article>
      <article class="metric-card ${data.processFlags.length ? 'metric-danger' : 'metric-good'}"><p class="eyebrow">Pattern Flags</p><strong>${data.processFlags.length}</strong><p class="subtle">Potential process issues worth reviewing first</p></article>
      <article class="metric-card"><p class="eyebrow">Completed Jobs</p><strong>${data.completedJobs.length}</strong><p class="subtle">Finished jobs included in this filtered view</p></article>
    </div>
    <article class="panel insight-panel insight-panel-wide">
      <div class="table-header compact-header">
        <div><h4>Pattern / Anomaly Flags</h4><p class="subtle">The strongest warning signs are surfaced first.</p></div>
      </div>
      <div class="insight-flags-list">
        ${data.processFlags.length ? data.processFlags.map((flag) => `<div class="insight-flag-card ${flag.tone}"><strong>${flag.title}</strong><p>${flag.body}</p></div>`).join('') : emptyState()}
      </div>
    </article>
    <article class="panel insight-panel">
      <div class="table-header compact-header">
        <div><h4>Plain-English Summary</h4><p class="subtle">A readable summary built from the same rule-based calculations shown below.</p></div>
      </div>
      <div class="insight-summary-list">
        ${data.summaries.length ? data.summaries.map((item) => `<div class="activity-card"><p>${item}</p></div>`).join('') : emptyState()}
      </div>
    </article>
    <div class="insights-grid">
      <article class="panel insight-panel insight-panel-wide">
        <h4>Reorder Forecast</h4>
        <p class="subtle">Forecast uses average daily usage over the last 60 days, compared against current stock and reorder point.</p>
        ${insightTable(
          ['Part', 'Used 30d', 'Used 60d', 'Stock', 'Reorder', 'Est. Days To Reorder'],
          data.reorderPredictions.map(
            (entry) =>
              `<tr><td><strong class="part-number-link">${entry.partNumber}</strong><div class="subtle">${entry.description || ''}</div></td><td>${entry.used30}</td><td>${entry.used60}</td><td>${entry.stock}</td><td>${entry.reorderPoint}</td><td>${entry.daysUntilReorder === null ? 'No forecast yet' : entry.daysUntilReorder === 0 ? 'Now' : entry.daysUntilReorder}</td></tr>`,
          ),
          'Not enough usage history yet for reorder forecasting.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Most Used Parts</h4>
        ${insightTable(
          ['Part', 'Used', 'Touches'],
          data.mostUsedParts.map(
            (entry) =>
              `<tr><td><strong class="part-number-link">${entry.partNumber}</strong><div class="subtle">${entry.description || ''}</div></td><td>${entry.quantity}</td><td>${entry.hits}</td></tr>`,
          ),
          'No part usage yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Fastest Moving Parts</h4>
        ${insightTable(
          ['Part', 'Per Week', '30-Day Usage'],
          data.fastestMovingParts.map(
            (entry) =>
              `<tr><td><strong class="part-number-link">${entry.partNumber}</strong></td><td>${entry.perWeek}</td><td>${entry.quantity}</td></tr>`,
          ),
          'No 30-day usage yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Usage by Month</h4>
        <div class="insight-bar-list">
          ${data.monthlyUsage.length ? data.monthlyUsage.map((entry) => `<div class="insight-bar-row"><div class="insight-bar-label">${monthLabel(entry.key)}</div><div class="insight-bar-track"><div class="insight-bar-fill" style="width:${Math.max((entry.quantity / maxMonthlyUsage) * 100, 8)}%"></div></div><div class="insight-bar-value">${entry.quantity}</div></div>`).join('') : emptyState()}
        </div>
      </article>
      <article class="panel insight-panel">
        <h4>Most Common Job Types</h4>
        ${insightTable(
          ['Job Type', 'Completed', 'Avg Parts Used'],
          data.commonJobTypes
            .slice(0, 8)
            .map(
              (entry) =>
                `<tr><td>${entry.title}</td><td>${entry.count}</td><td>${(entry.totalUsage / Math.max(entry.count, 1)).toFixed(1)}</td></tr>`,
            ),
          'No completed jobs yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Repeated Jobs / Categories</h4>
        ${insightTable(
          ['Job Type', 'Repeat Count'],
          data.repeatedJobTypes.map((entry) => `<tr><td>${entry.title}</td><td>${entry.count}</td></tr>`),
          'No repeated completed job types yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Jobs With High Part Usage</h4>
        ${insightTable(
          ['Job', 'Type', 'Parts Used', 'Avg For Type'],
          data.unusualHighUsageJobs.map(
            (entry) =>
              `<tr><td><strong class="job-number-link">${entry.job.job_number}</strong></td><td>${entry.job.title}</td><td>${entry.totalUsage}</td><td>${entry.averageUsage.toFixed(1)}</td></tr>`,
          ),
          'No unusually high-usage completed jobs found yet.',
        )}
      </article>
    </div>
  `;
}

function partTypeFor(partId) {
  return isNonStock(partById(partId)) ? 'non_stock' : 'stocked';
}

function vendorById(vendorId) {
  return state.vendors.find((vendor) => Number(vendor.id) === Number(vendorId));
}

function insightJobLookup() {
  return [...(state.jobs || []), ...(state.completedJobs || [])].reduce((lookup, job) => {
    lookup.set(String(job.job_number), job);
    return lookup;
  }, new Map());
}

function matchesInsightsPart(part) {
  if (!part) return false;
  const matchesCategory =
    insightsFilters.partCategory === 'all' || (part.category || 'Uncategorized') === insightsFilters.partCategory;
  const matchesVendor = insightsFilters.vendor === 'all' || String(part.vendor_id) === insightsFilters.vendor;
  const matchesPartType =
    insightsFilters.partType === 'all' || String(part.item_type || 'stocked') === insightsFilters.partType;
  const matchesWarehouse =
    insightsFilters.warehouseId === 'all' || String(part.warehouse_id) === insightsFilters.warehouseId;
  return matchesCategory && matchesVendor && matchesPartType && matchesWarehouse;
}

function matchesInsightsJob(job, cutoff) {
  if (!job) return false;
  const matchesDate = new Date(job.created_at) >= cutoff;
  const matchesType = insightsFilters.jobType === 'all' || job.title === insightsFilters.jobType;
  const matchesCrew = insightsFilters.crew === 'all' || job.technician === insightsFilters.crew;
  const matchesWarehouse =
    insightsFilters.warehouseId === 'all' || String(job.warehouse_id) === insightsFilters.warehouseId;
  return matchesDate && matchesType && matchesCrew && matchesWarehouse;
}

function matchesInsightsUsageLog(log, cutoff, jobLookup) {
  if (Number(log.quantity || 0) <= 0 || new Date(log.created_at) < cutoff) return false;
  const part = partById(log.part_id);
  if (!matchesInsightsPart(part)) return false;
  const relatedJob = jobLookup.get(String(log.job_number));
  if (relatedJob) return matchesInsightsJob(relatedJob, cutoff);
  const matchesCrew = insightsFilters.crew === 'all' || log.technician === insightsFilters.crew;
  const matchesWarehouse =
    insightsFilters.warehouseId === 'all' || String(log.warehouse_id) === insightsFilters.warehouseId;
  return matchesCrew && matchesWarehouse && insightsFilters.jobType === 'all';
}

function matchesInsightsPurchaseOrder(po, cutoff) {
  const poDate = new Date(po.updated_at || po.created_at);
  if (poDate < cutoff) return false;
  const matchesVendor = insightsFilters.vendor === 'all' || String(po.vendor_id) === insightsFilters.vendor;
  const matchesWarehouse =
    insightsFilters.warehouseId === 'all' || String(po.warehouse_id) === insightsFilters.warehouseId;
  const hasMatchingLine = (po.lines || []).some((line) => matchesInsightsPart(partById(line.part_id)));
  return matchesVendor && matchesWarehouse && hasMatchingLine;
}

function filteredInsightsUsageLogsWithinDays(days, jobLookup) {
  const cutoff = daysAgoDate(days);
  return (state.usageLogs || []).filter((log) => matchesInsightsUsageLog(log, cutoff, jobLookup));
}

function filteredInsightsInputs() {
  const dateRangeDays = Number(insightsFilters.dateRange || 90);
  const cutoff = daysAgoDate(dateRangeDays);
  const jobLookup = insightJobLookup();
  const completedJobs = (state.completedJobs || []).filter((job) => matchesInsightsJob(job, cutoff));
  const activeJobs = (state.jobs || []).filter((job) => matchesInsightsJob(job, cutoff));
  const activeJobIds = new Set(activeJobs.map((job) => Number(job.id)));
  const usageLogs = (state.usageLogs || []).filter((log) => matchesInsightsUsageLog(log, cutoff, jobLookup));
  const purchaseOrders = (state.purchaseOrders || []).filter((po) => matchesInsightsPurchaseOrder(po, cutoff));
  const incompleteRequirements = (state.jobRequirements || []).filter((requirement) => {
    const relatedJob = jobById(requirement.job_id);
    if (!relatedJob || !activeJobIds.has(Number(relatedJob.id))) return false;
    if (!matchesInsightsPart(partById(requirement.part_id))) return false;
    return Number(requirement.required_quantity || 0) > Number(requirement.pulled_quantity || 0);
  });
  return {
    dateRangeDays,
    jobLookup,
    completedJobs,
    activeJobs,
    usageLogs,
    purchaseOrders,
    incompleteRequirements,
  };
}

function insightsRequirementsForJob(jobId) {
  return jobRequirementsFor(jobId).filter((requirement) => matchesInsightsPart(partById(requirement.part_id)));
}

function completedJobUsage(job) {
  return insightsRequirementsForJob(job.id).reduce(
    (sum, requirement) => sum + Number(requirement.pulled_quantity || 0),
    0,
  );
}

function sumUsageForPart(logs, partId) {
  return logs
    .filter((log) => Number(log.part_id) === Number(partId))
    .reduce((sum, log) => sum + Number(log.quantity || 0), 0);
}

function percentChange(currentValue, previousValue) {
  if (currentValue > 0 && previousValue <= 0) return 100;
  if (currentValue <= 0 && previousValue <= 0) return 0;
  return ((currentValue - previousValue) / Math.max(previousValue, 1)) * 100;
}

function buildCompanionCounts(completedJobs) {
  const companionCounts = new Map();
  completedJobs.forEach((job) => {
    const partIds = [
      ...new Set(
        insightsRequirementsForJob(job.id)
          .filter((requirement) => Number(requirement.pulled_quantity || 0) > 0)
          .map((requirement) => Number(requirement.part_id)),
      ),
    ];
    partIds.forEach((partId) => {
      if (!companionCounts.has(partId)) companionCounts.set(partId, new Map());
      partIds
        .filter((candidateId) => candidateId !== partId)
        .forEach((candidateId) => {
          const current = companionCounts.get(partId).get(candidateId) || 0;
          companionCounts.get(partId).set(candidateId, current + 1);
        });
    });
  });
  return companionCounts;
}

function recentUsageSeries(logs, limit = 6) {
  const monthMap = new Map();
  logs.forEach((log) => {
    const key = new Date(log.created_at).toISOString().slice(0, 7);
    const current = monthMap.get(key) || { key, quantity: 0 };
    current.quantity += Number(log.quantity || 0);
    monthMap.set(key, current);
  });
  return [...monthMap.values()].sort((left, right) => left.key.localeCompare(right.key)).slice(-limit);
}

function htmlEscape(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function insightLink(label, type, key, extraClass = '') {
  if (['part', 'job', 'po'].includes(type)) {
    return `<button type="button" class="insight-link ${extraClass}" data-summary-route="${htmlEscape(type)}" data-summary-key="${htmlEscape(key)}">${htmlEscape(label)}</button>`;
  }
  if (type === 'archived-job') {
    return `<button type="button" class="insight-link ${extraClass}" data-summary-route="job" data-summary-key="${htmlEscape(key)}" data-summary-archive="1">${htmlEscape(label)}</button>`;
  }
  return `<button type="button" class="insight-link ${extraClass}" data-insight-detail="${htmlEscape(type)}" data-insight-key="${htmlEscape(key)}">${htmlEscape(label)}</button>`;
}

function insightBarList(items, emptyMessage = 'No comparison data yet.') {
  const maxValue = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  if (!items.length) {
    return `<div class="empty-state"><p>${emptyMessage}</p></div>`;
  }
  return `
    <div class="insight-bar-list">
      ${items
        .map(
          (item) => `
            <div class="insight-bar-row ${item.tone || ''}">
              <div class="insight-bar-label">${item.label}</div>
              <div class="insight-bar-track"><div class="insight-bar-fill" style="width:${Math.max((Number(item.value || 0) / maxValue) * 100, 8)}%"></div></div>
              <div class="insight-bar-value">${item.valueLabel || item.value}</div>
            </div>
          `,
        )
        .join('')}
    </div>
  `;
}

function recommendationCardMarkup(recommendation) {
  const actionLink =
    recommendation.entityType && recommendation.entityKey !== undefined
      ? `<div class="insight-card-actions">${insightLink(
          recommendation.actionLabel || 'Open detail',
          recommendation.entityType,
          recommendation.entityKey,
          'secondary-link',
        )}</div>`
      : '';
  return `
    <div class="insight-recommendation-card ${recommendation.tone || 'info'}">
      <strong>${htmlEscape(recommendation.title)}</strong>
      <p>${htmlEscape(recommendation.body)}</p>
      ${actionLink}
    </div>
  `;
}

function resetAiInsightsState() {
  aiInsightsState.loading = false;
  aiInsightsState.error = '';
  aiInsightsState.brief = null;
  aiInsightsState.answer = null;
  aiInsightsState.question = '';
  aiInsightsState.contextKey = '';
}

function aiInsightsContextKey(data) {
  return JSON.stringify({
    filters: insightsFilters,
    completedJobs: data.completedJobs.length,
    usageLogs: data.usageLogs.length,
    flags: data.processFlags.map((flag) => flag.id),
    reorder: data.reorderPredictions.slice(0, 5).map((entry) => [entry.partId, entry.daysUntilReorder]),
  });
}

function buildAiInsightsContext(data) {
  const monthlyChangeMetric =
    data.monthlyUsage.length >= 2
      ? Number(
          percentChange(
            data.monthlyUsage[data.monthlyUsage.length - 1].quantity,
            data.monthlyUsage[data.monthlyUsage.length - 2].quantity,
          ).toFixed(0),
        )
      : null;
  const filteredPartIds = [
    ...new Set(
      [
        ...data.mostUsedParts.map((entry) => entry.partId),
        ...data.fastestMovingParts.map((entry) => entry.partId),
        ...data.reorderPredictions.map((entry) => entry.partId),
      ].filter((value) => Number.isFinite(Number(value))),
    ),
  ].map(Number);
  return {
    filters: { ...insightsFilters },
    warehouseId: currentWarehouseId(),
    allowedPartIds: filteredPartIds,
    scope: {
      filters: { ...insightsFilters },
      dateRangeDays: Number(insightsFilters.dateRange || 90),
      jobsAnalyzed: data.completedJobs.length,
      usageLogsAnalyzed: data.usageLogs.length,
      sampling: {
        completedJobs:
          data.completedJobs.length > 25
            ? `sampled first 25 of ${data.completedJobs.length} filtered jobs`
            : `full filtered set (${data.completedJobs.length})`,
        usageHistory:
          data.usageLogs.length > 80
            ? `sampled first 80 of ${data.usageLogs.length} filtered usage records`
            : `full filtered set (${data.usageLogs.length})`,
      },
    },
    overview: {
      completedJobs: data.completedJobs.length,
      usageLogCount: data.usageLogs.length,
      processFlagCount: data.processFlags.length,
      recommendationCount: data.recommendations.length,
    },
    metricsCatalog: [
      { key: 'completed_jobs_count', label: 'Completed jobs analyzed', value: String(data.completedJobs.length) },
      { key: 'usage_log_count', label: 'Usage log records analyzed', value: String(data.usageLogs.length) },
      { key: 'process_flag_count', label: 'Pattern flags in current view', value: String(data.processFlags.length) },
      { key: 'recommendation_count', label: 'Rule-based recommendations', value: String(data.recommendations.length) },
      ...(monthlyChangeMetric === null
        ? []
        : [
            {
              key: 'monthly_usage_change_pct',
              label: 'Latest monthly usage change',
              value: `${monthlyChangeMetric}%`,
            },
          ]),
      ...data.reorderPredictions.slice(0, 10).flatMap((entry) => [
        {
          key: `reorder_days_${entry.partId}`,
          label: `${entry.partNumber} days to reorder`,
          value: entry.daysUntilReorder === null ? 'No forecast yet' : String(entry.daysUntilReorder),
        },
        {
          key: `reorder_qty_${entry.partId}`,
          label: `${entry.partNumber} suggested reorder quantity`,
          value: String(entry.suggestedReorderQty),
        },
      ]),
      ...data.processFlags.slice(0, 10).map((flag) => ({
        key: `flag_${flag.id}`,
        label: flag.title,
        value: flag.body,
      })),
    ],
    anomalies: data.processFlags.map((flag) => ({
      id: flag.id,
      title: flag.title,
      tone: flag.tone,
      body: flag.body,
      records: (flag.records || []).slice(0, 8),
    })),
    reorder: data.reorderPredictions.slice(0, 12).map((entry) => ({
      partId: entry.partId,
      partNumber: entry.partNumber,
      description: entry.description,
      stock: entry.stock,
      reorderPoint: entry.reorderPoint,
      used30: entry.used30,
      used60: entry.used60,
      forecastDaily: Number(entry.forecastDaily.toFixed(2)),
      leadTimeDays: entry.leadTimeDays,
      daysUntilReorder: entry.daysUntilReorder,
      suggestedReorderQty: entry.suggestedReorderQty,
      topCompanion: entry.topCompanion,
    })),
    mostUsedParts: data.mostUsedParts.slice(0, 12),
    fastestMovingParts: data.fastestMovingParts.slice(0, 12),
    commonJobTypes: data.commonJobTypes.slice(0, 10).map((entry) => ({
      title: entry.title,
      count: entry.count,
      avgUsage: Number(entry.avgUsage.toFixed(1)),
      crewCount: entry.crewCount,
    })),
    unusualHighUsageJobs: data.unusualHighUsageJobs.slice(0, 10).map((entry) => ({
      jobNumber: entry.job.job_number,
      title: entry.job.title,
      technician: entry.job.technician,
      totalUsage: entry.totalUsage,
      averageUsage: Number(entry.averageUsage.toFixed(1)),
      createdAt: entry.job.created_at,
    })),
    recommendations: data.recommendations.slice(0, 8),
    monthlyUsage: data.monthlyUsage,
    summaries: data.summaries,
    completedJobs: data.completedJobs.slice(0, 25).map((job) => ({
      id: job.id,
      jobNumber: job.job_number,
      title: job.title,
      technician: job.technician,
      createdAt: job.created_at,
      scheduledFor: job.scheduled_for,
      totalUsage: completedJobUsage(job),
    })),
    usageHistory: data.usageLogs.slice(0, 80).map((log) => ({
      createdAt: log.created_at,
      jobNumber: log.job_number,
      technician: log.technician,
      partNumber: log.part_number,
      quantity: log.quantity,
      notes: log.notes,
    })),
  };
}

async function requestAiInsights(mode = 'brief', question = '') {
  const data = insightsData();
  const contextKey = aiInsightsContextKey(data);
  const cacheKey = `${mode}:${question.trim().toLowerCase()}:${contextKey}`;
  if (aiInsightsCache.has(cacheKey)) {
    const cached = aiInsightsCache.get(cacheKey);
    aiInsightsState.error = '';
    aiInsightsState.loading = false;
    aiInsightsState.contextKey = contextKey;
    if (mode === 'brief') aiInsightsState.brief = cached.response;
    if (mode === 'query') {
      aiInsightsState.answer = cached.response;
      aiInsightsState.question = question;
    }
    renderInsights();
    return;
  }

  aiInsightsState.loading = true;
  aiInsightsState.error = '';
  aiInsightsState.contextKey = contextKey;
  renderInsights();

  try {
    const response = await fetch('/api/insights/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        warehouseId: currentWarehouseId(),
        mode,
        question,
        context: buildAiInsightsContext(data),
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'AI Insights request failed.');
    }
    aiInsightsCache.set(cacheKey, payload);
    if (mode === 'brief') {
      aiInsightsState.brief = payload.response;
    } else {
      aiInsightsState.answer = payload.response;
      aiInsightsState.question = question;
    }
  } catch (error) {
    aiInsightsState.error = error.message || 'AI Insights request failed.';
  } finally {
    aiInsightsState.loading = false;
    renderInsights();
  }
}

function aiResponseMarkup(text) {
  if (!text || typeof text !== 'object') return '';
  const scope = text.scope || {};
  const scopeLines = [
    `Date range: ${scope.dateRangeDays || '--'} days`,
    `Jobs analyzed: ${scope.jobsAnalyzed ?? '--'}`,
    `Usage records analyzed: ${scope.usageLogsAnalyzed ?? '--'}`,
    `Sampling: ${htmlEscape((scope.sampling?.completedJobs || 'Not stated') + '; ' + (scope.sampling?.usageHistory || 'Not stated'))}`,
  ];
  const filters = Object.entries(scope.filters || {})
    .filter(([, value]) => value && value !== 'all')
    .map(([key, value]) => `${key}: ${value}`);
  return `
    <div class="insight-ai-response">
      <p><strong>Answer:</strong> ${htmlEscape(text.answer || 'No answer provided.')}</p>
      <p><strong>Confidence:</strong> ${htmlEscape(text.confidence || 'medium')}</p>
      <p><strong>Scope:</strong> ${scopeLines.join(' | ')}${filters.length ? ` | Filters: ${htmlEscape(filters.join(', '))}` : ''}</p>
      ${text.data_gaps?.length ? `<p><strong>Data Gaps:</strong> ${htmlEscape(text.data_gaps.join(' | '))}</p>` : ''}
      ${
        text.referenced_metrics?.length
          ? `<div><strong>Referenced Metrics:</strong><ul>${text.referenced_metrics
              .map(
                (metric) =>
                  `<li><strong>${htmlEscape(metric.label || metric.metric_key)}:</strong> ${htmlEscape(metric.value || '')}${metric.why_it_matters ? ` - ${htmlEscape(metric.why_it_matters)}` : ''}</li>`,
              )
              .join('')}</ul></div>`
          : ''
      }
      ${
        text.recommended_actions?.length
          ? `<div><strong>Recommended Actions:</strong><ul>${text.recommended_actions
              .map(
                (action) =>
                  `<li><strong>${htmlEscape(action.action)}:</strong> ${htmlEscape(action.rationale || '')}${action.related_part_numbers?.length ? ` | Related parts: ${htmlEscape(action.related_part_numbers.join(', '))}` : ''}</li>`,
              )
              .join('')}</ul></div>`
          : ''
      }
    </div>
  `;
}

function renderInsightDrilldown(data) {
  if (!insightsDrilldown || insightsDrilldown.type === 'overview') {
    return `
      <article class="panel insight-panel insight-panel-wide insight-detail-panel">
        <div class="table-header compact-header">
          <div>
            <h4>Drill-Down Detail</h4>
            <p class="subtle">Click a part number, job type, flag, or recommendation to inspect the supporting records here.</p>
          </div>
        </div>
        <div class="activity-card">
          <strong>Nothing selected yet</strong>
          <p class="subtle">Use the links in the Insights tables and cards above to see usage history, outliers, and reorder pressure in more detail.</p>
        </div>
      </article>
    `;
  }

  if (insightsDrilldown.type === 'part') {
    const partId = Number(insightsDrilldown.key);
    const part = partById(partId);
    const prediction = data.reorderPredictions.find((entry) => Number(entry.partId) === partId);
    const partLogs = data.usageLogs.filter((log) => Number(log.part_id) === partId);
    const partSeries = recentUsageSeries(partLogs, 6);
    const relatedJobs = data.completedJobs
      .map((job) => ({
        job,
        quantity: insightsRequirementsForJob(job.id)
          .filter((requirement) => Number(requirement.part_id) === partId)
          .reduce((sum, requirement) => sum + Number(requirement.pulled_quantity || 0), 0),
      }))
      .filter((entry) => entry.quantity > 0)
      .sort((left, right) => right.quantity - left.quantity)
      .slice(0, 6);
    const companionEntries = [...(data.companionCounts.get(partId)?.entries() || [])]
      .map(([candidateId, count]) => ({ part: partById(candidateId), count }))
      .filter((entry) => entry.part)
      .sort((left, right) => right.count - left.count)
      .slice(0, 5);

    if (!part) {
      insightsDrilldown = { type: 'overview', key: 'overview' };
      return renderInsightDrilldown(data);
    }

    return `
      <article class="panel insight-panel insight-panel-wide insight-detail-panel">
        <div class="table-header compact-header">
          <div>
            <h4>Part Detail</h4>
            <p class="subtle">${htmlEscape(part.part_number)} - ${htmlEscape(part.description)}</p>
          </div>
          <button type="button" class="ghost" data-insight-detail-clear="true">Clear Detail</button>
        </div>
        <div class="insight-detail-stats">
          <div class="activity-card"><strong>${part.stock}</strong><p class="subtle">Current stock</p></div>
          <div class="activity-card"><strong>${prediction?.forecastDaily?.toFixed(2) || '0.00'}</strong><p class="subtle">Forecasted daily usage</p></div>
          <div class="activity-card"><strong>${prediction?.daysUntilReorder === null ? 'No forecast' : prediction.daysUntilReorder === 0 ? 'Now' : prediction.daysUntilReorder}</strong><p class="subtle">Days to reorder point</p></div>
          <div class="activity-card"><strong>${prediction?.suggestedReorderQty || 0}</strong><p class="subtle">Suggested reorder quantity</p></div>
        </div>
        <div class="insights-grid">
          <article class="panel insight-panel">
            <h4>Usage History</h4>
            ${insightBarList(
              partSeries.map((entry) => ({ label: monthLabel(entry.key), value: entry.quantity })),
              'No recent usage history for this part.',
            )}
          </article>
          <article class="panel insight-panel">
            <h4>Related Completed Jobs</h4>
            ${insightTable(
              ['Job', 'Type', 'Qty Used'],
              relatedJobs.map(
                (entry) =>
                  `<tr><td>${insightLink(entry.job.job_number, 'job', entry.job.id)}</td><td>${htmlEscape(entry.job.title)}</td><td>${entry.quantity}</td></tr>`,
              ),
              'This part has not been tied to completed jobs in the current view.',
            )}
          </article>
          <article class="panel insight-panel insight-panel-wide">
            <h4>Frequently Used Together</h4>
            ${insightTable(
              ['Part', 'Jobs Together'],
              companionEntries.map(
                (entry) =>
                  `<tr><td>${insightLink(entry.part.part_number, 'part', entry.part.id)}</td><td>${entry.count}</td></tr>`,
              ),
              'No repeat pairings found for this part yet.',
            )}
          </article>
        </div>
      </article>
    `;
  }

  if (insightsDrilldown.type === 'job-type') {
    const title = String(insightsDrilldown.key);
    const matchingJobs = data.completedJobs.filter((job) => job.title === title);
    if (!matchingJobs.length) {
      insightsDrilldown = { type: 'overview', key: 'overview' };
      return renderInsightDrilldown(data);
    }
    const avgUsage =
      matchingJobs.reduce((sum, job) => sum + completedJobUsage(job), 0) / Math.max(matchingJobs.length, 1);
    const outliers = matchingJobs
      .map((job) => ({ job, usage: completedJobUsage(job) }))
      .filter((entry) => entry.usage > avgUsage * 1.25 && entry.usage >= avgUsage + 2)
      .sort((left, right) => right.usage - left.usage);
    const topParts = [
      ...matchingJobs
        .reduce((totals, job) => {
          insightsRequirementsForJob(job.id)
            .filter((requirement) => Number(requirement.pulled_quantity || 0) > 0)
            .forEach((requirement) => {
              const key = String(requirement.part_id);
              const current = totals.get(key) || {
                partId: Number(requirement.part_id),
                partNumber: requirement.part_number,
                quantity: 0,
              };
              current.quantity += Number(requirement.pulled_quantity || 0);
              totals.set(key, current);
            });
          return totals;
        }, new Map())
        .values(),
    ]
      .sort((left, right) => right.quantity - left.quantity)
      .slice(0, 8);

    return `
      <article class="panel insight-panel insight-panel-wide insight-detail-panel">
        <div class="table-header compact-header">
          <div>
            <h4>Job Type Detail</h4>
            <p class="subtle">${htmlEscape(title)}</p>
          </div>
          <button type="button" class="ghost" data-insight-detail-clear="true">Clear Detail</button>
        </div>
        <div class="insight-detail-stats">
          <div class="activity-card"><strong>${matchingJobs.length}</strong><p class="subtle">Completed jobs in view</p></div>
          <div class="activity-card"><strong>${avgUsage.toFixed(1)}</strong><p class="subtle">Average parts used</p></div>
          <div class="activity-card"><strong>${outliers.length}</strong><p class="subtle">Outlier jobs</p></div>
        </div>
        <div class="insights-grid">
          <article class="panel insight-panel">
            <h4>Most Used Parts for This Job Type</h4>
            ${insightTable(
              ['Part', 'Qty Used'],
              topParts.map(
                (entry) =>
                  `<tr><td>${insightLink(entry.partNumber, 'part', entry.partId)}</td><td>${entry.quantity}</td></tr>`,
              ),
              'No part history available for this job type.',
            )}
          </article>
          <article class="panel insight-panel">
            <h4>Outlier Jobs</h4>
            ${insightTable(
              ['Job', 'Parts Used'],
              outliers.map(
                (entry) =>
                  `<tr><td>${insightLink(entry.job.job_number, 'job', entry.job.id)}</td><td>${entry.usage}</td></tr>`,
              ),
              'No outlier jobs for this job type in the current view.',
            )}
          </article>
        </div>
      </article>
    `;
  }

  if (insightsDrilldown.type === 'job') {
    const jobId = Number(insightsDrilldown.key);
    const job = [...(state.completedJobs || []), ...(state.jobs || [])].find((entry) => Number(entry.id) === jobId);
    if (!job) {
      insightsDrilldown = { type: 'overview', key: 'overview' };
      return renderInsightDrilldown(data);
    }
    const requirements = insightsRequirementsForJob(job.id).sort(
      (left, right) => Number(right.pulled_quantity || 0) - Number(left.pulled_quantity || 0),
    );
    return `
      <article class="panel insight-panel insight-panel-wide insight-detail-panel">
        <div class="table-header compact-header">
          <div>
            <h4>Job Detail</h4>
            <p class="subtle">${htmlEscape(job.job_number)} - ${htmlEscape(job.title)}</p>
          </div>
          <button type="button" class="ghost" data-insight-detail-clear="true">Clear Detail</button>
        </div>
        ${insightTable(
          ['Part', 'Required', 'Pulled'],
          requirements.map(
            (requirement) =>
              `<tr><td>${insightLink(requirement.part_number, 'part', requirement.part_id)}</td><td>${requirement.required_quantity}</td><td>${requirement.pulled_quantity}</td></tr>`,
          ),
          'No filtered part usage available for this job.',
        )}
      </article>
    `;
  }

  if (insightsDrilldown.type === 'flag') {
    const flag = data.flagMap.get(String(insightsDrilldown.key));
    if (!flag) {
      insightsDrilldown = { type: 'overview', key: 'overview' };
      return renderInsightDrilldown(data);
    }
    return `
      <article class="panel insight-panel insight-panel-wide insight-detail-panel">
        <div class="table-header compact-header">
          <div>
            <h4>Flag Detail</h4>
            <p class="subtle">${htmlEscape(flag.title)}</p>
          </div>
          <button type="button" class="ghost" data-insight-detail-clear="true">Clear Detail</button>
        </div>
        <div class="insight-flag-card ${flag.tone}"><strong>${htmlEscape(flag.title)}</strong><p>${htmlEscape(flag.body)}</p></div>
        ${
          flag.records?.length
            ? insightTable(
                ['Record', 'Context', 'Value'],
                flag.records.map(
                  (record) =>
                    `<tr><td>${record.linkType ? insightLink(record.label, record.linkType, record.linkKey) : htmlEscape(record.label)}</td><td>${htmlEscape(record.context || '')}</td><td>${htmlEscape(record.value || '')}</td></tr>`,
                ),
                'No underlying records were captured for this flag.',
              )
            : '<div class="empty-state"><p>No underlying records were captured for this flag.</p></div>'
        }
      </article>
    `;
  }

  return '';
}

function insightsData() {
  const { dateRangeDays, jobLookup, completedJobs, activeJobs, usageLogs, purchaseOrders, incompleteRequirements } =
    filteredInsightsInputs();
  const usage30 = filteredInsightsUsageLogsWithinDays(30, jobLookup);
  const usage60 = filteredInsightsUsageLogsWithinDays(60, jobLookup);
  const usage90 = filteredInsightsUsageLogsWithinDays(90, jobLookup);
  const recentWindowDays = Math.min(dateRangeDays, 30);
  const previousWindowEnd = daysAgoDate(recentWindowDays);
  const previousWindowStart = daysAgoDate(recentWindowDays * 2);
  const recentWindowLogs = usageLogs.filter((log) => new Date(log.created_at) >= daysAgoDate(recentWindowDays));
  const previousWindowLogs = (state.usageLogs || []).filter((log) => {
    const logDate = new Date(log.created_at);
    return (
      logDate >= previousWindowStart &&
      logDate < previousWindowEnd &&
      matchesInsightsUsageLog(log, previousWindowStart, jobLookup)
    );
  });

  const usageTotals = quantityByPartLogs(usageLogs);
  const mostUsedParts = [...usageTotals.values()].sort((left, right) => right.quantity - left.quantity).slice(0, 8);
  const fastestMovingParts = [...quantityByPartLogs(recentWindowLogs).values()]
    .map((entry) => ({ ...entry, perWeek: Number(((entry.quantity / Math.max(recentWindowDays, 1)) * 7).toFixed(1)) }))
    .sort((left, right) => right.perWeek - left.perWeek)
    .slice(0, 8);

  const jobTypeCounts = completedJobs.reduce((counts, job) => {
    const key = job.title || 'Uncategorized Job';
    const current = counts.get(key) || { title: key, count: 0, totalUsage: 0, crews: new Set() };
    current.count += 1;
    current.totalUsage += completedJobUsage(job);
    current.crews.add(job.technician);
    counts.set(key, current);
    return counts;
  }, new Map());
  const commonJobTypes = [...jobTypeCounts.values()]
    .map((entry) => ({ ...entry, avgUsage: entry.totalUsage / Math.max(entry.count, 1), crewCount: entry.crews.size }))
    .sort((left, right) => right.count - left.count);
  const repeatedJobTypes = commonJobTypes.filter((entry) => entry.count > 1).slice(0, 6);

  const unusualHighUsageJobs = completedJobs
    .map((job) => {
      const totalUsage = completedJobUsage(job);
      const titleGroup = commonJobTypes.find((entry) => entry.title === job.title);
      const averageUsage = titleGroup ? titleGroup.avgUsage : totalUsage;
      return { job, totalUsage, averageUsage };
    })
    .filter((entry) => entry.totalUsage >= entry.averageUsage + 2 && entry.totalUsage > entry.averageUsage * 1.25)
    .sort((left, right) => right.totalUsage - left.totalUsage)
    .slice(0, 8);

  const overpullRequirements = [...(state.jobRequirements || [])]
    .map((requirement) => {
      const relatedJob = [...activeJobs, ...completedJobs].find((job) => Number(job.id) === Number(requirement.job_id));
      const part = partById(requirement.part_id);
      if (!relatedJob || !matchesInsightsPart(part)) return null;
      const overpullQuantity = Number(requirement.pulled_quantity || 0) - Number(requirement.required_quantity || 0);
      if (overpullQuantity <= 0) return null;
      return { relatedJob, part, overpullQuantity };
    })
    .filter(Boolean)
    .sort((left, right) => right.overpullQuantity - left.overpullQuantity);

  const overpullByPart = overpullRequirements.reduce((counts, entry) => {
    const key = String(entry.part.id);
    const current = counts.get(key) || {
      partId: Number(entry.part.id),
      partNumber: entry.part.part_number,
      count: 0,
      quantity: 0,
      records: [],
    };
    current.count += 1;
    current.quantity += entry.overpullQuantity;
    current.records.push({
      label: entry.relatedJob.job_number,
      linkType: 'job',
      linkKey: entry.relatedJob.id,
      context: entry.relatedJob.title,
      value: `+${entry.overpullQuantity} over`,
    });
    counts.set(key, current);
    return counts;
  }, new Map());

  const usageSpikes = state.parts
    .filter((part) => matchesInsightsPart(part))
    .map((part) => {
      const recent = sumUsageForPart(recentWindowLogs, part.id);
      const previous = sumUsageForPart(previousWindowLogs, part.id);
      return {
        partId: Number(part.id),
        partNumber: part.part_number,
        recent,
        previous,
        changePct: Number(percentChange(recent, previous).toFixed(0)),
      };
    })
    .filter((entry) => entry.recent >= entry.previous + 3 && entry.recent >= Math.max(entry.previous * 1.5, 4))
    .sort((left, right) => right.changePct - left.changePct)
    .slice(0, 6);

  const extraUsageLogs = usageLogs.filter((log) => {
    const note = String(log.notes || '').toLowerCase();
    return note.includes('extra') || note.includes('misc');
  });
  const extraUsageByJobType = extraUsageLogs.reduce((counts, log) => {
    const key = jobLookup.get(String(log.job_number))?.title || 'Unassigned';
    const current = counts.get(key) || { title: key, count: 0 };
    current.count += 1;
    counts.set(key, current);
    return counts;
  }, new Map());

  const vendorShortages = incompleteRequirements.reduce((counts, requirement) => {
    const part = partById(requirement.part_id);
    const vendor = vendorById(part?.vendor_id);
    const key = String(vendor?.id || 'unassigned');
    const current = counts.get(key) || {
      vendorId: vendor?.id || 'unassigned',
      vendorName: vendor?.name || 'Unassigned vendor',
      count: 0,
      shortfall: 0,
      records: [],
    };
    const relatedJob = jobById(requirement.job_id);
    current.count += 1;
    current.shortfall += Number(requirement.required_quantity || 0) - Number(requirement.pulled_quantity || 0);
    current.records.push({
      label: relatedJob?.job_number || `Job ${requirement.job_id}`,
      linkType: 'job',
      linkKey: relatedJob?.id || requirement.job_id,
      context: part?.part_number || requirement.part_number,
      value: `${Number(requirement.required_quantity || 0) - Number(requirement.pulled_quantity || 0)} short`,
    });
    counts.set(key, current);
    return counts;
  }, new Map());

  const reorderedOften = purchaseOrders.reduce((counts, po) => {
    (po.lines || []).forEach((line) => {
      const part = partById(line.part_id);
      if (!matchesInsightsPart(part)) return;
      const key = String(line.part_id);
      const current = counts.get(key) || {
        partId: Number(line.part_id),
        partNumber: line.part_number,
        count: 0,
        records: [],
      };
      current.count += 1;
      current.records.push({
        label: po.po_number,
        context: vendorName(po.vendor_id),
        value: `${line.quantity_ordered} ordered`,
      });
      counts.set(key, current);
    });
    return counts;
  }, new Map());

  const companionCounts = buildCompanionCounts(completedJobs);
  const reorderPredictions = state.parts
    .filter((part) => !isNonStock(part) && matchesInsightsPart(part))
    .map((part) => {
      const vendor = vendorById(part.vendor_id);
      const used30 = sumUsageForPart(usage30, part.id);
      const used60 = sumUsageForPart(usage60, part.id);
      const used90 = sumUsageForPart(usage90, part.id);
      const forecastDaily = (used30 / 30) * 0.5 + (used60 / 60) * 0.3 + (used90 / 90) * 0.2;
      const leadTimeDays = Number(vendor?.lead_time_days || vendor?.leadTimeDays || 7);
      const availableBeforeReorder = Number(part.stock || 0) - Number(part.reorder_point || 0);
      let daysUntilReorder = null;
      if (forecastDaily > 0) {
        daysUntilReorder =
          availableBeforeReorder <= 0 ? 0 : Number((availableBeforeReorder / forecastDaily).toFixed(1));
      }
      const suggestedReorderQty = Math.max(
        Math.ceil(forecastDaily * (leadTimeDays + 14) + Number(part.reorder_point || 0) - Number(part.stock || 0)),
        Number(part.stock || 0) <= Number(part.reorder_point || 0) ? Number(part.reorder_point || 0) : 0,
      );
      const topCompanion = [...(companionCounts.get(Number(part.id))?.entries() || [])]
        .map(([candidateId, count]) => ({ candidate: partById(candidateId), count }))
        .filter((entry) => entry.candidate)
        .sort((left, right) => right.count - left.count)[0];
      return {
        partId: Number(part.id),
        partNumber: part.part_number,
        description: part.description,
        stock: Number(part.stock || 0),
        reorderPoint: Number(part.reorder_point || 0),
        used30,
        used60,
        forecastDaily,
        leadTimeDays,
        daysUntilReorder,
        suggestedReorderQty,
        topCompanion: topCompanion ? topCompanion.candidate.part_number : null,
        pressureScore:
          Number(part.stock || 0) <= Number(part.reorder_point || 0)
            ? 100
            : daysUntilReorder === null
              ? 0
              : Math.max(1, Math.round(((leadTimeDays + 14) / Math.max(daysUntilReorder, 1)) * 100)),
      };
    })
    .filter((entry) => entry.used60 > 0 || entry.stock <= entry.reorderPoint)
    .sort(
      (left, right) =>
        (left.daysUntilReorder ?? Number.POSITIVE_INFINITY) - (right.daysUntilReorder ?? Number.POSITIVE_INFINITY),
    )
    .slice(0, 10);

  const processFlags = [];
  const overallAvgUsage =
    completedJobs.reduce((sum, job) => sum + completedJobUsage(job), 0) / Math.max(completedJobs.length, 1);
  const highestJobTypePressure = commonJobTypes
    .filter((entry) => entry.count > 1 && entry.avgUsage > overallAvgUsage * 1.15)
    .sort((left, right) => right.avgUsage - left.avgUsage)[0];
  if (highestJobTypePressure) {
    processFlags.push({
      id: `flag-jobtype-${highestJobTypePressure.title}`,
      tone: 'warning',
      priority: 5,
      title: 'Job Type Using More Material Than Expected',
      body: `${highestJobTypePressure.title} is averaging ${highestJobTypePressure.avgUsage.toFixed(1)} parts per job, above the overall completed-job average of ${overallAvgUsage.toFixed(1)}.`,
      records: unusualHighUsageJobs
        .filter((entry) => entry.job.title === highestJobTypePressure.title)
        .slice(0, 6)
        .map((entry) => ({
          label: entry.job.job_number,
          linkType: 'job',
          linkKey: entry.job.id,
          context: entry.job.technician,
          value: `${entry.totalUsage} used vs ${entry.averageUsage.toFixed(1)} avg`,
        })),
    });
  }
  const topOverpull = [...overpullByPart.values()].sort((left, right) => right.quantity - left.quantity)[0];
  if (topOverpull) {
    processFlags.push({
      id: `flag-overpull-${topOverpull.partId}`,
      tone: 'warning',
      priority: 5,
      title: 'Repeated Over-Pull Pattern',
      body: `${topOverpull.partNumber} has been over-pulled across ${topOverpull.count} job record(s), totaling ${topOverpull.quantity} extra unit(s).`,
      records: topOverpull.records,
    });
  }
  const topSpike = usageSpikes[0];
  if (topSpike) {
    processFlags.push({
      id: `flag-spike-${topSpike.partId}`,
      tone: 'warning',
      priority: 4,
      title: 'Unusual Usage Spike',
      body: `${topSpike.partNumber} jumped from ${topSpike.previous} to ${topSpike.recent} units between the last two comparison windows, a ${topSpike.changePct}% increase.`,
      records: usageSpikes.map((entry) => ({
        label: entry.partNumber,
        linkType: 'part',
        linkKey: entry.partId,
        context: `${entry.previous} -> ${entry.recent}`,
        value: `${entry.changePct}% change`,
      })),
    });
  }
  const topReordered = [...reorderedOften.values()].sort((left, right) => right.count - left.count)[0];
  if (topReordered && topReordered.count > 1) {
    processFlags.push({
      id: `flag-reorder-${topReordered.partId}`,
      tone: 'info',
      priority: 3,
      title: 'Frequently Reordered Part',
      body: `${topReordered.partNumber} has appeared on ${topReordered.count} purchase orders in the selected window, suggesting recurring replenishment pressure.`,
      records: topReordered.records,
    });
  }
  const topVendorShortage = [...vendorShortages.values()].sort((left, right) => right.shortfall - left.shortfall)[0];
  if (topVendorShortage) {
    processFlags.push({
      id: `flag-vendor-${topVendorShortage.vendorId}`,
      tone: 'warning',
      priority: 4,
      title: 'Vendor Linked to Repeated Shortages',
      body: `${topVendorShortage.vendorName} is tied to ${topVendorShortage.count} active shortfall record(s), totaling ${topVendorShortage.shortfall} unit(s) still needed.`,
      records: topVendorShortage.records,
    });
  }
  const topExtraJobType = [...extraUsageByJobType.values()].sort((left, right) => right.count - left.count)[0];
  if (topExtraJobType && topExtraJobType.count > 1) {
    processFlags.push({
      id: `flag-extra-${topExtraJobType.title}`,
      tone: 'info',
      priority: 2,
      title: 'Repeated Extra Usage Notes',
      body: `${topExtraJobType.title} logged ${topExtraJobType.count} extra or miscellaneous usage note(s), which may point to a repeat material-planning issue.`,
      records: extraUsageLogs
        .filter((log) => (jobLookup.get(String(log.job_number))?.title || 'Unassigned') === topExtraJobType.title)
        .slice(0, 8)
        .map((log) => ({
          label: log.job_number,
          linkType: 'job',
          linkKey: jobLookup.get(String(log.job_number))?.id || 0,
          context: log.part_number,
          value: log.notes || 'Extra usage',
        })),
    });
  }
  processFlags.sort((left, right) => right.priority - left.priority);
  const flagMap = processFlags.reduce((map, flag) => map.set(String(flag.id), flag), new Map());

  const monthlyUsage = recentUsageSeries(usageLogs, 6);
  const monthlyChange =
    monthlyUsage.length >= 2
      ? percentChange(monthlyUsage[monthlyUsage.length - 1].quantity, monthlyUsage[monthlyUsage.length - 2].quantity)
      : 0;

  const recommendations = [];
  const topPressure = reorderPredictions[0];
  if (
    topPressure &&
    topPressure.daysUntilReorder !== null &&
    topPressure.daysUntilReorder <= topPressure.leadTimeDays + 7
  ) {
    recommendations.push({
      tone: 'warning',
      title: 'Consider increasing stock coverage',
      body: `${topPressure.partNumber} is projected to reach its reorder point in ${topPressure.daysUntilReorder} day(s), close to its ${topPressure.leadTimeDays}-day lead time.`,
      entityType: 'part',
      entityKey: topPressure.partId,
      actionLabel: 'Review part detail',
    });
  }
  const frequentNonStock = mostUsedParts
    .map((entry) => ({ ...entry, part: partById(entry.partId) }))
    .find((entry) => entry.part && isNonStock(entry.part) && entry.quantity >= 4);
  if (frequentNonStock) {
    recommendations.push({
      tone: 'info',
      title: 'Consider changing a non-stock item to stocked',
      body: `${frequentNonStock.partNumber} has been used ${frequentNonStock.quantity} times in the current view even though it is marked non-stock.`,
      entityType: 'part',
      entityKey: frequentNonStock.partId,
      actionLabel: 'Open part detail',
    });
  }
  if (highestJobTypePressure) {
    recommendations.push({
      tone: 'warning',
      title: 'Review repeated overuse on a job type',
      body: `${highestJobTypePressure.title} is consuming more material than the rest of the completed-job mix, so it is a good candidate for scope or kit review.`,
      entityType: 'job-type',
      entityKey: highestJobTypePressure.title,
      actionLabel: 'Open job type detail',
    });
  }
  if (topVendorShortage) {
    recommendations.push({
      tone: 'info',
      title: 'Review vendor lead time or reorder cycle',
      body: `${topVendorShortage.vendorName} is tied to the largest active shortfall in the current view, which may justify a lead-time or cadence review.`,
      entityType: 'flag',
      entityKey: `flag-vendor-${topVendorShortage.vendorId}`,
      actionLabel: 'Open shortage detail',
    });
  }

  const summaries = [];
  if (monthlyUsage.length >= 2) {
    const direction = monthlyChange >= 0 ? 'rose' : 'fell';
    summaries.push(
      `Overall part usage ${direction} ${Math.abs(monthlyChange).toFixed(0)}% from ${monthLabel(monthlyUsage[monthlyUsage.length - 2].key)} to ${monthLabel(monthlyUsage[monthlyUsage.length - 1].key)}, which changes how quickly current stock will be consumed.`,
    );
  }
  if (topPressure) {
    summaries.push(
      `${topPressure.partNumber} is carrying the highest reorder pressure in this view${topPressure.daysUntilReorder === null ? ', but it still needs more usage history before the system can estimate timing.' : ` and is projected to touch its reorder point in about ${topPressure.daysUntilReorder} day(s), which matters because the vendor lead time is ${topPressure.leadTimeDays} day(s).`}`,
    );
  }
  if (processFlags[0]) summaries.push(`${processFlags[0].title}: ${processFlags[0].body}`);
  if (recommendations[0]) summaries.push(`${recommendations[0].title}: ${recommendations[0].body}`);

  return {
    completedJobs,
    usageLogs,
    mostUsedParts,
    fastestMovingParts,
    commonJobTypes,
    repeatedJobTypes,
    unusualHighUsageJobs,
    reorderPredictions,
    processFlags,
    flagMap,
    monthlyUsage,
    summaries,
    recommendations,
    companionCounts,
    topMovingBars: fastestMovingParts.slice(0, 6).map((entry) => ({
      label: entry.partNumber,
      value: entry.perWeek,
      valueLabel: `${entry.perWeek}/wk`,
    })),
    jobTypeComparisonBars: commonJobTypes.slice(0, 6).map((entry) => ({
      label: entry.title,
      value: Number(entry.avgUsage.toFixed(1)),
      valueLabel: `${entry.avgUsage.toFixed(1)} avg`,
    })),
    reorderPressureBars: reorderPredictions.slice(0, 6).map((entry) => ({
      label: entry.partNumber,
      value: entry.pressureScore,
      valueLabel:
        entry.daysUntilReorder === null ? 'watch' : entry.daysUntilReorder === 0 ? 'Now' : `${entry.daysUntilReorder}d`,
    })),
    issuePatternBars: [
      { label: 'Over-pulls', value: overpullRequirements.length },
      { label: 'Shortages', value: incompleteRequirements.length },
      { label: 'Extra usage notes', value: extraUsageLogs.length },
      { label: 'Usage spikes', value: usageSpikes.length },
      { label: 'Repeat reorders', value: [...reorderedOften.values()].filter((entry) => entry.count > 1).length },
    ],
  };
}

function renderInsights() {
  const root = document.querySelector('#insights-page');
  if (!root) return;
  const data = insightsData();
  const currentAiContextKey = aiInsightsContextKey(data);
  if (aiInsightsState.contextKey && aiInsightsState.contextKey !== currentAiContextKey && !aiInsightsState.loading) {
    aiInsightsState.brief = null;
    aiInsightsState.answer = null;
    aiInsightsState.question = '';
    aiInsightsState.error = '';
    aiInsightsState.contextKey = currentAiContextKey;
  } else if (!aiInsightsState.contextKey) {
    aiInsightsState.contextKey = currentAiContextKey;
  }
  const maxMonthlyUsage = Math.max(...data.monthlyUsage.map((entry) => entry.quantity), 1);
  const jobTypes = [...new Set((state.completedJobs || []).map((job) => job.title).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
  const vendors = [...(state.vendors || [])].sort((left, right) => left.name.localeCompare(right.name));
  const partCategories = [...new Set((state.parts || []).map((part) => part.category || 'Uncategorized'))].sort(
    (a, b) => a.localeCompare(b),
  );
  const crews = [
    ...new Set([...(state.jobs || []), ...(state.completedJobs || [])].map((job) => job.technician).filter(Boolean)),
  ].sort((a, b) => a.localeCompare(b));
  const warehouses = [
    ...new Set(
      [
        ...(state.parts || []).map((part) => part.warehouse_id),
        ...(state.jobs || []).map((job) => job.warehouse_id),
        ...(state.completedJobs || []).map((job) => job.warehouse_id),
      ].filter(Boolean),
    ),
  ]
    .map((warehouseId) => warehouseById(warehouseId))
    .filter(Boolean)
    .sort((left, right) => left.name.localeCompare(right.name));

  root.innerHTML = `
    <article class="panel insight-panel">
      <div class="table-header compact-header">
        <div>
          <h4>Insight Filters</h4>
          <p class="subtle">Narrow the view without changing the deterministic decision rules.</p>
        </div>
      </div>
      <div class="inventory-filters insights-filters insights-filter-grid">
        <label>Date Range<select id="insights-date-range"><option value="30" ${insightsFilters.dateRange === '30' ? 'selected' : ''}>Last 30 days</option><option value="60" ${insightsFilters.dateRange === '60' ? 'selected' : ''}>Last 60 days</option><option value="90" ${insightsFilters.dateRange === '90' ? 'selected' : ''}>Last 90 days</option><option value="180" ${insightsFilters.dateRange === '180' ? 'selected' : ''}>Last 180 days</option></select></label>
        <label>Job Type<select id="insights-job-type"><option value="all">All Job Types</option>${jobTypes.map((title) => `<option value="${htmlEscape(title)}" ${insightsFilters.jobType === title ? 'selected' : ''}>${htmlEscape(title)}</option>`).join('')}</select></label>
        <label>Vendor<select id="insights-vendor"><option value="all">All Vendors</option>${vendors.map((vendor) => `<option value="${vendor.id}" ${insightsFilters.vendor === String(vendor.id) ? 'selected' : ''}>${htmlEscape(vendor.name)}</option>`).join('')}</select></label>
        <label>Part Category<select id="insights-part-category"><option value="all">All Categories</option>${partCategories.map((category) => `<option value="${htmlEscape(category)}" ${insightsFilters.partCategory === category ? 'selected' : ''}>${htmlEscape(category)}</option>`).join('')}</select></label>
        <label>Item Type<select id="insights-part-type"><option value="all">All Items</option><option value="stocked" ${insightsFilters.partType === 'stocked' ? 'selected' : ''}>Stocked</option><option value="non_stock" ${insightsFilters.partType === 'non_stock' ? 'selected' : ''}>Non-Stock</option></select></label>
        <label>Warehouse<select id="insights-warehouse"><option value="all">All Loaded Warehouses</option>${warehouses.map((warehouse) => `<option value="${warehouse.id}" ${insightsFilters.warehouseId === String(warehouse.id) ? 'selected' : ''}>${htmlEscape(warehouse.name)}</option>`).join('')}</select></label>
        <label>Crew / Installer<select id="insights-crew"><option value="all">All Crews</option>${crews.map((crew) => `<option value="${htmlEscape(crew)}" ${insightsFilters.crew === crew ? 'selected' : ''}>${htmlEscape(crew)}</option>`).join('')}</select></label>
      </div>
    </article>
    <div class="metrics metrics-dashboard insights-metrics insights-metrics-four">
      <button type="button" class="metric-card metric-button metric-warn" data-summary-open="insights-reorder-watch"><p class="eyebrow">Reorder Watch</p><strong>${data.reorderPredictions[0]?.daysUntilReorder === 0 ? 'Now' : (data.reorderPredictions[0]?.daysUntilReorder ?? '--')}</strong><p class="subtle">Closest estimated days to reorder in this filtered view</p></button>
      <button type="button" class="metric-card metric-button ${data.processFlags.length ? 'metric-danger' : 'metric-good'}" data-summary-open="insights-pattern-flags"><p class="eyebrow">Pattern Flags</p><strong>${data.processFlags.length}</strong><p class="subtle">Specific issues worth reviewing first</p></button>
      <button type="button" class="metric-card metric-button" data-summary-open="insights-recommendations"><p class="eyebrow">Recommendations</p><strong>${data.recommendations.length}</strong><p class="subtle">Rule-based suggestions from the current data</p></button>
      <button type="button" class="metric-card metric-button" data-summary-open="insights-completed-jobs"><p class="eyebrow">Completed Jobs</p><strong>${data.completedJobs.length}</strong><p class="subtle">Finished jobs included in this analysis</p></button>
    </div>
    <article class="panel insight-panel insight-panel-wide">
      <div class="table-header compact-header">
        <div><h4>Pattern / Anomaly Flags</h4><p class="subtle">Each flag is clickable so you can inspect the records behind it.</p></div>
      </div>
      <div class="insight-flags-list">
        ${data.processFlags.length ? data.processFlags.map((flag) => `<button type="button" class="insight-flag-card ${flag.tone}" data-insight-detail="flag" data-insight-key="${htmlEscape(flag.id)}"><strong>${htmlEscape(flag.title)}</strong><p>${htmlEscape(flag.body)}</p></button>`).join('') : emptyState()}
      </div>
    </article>
    <article class="panel insight-panel insight-panel-wide">
      <div class="table-header compact-header">
        <div><h4>Actionable Recommendations</h4><p class="subtle">These suggestions are rule-based and come directly from archive and usage patterns.</p></div>
      </div>
      <div class="insight-recommendations-grid">
        ${data.recommendations.length ? data.recommendations.map((recommendation) => recommendationCardMarkup(recommendation)).join('') : emptyState()}
      </div>
    </article>
    <article class="panel insight-panel insight-panel-wide">
      <div class="table-header compact-header">
        <div><h4>Ask Insights</h4><p class="subtle">Use AI to interpret the current filtered data in plain English. Answers are grounded in the live app data sent with this view.</p></div>
      </div>
      <div class="activity-card insight-ai-note"><p class="subtle">AI summaries interpret current filtered data and do not replace underlying counts or reorder calculations.</p></div>
      <div class="insight-ai-toolbar">
        <button type="button" class="secondary" id="insights-ai-brief-button">${aiInsightsState.brief ? 'Refresh AI Brief' : 'Generate AI Brief'}</button>
        <form id="insights-ai-form" class="insights-ai-form">
          <input id="insights-ai-question" type="text" placeholder="Ask: What should I reorder this week?" value="${htmlEscape(aiInsightsState.question)}" />
          <button type="submit" class="primary">Ask Data</button>
        </form>
      </div>
      ${
        aiInsightsState.loading
          ? '<div class="activity-card"><strong>AI is analyzing the current view...</strong><p class="subtle">This uses the same parts, jobs, usage history, reorder forecast, and anomaly context shown on the page.</p></div>'
          : ''
      }
      ${
        aiInsightsState.error
          ? `<div class="activity-card"><strong>AI unavailable</strong><p class="subtle">${htmlEscape(aiInsightsState.error)}</p></div>`
          : ''
      }
      ${
        aiInsightsState.brief
          ? `<div class="activity-card"><strong>AI Brief</strong>${aiResponseMarkup(aiInsightsState.brief)}</div>`
          : '<div class="activity-card"><strong>AI Brief</strong><p class="subtle">Generate an AI brief to get a context-aware explanation of the current trends, risks, and likely next actions.</p></div>'
      }
      ${
        aiInsightsState.answer
          ? `<div class="activity-card"><strong>Ask Data: ${htmlEscape(aiInsightsState.question || 'Latest question')}</strong>${aiResponseMarkup(aiInsightsState.answer)}</div>`
          : ''
      }
    </article>
    <article class="panel insight-panel insight-panel-wide">
      <div class="table-header compact-header">
        <div><h4>Plain-English Summary</h4><p class="subtle">This summary explains what changed, why it matters, and what may need attention.</p></div>
      </div>
      <div class="insight-summary-list">
        ${data.summaries.length ? data.summaries.map((item) => `<div class="activity-card"><p>${htmlEscape(item)}</p></div>`).join('') : emptyState()}
      </div>
    </article>
    <div class="insights-grid">
      <article class="panel insight-panel insight-panel-wide">
        <h4>Reorder Forecast</h4>
        <p class="subtle">Forecast blends 30-day, 60-day, and 90-day demand, then compares that pace against reorder point, stock on hand, and vendor lead time.</p>
        ${insightTable(
          ['Part', '30d', '60d', 'Forecast / Day', 'Lead Time', 'Days To Reorder', 'Suggested Qty'],
          data.reorderPredictions.map(
            (entry) =>
              `<tr><td>${insightLink(entry.partNumber, 'part', entry.partId)}<div class="subtle">${htmlEscape(entry.description || '')}${entry.topCompanion ? ` | Often with ${htmlEscape(entry.topCompanion)}` : ''}</div></td><td>${entry.used30}</td><td>${entry.used60}</td><td>${entry.forecastDaily.toFixed(2)}</td><td>${entry.leadTimeDays}d</td><td>${entry.daysUntilReorder === null ? 'No forecast yet' : entry.daysUntilReorder === 0 ? 'Now' : entry.daysUntilReorder}</td><td>${entry.suggestedReorderQty}</td></tr>`,
          ),
          'Not enough usage history yet for reorder forecasting.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Usage Over Time</h4>
        <div class="insight-bar-list">
          ${data.monthlyUsage.length ? data.monthlyUsage.map((entry) => `<div class="insight-bar-row"><div class="insight-bar-label">${monthLabel(entry.key)}</div><div class="insight-bar-track"><div class="insight-bar-fill" style="width:${Math.max((entry.quantity / maxMonthlyUsage) * 100, 8)}%"></div></div><div class="insight-bar-value">${entry.quantity}</div></div>`).join('') : emptyState()}
        </div>
      </article>
      <article class="panel insight-panel">
        <h4>Top Moving Parts</h4>
        ${insightBarList(data.topMovingBars, 'No fast-moving parts in the current view.')}
      </article>
      <article class="panel insight-panel">
        <h4>Job Type Comparison</h4>
        ${insightBarList(data.jobTypeComparisonBars, 'No completed job comparison data available yet.')}
      </article>
      <article class="panel insight-panel">
        <h4>Reorder Pressure</h4>
        ${insightBarList(data.reorderPressureBars, 'No reorder pressure to compare right now.')}
      </article>
      <article class="panel insight-panel">
        <h4>Repeated Issue Patterns</h4>
        ${insightBarList(data.issuePatternBars, 'No repeat issue patterns in this view.')}
      </article>
      <article class="panel insight-panel">
        <h4>Most Used Parts</h4>
        ${insightTable(
          ['Part', 'Used', 'Touches'],
          data.mostUsedParts.map(
            (entry) =>
              `<tr><td>${insightLink(entry.partNumber, 'part', entry.partId)}<div class="subtle">${htmlEscape(entry.description || '')}</div></td><td>${entry.quantity}</td><td>${entry.hits}</td></tr>`,
          ),
          'No part usage yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Most Common Job Types</h4>
        ${insightTable(
          ['Job Type', 'Completed', 'Avg Parts Used'],
          data.commonJobTypes
            .slice(0, 8)
            .map(
              (entry) =>
                `<tr><td>${insightLink(entry.title, 'job-type', entry.title)}</td><td>${entry.count}</td><td>${entry.avgUsage.toFixed(1)}</td></tr>`,
            ),
          'No completed jobs yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Repeated Jobs / Categories</h4>
        ${insightTable(
          ['Job Type', 'Repeat Count'],
          data.repeatedJobTypes.map(
            (entry) => `<tr><td>${insightLink(entry.title, 'job-type', entry.title)}</td><td>${entry.count}</td></tr>`,
          ),
          'No repeated completed job types yet.',
        )}
      </article>
      <article class="panel insight-panel">
        <h4>Jobs With High Part Usage</h4>
        ${insightTable(
          ['Job', 'Type', 'Parts Used', 'Avg For Type'],
          data.unusualHighUsageJobs.map(
            (entry) =>
              `<tr><td>${insightLink(entry.job.job_number, 'job', entry.job.id)}</td><td>${htmlEscape(entry.job.title)}</td><td>${entry.totalUsage}</td><td>${entry.averageUsage.toFixed(1)}</td></tr>`,
          ),
          'No unusually high-usage completed jobs found yet.',
        )}
      </article>
    </div>
    ${renderInsightDrilldown(data)}
  `;
}

function renderInventoryTable() {
  const filteredParts = filteredInventoryParts();
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) =>
    left[0].localeCompare(right[0]),
  );
  const rows = groups
    .map(([category, parts]) => {
      const isCollapsed = collapsedCategories.has(category);
      const attentionCount = parts.filter(needsAttention).length;
      const categoryRow = `
      <tr class="category-row" data-category-toggle="${category}">
        <td colspan="6">
          <div class="category-row-inner">
            <div class="category-title-wrap">
              <button type="button" class="category-toggle" data-category-toggle="${category}">${isCollapsed ? '>' : 'v'}</button>
              <strong>${category}</strong>
              <span class="subtle">${parts.length} parts</span>
            </div>
            ${attentionCount ? `<span class="status-pill status-warn">${attentionCount} need attention</span>` : ''}
          </div>
        </td>
      </tr>
    `;
      if (isCollapsed) {
        return categoryRow;
      }
      const partRows = parts
        .map((part) => {
          if (Number(inlineEditors.partId) === Number(part.id)) {
            return renderInlinePartEditor(part);
          }
          const status = inventoryStatus(part);
          return `<tr data-part-row-id="${part.id}">
        <td class="part-meta"><strong class="part-number-link">${part.part_number}</strong>${partTypeTag(part)}<span class="subtle">${part.description}</span></td>
        <td><img class="part-thumb" src="${makePartThumbnail(part)}" alt="${part.part_number} thumbnail"></td>
        <td>${part.stock}</td>
        <td>${vendorName(part.vendor_id)}</td>
        <td><span class="status-pill ${status.className}">${status.label}</span></td>
        <td><button class="tiny-action" data-add-to-order-list="${part.id}">Add to Order List</button> <button class="tiny-action" data-edit-part="${part.id}">Edit</button></td>
      </tr>`;
        })
        .join('');
      return `${categoryRow}${partRows}`;
    })
    .join('');
  document.querySelector('#inventory-table').innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;
}

function renderVendorTable() {
  const rows = state.vendors
    .map((vendor) => {
      if (Number(inlineEditors.vendorId) === Number(vendor.id)) {
        return renderInlineVendorEditor(vendor);
      }
      const linkedForm = vendor.linked_template_name || orderFormTemplateName(vendor.linked_template_id);
      const rowMarkup = `<tr><td><strong>${vendor.name}</strong></td><td>${vendor.contact}</td><td>${vendor.email}</td><td>${vendor.phone}</td><td>${vendor.lead_time_days} days</td><td>${linkedForm || 'Not linked'}</td><td><div class="action-stack-inline"><button class="tiny-action" data-edit-vendor="${vendor.id}">Edit Vendor</button><button class="tiny-action" data-copy-vendor-form="${vendor.id}">Copy Form</button><button class="tiny-action" data-open-order-form-panel="true">Add Form</button></div></td></tr>`;
      return rowMarkup;
    })
    .join('');
  document.querySelector('#vendor-table').innerHTML = rows || `<tr><td colspan="7">${emptyState()}</td></tr>`;
}

function renderOrderFormTemplateTable() {
  const rows = state.orderFormTemplates
    .map((template) => {
      if (Number(inlineEditors.orderFormTemplateId) === Number(template.id)) {
        return renderInlineOrderFormTemplateEditor(template);
      }
      return `<tr><td><strong>${template.template_id}</strong></td><td>${template.name}</td><td>${template.form_variant}</td><td>${template.notes || ''}</td><td><button class="tiny-action" data-edit-order-form-template="${template.id}">Edit</button></td></tr>`;
    })
    .join('');
  document.querySelector('#order-form-template-table').innerHTML =
    rows || `<tr><td colspan="5">${emptyState()}</td></tr>`;
}

function renderWarehouseTable() {
  const rows = state.warehouses
    .map((warehouse) => {
      if (Number(inlineEditors.warehouseId) === Number(warehouse.id)) {
        return renderInlineWarehouseEditor(warehouse);
      }
      const rowMarkup = `<tr><td><strong>${warehouse.name}</strong></td><td>${warehouse.code}</td><td>${warehouse.is_active ? 'Active' : 'Archived'}</td><td><button class="tiny-action" data-edit-warehouse="${warehouse.id}">Edit</button></td></tr>`;
      return rowMarkup;
    })
    .join('');
  document.querySelector('#warehouse-table').innerHTML = rows || `<tr><td colspan="4">${emptyState()}</td></tr>`;
}

function serviceSummaryPairs(job, pairs) {
  return pairs
    .map(
      ([label, value]) =>
        `<div class="service-summary-item"><span class="subtle">${htmlEscape(label)}</span><strong>${htmlEscape(value || 'Not set')}</strong></div>`,
    )
    .join('');
}

function renderServiceHistory(job) {
  const items = serviceHistoryForJob(job).slice(0, 8);
  if (!items.length) {
    return `<div class="empty-state compact-empty-state"><p>No related service history found yet.</p></div>`;
  }
  return items
    .map(
      (entry) => `
        <div class="activity-card service-history-card">
          <button type="button" class="job-number-link button-link" data-summary-route="job" data-summary-key="${entry.id}" ${entry.status === 'Completed' ? 'data-summary-archive="1"' : ''}>${htmlEscape(entry.job_number)}</button>
          <p class="subtle">${htmlEscape(formatDate(entry.completed_at || entry.created_at))} | ${htmlEscape(entry.assigned_user_name || entry.technician || 'Unassigned')}</p>
          <p class="subtle">${htmlEscape(serviceDisplayValue(entry, 'service_category', canonicalJobType(entry)))} | Return trip: ${htmlEscape(serviceDisplayValue(entry, 'return_trip_required', 'Unknown'))}</p>
          <p class="subtle">${htmlEscape(serviceDisplayValue(entry, 'service_fault_category', 'Not set'))}</p>
          <p class="subtle">${htmlEscape(entry.completion_work_performed || entry.completion_notes || entry.notes || 'No resolution notes yet.')}</p>
          ${serviceFieldValue(entry, 'parts_to_order') ? `<p class="subtle">Parts ordered: ${htmlEscape(serviceFieldValue(entry, 'parts_to_order'))}</p>` : ''}
        </div>
      `,
    )
    .join('');
}

function renderServiceDetailSections(job) {
  if (!isServiceJob(job)) return '';
  return `
    <div class="service-detail-grid">
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Customer / Contact</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Primary', serviceFieldValue(job, 'customer_name_primary', job.customer_name)],
            ['Secondary', serviceFieldValue(job, 'customer_name_secondary')],
            ['Address', serviceFieldValue(job, 'address_line_1', job.address)],
            [
              'City / State / Zip',
              [serviceFieldValue(job, 'city'), serviceFieldValue(job, 'state'), serviceFieldValue(job, 'zip')]
                .filter(Boolean)
                .join(', '),
            ],
            ['Primary Phone', serviceFieldValue(job, 'primary_phone')],
            ['Secondary Phone', serviceFieldValue(job, 'secondary_phone')],
            ['Email', serviceFieldValue(job, 'email')],
            ['Best Contact Note', serviceFieldValue(job, 'best_contact_note')],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Contract / Install Info</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Contract #', serviceFieldValue(job, 'contract_number')],
            ['Sale Date', serviceFieldValue(job, 'sale_date')],
            ['Salesperson', serviceFieldValue(job, 'salesperson')],
            ['Install Date', serviceFieldValue(job, 'install_date')],
            ['Product Type', serviceFieldValue(job, 'product_type')],
            ['Color', serviceFieldValue(job, 'color')],
            ['Prior Visits', String(job.prior_visit_count || 0)],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Scheduling / Dispatch</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Service Code', serviceFieldValue(job, 'service_code', canonicalJobType(job))],
            ['Status', job.status || 'Not set'],
            ['Office #', serviceFieldValue(job, 'office_number')],
            ['Zone #', serviceFieldValue(job, 'zone_number')],
            ['Call Date', serviceFieldValue(job, 'call_date')],
            ['Scheduled Date', job.scheduled_for ? formatDate(job.scheduled_for) : 'Not set'],
            ['Scheduled Time', serviceFieldValue(job, 'scheduled_time')],
            ['Estimated Hours', serviceFieldValue(job, 'estimated_hours')],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Service Issue</h4></div>
        <div class="service-notes-stack">
          <p><strong>Customer Complaint:</strong> ${htmlEscape(serviceFieldValue(job, 'customer_complaint') || 'Not set')}</p>
          <p><strong>Dispatch Description:</strong> ${htmlEscape(serviceFieldValue(job, 'dispatch_description') || 'Not set')}</p>
          <p><strong>Probable Issue:</strong> ${htmlEscape(serviceFieldValue(job, 'probable_issue_category') || 'Not set')}</p>
          <p><strong>Service Category:</strong> ${htmlEscape(serviceFieldValue(job, 'service_category') || 'Not set')}</p>
          <p><strong>Urgency:</strong> ${htmlEscape(serviceFieldValue(job, 'urgency') || 'Not set')}</p>
          <p><strong>Internal Notes:</strong> ${htmlEscape(serviceFieldValue(job, 'internal_notes') || 'Not set')}</p>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Work Completed</h4></div>
        <div class="service-notes-stack">
          <p><strong>Completion Date:</strong> ${job.completed_at ? formatDateTime(job.completed_at) : 'Not completed yet'}</p>
          <p><strong>Work Completed:</strong> ${htmlEscape(job.completion_work_performed || 'Not set')}</p>
          <p><strong>Customer Comments:</strong> ${htmlEscape(serviceFieldValue(job, 'customer_comments') || 'Not set')}</p>
          <p><strong>Signature:</strong> ${htmlEscape(serviceFieldValue(job, 'customer_signature') || 'Not captured')}</p>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Parts / Ordering</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Return Trip Required', serviceFieldValue(job, 'return_trip_required', 'Unknown')],
            ['Return Reason', serviceFieldValue(job, 'return_reason')],
            ['Return Est. Hours', serviceFieldValue(job, 'return_estimated_hours')],
            ['Survey Left', serviceFieldValue(job, 'survey_left', 'Unknown')],
            ['Parts To Order', serviceFieldValue(job, 'parts_to_order')],
            ['Waiting On Parts', job.status === 'Waiting on Parts' ? 'Yes' : 'No'],
          ])}
        </div>
        ${
          canManageJobs() && serviceFieldValue(job, 'return_trip_required', 'Unknown') === 'Yes'
            ? `<div class="service-follow-up-action"><button type="button" class="secondary" data-create-followup-service-job="${job.id}">Create Follow-Up Service Job</button></div>`
            : ''
        }
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Billing / Responsibility</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Service Cost', serviceFieldValue(job, 'service_cost')],
            ['Payment Method', serviceFieldValue(job, 'payment_method')],
            ['No Payment Due', serviceFieldValue(job, 'no_payment_due', 'Unknown')],
            ['Paid Service', serviceFieldValue(job, 'paid_service', 'Unknown')],
            ['Fault Category', serviceFieldValue(job, 'service_fault_category')],
            ['Service Item', serviceFieldValue(job, 'service_item')],
            ['Service Issue', serviceFieldValue(job, 'service_issue')],
            ['Return For Credit', serviceFieldValue(job, 'return_for_credit', 'Unknown')],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Service History</h4></div>
        <div class="job-quick-notes-list">${renderServiceHistory(job)}</div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Attachments / Signature</h4></div>
        <div class="service-summary-grid">
          ${serviceSummaryPairs(job, [
            ['Manager Approval', serviceFieldValue(job, 'manager_approval_name')],
            ['Approval Date', serviceFieldValue(job, 'manager_approval_date')],
            ['Service Record ID', serviceFieldValue(job, 'service_record_id')],
          ])}
        </div>
      </div>
    </div>
  `;
}

function serviceFieldsFormMarkup(job = {}, mode = 'create') {
  const isEdit = mode === 'edit';
  const isCompletion = mode === 'complete';
  return `
    <div class="service-form-sections">
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Customer / Contact</h4></div>
        <div class="form-grid compact">
          <label>Primary Name<input name="customer_name_primary" type="text" value="${htmlEscape(serviceFieldValue(job, 'customer_name_primary', job.customer_name))}" /></label>
          <label>Secondary Name<input name="customer_name_secondary" type="text" value="${htmlEscape(serviceFieldValue(job, 'customer_name_secondary'))}" /></label>
          <label>Address Line 1<input name="address_line_1" type="text" value="${htmlEscape(serviceFieldValue(job, 'address_line_1', job.address))}" /></label>
          <label>City<input name="city" type="text" value="${htmlEscape(serviceFieldValue(job, 'city'))}" /></label>
          <label>State<input name="state" type="text" value="${htmlEscape(serviceFieldValue(job, 'state'))}" /></label>
          <label>Zip<input name="zip" type="text" value="${htmlEscape(serviceFieldValue(job, 'zip'))}" /></label>
          <label>Primary Phone<input name="primary_phone" type="text" value="${htmlEscape(serviceFieldValue(job, 'primary_phone'))}" /></label>
          <label>Secondary Phone<input name="secondary_phone" type="text" value="${htmlEscape(serviceFieldValue(job, 'secondary_phone'))}" /></label>
          <label>Email<input name="email" type="email" value="${htmlEscape(serviceFieldValue(job, 'email'))}" /></label>
          <label style="grid-column: 1 / -1">Best Contact Note<input name="best_contact_note" type="text" value="${htmlEscape(serviceFieldValue(job, 'best_contact_note'))}" /></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Contract / Install Info</h4></div>
        <div class="form-grid compact">
          <label>Contract Number<input name="contract_number" type="text" value="${htmlEscape(serviceFieldValue(job, 'contract_number'))}" /></label>
          <label>Sale Date<input name="sale_date" type="date" value="${htmlEscape(serviceFieldValue(job, 'sale_date'))}" /></label>
          <label>Salesperson<input name="salesperson" type="text" value="${htmlEscape(serviceFieldValue(job, 'salesperson'))}" /></label>
          <label>Install Date<input name="install_date" type="date" value="${htmlEscape(serviceFieldValue(job, 'install_date'))}" /></label>
          <label>Product Type<input name="product_type" type="text" value="${htmlEscape(serviceFieldValue(job, 'product_type'))}" /></label>
          <label>Color<input name="color" type="text" value="${htmlEscape(serviceFieldValue(job, 'color'))}" /></label>
          ${isEdit ? `<label>Prior Visit Count<input name="prior_visit_count" type="number" min="0" value="${htmlEscape(serviceFieldValue(job, 'prior_visit_count', '0'))}" /></label>` : ''}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Scheduling / Dispatch</h4></div>
        <div class="form-grid compact">
          <label>Service Code<select name="service_code">${selectOptionsMarkup(serviceFieldOptions('serviceCode'), serviceFieldValue(job, 'service_code', canonicalJobType(job)), 'Select code')}</select></label>
          <label>Status<select name="service_status">${selectOptionsMarkup(serviceFieldOptions('status'), serviceFieldValue(job, 'status', 'Scheduled'), 'Select status')}</select></label>
          <label>Office Number<input name="office_number" type="text" value="${htmlEscape(serviceFieldValue(job, 'office_number'))}" /></label>
          <label>Zone Number<input name="zone_number" type="text" value="${htmlEscape(serviceFieldValue(job, 'zone_number'))}" /></label>
          <label>Call Date<input name="call_date" type="date" value="${htmlEscape(serviceFieldValue(job, 'call_date'))}" /></label>
          <label>Scheduled Time<input name="scheduled_time" type="time" value="${htmlEscape(serviceFieldValue(job, 'scheduled_time'))}" /></label>
          <label>Estimated Hours<input name="estimated_hours" type="text" value="${htmlEscape(serviceFieldValue(job, 'estimated_hours'))}" placeholder="e.g. 2.5" /></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Service Issue</h4></div>
        <div class="form-grid compact">
          <label>Probable Issue<select name="probable_issue_category">${selectOptionsMarkup(serviceFieldOptions('probableIssueCategory'), serviceFieldValue(job, 'probable_issue_category'), 'Select issue')}</select></label>
          <label>Service Category<select name="service_category">${selectOptionsMarkup(serviceFieldOptions('serviceCategory'), serviceFieldValue(job, 'service_category'), 'Select category')}</select></label>
          <label>Urgency<select name="urgency">${selectOptionsMarkup(serviceFieldOptions('urgency'), serviceFieldValue(job, 'urgency', 'Normal'), 'Select urgency')}</select></label>
          <label style="grid-column: 1 / -1">Customer Complaint<textarea name="customer_complaint" class="job-notes-input" rows="3">${htmlEscape(serviceFieldValue(job, 'customer_complaint'))}</textarea></label>
          <label style="grid-column: 1 / -1">Dispatch Description<textarea name="dispatch_description" class="job-notes-input" rows="3">${htmlEscape(serviceFieldValue(job, 'dispatch_description'))}</textarea></label>
          <label style="grid-column: 1 / -1">Internal Notes<textarea name="internal_notes" class="job-notes-input" rows="3">${htmlEscape(serviceFieldValue(job, 'internal_notes'))}</textarea></label>
        </div>
      </div>
      ${
        isEdit || isCompletion
          ? `
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Work Completed</h4></div>
        <div class="form-grid compact">
          <label>Start Time<input name="start_time" type="time" value="${htmlEscape(serviceFieldValue(job, 'start_time'))}" /></label>
          <label>End Time<input name="end_time" type="time" value="${htmlEscape(serviceFieldValue(job, 'end_time'))}" /></label>
          <label>Travel Minutes<input name="travel_time_minutes" type="number" min="0" value="${htmlEscape(serviceFieldValue(job, 'travel_time_minutes', '0'))}" /></label>
          <label>Total Minutes<input name="total_time_minutes" type="number" min="0" value="${htmlEscape(serviceFieldValue(job, 'total_time_minutes', '0'))}" /></label>
          <label style="grid-column: 1 / -1">Customer Comments<textarea name="customer_comments" class="job-notes-input" rows="3">${htmlEscape(serviceFieldValue(job, 'customer_comments'))}</textarea></label>
          <label style="grid-column: 1 / -1">Customer Signature<input name="customer_signature" type="text" value="${htmlEscape(serviceFieldValue(job, 'customer_signature'))}" placeholder="Type name or signature note" /></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Parts / Ordering</h4></div>
        <div class="form-grid compact">
          <label>Return Trip Required<select name="return_trip_required">${selectOptionsMarkup(serviceFieldOptions('yesNo'), serviceFieldValue(job, 'return_trip_required', 'Unknown'), 'Select')}</select></label>
          <label>Return Est. Hours<input name="return_estimated_hours" type="text" value="${htmlEscape(serviceFieldValue(job, 'return_estimated_hours'))}" /></label>
          <label>Survey Left<select name="survey_left">${selectOptionsMarkup(serviceFieldOptions('yesNo'), serviceFieldValue(job, 'survey_left', 'Unknown'), 'Select')}</select></label>
          <label style="grid-column: 1 / -1">Return Reason<textarea name="return_reason" class="job-notes-input" rows="2" placeholder="Required when a return trip is needed">${htmlEscape(serviceFieldValue(job, 'return_reason'))}</textarea></label>
          <label style="grid-column: 1 / -1">Parts To Order<textarea name="parts_to_order" class="job-notes-input" rows="3">${htmlEscape(serviceFieldValue(job, 'parts_to_order'))}</textarea></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Billing / Responsibility</h4></div>
        <div class="form-grid compact">
          <label>Service Cost<input name="service_cost" type="number" min="0" step="0.01" value="${htmlEscape(serviceFieldValue(job, 'service_cost'))}" /></label>
          <label>Payment Method<select name="payment_method">${selectOptionsMarkup(serviceFieldOptions('paymentMethod'), serviceFieldValue(job, 'payment_method', 'No Payment Due'), 'Select')}</select></label>
          <label>No Payment Due<select name="no_payment_due">${selectOptionsMarkup(serviceFieldOptions('yesNo'), serviceFieldValue(job, 'no_payment_due', 'Unknown'), 'Select')}</select></label>
          <label>Paid Service<select name="paid_service">${selectOptionsMarkup(serviceFieldOptions('yesNo'), serviceFieldValue(job, 'paid_service', 'Unknown'), 'Select')}</select></label>
          <label>Fault Category<select name="service_fault_category">${selectOptionsMarkup(serviceFieldOptions('serviceFaultCategory'), serviceFieldValue(job, 'service_fault_category', 'Evaluation'), 'Select')}</select></label>
          <label>Return For Credit<select name="return_for_credit">${selectOptionsMarkup(serviceFieldOptions('yesNo'), serviceFieldValue(job, 'return_for_credit', 'Unknown'), 'Select')}</select></label>
          <label>Service Item<input name="service_item" type="text" value="${htmlEscape(serviceFieldValue(job, 'service_item'))}" /></label>
          <label>Service Issue<input name="service_issue" type="text" value="${htmlEscape(serviceFieldValue(job, 'service_issue'))}" /></label>
          <label>Manager Approval<input name="manager_approval_name" type="text" value="${htmlEscape(serviceFieldValue(job, 'manager_approval_name'))}" /></label>
          <label>Approval Date<input name="manager_approval_date" type="date" value="${htmlEscape(serviceFieldValue(job, 'manager_approval_date'))}" /></label>
          <label>Service Record ID<input name="service_record_id" type="text" value="${htmlEscape(serviceFieldValue(job, 'service_record_id'))}" /></label>
        </div>
      </div>
      `
          : ''
      }
    </div>
  `;
}

function detailFieldValue(job, key, fallback = '') {
  return String(job?.[key] || fallback || '');
}

function detailSummaryPairs(job, pairs) {
  return pairs
    .map(
      ([label, value]) =>
        `<div class="service-summary-item"><span class="subtle">${htmlEscape(label)}</span><strong>${htmlEscape(value || 'Not set')}</strong></div>`,
    )
    .join('');
}

function renderDetailJobSections(job) {
  if (!isDetailJob(job)) return '';
  const attachments = jobAttachmentsFor(job.id);
  const sourceDocs = attachments.length
    ? attachments
        .map(
          (attachment) =>
            `<p class="subtle"><a href="${attachment.view_url}" target="_blank" rel="noreferrer">${htmlEscape(attachment.original_name)}</a></p>`,
        )
        .join('')
    : '<p class="subtle">Upload original sales paperwork in Files to generate the first extraction summary.</p>';
  return `
    <div class="service-detail-grid detail-detail-grid">
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Customer / Job</h4></div>
        <div class="service-summary-grid">
          ${detailSummaryPairs(job, [
            ['Customer', job.customer_name],
            ['Address', job.address],
            ['Contract #', detailFieldValue(job, 'linked_contract_number', detailFieldValue(job, 'contract_number'))],
            ['Assigned', job.assigned_user_name || job.technician || 'Unassigned'],
            ['Scheduled', job.scheduled_for ? formatDate(job.scheduled_for) : 'Not set'],
            ['Status', job.status],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Sold Configuration</h4></div>
        <div class="service-summary-grid">
          ${detailSummaryPairs(job, [
            ['Product Type', detailFieldValue(job, 'extracted_product_type')],
            ['Color / Finish', detailFieldValue(job, 'extracted_color')],
            ['Configuration', detailFieldValue(job, 'extracted_configuration')],
            ['Accessories / Options', detailFieldValue(job, 'extracted_accessories')],
            ['Special Requirements', detailFieldValue(job, 'extracted_special_requirements')],
          ])}
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Measurements To Confirm</h4></div>
        <div class="service-notes-stack">
          <p><strong>Extracted:</strong> ${htmlEscape(detailFieldValue(job, 'extracted_measurements') || 'Not found in uploaded documents')}</p>
          <p><strong>Confirmed:</strong> ${htmlEscape(detailFieldValue(job, 'confirmed_measurements') || 'Not confirmed yet')}</p>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Detail Checklist</h4></div>
        <pre class="job-completion-preview-body">${htmlEscape(detailFieldValue(job, 'detail_checklist') || 'No checklist generated yet.')}</pre>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Flags / Missing Info</h4></div>
        <div class="service-notes-stack">
          <p>${htmlEscape(detailFieldValue(job, 'extracted_confidence_flags') || 'No extraction flags yet.')}</p>
          <p><strong>Discrepancies:</strong> ${htmlEscape(detailFieldValue(job, 'discrepancies_found', 'Unknown'))}</p>
          <p><strong>Category:</strong> ${htmlEscape(detailFieldValue(job, 'discrepancy_category') || 'Not set')}</p>
          <p><strong>Notes:</strong> ${htmlEscape(detailFieldValue(job, 'discrepancy_notes') || 'No discrepancy notes')}</p>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Install Handoff</h4></div>
        <div class="service-notes-stack">
          <p><strong>Ready for Install:</strong> ${htmlEscape(detailFieldValue(job, 'ready_for_install', 'Unknown'))}</p>
          <p><strong>Changes Needed:</strong> ${htmlEscape(detailFieldValue(job, 'changes_needed', 'Unknown'))}</p>
          <p><strong>Follow-Up Required:</strong> ${htmlEscape(detailFieldValue(job, 'follow_up_required', 'Unknown'))}</p>
          <pre class="job-completion-preview-body">${htmlEscape(detailFieldValue(job, 'install_handoff_summary') || 'Handoff summary will be generated when ready for install is confirmed.')}</pre>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Source Documents</h4></div>
        ${sourceDocs}
      </div>
    </div>
  `;
}

function detailFieldsFormMarkup(job = {}, mode = 'create') {
  const isCreate = mode === 'create';
  return `
    <div class="service-form-sections">
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Detail Job Setup</h4></div>
        <div class="form-grid compact">
          <label>Contract Number<input name="linked_contract_number" type="text" value="${htmlEscape(detailFieldValue(job, 'linked_contract_number', detailFieldValue(job, 'contract_number')))}" /></label>
          <label>Sale Record ID<input name="linked_sale_record_id" type="text" value="${htmlEscape(detailFieldValue(job, 'linked_sale_record_id'))}" /></label>
          <label style="grid-column: 1 / -1">Extracted Summary<textarea name="extracted_document_summary" class="job-notes-input" rows="4" ${isCreate ? 'placeholder="Upload sales documents after creating the Detail job to generate this."' : ''}>${htmlEscape(detailFieldValue(job, 'extracted_document_summary'))}</textarea></label>
          <label>Product Type<input name="extracted_product_type" type="text" value="${htmlEscape(detailFieldValue(job, 'extracted_product_type'))}" /></label>
          <label>Color / Finish<input name="extracted_color" type="text" value="${htmlEscape(detailFieldValue(job, 'extracted_color'))}" /></label>
          <label style="grid-column: 1 / -1">Sold Configuration<textarea name="extracted_configuration" class="job-notes-input" rows="3">${htmlEscape(detailFieldValue(job, 'extracted_configuration'))}</textarea></label>
          <label style="grid-column: 1 / -1">Extracted Measurements<textarea name="extracted_measurements" class="job-notes-input" rows="3">${htmlEscape(detailFieldValue(job, 'extracted_measurements'))}</textarea></label>
          <label style="grid-column: 1 / -1">Accessories / Options<textarea name="extracted_accessories" class="job-notes-input" rows="3">${htmlEscape(detailFieldValue(job, 'extracted_accessories'))}</textarea></label>
          <label style="grid-column: 1 / -1">Extraction Flags<textarea name="extracted_confidence_flags" class="job-notes-input" rows="3">${htmlEscape(detailFieldValue(job, 'extracted_confidence_flags'))}</textarea></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Technician Verification</h4></div>
        <div class="form-grid compact">
          <label style="grid-column: 1 / -1">Editable Checklist<textarea name="detail_checklist" class="job-notes-input" rows="8">${htmlEscape(detailFieldValue(job, 'detail_checklist'))}</textarea></label>
          <label style="grid-column: 1 / -1">Confirmed Measurements<textarea name="confirmed_measurements" class="job-notes-input" rows="3">${htmlEscape(detailFieldValue(job, 'confirmed_measurements'))}</textarea></label>
          <label>Layout Confirmed<select name="confirmed_layout">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'confirmed_layout', 'Unknown'), 'Select')}</select></label>
          <label>Product Match<select name="confirmed_product_match">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'confirmed_product_match', 'Unknown'), 'Select')}</select></label>
          <label>Accessories Confirmed<select name="confirmed_accessories">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'confirmed_accessories', 'Unknown'), 'Select')}</select></label>
          <label>Customer Expectations<select name="confirmed_customer_expectations">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'confirmed_customer_expectations', 'Unknown'), 'Select')}</select></label>
        </div>
      </div>
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Discrepancy / Install Handoff</h4></div>
        <div class="form-grid compact">
          <label>Discrepancies Found<select name="discrepancies_found">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'discrepancies_found', 'Unknown'), 'Select')}</select></label>
          <label>Discrepancy Category<select name="discrepancy_category">${selectOptionsMarkup(serviceFieldOptions('detailDiscrepancyCategory'), detailFieldValue(job, 'discrepancy_category', 'Other'), 'Select category')}</select></label>
          <label>Changes Needed<select name="changes_needed">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'changes_needed', 'Unknown'), 'Select')}</select></label>
          <label>Ready For Install<select name="ready_for_install">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'ready_for_install', 'Unknown'), 'Select')}</select></label>
          <label>Follow-Up Required<select name="follow_up_required">${selectOptionsMarkup(serviceFieldOptions('yesNo'), detailFieldValue(job, 'follow_up_required', 'Unknown'), 'Select')}</select></label>
          <label style="grid-column: 1 / -1">Discrepancy Notes<textarea name="discrepancy_notes" class="job-notes-input" rows="4">${htmlEscape(detailFieldValue(job, 'discrepancy_notes'))}</textarea></label>
          <label style="grid-column: 1 / -1">Install Handoff Summary<textarea name="install_handoff_summary" class="job-notes-input" rows="4">${htmlEscape(detailFieldValue(job, 'install_handoff_summary'))}</textarea></label>
        </div>
      </div>
    </div>
  `;
}

function renderJobCards(jobs, rootSelector, options = {}) {
  const root = document.querySelector(rootSelector);
  if (!root) return;
  const showActions = options.showActions !== false;
  const archiveMode = options.archiveMode === true;
  const visibleJobs =
    showActions && editingJobId ? jobs.filter((job) => Number(job.id) === Number(editingJobId)) : jobs;
  const sortedJobs = [...visibleJobs].sort((left, right) => {
    const leftReady = left.status === 'Ready to Go' ? 1 : 0;
    const rightReady = right.status === 'Ready to Go' ? 1 : 0;
    if (leftReady !== rightReady) {
      return rightReady - leftReady;
    }
    return new Date(right.created_at) - new Date(left.created_at);
  });

  root.innerHTML = sortedJobs.length
    ? sortedJobs
        .map((job) => {
          const managerMode = canManageJobs();
          const requirements = jobRequirementsFor(job.id);
          const attachments = jobAttachmentsFor(job.id);
          const recentNotes = jobNotesFor(job.id).slice(0, 3);
          const readyToGo = job.status === 'Ready to Go';
          const isCollapsed = showActions && !editingJobId ? collapsedJobs.has(Number(job.id)) : false;
          const totalRequired = requirements.reduce((sum, requirement) => sum + requirement.required_quantity, 0);
          const totalPulled = requirements.reduce((sum, requirement) => sum + requirement.pulled_quantity, 0);
          const requirementRows = requirements.length
            ? requirements
                .map((requirement) => {
                  const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
                  const part = partById(requirement.part_id);
                  const directReceiveLabel = isNonStock(part) ? 'Receive Direct' : 'Receive to Job';
                  return `
        <div class="job-part-row">
          <div class="job-part-copy">
            <strong><span class="part-number-link">${part ? part.part_number : 'Unknown'}</span>${part ? partTypeTag(part) : ''}${part ? ` <span class="subtle">- ${part.description}</span>` : ''}</strong>
            <p class="subtle">Required ${requirement.required_quantity} | Pulled ${requirement.pulled_quantity} | In Inventory ${part ? part.stock : 0}</p>
          </div>
          <div class="job-part-actions ${showActions ? '' : 'job-part-actions-static'}">
            ${showActions ? `<button class="tiny-action" data-return-job-part="${requirement.id}" ${requirement.pulled_quantity === 0 ? 'disabled' : ''}>Return</button><button class="tiny-action" data-pull-job-part="${requirement.id}" ${remaining === 0 ? 'disabled' : ''}>Pull</button>${canReceiveJobs() ? `<button class="tiny-action" data-receive-job-part-direct="${requirement.id}" ${remaining === 0 ? 'disabled' : ''}>${directReceiveLabel}</button>` : ''}` : ''}
          </div>
        </div>
      `;
                })
                .join('')
            : emptyState();
          const quickNoteRows = recentNotes.length
            ? recentNotes
                .map(
                  (note) => `
        <div class="job-quick-note">
          <div class="job-quick-note-copy">
            <strong>${note.note_author || 'Unknown user'}</strong>
            <p>${note.body}</p>
            <p class="subtle">${formatDateTime(note.created_at)}</p>
          </div>
        </div>
      `,
                )
                .join('')
            : `<div class="empty-state compact-empty-state"><p>No notes yet.</p></div>`;
          const attachmentRows = attachments.length
            ? attachments
                .map(
                  (attachment) => `
        <div class="job-attachment-row">
          <div class="job-attachment-copy">
            <strong>${attachment.original_name}</strong>
            <p class="subtle">${formatFileSize(attachment.file_size)} | ${attachment.uploaded_by_name || 'Unknown uploader'} | ${formatDateTime(attachment.created_at)}</p>
          </div>
          <div class="job-part-actions ${showActions ? '' : 'job-part-actions-static'}">
            <a class="tiny-action" href="/api/job-attachments/${attachment.id}/view" target="_blank" rel="noopener noreferrer">View</a>
            <a class="tiny-action" href="/api/job-attachments/${attachment.id}/download">Download</a>
            ${managerMode && showActions ? `<button class="tiny-action" data-delete-job-attachment="${attachment.id}">Remove</button>` : ''}
          </div>
        </div>
      `,
                )
                .join('')
            : `<div class="empty-state compact-empty-state"><p>No files attached yet.</p></div>`;

          return `
      <div class="activity-card job-card ${readyToGo ? 'job-card-ready' : ''}" data-job-card-id="${job.id}" ${archiveMode ? `data-archive-job-id="${job.id}"` : ''}>
        <div class="category-row-inner job-row-header" data-job-toggle="${job.id}">
          <div class="category-title-wrap">
            ${showActions && !editingJobId ? `<button type="button" class="category-toggle" data-job-toggle="${job.id}">${isCollapsed ? '>' : 'v'}</button>` : ''}
            <div class="job-identity-block">
              <div class="job-title-line">
                <strong class="job-number-link">${job.job_number}</strong>
                <span class="subtle">${job.title}</span>
              </div>
              <div class="job-meta-grid">
                <span><strong>Customer:</strong> ${job.customer_name || 'Not set'}</span>
                <span><strong>Address:</strong> ${job.address || 'Not set'}</span>
                <span><strong>Assigned:</strong> ${job.assigned_user_name || 'Unassigned'}</span>
                <span><strong>Type:</strong> ${job.job_type || job.title || 'Not set'}</span>
                <span><strong>Scheduled:</strong> ${job.scheduled_for ? formatDate(job.scheduled_for) : 'Not set'}</span>
                <span><strong>Created By:</strong> ${job.created_by_name || 'Unknown'}</span>
                ${job.completed_by_name ? `<span><strong>Completed By:</strong> ${job.completed_by_name}</span>` : ''}
              </div>
            </div>
          </div>
          <div class="job-header-side">
            ${job.status === 'Completed' ? '<span class="status-pill status-ok">Completed</span>' : readyToGo ? '<span class="status-pill status-ok">Ready To Go</span>' : '<span class="status-pill status-warn">Needs Parts</span>'}
            <p class="subtle">${totalPulled} pulled of ${totalRequired}</p>
          </div>
        </div>
        ${
          isCollapsed
            ? ''
            : `
          <div class="job-detail-block">
            ${
              showActions
                ? `<div class="job-detail-toolbar">${managerMode ? `<button class="tiny-action" data-edit-job="${job.id}">Edit Job</button><button class="tiny-action" data-open-job-part-modal="${job.id}">Add Part</button><button class="tiny-action" data-open-job-scan-add-modal="${job.id}">Scan Part to Add</button>` : ''}${canCompleteJobs() ? `<button class="tiny-action" data-complete-job="${job.id}" ${readyToGo ? '' : 'disabled'}>Complete Job</button>` : ''}</div>`
                : ''
            }
            ${renderServiceDetailSections(job)}
            ${renderDetailJobSections(job)}
            <div class="job-notes-card">
              <div class="table-header compact-header">
                <h4>Notes</h4>
              </div>
              <div class="job-quick-notes-list">${quickNoteRows}</div>
              ${
                hasPermission('notes_access') && showActions
                  ? `<div class="job-quick-note-entry"><textarea class="job-notes-input" rows="2" placeholder="Add a note..." data-job-quick-note-input="${job.id}"></textarea><button class="tiny-action" data-add-job-note="${job.id}">Add New Note</button></div>`
                  : ''
              }
            </div>
            <div class="job-notes-card">
              <div class="table-header compact-header">
                <h4>Files</h4>
                ${showActions ? `<div class="job-attachment-upload"><input type="file" data-job-attachment-input="${job.id}" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.doc,.docx,.xls,.xlsx,.csv"><button class="tiny-action" data-upload-job-attachment="${job.id}">Upload File</button></div>` : ''}
              </div>
              <div class="job-attachments-list">${attachmentRows}</div>
            </div>
            <div class="job-parts-list">${requirementRows}</div>
          </div>
        `
        }
      </div>
    `;
        })
        .join('')
    : emptyState();
}

function renderJobsList() {
  const jobs = (state.jobs || []).map((job) => ({ ...job, job_type: canonicalJobType(job) }));
  const installJobs = jobs.filter((job) => canonicalJobType(job) === 'Install');
  const detailJobs = jobs.filter((job) => canonicalJobType(job) === 'Detail');
  const serviceJobs = jobs.filter((job) => ['Service', 'Warranty'].includes(canonicalJobType(job)));
  const summary = document.querySelector('#jobs-workflow-summary');
  const installSummary = document.querySelector('#jobs-install-summary');
  const detailSummary = document.querySelector('#jobs-detail-summary');
  const serviceSummary = document.querySelector('#jobs-service-summary');
  const installSection = document.querySelector('#jobs-install-section');
  const detailSection = document.querySelector('#jobs-detail-section');
  const serviceSection = document.querySelector('#jobs-service-section');
  const showInstall = hasGlobalJobScope() || isInstallRole();
  const showDetail = hasGlobalJobScope() || isInstallRole();
  const showService = hasGlobalJobScope() || isServiceRole();
  if (installSection) installSection.classList.toggle('hidden', !showInstall);
  if (detailSection) detailSection.classList.toggle('hidden', !showDetail);
  if (serviceSection) serviceSection.classList.toggle('hidden', !showService);
  renderJobCards(showInstall ? installJobs : [], '#jobs-install-list', { showActions: true });
  renderJobCards(showDetail ? detailJobs : [], '#jobs-detail-list', { showActions: true });
  renderJobCards(showService ? serviceJobs : [], '#jobs-service-list', { showActions: true });
  if (summary) {
    if (hasGlobalJobScope()) {
      summary.textContent = `${installJobs.length} install, ${detailJobs.length} detail, and ${serviceJobs.length} service / warranty job(s) are active right now.`;
    } else if (showInstall) {
      summary.textContent = `${installJobs.length} install and ${detailJobs.length} detail job(s) assigned to you.`;
    } else if (showService) {
      summary.textContent = `${serviceJobs.length} service / warranty job(s) assigned to you.`;
    } else {
      summary.textContent = 'No job access for this role.';
    }
  }
  if (installSummary) {
    installSummary.textContent = showInstall
      ? `${installJobs.length} install job(s) currently visible.`
      : 'Install jobs are hidden for this role.';
  }
  if (detailSummary) {
    detailSummary.textContent = showDetail
      ? `${detailJobs.length} pre-install detail job(s) currently visible.`
      : 'Detail jobs are hidden for this role.';
  }
  if (serviceSummary) {
    serviceSummary.textContent = showService
      ? `${serviceJobs.length} service / warranty job(s) currently visible.`
      : 'Service and warranty jobs are hidden for this role.';
  }
}

function sortArchiveItems(items, sortKey, numberKey) {
  const sorted = [...items];
  if (sortKey === 'oldest') {
    sorted.sort((left, right) => new Date(left.created_at) - new Date(right.created_at));
  } else if (sortKey === 'job-number' || sortKey === 'po-number') {
    sorted.sort((left, right) => String(left[numberKey] || '').localeCompare(String(right[numberKey] || '')));
  } else {
    sorted.sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
  }
  return sorted;
}

function archiveSearchMatch(item, search, fields) {
  if (!search) return true;
  return fields
    .map((field) => String(item[field] || ''))
    .join(' ')
    .toLowerCase()
    .includes(search);
}

function renderArchiveList() {
  const installRoot = document.querySelector('#archive-install-list');
  const detailRoot = document.querySelector('#archive-detail-list');
  const serviceRoot = document.querySelector('#archive-service-list');
  const poRoot = document.querySelector('#archive-po-list');
  if (!installRoot || !detailRoot || !serviceRoot || !poRoot) return;
  document.querySelector('#archive-install-list')?.closest('.panel')?.classList.toggle('hidden', isServiceRole());
  document.querySelector('#archive-detail-list')?.closest('.panel')?.classList.toggle('hidden', isServiceRole());
  document.querySelector('#archive-service-list')?.closest('.panel')?.classList.toggle('hidden', isInstallRole());

  const completedJobs = (state.completedJobs || []).map((job) => ({ ...job, job_type: canonicalJobType(job) }));
  const installJobs = sortArchiveItems(
    completedJobs
      .filter((job) => canonicalJobType(job) === 'Install')
      .filter((job) =>
        archiveSearchMatch(job, archiveFilters.installSearch.toLowerCase(), [
          'job_number',
          'customer_name',
          'address',
          'title',
        ]),
      ),
    archiveFilters.installSort,
    'job_number',
  );
  const serviceJobs = sortArchiveItems(
    completedJobs
      .filter((job) => ['Service', 'Warranty'].includes(canonicalJobType(job)))
      .filter((job) =>
        archiveSearchMatch(job, archiveFilters.serviceSearch.toLowerCase(), [
          'job_number',
          'customer_name',
          'address',
          'title',
        ]),
      ),
    archiveFilters.serviceSort,
    'job_number',
  );
  const detailJobs = sortArchiveItems(
    completedJobs
      .filter((job) => canonicalJobType(job) === 'Detail')
      .filter((job) =>
        archiveSearchMatch(job, archiveFilters.detailSearch.toLowerCase(), [
          'job_number',
          'customer_name',
          'address',
          'title',
        ]),
      ),
    archiveFilters.detailSort,
    'job_number',
  );
  renderJobCards(installJobs, '#archive-install-list', { showActions: false, archiveMode: true });
  renderJobCards(detailJobs, '#archive-detail-list', { showActions: false, archiveMode: true });
  renderJobCards(serviceJobs, '#archive-service-list', { showActions: false, archiveMode: true });

  const archivedPos = sortArchiveItems(
    (state.purchaseOrders || [])
      .filter((po) => po.status === 'Received')
      .filter((po) =>
        archiveSearchMatch(po, archiveFilters.poSearch.toLowerCase(), ['po_number', 'vendor_name', 'notes']),
      ),
    archiveFilters.poSort,
    'po_number',
  );
  poRoot.innerHTML = archivedPos.length
    ? archivedPos
        .map(
          (po) => `
        <div class="activity-card po-card-detail" data-archive-po-id="${po.id}">
          <div class="job-card-header">
            <div>
              <button type="button" class="po-number-link button-link" data-summary-route="po" data-summary-key="${po.id}" data-summary-archive="1">${po.po_number}</button>
              <p class="subtle">${po.vendor_name} | ${po.line_count} line item(s)</p>
            </div>
            <span class="status-pill status-ok">${po.status}</span>
          </div>
          <div class="po-card-meta">
            <p><strong>Created By:</strong> ${po.created_by_name || 'Unknown'}</p>
            ${po.checked_in_by_name ? `<p><strong>Checked In By:</strong> ${po.checked_in_by_name}${po.checked_in_at ? ` | ${formatDateTime(po.checked_in_at)}` : ''}</p>` : ''}
            <p><strong>Outstanding:</strong> ${po.outstanding_quantity}</p>
            <p><strong>Notes:</strong> ${po.notes || 'No notes'}</p>
          </div>
        </div>
      `,
        )
        .join('')
    : emptyState();
}

function buildSummaryItems(summaryKey) {
  const data = insightsData();
  if (summaryKey === 'dashboard-active-jobs') {
    return {
      title: 'Active Jobs',
      items: (state.jobs || []).map((job) => ({
        title: job.job_number,
        subtitle: `${job.customer_name || 'No customer'} | ${canonicalJobType(job)} | ${job.assigned_user_name || 'Unassigned'}`,
        routeType: 'job',
        routeKey: job.id,
      })),
    };
  }
  if (summaryKey === 'dashboard-low-stock') {
    return {
      title: 'Low Stock Alerts',
      items: (state.parts || []).filter(needsAttention).map((part) => ({
        title: part.part_number,
        subtitle: `${part.description} | Stock ${part.stock} | Reorder ${part.reorder_point}`,
        routeType: 'part',
        routeKey: part.id,
      })),
    };
  }
  if (summaryKey === 'insights-reorder-watch') {
    return {
      title: 'Reorder Watch',
      items: data.reorderPredictions.map((entry) => ({
        title: entry.partNumber,
        subtitle: `${entry.description || 'Part'} | ${entry.daysUntilReorder === null ? 'No forecast yet' : entry.daysUntilReorder === 0 ? 'Reorder now' : `${entry.daysUntilReorder} day(s) to reorder`} | Suggested ${entry.suggestedReorderQty}`,
        routeType: 'part',
        routeKey: entry.partId,
      })),
    };
  }
  if (summaryKey === 'insights-pattern-flags') {
    return {
      title: 'Pattern Flags',
      items: data.processFlags.map((flag) => ({
        title: flag.title,
        subtitle: flag.body,
        routeType: 'insight-flag',
        routeKey: flag.id,
      })),
    };
  }
  if (summaryKey === 'insights-recommendations') {
    return {
      title: 'Recommendations',
      items: data.recommendations.map((recommendation) => ({
        title: recommendation.title,
        subtitle: recommendation.body,
        routeType: recommendation.entityType || 'flag',
        routeKey: recommendation.entityKey ?? recommendation.id,
      })),
    };
  }
  if (summaryKey === 'insights-completed-jobs') {
    return {
      title: 'Completed Jobs',
      items: data.completedJobs.map((job) => ({
        title: job.job_number,
        subtitle: `${job.customer_name || 'No customer'} | ${canonicalJobType(job)} | ${job.completed_by_name || 'Completed'}`,
        routeType: 'archived-job',
        routeKey: job.id,
        preferArchive: true,
      })),
    };
  }
  return { title: 'Items', items: [] };
}

function closeJobCompletionModal() {
  jobCompletionModalJobId = null;
  jobCompletionPreview = null;
  renderJobCompletionModal();
}

function completionDraftValues() {
  const form = document.querySelector('#job-completion-form');
  const formData = form ? new FormData(form) : null;
  return {
    recipientName: document.querySelector('#job-completion-recipient-name')?.value.trim() || '',
    recipientEmail: document.querySelector('#job-completion-recipient-email')?.value.trim() || '',
    workPerformed: document.querySelector('#job-completion-work-performed')?.value.trim() || '',
    completionNotes: document.querySelector('#job-completion-notes')?.value.trim() || '',
    ...servicePayloadFromFormData(formData),
    ...detailPayloadFromFormData(formData),
  };
}

function servicePayloadFromFormData(formData) {
  if (!formData) return {};
  const keys = [
    'service_code',
    'service_status',
    'office_number',
    'zone_number',
    'contract_number',
    'call_date',
    'scheduled_time',
    'estimated_hours',
    'prior_visit_count',
    'customer_name_primary',
    'customer_name_secondary',
    'address_line_1',
    'city',
    'state',
    'zip',
    'primary_phone',
    'secondary_phone',
    'email',
    'best_contact_note',
    'sale_date',
    'salesperson',
    'install_date',
    'product_type',
    'color',
    'customer_complaint',
    'dispatch_description',
    'probable_issue_category',
    'service_category',
    'urgency',
    'internal_notes',
    'return_trip_required',
    'return_reason',
    'return_estimated_hours',
    'survey_left',
    'parts_to_order',
    'service_cost',
    'payment_method',
    'no_payment_due',
    'start_time',
    'end_time',
    'travel_time_minutes',
    'total_time_minutes',
    'customer_comments',
    'customer_signature',
    'paid_service',
    'service_fault_category',
    'service_item',
    'service_issue',
    'manager_approval_name',
    'manager_approval_date',
    'return_for_credit',
    'service_record_id',
  ];
  return keys.reduce((payload, key) => {
    const value = formData.get(key);
    if (value !== null) payload[key] = String(value).trim();
    return payload;
  }, {});
}

function detailPayloadFromFormData(formData) {
  if (!formData) return {};
  const keys = [
    'linked_contract_number',
    'linked_sale_record_id',
    'extracted_document_summary',
    'extracted_product_type',
    'extracted_color',
    'extracted_configuration',
    'extracted_measurements',
    'extracted_accessories',
    'extracted_notes',
    'extracted_special_requirements',
    'extracted_confidence_flags',
    'detail_checklist',
    'confirmed_measurements',
    'confirmed_layout',
    'confirmed_product_match',
    'confirmed_accessories',
    'confirmed_customer_expectations',
    'discrepancies_found',
    'discrepancy_category',
    'discrepancy_notes',
    'changes_needed',
    'ready_for_install',
    'follow_up_required',
    'install_handoff_summary',
  ];
  return keys.reduce((payload, key) => {
    const value = formData.get(key);
    if (value !== null) payload[key] = String(value).trim();
    return payload;
  }, {});
}

function renderJobCompletionModal() {
  const overlay = document.querySelector('#job-completion-modal');
  const title = document.querySelector('#job-completion-title');
  const previewPanel = document.querySelector('#job-completion-preview-panel');
  const emailStatus = document.querySelector('#job-completion-email-status');
  const recipientNameInput = document.querySelector('#job-completion-recipient-name');
  const recipientEmailInput = document.querySelector('#job-completion-recipient-email');
  const workPerformedInput = document.querySelector('#job-completion-work-performed');
  const completionNotesInput = document.querySelector('#job-completion-notes');
  const sendButton = document.querySelector('#job-completion-send-button');
  const serviceFieldsRoot = document.querySelector('#job-completion-service-fields');
  if (
    !overlay ||
    !title ||
    !previewPanel ||
    !emailStatus ||
    !recipientNameInput ||
    !recipientEmailInput ||
    !workPerformedInput ||
    !completionNotesInput ||
    !sendButton
  )
    return;

  if (!jobCompletionModalJobId) {
    overlay.classList.add('hidden');
    previewPanel.innerHTML = `<div class="table-header compact-header"><h4>Email Preview</h4></div><div class="empty-state"><p>Preview the completion email before sending it.</p></div>`;
    return;
  }

  const job = jobById(jobCompletionModalJobId);
  if (!job) {
    closeJobCompletionModal();
    return;
  }

  title.textContent = `Complete ${job.job_number}`;
  recipientNameInput.value = recipientNameInput.value || job.completion_recipient_name || job.customer_name || '';
  recipientEmailInput.value = recipientEmailInput.value || job.completion_recipient_email || '';
  workPerformedInput.value = workPerformedInput.value || job.completion_work_performed || '';
  completionNotesInput.value = completionNotesInput.value || job.completion_notes || '';
  emailStatus.textContent = state.emailSettings?.sendAvailable
    ? `Email sending is configured${state.emailSettings?.fromEmail ? ` from ${state.emailSettings.fromEmail}` : ''}.`
    : 'Email preview works now. Sending will work after SMTP settings are configured.';
  sendButton.disabled = !state.emailSettings?.sendAvailable;
  if (serviceFieldsRoot) {
    if (isServiceJob(job)) {
      const draft = servicePayloadFromFormData(
        document.querySelector('#job-completion-form')
          ? new FormData(document.querySelector('#job-completion-form'))
          : null,
      );
      serviceFieldsRoot.innerHTML = serviceFieldsFormMarkup({ ...job, ...draft }, 'complete');
      serviceFieldsRoot.classList.remove('hidden');
    } else if (isDetailJob(job)) {
      const draft = detailPayloadFromFormData(
        document.querySelector('#job-completion-form')
          ? new FormData(document.querySelector('#job-completion-form'))
          : null,
      );
      serviceFieldsRoot.innerHTML = detailFieldsFormMarkup({ ...job, ...draft }, 'complete');
      serviceFieldsRoot.classList.remove('hidden');
    } else {
      serviceFieldsRoot.innerHTML = '';
      serviceFieldsRoot.classList.add('hidden');
    }
  }

  if (!jobCompletionPreview) {
    previewPanel.innerHTML = `
      <div class="table-header compact-header"><h4>Email Preview</h4></div>
      <div class="empty-state"><p>Preview the completion email to review the job summary, parts used, and attached files.</p></div>
    `;
  } else {
    previewPanel.innerHTML = `
      <div class="table-header compact-header"><h4>Email Preview</h4></div>
      <div class="job-completion-preview-meta">
        <p><strong>To:</strong> ${jobCompletionPreview.recipientName || 'Recipient'} ${jobCompletionPreview.recipientEmail ? `&lt;${jobCompletionPreview.recipientEmail}&gt;` : ''}</p>
        <p><strong>Subject:</strong> ${jobCompletionPreview.subject}</p>
      </div>
      <div class="job-completion-preview-block">
        <h5>Included Parts</h5>
        ${
          jobCompletionPreview.parts.length
            ? jobCompletionPreview.parts
                .map(
                  (item) =>
                    `<p class="subtle">${item.partNumber}: pulled ${item.pulledQuantity} of ${item.requiredQuantity} required</p>`,
                )
                .join('')
            : `<p class="subtle">No job parts recorded.</p>`
        }
      </div>
      <div class="job-completion-preview-block">
        <h5>Attached Files</h5>
        ${
          jobCompletionPreview.attachments.length
            ? jobCompletionPreview.attachments.map((item) => `<p class="subtle">${item.original_name}</p>`).join('')
            : `<p class="subtle">No attachments will be sent.</p>`
        }
      </div>
      <pre class="job-completion-preview-body">${jobCompletionPreview.body}</pre>
    `;
  }

  overlay.classList.remove('hidden');
}

function renderJobEditOverlay() {
  const overlay = document.querySelector('#job-edit-overlay');
  const form = document.querySelector('#job-edit-modal-form');
  const title = document.querySelector('#job-edit-title');
  if (!overlay || !form || !title) return;
  if (!canManageJobs()) {
    overlay.classList.add('hidden');
    form.innerHTML = '';
    return;
  }
  if (!editingJobId) {
    overlay.classList.add('hidden');
    form.innerHTML = '';
    return;
  }

  const job = jobById(editingJobId);
  if (!job) {
    overlay.classList.add('hidden');
    form.innerHTML = '';
    return;
  }

  title.textContent = `${job.job_number} details`;
  const requirements = jobRequirementsFor(job.id);
  const requirementRows = requirements.length
    ? requirements
        .map((requirement) => {
          const part = partById(requirement.part_id);
          return `
      <div class="job-part-row">
        <div class="job-part-copy">
          <strong><span class="part-number-link">${part ? part.part_number : 'Unknown'}</span>${part ? ` <span class="subtle">- ${part.description}</span>` : ''}</strong>
          <p class="subtle">Pulled ${requirement.pulled_quantity} | In Inventory ${part ? part.stock : 0}</p>
        </div>
        <div class="job-part-actions">
          <label class="field-small compact-field">Required Qty<input type="number" min="${Math.max(requirement.pulled_quantity, 1)}" value="${requirement.required_quantity}" data-job-part-qty="${requirement.id}"></label>
          <button type="button" class="tiny-action" data-delete-job-part="${requirement.id}" ${requirement.pulled_quantity > 0 ? 'disabled' : ''}>Remove</button>
        </div>
      </div>
    `;
        })
        .join('')
    : emptyState();

  form.innerHTML = `
    <div class="job-edit-modal-layout">
      <div class="job-edit-modal-fields">
        <label>Job / Work Order<input name="jobNumber" type="text" value="${job.job_number}" required></label>
        <label>Customer Name<input name="customerName" type="text" value="${job.customer_name || ''}" required></label>
        <label>Address<input name="address" type="text" value="${job.address || ''}" required></label>
        <label>Job Title<input name="title" type="text" value="${job.title}" required></label>
        <label>Job Type<select name="jobType">${(state.jobTypeOptions || [])
          .map(
            (option) =>
              `<option value="${option}" ${String(job.job_type || '') === String(option) ? 'selected' : ''}>${option}</option>`,
          )
          .join('')}</select></label>
        <label>Assigned User<select name="assignedUserId"><option value="">Choose assignee</option>${assignableUsers()
          .map(
            (user) =>
              `<option value="${user.id}" ${Number(job.assigned_user_id) === Number(user.id) ? 'selected' : ''}>${user.display_name} (${roleLabel(user.role)})</option>`,
          )
          .join('')}</select></label>
        <label>Scheduled Date<input name="scheduledFor" type="date" value="${job.scheduled_for || ''}" required></label>
      </div>
      ${isServiceJob(job) ? serviceFieldsFormMarkup(job, 'edit') : ''}
      ${isDetailJob(job) ? detailFieldsFormMarkup(job, 'edit') : ''}
      <div class="job-notes-card">
        <div class="table-header compact-header"><h4>Notes</h4></div>
        <textarea name="notes" class="job-notes-input" rows="4">${job.notes || ''}</textarea>
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
  overlay.classList.remove('hidden');
}

function renderOrderList() {
  const summary = document.querySelector('#order-list-summary');
  const table = document.querySelector('#order-list-table');
  if (!summary || !table) return;

  const rows = state.orderListItems
    .map(
      (item) => `
    <tr>
      <td><span class="part-number-link">${item.part_number}</span>${partTypeTag(item)} - ${item.description}</td>
      <td>${item.vendor_name}</td>
      <td><input class="compact-field order-list-qty-input" type="number" min="1" value="${item.quantity_requested}" data-order-list-qty="${item.id}"></td>
      <td>${item.template_id || 'Standard'}</td>
      <td><input class="compact-field order-list-notes-input" type="text" value="${item.notes || ''}" data-order-list-notes="${item.id}"><div class="subtle">Created by ${item.created_by_name || 'Unknown'}${item.updated_by_name ? ` | Updated by ${item.updated_by_name}` : ''}</div></td>
      <td><div class="action-stack"><button class="tiny-action" data-order-list-save="${item.id}">Save</button><button class="tiny-action" data-order-list-delete="${item.id}">Remove</button></div></td>
    </tr>
  `,
    )
    .join('');
  table.innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;

  const groupedCount = new Set(
    state.orderListItems.map((item) => `${item.vendor_id}|${item.template_id}|${item.warehouse_id}`),
  ).size;
  summary.classList.toggle('hidden', state.orderListItems.length === 0);
  summary.textContent = state.orderListItems.length
    ? `${state.orderListItems.length} staged item(s) will create ${groupedCount} grouped purchase order(s).`
    : '';
}

function renderPurchaseOrders() {
  renderOrderList();
  const root = document.querySelector('#po-list');
  if (!root) return;
  const activePurchaseOrders = state.purchaseOrders.filter((po) => po.status !== 'Received');
  const vendorGroups = activePurchaseOrders.reduce((groups, po) => {
    const key = po.vendor_name || 'Unassigned Vendor';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(po);
    return groups;
  }, new Map());

  root.innerHTML = activePurchaseOrders.length
    ? [...vendorGroups.entries()]
        .map(
          ([vendorName, orders]) => `
    <section class="vendor-po-group">
      <div class="table-header compact-header">
        <div><h4>${vendorName}</h4><p class="subtle">${orders.length} open order(s)</p></div>
      </div>
      ${orders
        .map((po) => {
          const statusClass =
            po.status === 'Email Pending'
              ? 'status-danger'
              : po.status === 'Partial Received'
                ? 'status-info'
                : 'status-warn';
          const receivableLineKeys = [];
          const lineRows = (po.lines || [])
            .map((line) => {
              const outstanding = Math.max(Number(line.quantity_ordered) - Number(line.quantity_received), 0);
              const lineKey = `${po.id}:${line.id}`;
              const isVerified = verifiedReceiptLines.has(lineKey);
              const canReceive = outstanding > 0;
              const draftQuantity = poLineReceiveDrafts.has(lineKey)
                ? Number(poLineReceiveDrafts.get(lineKey))
                : outstanding;
              if (canReceive) receivableLineKeys.push(lineKey);
              return `
            <tr>
              <td><span class="part-number-link">${line.part_number}</span>${partTypeTag(line)}<div class="subtle">${line.description}</div></td>
              <td>${line.quantity_ordered}</td>
              <td>${line.quantity_received}</td>
              <td>${outstanding}</td>
              <td><input class="compact-field po-line-receive-input" type="number" min="0" value="${draftQuantity}" data-po-line-receive="${po.id}:${line.id}" ${canReceive ? '' : 'disabled'}></td>
              <td><label class="verification-check ${canReceive ? '' : 'verification-check-disabled'}"><input type="checkbox" data-po-line-verified="${lineKey}" ${isVerified ? 'checked' : ''} ${canReceive ? '' : 'disabled'}>Visually Verified</label></td>
            </tr>
          `;
            })
            .join('');
          const hasVerifiedReceipts = receivableLineKeys.some((lineKey) => verifiedReceiptLines.has(lineKey));
          return `
          <article class="activity-card po-card-detail" data-po-card-id="${po.id}">
            <div class="job-card-header">
              <div>
                <button type="button" class="po-number-link button-link" data-summary-route="po" data-summary-key="${po.id}">${po.po_number}</button>
                <p class="subtle">${po.vendor_name} | ${po.line_count} line item(s) | ETA ${po.eta ? formatDate(po.eta) : 'TBD'}</p>
              </div>
              <span class="status-pill ${statusClass}">${po.status}</span>
            </div>
            <div class="po-card-meta">
              <p><strong>Outstanding:</strong> ${po.outstanding_quantity}</p>
              <p><strong>Notes:</strong> ${po.notes || 'No notes'}</p>
              <p><strong>Created By:</strong> ${po.created_by_name || 'Unknown'}</p>
              ${po.checked_in_by_name ? `<p><strong>Checked In By:</strong> ${po.checked_in_by_name}${po.checked_in_at ? ` | ${formatDateTime(po.checked_in_at)}` : ''}</p>` : ''}
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Part</th><th>Ordered</th><th>Received</th><th>Outstanding</th><th>Check In Now</th><th>Visual Verification</th></tr></thead>
                <tbody>${lineRows}</tbody>
              </table>
            </div>
            <div class="po-card-actions">
              <a class="tiny-action" href="/purchase-orders/${po.id}/form" target="_blank" rel="noreferrer">Open Form</a>
              ${po.status === 'Email Pending' ? `<button class="tiny-action" data-po-status="${po.id}" data-status-value="Waiting for Part">Email Sent</button>` : ''}
              ${po.status === 'Waiting for Part' || po.status === 'Partial Received' ? `<button class="tiny-action" data-po-receive="${po.id}" ${hasVerifiedReceipts ? '' : 'disabled'}>Check In Verified Items</button>` : ''}
            </div>
          </article>
        `;
        })
        .join('')}
    </section>
  `,
        )
        .join('')
    : emptyState();
}

function renderReceivingLog() {
  const root = document.querySelector('#receiving-log');
  const archiveRoot = document.querySelector('#receiving-archive');
  if (!root || !archiveRoot) return;

  const { recent, archived } = splitRecentAndArchived(state.receivingLogs || []);
  const recentLogs = recent.slice(0, 20);
  root.innerHTML = recentLogs.length
    ? recentLogs
        .map(
          (log) =>
            `<div class="activity-card"><strong class="po-number-link">${log.po_number || 'Manual receipt'}</strong><p><span class="part-number-link">${log.part_number || 'Unknown Part'}</span></p><p class="subtle">${log.quantity} checked in by ${log.checked_in_by_name || log.received_by}</p><p class="subtle">${log.notes || 'No notes'} | ${formatDateTime(log.checked_in_at || log.created_at)}</p></div>`,
        )
        .join('')
    : emptyState();

  const groupedArchive = [...groupArchiveItemsByMonth(archived).entries()].sort((left, right) =>
    right[0].localeCompare(left[0]),
  );
  archiveRoot.innerHTML = groupedArchive.length
    ? groupedArchive
        .map(
          ([, logs]) => `
        <section class="archive-group">
          <div class="archive-header">
            <h5>${archiveMonthLabel(logs[0].created_at)}</h5>
            <p class="subtle">${logs.length} received record(s)</p>
          </div>
          <div class="activity-list compact-list">
            ${logs
              .map(
                (log) =>
                  `<div class="activity-card"><strong><span class="part-number-link">${log.part_number || 'Unknown Part'}</span></strong><p class="subtle">${log.quantity} received on ${log.po_number || 'manual receipt'}</p><p class="subtle">${log.checked_in_by_name || log.received_by} | ${formatDateTime(log.checked_in_at || log.created_at)}</p></div>`,
              )
              .join('')}
          </div>
        </section>
      `,
        )
        .join('')
    : emptyState();
}

function renderUsageLog() {
  const logs = state.usageLogs.slice(0, 12);
  document.querySelector('#usage-log').innerHTML = logs.length
    ? logs
        .map(
          (log) =>
            `<div class="activity-card"><strong class="job-number-link">${log.job_number}</strong><p class="subtle">${log.technician} used ${log.quantity} of <span class="part-number-link">${log.part_number}</span> - ${log.description}</p><p class="subtle">${log.notes || 'No notes'} - ${formatDate(log.created_at)}</p></div>`,
        )
        .join('')
    : emptyState();
}

function renderTransferLog() {
  const logs = state.transferLogs.slice(0, 12);
  document.querySelector('#transfer-log').innerHTML = logs.length
    ? logs
        .map(
          (log) => `
    <div class="activity-card">
      <strong>${log.part_number} - ${log.quantity} moved</strong>
      <p class="subtle">${log.from_warehouse_code} to ${log.to_warehouse_code} by ${log.transferred_by}</p>
      <p class="subtle">${log.notes || 'No notes'} - ${formatDate(log.created_at)}</p>
    </div>
  `,
        )
        .join('')
    : emptyState();
}

function renderTransferPreview() {
  const root = document.querySelector('#transfer-preview');
  const fromWarehouseId = Number(document.querySelector('#transfer-from').value || currentWarehouseId());
  const toWarehouseId = Number(document.querySelector('#transfer-to').value || 0);
  const quantity = Number(document.querySelector('#transfer-quantity').value || 0);
  const part = partById(document.querySelector('#transfer-part').value);
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
  select.innerHTML = options.map((option) => `<option value="${option.id}">${formatter(option)}</option>`).join('');
}

function renderArchiveCutoffSelector() {
  const select = document.querySelector('#archive-cutoff-selector');
  if (!select) return;
  select.value = String(archiveAfterDays());
}

function showLoginOverlay(message = '') {
  document.querySelector('#login-overlay')?.classList.remove('hidden');
  document.querySelector('.page-shell')?.classList.add('app-locked');
  const error = document.querySelector('#login-error');
  if (error) {
    error.textContent = message;
    error.classList.toggle('hidden', !message);
  }
}

function hideLoginOverlay() {
  document.querySelector('#login-overlay')?.classList.add('hidden');
  document.querySelector('.page-shell')?.classList.remove('app-locked');
  const error = document.querySelector('#login-error');
  if (error) {
    error.textContent = '';
    error.classList.add('hidden');
  }
}

function renderSessionUi() {
  const summary = document.querySelector('#session-summary');
  if (summary) {
    summary.innerHTML = currentUser()
      ? `<strong>${currentUser().display_name}</strong><span>${roleLabel(currentUser().role)}</span>`
      : '';
  }
  document.querySelectorAll('[data-manager-only]').forEach((element) => {
    element.classList.toggle('hidden', !isManager());
  });
  document.querySelectorAll('[data-permission]').forEach((element) => {
    element.classList.toggle('hidden', !hasPermission(element.dataset.permission));
  });
  document.querySelector('.nav-link[data-view="inventory"]')?.classList.toggle('hidden', !state.featureFlags.inventory);
  document.querySelector('#inventory-view')?.classList.toggle('hidden', !state.featureFlags.inventory);
  document
    .querySelector('.nav-link[data-view="purchase-orders"]')
    ?.classList.toggle('hidden', !state.featureFlags.purchase_orders);
  document.querySelector('#purchase-orders-view')?.classList.toggle('hidden', !state.featureFlags.purchase_orders);
  document.querySelector('.nav-link[data-view="receiving"]')?.classList.toggle('hidden', !state.featureFlags.receiving);
  document.querySelector('#receiving-view')?.classList.toggle('hidden', !state.featureFlags.receiving);
  document.querySelector('.nav-link[data-view="insights"]')?.classList.toggle('hidden', !state.featureFlags.insights);
  document.querySelector('#insights-view')?.classList.toggle('hidden', !state.featureFlags.insights);
  document.querySelector('.nav-link[data-view="users"]')?.classList.toggle('hidden', !state.featureFlags.users);
  document.querySelector('#users-view')?.classList.toggle('hidden', !state.featureFlags.users);
  if (!hasPermission('job_access')) {
    document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
    document.querySelector('.nav-link[data-view="dashboard"]')?.classList.add('active');
    document.querySelector('#dashboard-view')?.classList.add('active');
  }
  if (!hasPermission('edit_records')) {
    hideForm(formPanels.part);
    hideForm(formPanels.vendor);
    hideForm(formPanels.orderForm);
    hideForm(formPanels.warehouse);
    hideForm(formPanels.job);
    const activeButton = document.querySelector('.nav-link.active');
    if (activeButton?.dataset.view && !['dashboard', 'jobs', 'archive'].includes(activeButton.dataset.view)) {
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      const jobsTab = document.querySelector('.nav-link[data-view="jobs"]');
      jobsTab?.classList.add('active');
      document.querySelector('#jobs-view')?.classList.add('active');
    }
  }
}

function renderSelects() {
  const vendorSelects = [document.querySelector('#part-vendor')];
  vendorSelects.forEach((select) => fillSelect(select, state.vendors, (vendor) => vendor.name));

  const vendorTemplateSelect = document.querySelector('#vendor-template');
  if (vendorTemplateSelect) {
    vendorTemplateSelect.innerHTML = orderFormTemplateOptionsMarkup();
  }
  const assignedUserSelect = document.querySelector('#job-assigned-user');
  if (assignedUserSelect) {
    const options = assignableUsers();
    assignedUserSelect.innerHTML =
      `<option value="">Choose assignee</option>` +
      options
        .map((user) => `<option value="${user.id}">${user.display_name} (${roleLabel(user.role)})</option>`)
        .join('');
  }
  const jobTypeSelect = document.querySelector('#job-type');
  if (jobTypeSelect) {
    jobTypeSelect.innerHTML = state.jobTypeOptions
      .map((option) => `<option value="${option}">${option}</option>`)
      .join('');
  }
}

function renderUsersTable() {
  const root = document.querySelector('#users-table');
  if (!root) return;
  root.innerHTML = (state.users || []).length
    ? state.users
        .map(
          (user) => `
      <tr>
        <td><strong>${user.display_name}</strong><div class="subtle">${user.username}</div></td>
        <td>${roleLabel(user.role)}</td>
        <td>${user.is_active ? 'Active' : 'Inactive'}</td>
        <td><button class="tiny-action" data-user-toggle="${user.id}" data-user-active="${user.is_active ? '0' : '1'}">${user.is_active ? 'Deactivate' : 'Reactivate'}</button></td>
      </tr>
    `,
        )
        .join('')
    : `<tr><td colspan="4">${emptyState()}</td></tr>`;
}

function renderRolePermissionsTable() {
  const root = document.querySelector('#role-permissions-table');
  if (!root) return;
  const permissionLabels = {
    inventory_access: 'Inventory',
    job_access: 'Jobs',
    purchase_orders_access: 'Purchase Orders',
    receiving_access: 'Receiving',
    notes_access: 'Notes',
    user_management: 'Users',
    reporting_access: 'Reporting',
    receive_jobs: 'Receive Jobs',
    complete_jobs: 'Complete Jobs',
    edit_records: 'Edit Records',
    delete_records: 'Delete Records',
  };
  root.innerHTML = (state.rolePermissions || []).length
    ? state.rolePermissions
        .map(
          (roleConfig) => `
      <tr>
        <td><strong>${roleLabel(roleConfig.role)}</strong></td>
        <td>
          <div class="role-permission-grid">
            ${Object.entries(permissionLabels)
              .map(
                ([key, label]) => `
              <label class="role-permission-toggle">
                <input type="checkbox" data-role-permission-input="${roleConfig.role}:${key}" ${
                  roleConfig[key] ? 'checked' : ''
                }>
                <span>${label}</span>
              </label>
            `,
              )
              .join('')}
          </div>
        </td>
        <td><button class="tiny-action" data-save-role-permissions="${roleConfig.role}">Save</button></td>
      </tr>
    `,
        )
        .join('')
    : `<tr><td colspan="3">${emptyState()}</td></tr>`;
}

function safeRender(label, renderFn) {
  try {
    renderFn();
  } catch (error) {
    renderFeatureFallback(label);
    logClientError(`Render failed for ${label}`, error, { feature: label }, 'render');
  }
}

function renderAll() {
  safeRender('session ui', renderSessionUi);
  safeRender('warehouse selector', renderWarehouseSelector);
  safeRender('archive cutoff selector', renderArchiveCutoffSelector);
  safeRender('inventory attention badge', renderInventoryAttentionBadge);
  safeRender('purchase order attention badge', renderPoAttentionBadge);
  safeRender('jobs attention badge', renderJobsAttentionBadge);
  safeRender('inventory category init', initializeCollapsedCategories);
  safeRender('jobs init', initializeCollapsedJobs);
  safeRender('selects', renderSelects);
  safeRender('inventory filters', renderInventoryFilters);
  safeRender('dashboard', renderDashboard);
  safeRender('insights', renderInsights);
  safeRender('inventory table', renderInventoryTable);
  safeRender('vendor table', renderVendorTable);
  safeRender('warehouse table', renderWarehouseTable);
  safeRender('purchase orders', renderPurchaseOrders);
  safeRender('receiving log', renderReceivingLog);
  safeRender('jobs list', renderJobsList);
  safeRender('archive', renderArchiveList);
  safeRender('job edit overlay', renderJobEditOverlay);
  safeRender('job draft requirements', renderJobDraftRequirements);
  safeRender('job part modal', renderJobPartModal);
  safeRender('job pull modal', renderJobPullModal);
  safeRender('inventory scan modal', renderInventoryScanModal);
  safeRender('job scan add modal', renderJobScanAddModal);
  safeRender('job completion modal', renderJobCompletionModal);
  safeRender('summary panel', renderSummaryPanel);
  safeRender('users table', renderUsersTable);
  safeRender('role permissions table', renderRolePermissionsTable);
}

function updateToggleButton(panelId) {
  const button = document.querySelector(`.form-toggle[data-form-target="${panelId}"]`);
  const panel = document.querySelector(`#${panelId}`);
  if (!button || !panel) return;
  button.textContent = panel.classList.contains('hidden') ? button.dataset.openLabel : button.dataset.closeLabel;
}

function showForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.remove('hidden');
  updateToggleButton(panelId);
}

function hideForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.add('hidden');
  updateToggleButton(panelId);
}

function toggleForm(panelId) {
  const panel = document.querySelector(`#${panelId}`);
  if (!panel) return;
  panel.classList.toggle('hidden');
  updateToggleButton(panelId);
}

function clearPartForm() {
  const form = document.querySelector('#part-form');
  if (form) {
    form.reset();
  }
  hideForm(formPanels.part);
}

function closeJobPartModal(resetFilters = false) {
  jobPartModalJobId = null;
  jobPartModalSelectedPartId = null;
  jobFormPartPickerMode = false;
  if (resetFilters) {
    jobPartModalSearch = '';
    jobPartModalFilters.status = 'all';
    jobPartModalFilters.partType = 'all';
    jobPartModalFilters.vendor = 'all';
    jobPartModalFilters.category = 'all';
    collapsedJobPartCategories.clear();
    knownJobPartCategories.clear();
  }
  const quantityInput = document.querySelector('#job-part-modal-quantity');
  if (quantityInput) {
    quantityInput.value = '1';
  }
  renderJobPartModal();
}

function stopInventoryScanCamera() {
  if (inventoryScanScannerTimer) {
    window.clearInterval(inventoryScanScannerTimer);
    inventoryScanScannerTimer = null;
  }
  if (inventoryScanScannerStream) {
    inventoryScanScannerStream.getTracks().forEach((track) => track.stop());
    inventoryScanScannerStream = null;
  }
  const preview = document.querySelector('#inventory-scan-camera-preview');
  if (preview) {
    preview.pause();
    preview.srcObject = null;
    preview.classList.add('hidden');
  }
  inventoryScanCameraEnabled = false;
}

function closeInventoryScanModal(resetSession = false) {
  stopInventoryScanCamera();
  inventoryScanModalOpen = false;
  inventoryScanValue = '';
  inventoryScanMatchedPart = null;
  if (resetSession) {
    const status = document.querySelector('#inventory-scan-camera-status');
    if (status) {
      status.textContent = 'Scan a QR code or barcode to jump straight to the matching inventory item.';
    }
  }
  renderInventoryScanModal();
}

async function startInventoryScanCamera() {
  const status = document.querySelector('#inventory-scan-camera-status');
  const preview = document.querySelector('#inventory-scan-camera-preview');
  const input = document.querySelector('#inventory-scan-input');
  if (!status || !preview || !input) return;
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
    status.textContent = 'Camera scanning is not supported in this browser. USB scanners still work in the scan field.';
    return;
  }
  stopInventoryScanCamera();
  try {
    const detector = new window.BarcodeDetector({
      formats: ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'upc_a', 'upc_e'],
    });
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    inventoryScanScannerStream = stream;
    preview.srcObject = stream;
    await preview.play();
    preview.classList.remove('hidden');
    inventoryScanCameraEnabled = true;
    status.textContent = 'Camera scanner is live. Point it at a part code.';
    inventoryScanScannerTimer = window.setInterval(async () => {
      if (!inventoryScanCameraEnabled || inventoryScanInFlight || preview.readyState < 2) return;
      const matches = await detector.detect(preview).catch(() => []);
      if (!matches.length) return;
      const firstMatch = matches[0];
      if (!firstMatch?.rawValue) return;
      inventoryScanValue = firstMatch.rawValue;
      input.value = inventoryScanValue;
      await submitInventoryScan(true);
    }, 900);
  } catch (error) {
    status.textContent = 'Unable to access the camera. Check browser permissions or use the scan field.';
    stopInventoryScanCamera();
  }
}

async function submitInventoryScan(fromCamera = false) {
  const scanInput = document.querySelector('#inventory-scan-input');
  const value = (scanInput?.value || inventoryScanValue || '').trim();
  if (!value) {
    window.alert('Scan or enter a code first.');
    return;
  }
  inventoryScanInFlight = true;
  try {
    const data = await postData('/api/parts/scan-match', {
      warehouseId: currentWarehouseId(),
      scanValue: value,
    });
    inventoryScanValue = value;
    inventoryScanMatchedPart = data.part;
    renderInventoryScanModal();
    if (fromCamera) flashToast(`Matched ${data.part.partNumber}.`);
  } catch (error) {
    window.alert(error.message);
  } finally {
    inventoryScanInFlight = false;
  }
}

function renderInventoryScanModal() {
  const overlay = document.querySelector('#inventory-scan-modal');
  const title = document.querySelector('#inventory-scan-modal-title');
  const matchPanel = document.querySelector('#inventory-scan-match-panel');
  const scanInput = document.querySelector('#inventory-scan-input');
  const cameraToggle = document.querySelector('#inventory-scan-camera-toggle');
  const cameraStatus = document.querySelector('#inventory-scan-camera-status');
  if (!overlay || !title || !matchPanel || !scanInput || !cameraToggle || !cameraStatus) return;

  if (!hasPermission('inventory_access')) {
    overlay.classList.add('hidden');
    return;
  }

  if (!inventoryScanModalOpen) {
    overlay.classList.add('hidden');
    scanInput.value = '';
    matchPanel.innerHTML = '';
    return;
  }

  title.textContent = 'Scan a part';
  scanInput.value = inventoryScanValue;
  cameraToggle.textContent = inventoryScanCameraEnabled ? 'Stop Camera' : 'Use Camera';
  if (!inventoryScanCameraEnabled && !cameraStatus.textContent.trim()) {
    cameraStatus.textContent = 'Scan a QR code or barcode to jump straight to the matching inventory item.';
  }

  const part = inventoryScanMatchedPart;
  if (!part) {
    matchPanel.innerHTML = `<div class="empty-state"><h4>Ready to scan</h4><p>Scan a part to review it, jump into editing, or stage it for ordering.</p></div>`;
  } else {
    const statePart = partById(part.id);
    const vendorLabel = part.vendorName || vendorName(part.vendorId) || 'No vendor';
    const status = statePart ? inventoryStatus(statePart) : { className: 'status-ok', label: 'Matched' };
    matchPanel.innerHTML = `
      <div class="job-pull-match-card">
        <div class="table-header compact-header">
          <div>
            <h4>${part.partNumber}</h4>
            <p class="subtle">${part.description}</p>
          </div>
          <span class="status-pill ${status.className}">${status.label}</span>
        </div>
        <div class="job-pull-metrics">
          <div><span class="subtle">Scan Code</span><strong>${part.scanCode || inventoryScanValue}</strong></div>
          <div><span class="subtle">Current Stock</span><strong>${part.currentStock}</strong></div>
          <div><span class="subtle">Category</span><strong>${part.category || 'Uncategorized'}</strong></div>
          <div><span class="subtle">Vendor</span><strong>${vendorLabel}</strong></div>
          <div><span class="subtle">Item Type</span><strong>${part.itemType === 'non_stock' ? 'Non-Stock' : 'Stocked'}</strong></div>
          <div><span class="subtle">Open Jobs Using It</span><strong>${part.openJobCount || 0}</strong></div>
        </div>
        <div class="job-pull-confirm-actions">
          <button type="button" class="primary" data-inventory-scan-edit-part="${part.id}">Edit Part</button>
          <button type="button" class="secondary" data-inventory-scan-add-to-order="${part.id}">Add to Order List</button>
          <button type="button" class="ghost" data-close-inventory-scan-modal="true">Close</button>
        </div>
      </div>
    `;
  }

  overlay.classList.remove('hidden');
  window.setTimeout(() => scanInput.focus(), 0);
}

function jobPullLogFor(jobId) {
  return jobPullRecentScans.get(Number(jobId)) || [];
}

function appendJobPullLog(jobId, entry) {
  const current = jobPullLogFor(jobId);
  const updated = [entry, ...current].slice(0, 10);
  jobPullRecentScans.set(Number(jobId), updated);
}

function stopJobPullCamera() {
  if (jobPullScannerTimer) {
    window.clearInterval(jobPullScannerTimer);
    jobPullScannerTimer = null;
  }
  if (jobPullScannerStream) {
    jobPullScannerStream.getTracks().forEach((track) => track.stop());
    jobPullScannerStream = null;
  }
  const preview = document.querySelector('#job-pull-camera-preview');
  if (preview) {
    preview.pause();
    preview.srcObject = null;
    preview.classList.add('hidden');
  }
  jobPullCameraEnabled = false;
}

async function startJobPullCamera() {
  const status = document.querySelector('#job-pull-camera-status');
  const preview = document.querySelector('#job-pull-camera-preview');
  const input = document.querySelector('#job-pull-scan-input');
  if (!status || !preview || !input) return;
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
    status.textContent = 'Camera scanning is not supported in this browser. USB scanners still work in the scan field.';
    return;
  }
  stopJobPullCamera();
  try {
    const detector = new window.BarcodeDetector({
      formats: ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'upc_a', 'upc_e'],
    });
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    jobPullScannerStream = stream;
    preview.srcObject = stream;
    await preview.play();
    preview.classList.remove('hidden');
    jobPullCameraEnabled = true;
    status.textContent = 'Camera scanner is live. Point it at a code to match a part.';
    jobPullScannerTimer = window.setInterval(async () => {
      if (!jobPullCameraEnabled || jobPullScanInFlight || preview.readyState < 2) return;
      try {
        const matches = await detector.detect(preview);
        const firstMatch = matches.find((match) => match.rawValue);
        if (!firstMatch) return;
        input.value = firstMatch.rawValue;
        jobPullScanValue = firstMatch.rawValue;
        await submitJobPullScan(true);
      } catch (_error) {
        // Ignore intermittent detector read errors while the stream is live.
      }
    }, 900);
  } catch (_error) {
    status.textContent = 'Unable to access the camera. Check browser permissions or use the scan field.';
    stopJobPullCamera();
  }
}

function closeJobPullModal(resetSession = false) {
  stopJobPullCamera();
  jobPullModalJobId = null;
  jobPullMatchedPart = null;
  jobPullScanValue = '';
  if (resetSession) {
    jobPullRecentScans.clear();
  }
  renderJobPullModal();
}

async function submitJobPullScan(fromCamera = false) {
  const scanInput = document.querySelector('#job-pull-scan-input');
  const value = (scanInput?.value || jobPullScanValue || '').trim();
  if (!jobPullModalJobId) return;
  if (!value) {
    window.alert('Scan or enter a code first.');
    return;
  }
  jobPullScanInFlight = true;
  try {
    const response = await fetch(`/api/jobs/${jobPullModalJobId}/scan-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ warehouseId: currentWarehouseId(), scanValue: value }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Unable to match that scan.');
    }
    jobPullScanValue = value;
    jobPullMatchedPart = data;
    renderJobPullModal();
    if (fromCamera) flashToast(`Matched ${data.part.partNumber}.`);
  } catch (error) {
    jobPullMatchedPart = null;
    renderJobPullModal();
    window.alert(error.message);
  } finally {
    jobPullScanInFlight = false;
  }
}

function filteredJobModalParts() {
  const search = jobPartModalSearch.trim().toLowerCase();
  return state.parts.filter((part) => {
    const status = inventoryStatus(part).label;
    const matchesSearch = [part.part_number, part.description, part.category, vendorName(part.vendor_id)]
      .join(' ')
      .toLowerCase()
      .includes(search);
    const matchesStatus = jobPartModalFilters.status === 'all' || status === jobPartModalFilters.status;
    const matchesPartType =
      jobPartModalFilters.partType === 'all' || partTypeLabel(part) === jobPartModalFilters.partType;
    const matchesVendor = jobPartModalFilters.vendor === 'all' || String(part.vendor_id) === jobPartModalFilters.vendor;
    const matchesCategory =
      jobPartModalFilters.category === 'all' || (part.category || 'Uncategorized') === jobPartModalFilters.category;
    return matchesSearch && matchesStatus && matchesPartType && matchesVendor && matchesCategory;
  });
}

function initializeCollapsedJobModalCategories(parts) {
  const categories = [...new Set(parts.map((part) => part.category || 'Uncategorized'))];
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
  const overlay = document.querySelector('#job-part-modal');
  const table = document.querySelector('#job-part-modal-table');
  const title = document.querySelector('#job-part-modal-title');
  const searchInput = document.querySelector('#job-part-modal-search');
  const statusSelect = document.querySelector('#job-part-modal-status-filter');
  const typeSelect = document.querySelector('#job-part-modal-type-filter');
  const vendorSelect = document.querySelector('#job-part-modal-vendor-filter');
  const categorySelect = document.querySelector('#job-part-modal-category-filter');
  const selectedLabel = document.querySelector('#job-part-modal-selected');
  const confirmButton = document.querySelector('#job-part-modal-confirm');
  if (
    !overlay ||
    !table ||
    !title ||
    !searchInput ||
    !statusSelect ||
    !typeSelect ||
    !vendorSelect ||
    !categorySelect ||
    !selectedLabel ||
    !confirmButton
  )
    return;

  if (!canManageJobs()) {
    overlay.classList.add('hidden');
    return;
  }

  if (!jobPartModalJobId && !jobFormPartPickerMode) {
    overlay.classList.add('hidden');
    searchInput.value = '';
    table.innerHTML = '';
    return;
  }

  const job = jobById(jobPartModalJobId);
  title.textContent = jobFormPartPickerMode
    ? 'Add part to new job'
    : job
      ? `Add part to ${job.job_number}`
      : 'Select a part';
  searchInput.value = jobPartModalSearch;

  const statuses = [
    'Healthy',
    'Low Stock',
    'Order In Process',
    'Order Processed',
    'Order Staged',
    'Out of Stock',
    'Non-Stock',
  ];
  statusSelect.innerHTML = `<option value="all">All Statuses</option>${statuses.map((status) => `<option value="${status}">${status}</option>`).join('')}`;
  statusSelect.value = jobPartModalFilters.status;
  typeSelect.innerHTML =
    '<option value="all">All Items</option><option value="Stocked">Stocked Only</option><option value="Non-Stock">Non-Stock Only</option>';
  typeSelect.value = jobPartModalFilters.partType;
  vendorSelect.innerHTML = `<option value="all">All Vendors</option>${state.vendors.map((vendor) => `<option value="${vendor.id}">${vendor.name}</option>`).join('')}`;
  vendorSelect.value = jobPartModalFilters.vendor;
  const categories = [...new Set(state.parts.map((part) => part.category || 'Uncategorized'))].sort((left, right) =>
    left.localeCompare(right),
  );
  categorySelect.innerHTML = `<option value="all">All Categories</option>${categories.map((category) => `<option value="${category}">${category}</option>`).join('')}`;
  categorySelect.value = jobPartModalFilters.category;

  const filteredParts = filteredJobModalParts();
  initializeCollapsedJobModalCategories(filteredParts);
  const groups = [...partCategoryGroups(filteredParts).entries()].sort((left, right) =>
    left[0].localeCompare(right[0]),
  );
  const rows = groups
    .map(([category, parts]) => {
      const isCollapsed = collapsedJobPartCategories.has(category);
      const header = `
      <tr class="category-row" data-job-modal-category-toggle="${category}">
        <td colspan="6">
          <div class="category-row-inner">
            <div class="category-title-wrap">
              <button type="button" class="category-toggle" data-job-modal-category-toggle="${category}">${isCollapsed ? '>' : 'v'}</button>
              <strong>${category}</strong>
              <span class="subtle">${parts.length} parts</span>
            </div>
          </div>
        </td>
      </tr>
    `;
      if (isCollapsed) return header;
      const partRows = parts
        .map((part) => {
          const status = inventoryStatus(part);
          const isSelected = Number(jobPartModalSelectedPartId) === Number(part.id);
          return `
        <tr class="${isSelected ? 'selected-modal-row' : ''}">
          <td class="part-meta"><strong class="part-number-link">${part.part_number}</strong>${partTypeTag(part)}<span class="subtle">${part.description}</span></td>
          <td><img class="part-thumb" src="${makePartThumbnail(part)}" alt="${part.part_number} thumbnail"></td>
          <td>${part.stock}</td>
          <td>${vendorName(part.vendor_id)}</td>
          <td><span class="status-pill ${status.className}">${status.label}</span></td>
          <td><button type="button" class="tiny-action" data-select-job-modal-part="${part.id}">${isSelected ? 'Selected' : 'Select'}</button></td>
        </tr>
      `;
        })
        .join('');
      return `${header}${partRows}`;
    })
    .join('');
  table.innerHTML = rows || `<tr><td colspan="6">${emptyState()}</td></tr>`;

  const selectedPart = partById(jobPartModalSelectedPartId);
  selectedLabel.textContent = selectedPart
    ? `Selected: ${selectedPart.part_number} (${partTypeLabel(selectedPart)}) - ${selectedPart.description}`
    : 'Choose a part from the list below.';
  confirmButton.disabled = !selectedPart;
  confirmButton.textContent = jobFormPartPickerMode ? 'Add Selected Part' : 'Add Selected Part';
  overlay.classList.remove('hidden');
}

function renderJobPullModal() {
  const overlay = document.querySelector('#job-pull-modal');
  const title = document.querySelector('#job-pull-modal-title');
  const matchPanel = document.querySelector('#job-pull-match-panel');
  const logRoot = document.querySelector('#job-pull-log');
  const scanInput = document.querySelector('#job-pull-scan-input');
  const cameraToggle = document.querySelector('#job-pull-camera-toggle');
  const cameraStatus = document.querySelector('#job-pull-camera-status');
  if (!overlay || !title || !matchPanel || !logRoot || !scanInput || !cameraToggle || !cameraStatus) return;

  if (!jobPullModalJobId) {
    overlay.classList.add('hidden');
    scanInput.value = '';
    matchPanel.innerHTML = '';
    logRoot.innerHTML = '';
    return;
  }

  const job = jobById(jobPullModalJobId);
  if (!job) {
    closeJobPullModal();
    return;
  }

  title.textContent = `Scan parts for ${job.job_number}`;
  scanInput.value = jobPullScanValue;
  cameraToggle.textContent = jobPullCameraEnabled ? 'Stop Camera' : 'Use Camera';
  if (!jobPullCameraEnabled && !cameraStatus.textContent.trim()) {
    cameraStatus.textContent =
      'USB barcode scanners can type directly into the scan field. Camera scanning works on supported phones and tablets.';
  }

  const part = jobPullMatchedPart?.part;
  if (!part) {
    matchPanel.innerHTML = `<div class="empty-state"><h4>Ready to scan</h4><p>Scan a part code to review the match, confirm the quantity, and update the job in real time.</p></div>`;
  } else {
    const suggestedQuantity = Math.max(Math.min(part.quantityRemaining || 1, part.currentStock || 1), 1);
    const assignmentWarning = part.assignedToJob
      ? ''
      : `<div class="alert-card job-pull-warning-card"><div><strong>Part not assigned to this job</strong><p class="subtle">You can cancel, add it to this job and pull it, or mark it as miscellaneous or extra usage.</p></div></div>`;
    const stockWarning =
      part.currentStock === 0
        ? `<div class="alert-card job-pull-warning-card"><div><strong>No stock available</strong><p class="subtle">This part matched, but the on-hand quantity is zero.</p></div></div>`
        : '';
    const actionButtons = part.assignedToJob
      ? `<button type="button" class="primary" data-scan-pull-action="job_requirement">Confirm Pull</button>`
      : `<button type="button" class="primary" data-scan-pull-action="add_to_job">Add Part to Job and Pull</button><button type="button" class="secondary" data-scan-pull-action="misc_usage">Mark Misc / Extra Usage</button><button type="button" class="ghost" data-close-job-pull-modal="true">Cancel</button>`;
    matchPanel.innerHTML = `
      <div class="job-pull-match-card">
        <div class="table-header compact-header">
          <div>
            <h4>${part.partNumber}</h4>
            <p class="subtle">${part.description}</p>
          </div>
          <span class="status-pill ${part.assignedToJob ? 'status-ok' : 'status-warn'}">${part.assignedToJob ? 'Assigned to Job' : 'Not Assigned'}</span>
        </div>
        <div class="job-pull-metrics">
          <div><span class="subtle">Scan Code</span><strong>${part.scanCode || jobPullScanValue}</strong></div>
          <div><span class="subtle">Current Stock</span><strong>${part.currentStock}</strong></div>
          <div><span class="subtle">Qty Needed</span><strong>${part.quantityNeeded}</strong></div>
          <div><span class="subtle">Already Pulled</span><strong>${part.quantityPulled}</strong></div>
          <div><span class="subtle">Remaining to Pull</span><strong>${part.quantityRemaining}</strong></div>
        </div>
        ${assignmentWarning}
        ${stockWarning}
        <div class="job-pull-confirm-row">
          <label>Quantity to Pull<input id="job-pull-quantity" type="number" min="1" max="${Math.max(part.currentStock, 1)}" value="${suggestedQuantity}"></label>
          <div class="job-pull-confirm-actions">${actionButtons}</div>
        </div>
        ${part.assignedToJob ? `<p class="subtle">If the quantity exceeds the remaining amount needed, the app will show an over-pull confirmation before inventory changes.</p>` : ''}
      </div>
    `;
  }

  const logs = jobPullLogFor(jobPullModalJobId);
  logRoot.innerHTML = logs.length
    ? logs
        .map(
          (entry) => `
    <div class="activity-card">
      <strong>${entry.partNumber}</strong>
      <p class="subtle">${entry.action} | Qty ${entry.quantity}</p>
      <p class="subtle">${entry.scanCode || 'No scan code'} | ${formatDateTime(entry.timestamp)}</p>
    </div>
  `,
        )
        .join('')
    : emptyState();

  overlay.classList.remove('hidden');
  window.setTimeout(() => scanInput.focus(), 0);
}

function stopJobScanAddCamera() {
  if (jobScanAddScannerTimer) {
    window.clearInterval(jobScanAddScannerTimer);
    jobScanAddScannerTimer = null;
  }
  if (jobScanAddScannerStream) {
    jobScanAddScannerStream.getTracks().forEach((track) => track.stop());
    jobScanAddScannerStream = null;
  }
  const preview = document.querySelector('#job-scan-add-camera-preview');
  if (preview) {
    preview.pause();
    preview.srcObject = null;
    preview.classList.add('hidden');
  }
  jobScanAddCameraEnabled = false;
}

function closeJobScanAddModal(resetSession = false) {
  stopJobScanAddCamera();
  jobScanAddModalJobId = null;
  jobScanAddMatchedPart = null;
  jobScanAddValue = '';
  if (resetSession) {
    const status = document.querySelector('#job-scan-add-camera-status');
    if (status) {
      status.textContent = 'Scan a part to add it directly to the selected job with the required quantity you choose.';
    }
  }
  renderJobScanAddModal();
}

async function startJobScanAddCamera() {
  const status = document.querySelector('#job-scan-add-camera-status');
  const preview = document.querySelector('#job-scan-add-camera-preview');
  const input = document.querySelector('#job-scan-add-input');
  if (!status || !preview || !input) return;
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
    status.textContent = 'Camera scanning is not supported in this browser. USB scanners still work in the scan field.';
    return;
  }
  stopJobScanAddCamera();
  try {
    const detector = new window.BarcodeDetector({
      formats: ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'upc_a', 'upc_e'],
    });
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    jobScanAddScannerStream = stream;
    preview.srcObject = stream;
    await preview.play();
    preview.classList.remove('hidden');
    jobScanAddCameraEnabled = true;
    status.textContent = 'Camera scanner is live. Point it at a part code.';
    jobScanAddScannerTimer = window.setInterval(async () => {
      if (!jobScanAddCameraEnabled || jobScanAddInFlight || preview.readyState < 2) return;
      const matches = await detector.detect(preview).catch(() => []);
      if (!matches.length) return;
      const firstMatch = matches[0];
      if (!firstMatch?.rawValue) return;
      jobScanAddValue = firstMatch.rawValue;
      input.value = jobScanAddValue;
      await submitJobScanAdd(true);
    }, 900);
  } catch (error) {
    status.textContent = 'Unable to access the camera. Check browser permissions or use the scan field.';
    stopJobScanAddCamera();
  }
}

async function submitJobScanAdd(fromCamera = false) {
  const scanInput = document.querySelector('#job-scan-add-input');
  const value = (scanInput?.value || jobScanAddValue || '').trim();
  if (!value) {
    window.alert('Scan or enter a code first.');
    return;
  }
  if (!jobScanAddModalJobId) return;
  jobScanAddInFlight = true;
  try {
    const data = await postData(`/api/jobs/${jobScanAddModalJobId}/scan-match`, {
      warehouseId: currentWarehouseId(),
      scanValue: value,
    });
    jobScanAddValue = value;
    jobScanAddMatchedPart = data.part;
    renderJobScanAddModal();
    if (fromCamera) flashToast(`Matched ${data.part.partNumber}.`);
  } catch (error) {
    window.alert(error.message);
  } finally {
    jobScanAddInFlight = false;
  }
}

function renderJobScanAddModal() {
  const overlay = document.querySelector('#job-scan-add-modal');
  const title = document.querySelector('#job-scan-add-modal-title');
  const matchPanel = document.querySelector('#job-scan-add-match-panel');
  const scanInput = document.querySelector('#job-scan-add-input');
  const cameraToggle = document.querySelector('#job-scan-add-camera-toggle');
  const cameraStatus = document.querySelector('#job-scan-add-camera-status');
  if (!overlay || !title || !matchPanel || !scanInput || !cameraToggle || !cameraStatus) return;

  if (!canManageJobs()) {
    overlay.classList.add('hidden');
    return;
  }

  if (!jobScanAddModalJobId) {
    overlay.classList.add('hidden');
    scanInput.value = '';
    matchPanel.innerHTML = '';
    return;
  }

  const job = jobById(jobScanAddModalJobId);
  if (!job) {
    closeJobScanAddModal();
    return;
  }

  title.textContent = `Scan part to add to ${job.job_number}`;
  scanInput.value = jobScanAddValue;
  cameraToggle.textContent = jobScanAddCameraEnabled ? 'Stop Camera' : 'Use Camera';
  if (!jobScanAddCameraEnabled && !cameraStatus.textContent.trim()) {
    cameraStatus.textContent =
      'Scan a part to add it directly to the selected job with the required quantity you choose.';
  }

  const part = jobScanAddMatchedPart;
  if (!part) {
    matchPanel.innerHTML = `<div class="empty-state"><h4>Ready to scan</h4><p>Scan a part to add it to this job without browsing the full catalog.</p></div>`;
  } else {
    const suggestedQuantity = Math.max(part.assignedToJob ? 1 : Number(part.quantityRemaining || 1), 1);
    const actionLabel = part.assignedToJob ? 'Increase Required Qty' : 'Add Part to Job';
    matchPanel.innerHTML = `
      <div class="job-pull-match-card">
        <div class="table-header compact-header">
          <div>
            <h4>${part.partNumber}</h4>
            <p class="subtle">${part.description}</p>
          </div>
          <span class="status-pill ${part.assignedToJob ? 'status-warn' : 'status-ok'}">${part.assignedToJob ? 'Already on Job' : 'Not on Job Yet'}</span>
        </div>
        <div class="job-pull-metrics">
          <div><span class="subtle">Scan Code</span><strong>${part.scanCode || jobScanAddValue}</strong></div>
          <div><span class="subtle">Current Stock</span><strong>${part.currentStock}</strong></div>
          <div><span class="subtle">Qty Needed</span><strong>${part.quantityNeeded}</strong></div>
          <div><span class="subtle">Already Pulled</span><strong>${part.quantityPulled}</strong></div>
          <div><span class="subtle">Remaining to Pull</span><strong>${part.quantityRemaining}</strong></div>
          <div><span class="subtle">Item Type</span><strong>${part.itemType === 'non_stock' ? 'Non-Stock' : 'Stocked'}</strong></div>
        </div>
        <div class="job-pull-confirm-row">
          <label>Quantity to Add<input id="job-scan-add-quantity" type="number" min="1" value="${suggestedQuantity}"></label>
          <div class="job-pull-confirm-actions">
            <button type="button" class="primary" data-job-scan-add-confirm="${part.id}">${actionLabel}</button>
            <button type="button" class="ghost" data-close-job-scan-add-modal="true">Close</button>
          </div>
        </div>
        <p class="subtle">${part.assignedToJob ? 'This will increase the required quantity for the existing job part.' : 'This will create a new required part line on the job.'}</p>
      </div>
    `;
  }

  overlay.classList.remove('hidden');
  window.setTimeout(() => scanInput.focus(), 0);
}

function clearReorderForm() {
  return;
}

function clearVendorForm() {
  document.querySelector('#vendor-form').reset();
  const templateSelect = document.querySelector('#vendor-template');
  if (templateSelect) templateSelect.value = '';
  hideForm(formPanels.vendor);
}

function clearOrderFormTemplateForm() {
  document.querySelector('#order-form-template-form').reset();
  document.querySelector('#order-form-template-variant').value = 'aquaflow';
  hideForm(formPanels.orderForm);
}

function clearWarehouseForm() {
  document.querySelector('#warehouse-form').reset();
  hideForm(formPanels.warehouse);
}

function renderJobDraftRequirements() {
  const container = document.querySelector('#job-required-parts');
  if (!container) return;
  container.innerHTML = jobDraftRequirements.length
    ? jobDraftRequirements
        .map((requirement) => {
          const part = partById(requirement.partId);
          return `
      <div class="job-part-row">
        <div class="job-part-copy">
          <strong><span class="part-number-link">${part ? part.part_number : 'Unknown'}</span>${part ? partTypeTag(part) : ''}${part ? ` <span class="subtle">- ${part.description}</span>` : ''}</strong>
          <p class="subtle">Required ${requirement.requiredQuantity}</p>
        </div>
        <div class="job-part-actions">
          <button type="button" class="tiny-action" data-edit-draft-job-part="${requirement.partId}">Change Qty</button>
          <button type="button" class="tiny-action" data-remove-draft-job-part="${requirement.partId}">Remove</button>
        </div>
      </div>
    `;
        })
        .join('')
    : `<div class="empty-state compact-empty-state"><p>No parts added yet. Use the inventory picker to add only what this job needs.</p></div>`;
}

function renderServiceJobFormSections() {
  const root = document.querySelector('#service-job-form-sections');
  if (!root) return;
  const jobType = document.querySelector('#job-type')?.value || 'Install';
  if (isDetailJob({ job_type: jobType })) {
    root.innerHTML = detailFieldsFormMarkup(
      {
        job_type: jobType,
        customer_name: document.querySelector('#job-customer')?.value || '',
        address: document.querySelector('#job-address')?.value || '',
        linked_contract_number: document.querySelector('#job-number')?.value || '',
      },
      'create',
    );
    root.classList.remove('hidden');
    return;
  }
  if (!isServiceJob({ job_type: jobType })) {
    root.innerHTML = '';
    root.classList.add('hidden');
    return;
  }
  root.innerHTML = serviceFieldsFormMarkup(
    {
      job_type: jobType,
      customer_name: document.querySelector('#job-customer')?.value || '',
      address: document.querySelector('#job-address')?.value || '',
      scheduled_for: document.querySelector('#job-scheduled-for')?.value || '',
      status: 'Scheduled',
      service_code: jobType === 'Warranty' ? 'Warranty' : 'Service',
    },
    'create',
  );
  root.classList.remove('hidden');
}

function resetJobForm() {
  const form = document.querySelector('#job-form');
  if (form) {
    form.reset();
  }
  const container = document.querySelector('#job-required-parts');
  if (container) {
    container.innerHTML = '';
  }
  jobDraftRequirements = [];
  renderJobDraftRequirements();
  setJobFormMessage('');
  const jobTypeSelect = document.querySelector('#job-type');
  if (jobTypeSelect) {
    jobTypeSelect.value = 'Install';
  }
  renderServiceJobFormSections();
  hideForm(formPanels.job);
}

function bindNavigation() {
  document.querySelectorAll('.nav-link').forEach((button) => {
    button.addEventListener('click', () => {
      if (editingJobId && button.dataset.view !== 'jobs') {
        window.alert('Save the current job before leaving the edit view.');
        return;
      }
      const currentView = document.querySelector('.nav-link.active')?.dataset.view;
      if (currentView && currentView !== button.dataset.view) {
        resetExpandableUiState();
        renderAll();
      }
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      button.classList.add('active');
      document.querySelector(`#${button.dataset.view}-view`).classList.add('active');
    });
  });
}

function bindFormToggles() {
  document.querySelectorAll('.form-toggle').forEach((button) => {
    updateToggleButton(button.dataset.formTarget);
    button.addEventListener('click', () => toggleForm(button.dataset.formTarget));
  });
}

async function loadApp(warehouseId = state.selectedWarehouseId) {
  try {
    const suffix = warehouseId ? `?warehouseId=${warehouseId}` : '';
    const response = await fetch(`/api/bootstrap${suffix}`);
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      return;
    }
    if (!response.ok) {
      throw new Error(data.error || 'Unable to load the application state.');
    }
    syncState(data);
    hideLoginOverlay();
    resetAiInsightsState();
    renderAll();
  } catch (error) {
    await logClientError('App bootstrap failed', error, { warehouseId }, 'bootstrap');
    flashToast('Some app data could not load. Showing the last safe state.', 'error');
    renderAll();
  }
}

async function postJson(url, payload) {
  const data = await postData(url, payload);
  syncState(data);
  renderAll();
}

async function postData(url, payload) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      throw new Error(data.error || 'Sign in required.');
    }
    if (!response.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    hideLoginOverlay();
    return data;
  } catch (error) {
    await logClientError('POST request failed', error, { url, payloadKeys: Object.keys(payload || {}) }, 'request');
    throw error;
  }
}

async function postFormData(url, formData) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      throw new Error(data.error || 'Sign in required.');
    }
    if (!response.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    syncState(data);
    hideLoginOverlay();
    renderAll();
  } catch (error) {
    await logClientError('Form upload failed', error, { url }, 'request');
    throw error;
  }
}

async function postReorder(url, payload) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      throw new Error(data.error || 'Sign in required.');
    }
    if (!response.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    syncState(data.state);
    hideLoginOverlay();
    renderAll();
    return data.createdReorderId;
  } catch (error) {
    await logClientError('Reorder request failed', error, { url, payloadKeys: Object.keys(payload || {}) }, 'request');
    throw error;
  }
}

async function postCreatedPurchaseOrder(url, payload) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      throw new Error(data.error || 'Sign in required.');
    }
    if (!response.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    syncState(data.state);
    hideLoginOverlay();
    renderAll();
    return data.createdPoId;
  } catch (error) {
    await logClientError(
      'Purchase order creation failed',
      error,
      { url, payloadKeys: Object.keys(payload || {}) },
      'request',
    );
    throw error;
  }
}

async function postScanPull(url, payload) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLoginOverlay(data.error || 'Sign in required.');
      throw new Error(data.error || 'Sign in required.');
    }
    if (!response.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    syncState(data.state);
    hideLoginOverlay();
    renderAll();
    return data.scanLogEntry;
  } catch (error) {
    await logClientError(
      'Scan pull request failed',
      error,
      { url, payloadKeys: Object.keys(payload || {}) },
      'request',
    );
    throw error;
  }
}

async function postAction(url, payload, confirmationMessage = '') {
  if (confirmationMessage && !window.confirm(confirmationMessage)) {
    return;
  }
  await postJson(url, payload);
}

function bindForms() {
  document.querySelector('#part-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await postJson('/api/parts', {
      warehouseId: currentWarehouseId(),
      partNumber: document.querySelector('#part-number').value.trim(),
      scanCode: document.querySelector('#part-scan-code').value.trim(),
      description: document.querySelector('#part-description').value.trim(),
      category: document.querySelector('#part-category').value.trim(),
      itemType: document.querySelector('#part-item-type').value,
      stock: Number(document.querySelector('#part-stock').value),
      reorderPoint: Number(document.querySelector('#part-reorder').value),
      vendorId: Number(document.querySelector('#part-vendor').value),
      unitCost: Number(document.querySelector('#part-cost').value),
    })
      .then(clearPartForm)
      .catch((error) => window.alert(error.message));
  });

  document.querySelector('#vendor-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await postJson('/api/vendors', {
      warehouseId: currentWarehouseId(),
      name: document.querySelector('#vendor-name').value.trim(),
      contact: document.querySelector('#vendor-contact').value.trim(),
      email: document.querySelector('#vendor-email').value.trim(),
      phone: document.querySelector('#vendor-phone').value.trim(),
      leadTimeDays: Number(document.querySelector('#vendor-lead-time').value),
      linkedTemplateId: document.querySelector('#vendor-template').value,
    })
      .then(clearVendorForm)
      .catch((error) => window.alert(error.message));
  });

  document.querySelector('#order-form-template-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await postJson('/api/order-form-templates', {
      warehouseId: currentWarehouseId(),
      templateId: document.querySelector('#order-form-template-id').value.trim(),
      name: document.querySelector('#order-form-template-name').value.trim(),
      formVariant: document.querySelector('#order-form-template-variant').value,
      notes: document.querySelector('#order-form-template-notes').value.trim(),
    })
      .then(clearOrderFormTemplateForm)
      .catch((error) => window.alert(error.message));
  });

  document.querySelector('#warehouse-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await postJson('/api/warehouses', {
      name: document.querySelector('#warehouse-name').value.trim(),
      code: document.querySelector('#warehouse-code').value.trim(),
    })
      .then(clearWarehouseForm)
      .catch((error) => window.alert(error.message));
  });

  document.querySelector('#job-type')?.addEventListener('change', renderServiceJobFormSections);

  document.querySelector('#job-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    setJobFormMessage('');
    const jobForm = document.querySelector('#job-form');
    const jobFormData = jobForm ? new FormData(jobForm) : null;
    const requirements = [...jobDraftRequirements];
    const selectedJobType = document.querySelector('#job-type').value.trim();
    const assignedUserId = Number(document.querySelector('#job-assigned-user').value || 0) || null;
    await postJson('/api/jobs', {
      warehouseId: currentWarehouseId(),
      jobNumber: document.querySelector('#job-number').value.trim(),
      customerName: document.querySelector('#job-customer').value.trim(),
      address: document.querySelector('#job-address').value.trim(),
      title: document.querySelector('#job-title').value.trim(),
      jobType: selectedJobType,
      assignedUserId,
      technician: userById(assignedUserId)?.display_name || '',
      scheduledFor: document.querySelector('#job-scheduled-for').value,
      requirements,
      ...servicePayloadFromFormData(jobFormData),
      ...detailPayloadFromFormData(jobFormData),
    })
      .then(() => {
        resetJobForm();
        flashToast('Job created.');
      })
      .catch((error) => {
        setJobFormMessage(error.message || 'Unable to create the job. Check the form values and try again.');
      });
  });

  document.querySelector('#user-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await postJson('/api/users', {
      username: document.querySelector('#user-username').value.trim(),
      displayName: document.querySelector('#user-display-name').value.trim(),
      role: document.querySelector('#user-role').value,
      password: document.querySelector('#user-password').value,
      isActive: true,
    })
      .then(() => {
        document.querySelector('#user-form')?.reset();
      })
      .catch((error) => window.alert(error.message));
  });
}

function bindAuth() {
  document.querySelector('#auth-login-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: document.querySelector('#login-username').value.trim(),
        password: document.querySelector('#login-password').value,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      showLoginOverlay(data.error || 'Unable to sign in.');
      return;
    }
    document.querySelector('#login-password').value = '';
    hideLoginOverlay();
    await loadApp();
  });
  document.querySelector('#logout-button')?.addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    state.currentUser = null;
    showLoginOverlay('Signed out.');
  });
  document.querySelector('#user-form-clear')?.addEventListener('click', () => {
    document.querySelector('#user-form')?.reset();
  });
}

function bindActions() {
  document.querySelectorAll('[data-jobs-workflow]').forEach((button) => {
    button.addEventListener('click', () => {
      activeJobsWorkflow = button.dataset.jobsWorkflow;
      const jobTypeSelect = document.querySelector('#job-type');
      if (jobTypeSelect && !document.querySelector('#job-form-panel')?.classList.contains('hidden')) {
        jobTypeSelect.value = activeJobsWorkflow === 'install' ? 'Install' : 'Service';
      }
      renderJobsList();
    });
  });
  document.querySelector('#inventory-search').addEventListener('input', renderInventoryTable);
  [
    '#inventory-status-filter',
    '#inventory-type-filter',
    '#inventory-vendor-filter',
    '#inventory-category-filter',
  ].forEach((selector) => {
    document.querySelector(selector).addEventListener('change', (event) => {
      if (selector === '#inventory-status-filter') inventoryFilters.status = event.target.value;
      if (selector === '#inventory-type-filter') inventoryFilters.partType = event.target.value;
      if (selector === '#inventory-vendor-filter') inventoryFilters.vendor = event.target.value;
      if (selector === '#inventory-category-filter') inventoryFilters.category = event.target.value;
      renderInventoryTable();
    });
  });
  document.querySelector('#part-form-clear').addEventListener('click', clearPartForm);
  document.querySelector('#vendor-form-clear').addEventListener('click', clearVendorForm);
  document.querySelector('#order-form-template-clear').addEventListener('click', clearOrderFormTemplateForm);
  document.querySelector('#warehouse-form-clear').addEventListener('click', clearWarehouseForm);
  document.querySelector('#job-add-part-row').addEventListener('click', () => {
    jobFormPartPickerMode = true;
    jobPartModalJobId = null;
    jobPartModalSelectedPartId = null;
    jobPartModalSearch = '';
    jobPartModalFilters.status = 'all';
    jobPartModalFilters.vendor = 'all';
    jobPartModalFilters.category = 'all';
    collapsedJobPartCategories.clear();
    renderJobPartModal();
  });
  document.querySelector('#order-list-clear')?.addEventListener('click', async () => {
    await postAction(
      '/api/order-list/clear',
      { warehouseId: currentWarehouseId() },
      'Clear the entire order list?',
    ).catch((error) => window.alert(error.message));
  });
  document.querySelector('#order-list-generate')?.addEventListener('click', async () => {
    const response = await fetch('/api/order-list/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ warehouseId: currentWarehouseId() }),
    });
    const data = await response.json();
    if (!response.ok) {
      window.alert(data.error || 'Request failed.');
      return;
    }
    state = data.state;
    pruneVerifiedReceipts();
    pruneInlineEditors();
    renderAll();
    const created = data.createdPurchaseOrders || [];
    if (created.length) {
      const summary = created.map((po) => `${po.poNumber} (${po.vendorName})`).join(', ');
      window.alert(`Created ${created.length} grouped purchase order(s): ${summary}`);
    }
  });
  document.querySelector('#job-part-modal-close').addEventListener('click', () => closeJobPartModal(true));
  document.querySelector('#inventory-scan-modal-close')?.addEventListener('click', () => closeInventoryScanModal(true));
  document.querySelector('#inventory-scan-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await submitInventoryScan();
  });
  document.querySelector('#inventory-scan-camera-toggle')?.addEventListener('click', async () => {
    if (inventoryScanCameraEnabled) {
      stopInventoryScanCamera();
      const status = document.querySelector('#inventory-scan-camera-status');
      if (status) status.textContent = 'Camera scanner stopped. USB scanners still work in the scan field.';
      renderInventoryScanModal();
      return;
    }
    inventoryScanValue = document.querySelector('#inventory-scan-input')?.value.trim() || inventoryScanValue;
    await startInventoryScanCamera();
    renderInventoryScanModal();
  });
  document.querySelector('#job-pull-modal-close').addEventListener('click', () => closeJobPullModal());
  document.querySelector('#job-pull-scan-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await submitJobPullScan();
  });
  document.querySelector('#job-pull-camera-toggle').addEventListener('click', async () => {
    if (jobPullCameraEnabled) {
      stopJobPullCamera();
      const status = document.querySelector('#job-pull-camera-status');
      if (status) status.textContent = 'Camera scanner stopped. USB scanners still work in the scan field.';
      renderJobPullModal();
      return;
    }
    await startJobPullCamera();
    renderJobPullModal();
  });
  document.querySelector('#job-scan-add-modal-close')?.addEventListener('click', () => closeJobScanAddModal(true));
  document.querySelector('#job-scan-add-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await submitJobScanAdd();
  });
  document.querySelector('#job-scan-add-camera-toggle')?.addEventListener('click', async () => {
    if (jobScanAddCameraEnabled) {
      stopJobScanAddCamera();
      const status = document.querySelector('#job-scan-add-camera-status');
      if (status) status.textContent = 'Camera scanner stopped. USB scanners still work in the scan field.';
      renderJobScanAddModal();
      return;
    }
    jobScanAddValue = document.querySelector('#job-scan-add-input')?.value.trim() || jobScanAddValue;
    await startJobScanAddCamera();
    renderJobScanAddModal();
  });
  document.querySelector('#job-completion-close')?.addEventListener('click', closeJobCompletionModal);
  document.querySelector('#job-completion-preview-button')?.addEventListener('click', async () => {
    if (!jobCompletionModalJobId) return;
    await postData(`/api/jobs/${jobCompletionModalJobId}/completion-preview`, {
      warehouseId: currentWarehouseId(),
      ...completionDraftValues(),
    })
      .then((data) => {
        jobCompletionPreview = data.preview;
        renderJobCompletionModal();
      })
      .catch((error) => window.alert(error.message));
  });
  document.querySelector('#job-completion-complete-only')?.addEventListener('click', async () => {
    if (!jobCompletionModalJobId) return;
    if (!window.confirm('Mark this job as completed?')) return;
    await postJson(`/api/jobs/${jobCompletionModalJobId}/complete`, {
      warehouseId: currentWarehouseId(),
      ...completionDraftValues(),
      sendEmail: false,
    })
      .then(() => {
        flashToast('Job completed.');
        closeJobCompletionModal();
      })
      .catch((error) => window.alert(error.message));
  });
  document.querySelector('#job-completion-send-button')?.addEventListener('click', async () => {
    if (!jobCompletionModalJobId) return;
    if (!window.confirm('Complete this job and send the completion email now?')) return;
    await postJson(`/api/jobs/${jobCompletionModalJobId}/complete`, {
      warehouseId: currentWarehouseId(),
      ...completionDraftValues(),
      sendEmail: true,
    })
      .then(() => {
        flashToast('Job completed and email sent.');
        closeJobCompletionModal();
      })
      .catch((error) => window.alert(error.message));
  });
  document.querySelector('#summary-panel-close')?.addEventListener('click', closeSummaryPanel);
  [
    ['#archive-install-search', 'installSearch'],
    ['#archive-detail-search', 'detailSearch'],
    ['#archive-service-search', 'serviceSearch'],
    ['#archive-po-search', 'poSearch'],
  ].forEach(([selector, key]) => {
    document.querySelector(selector)?.addEventListener('input', (event) => {
      archiveFilters[key] = String(event.target.value || '');
      renderArchiveList();
    });
  });
  [
    ['#archive-install-sort', 'installSort'],
    ['#archive-detail-sort', 'detailSort'],
    ['#archive-service-sort', 'serviceSort'],
    ['#archive-po-sort', 'poSort'],
  ].forEach(([selector, key]) => {
    document.querySelector(selector)?.addEventListener('change', (event) => {
      archiveFilters[key] = String(event.target.value || 'newest');
      renderArchiveList();
    });
  });
  document.querySelector('#job-part-modal-search').addEventListener('input', (event) => {
    jobPartModalSearch = event.target.value;
    renderJobPartModal();
  });
  document.querySelector('#job-part-modal-status-filter').addEventListener('change', (event) => {
    jobPartModalFilters.status = event.target.value;
    renderJobPartModal();
  });
  document.querySelector('#job-part-modal-type-filter').addEventListener('change', (event) => {
    jobPartModalFilters.partType = event.target.value;
    renderJobPartModal();
  });
  document.querySelector('#job-part-modal-vendor-filter').addEventListener('change', (event) => {
    jobPartModalFilters.vendor = event.target.value;
    renderJobPartModal();
  });
  document.querySelector('#job-part-modal-category-filter').addEventListener('change', (event) => {
    jobPartModalFilters.category = event.target.value;
    renderJobPartModal();
  });
  document.querySelector('#job-part-modal-confirm').addEventListener('click', async () => {
    const quantity = Number(document.querySelector('#job-part-modal-quantity')?.value || 0);
    if (!jobPartModalSelectedPartId) {
      window.alert('Select a part first.');
      return;
    }
    if (!Number.isInteger(quantity) || quantity <= 0) {
      window.alert('Enter a whole number greater than 0.');
      return;
    }
    if (jobFormPartPickerMode) {
      const existing = jobDraftRequirements.find(
        (requirement) => Number(requirement.partId) === Number(jobPartModalSelectedPartId),
      );
      if (existing) {
        existing.requiredQuantity += quantity;
      } else {
        jobDraftRequirements = [
          ...jobDraftRequirements,
          { partId: Number(jobPartModalSelectedPartId), requiredQuantity: quantity },
        ];
      }
      jobFormPartPickerMode = false;
      closeJobPartModal(true);
      renderJobDraftRequirements();
      flashToast('Part added to new job.');
      return;
    }
    const jobId = Number(jobPartModalJobId);
    await postJson(`/api/jobs/${jobId}/parts`, {
      warehouseId: currentWarehouseId(),
      partId: Number(jobPartModalSelectedPartId),
      requiredQuantity: quantity,
    })
      .then(() => {
        jobEditDirty = true;
        closeJobPartModal();
        renderJobEditOverlay();
        flashToast('Part added to job.');
      })
      .catch((error) => window.alert(error.message));
  });
  document.querySelector('#job-edit-modal-form').addEventListener('input', () => {
    if (editingJobId) jobEditDirty = true;
  });
  document.querySelectorAll('.form-toggle').forEach((button) => {
    updateToggleButton(button.dataset.formTarget);
    button.addEventListener('click', () => toggleForm(button.dataset.formTarget));
  });

  document.querySelector('#warehouse-selector').addEventListener('change', async (event) => {
    if (editingJobId) {
      window.alert('Save the current job before switching warehouses.');
      event.target.value = String(currentWarehouseId());
      return;
    }
    await loadApp(Number(event.target.value));
    clearPartForm();
    clearVendorForm();
    clearWarehouseForm();
    resetJobForm();
  });
  document.querySelector('#archive-cutoff-selector')?.addEventListener('change', (event) => {
    window.localStorage.setItem(
      ARCHIVE_CUTOFF_STORAGE_KEY,
      String(Number(event.target.value) || DEFAULT_ARCHIVE_AFTER_DAYS),
    );
    resetAiInsightsState();
    renderReceivingLog();
    renderArchiveList();
    renderInsights();
  });
  document.body.addEventListener('change', (event) => {
    const insightsFilterMap = {
      '#insights-date-range': 'dateRange',
      '#insights-job-type': 'jobType',
      '#insights-vendor': 'vendor',
      '#insights-part-category': 'partCategory',
      '#insights-part-type': 'partType',
      '#insights-warehouse': 'warehouseId',
      '#insights-crew': 'crew',
    };
    const matchingSelector = Object.keys(insightsFilterMap).find((selector) => event.target.matches(selector));
    if (matchingSelector) {
      insightsFilters[insightsFilterMap[matchingSelector]] = event.target.value;
      resetAiInsightsState();
      if (insightsDrilldown.type !== 'overview') {
        insightsDrilldown = { type: 'overview', key: 'overview' };
      }
      renderInsights();
    }
  });

  document.body.addEventListener('submit', async (event) => {
    if (!event.target.matches('#insights-ai-form')) return;
    event.preventDefault();
    const question = document.querySelector('#insights-ai-question')?.value.trim() || '';
    if (!question) {
      window.alert('Ask a question before sending it to Insights.');
      return;
    }
    await requestAiInsights('query', question);
  });

  document.body.addEventListener('click', async (event) => {
    const aiBriefButton = event.target.closest('#insights-ai-brief-button');
    if (aiBriefButton) {
      await requestAiInsights('brief');
      return;
    }

    const insightDetailClear = event.target.closest('[data-insight-detail-clear]');
    if (insightDetailClear) {
      insightsDrilldown = { type: 'overview', key: 'overview' };
      renderInsights();
      return;
    }

    const insightDetailTrigger = event.target.closest('[data-insight-detail]');
    if (insightDetailTrigger) {
      insightsDrilldown = {
        type: insightDetailTrigger.dataset.insightDetail,
        key: insightDetailTrigger.dataset.insightKey,
      };
      renderInsights();
      return;
    }

    const summaryOpenTrigger = event.target.closest('[data-summary-open]');
    if (summaryOpenTrigger) {
      const summary = buildSummaryItems(summaryOpenTrigger.dataset.summaryOpen);
      openSummaryPanel(summary.title, summary.items);
      return;
    }

    const summaryRouteTrigger = event.target.closest('[data-summary-route]');
    if (summaryRouteTrigger) {
      const routeType = summaryRouteTrigger.dataset.summaryRoute;
      const routeKey = summaryRouteTrigger.dataset.summaryKey;
      const preferArchive = summaryRouteTrigger.dataset.summaryArchive === '1';
      closeSummaryPanel();
      if (routeType === 'job') {
        openJobDestination(routeKey, preferArchive);
        return;
      }
      if (routeType === 'archived-job') {
        openJobDestination(routeKey, true);
        return;
      }
      if (routeType === 'part') {
        openPartDestination(routeKey);
        return;
      }
      if (routeType === 'po') {
        openPurchaseOrderDestination(routeKey, preferArchive);
        return;
      }
      if (routeType === 'insight-flag') {
        openInsightDestination('flag', routeKey);
        return;
      }
      if (routeType === 'job-type') {
        openInsightDestination('job-type', routeKey);
        return;
      }
      if (routeType === 'flag') {
        openInsightDestination('flag', routeKey);
        return;
      }
      if (routeType === 'insight-detail') {
        openInsightDestination('flag', routeKey);
      }
      return;
    }

    const categoryToggle = event.target.closest('[data-category-toggle]');
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

    const jobModalCategoryToggle = event.target.closest('[data-job-modal-category-toggle]');
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

    const jobToggle = event.target.closest('[data-job-toggle]');
    if (jobToggle) {
      const jobId = Number(jobToggle.dataset.jobToggle);
      if (collapsedJobs.has(jobId)) {
        collapsedJobs.delete(jobId);
      } else {
        collapsedJobs.add(jobId);
      }
      renderAll();
      return;
    }

    const weeklyUsageToggle = event.target.closest('[data-toggle-weekly-usage]');
    if (weeklyUsageToggle) {
      dashboardUsageExpanded = !dashboardUsageExpanded;
      renderDashboard();
      return;
    }

    const poStatusButton = event.target.closest('[data-po-status]');
    if (poStatusButton) {
      await postAction(
        `/api/purchase-orders/${poStatusButton.dataset.poStatus}/status`,
        { warehouseId: currentWarehouseId(), status: poStatusButton.dataset.statusValue },
        `Mark this order as ${poStatusButton.dataset.statusValue}?`,
      ).catch((error) => window.alert(error.message));
      return;
    }

    const saveJobNotesButton = event.target.closest('[data-save-job-notes]');
    if (saveJobNotesButton) {
      const jobId = Number(saveJobNotesButton.dataset.saveJobNotes);
      const notes = document.querySelector(`[data-job-notes-input="${jobId}"]`)?.value || '';
      await postJson(`/api/jobs/${jobId}/notes`, {
        warehouseId: currentWarehouseId(),
        notes,
      })
        .then(() => flashToast('Job notes saved.'))
        .catch((error) => window.alert(error.message));
      return;
    }

    const uploadJobAttachmentButton = event.target.closest('[data-upload-job-attachment]');
    if (uploadJobAttachmentButton) {
      const jobId = Number(uploadJobAttachmentButton.dataset.uploadJobAttachment);
      const input = document.querySelector(`[data-job-attachment-input="${jobId}"]`);
      const file = input?.files?.[0];
      if (!file) {
        window.alert('Choose a file first.');
        return;
      }
      const formData = new FormData();
      formData.append('attachment', file);
      await postFormData(`/api/jobs/${jobId}/attachments`, formData)
        .then(() => {
          if (input) input.value = '';
          flashToast('Job file uploaded.');
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const addJobNoteButton = event.target.closest('[data-add-job-note]');
    if (addJobNoteButton) {
      const jobId = Number(addJobNoteButton.dataset.addJobNote);
      const body = document.querySelector(`[data-job-quick-note-input="${jobId}"]`)?.value.trim() || '';
      await postJson(`/api/jobs/${jobId}/quick-notes`, {
        warehouseId: currentWarehouseId(),
        body,
      })
        .then(() => {
          const input = document.querySelector(`[data-job-quick-note-input="${jobId}"]`);
          if (input) input.value = '';
          collapsedJobs.delete(jobId);
          flashToast('Note added.');
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const copyVendorFormButton = event.target.closest('[data-copy-vendor-form]');
    if (copyVendorFormButton) {
      const vendor = (state.vendors || []).find(
        (entry) => Number(entry.id) === Number(copyVendorFormButton.dataset.copyVendorForm),
      );
      if (!vendor) return;
      const linkedForm = vendor.linked_template_name || orderFormTemplateName(vendor.linked_template_id);
      const copyText = [
        `Vendor: ${vendor.name}`,
        `Contact: ${vendor.contact || 'N/A'}`,
        `Email: ${vendor.email || 'N/A'}`,
        `Phone: ${vendor.phone || 'N/A'}`,
        `Lead Time: ${vendor.lead_time_days || 0} day(s)`,
        `Order Form: ${linkedForm || 'Not linked'}`,
      ].join('\n');
      try {
        await navigator.clipboard.writeText(copyText);
        flashToast('Vendor form copied to clipboard');
      } catch (_error) {
        window.alert('Clipboard copy is unavailable in this browser.');
      }
      return;
    }

    const deleteJobAttachmentButton = event.target.closest('[data-delete-job-attachment]');
    if (deleteJobAttachmentButton) {
      const attachmentId = Number(deleteJobAttachmentButton.dataset.deleteJobAttachment);
      await postAction(`/api/job-attachments/${attachmentId}/delete`, {}, 'Remove this job attachment?').catch(
        (error) => window.alert(error.message),
      );
      return;
    }

    const orderListSaveButton = event.target.closest('[data-order-list-save]');
    if (orderListSaveButton) {
      const itemId = Number(orderListSaveButton.dataset.orderListSave);
      const quantity = Number(document.querySelector(`[data-order-list-qty="${itemId}"]`)?.value || 0);
      const notes = document.querySelector(`[data-order-list-notes="${itemId}"]`)?.value || '';
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      await postJson(`/api/order-list/${itemId}`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes,
      }).catch((error) => window.alert(error.message));
      return;
    }

    const orderListDeleteButton = event.target.closest('[data-order-list-delete]');
    if (orderListDeleteButton) {
      await postAction(
        `/api/order-list/${orderListDeleteButton.dataset.orderListDelete}/delete`,
        { warehouseId: currentWarehouseId() },
        'Remove this item from the order list?',
      ).catch((error) => window.alert(error.message));
      return;
    }

    const openInventoryScanButton = event.target.closest('[data-open-inventory-scan-modal]');
    if (openInventoryScanButton) {
      inventoryScanModalOpen = true;
      inventoryScanValue = '';
      inventoryScanMatchedPart = null;
      renderInventoryScanModal();
      return;
    }

    const closeInventoryScanButton = event.target.closest('[data-close-inventory-scan-modal]');
    if (closeInventoryScanButton) {
      closeInventoryScanModal();
      return;
    }

    const inventoryScanEditButton = event.target.closest('[data-inventory-scan-edit-part]');
    if (inventoryScanEditButton) {
      inlineEditors.partId = Number(inventoryScanEditButton.dataset.inventoryScanEditPart);
      closeInventoryScanModal(true);
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      document.querySelector('[data-view="inventory"]')?.classList.add('active');
      document.querySelector('#inventory-view')?.classList.add('active');
      renderInventoryTable();
      return;
    }

    const inventoryScanOrderButton = event.target.closest('[data-inventory-scan-add-to-order]');
    if (inventoryScanOrderButton) {
      const part = partById(inventoryScanOrderButton.dataset.inventoryScanAddToOrder);
      if (!part) return;
      const suggested = isNonStock(part) ? 1 : Math.max(part.reorder_point * 2 - part.stock, 1);
      const requested = window.prompt(
        `How many of ${part.part_number} do you want to stage for ordering?`,
        String(suggested),
      );
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      await postJson('/api/order-list', {
        warehouseId: currentWarehouseId(),
        partId: part.id,
        quantity,
        notes: isNonStock(part)
          ? `Requested from scanned part for specific need: ${part.part_number}`
          : `Low stock reorder from scanned part: ${part.part_number}`,
      })
        .then(() => {
          flashToast(`${part.part_number} added to the order list.`);
          closeInventoryScanModal(true);
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const openJobPartModalButton = event.target.closest('[data-open-job-part-modal]');
    if (openJobPartModalButton) {
      const jobId = Number(openJobPartModalButton.dataset.openJobPartModal);
      jobFormPartPickerMode = false;
      jobPartModalJobId = jobId;
      jobPartModalSelectedPartId = null;
      jobPartModalSearch = '';
      jobPartModalFilters.status = 'all';
      jobPartModalFilters.vendor = 'all';
      jobPartModalFilters.category = 'all';
      collapsedJobPartCategories.clear();
      collapsedJobs.delete(jobId);
      renderJobPartModal();
      return;
    }

    const openJobScanAddModalButton = event.target.closest('[data-open-job-scan-add-modal]');
    if (openJobScanAddModalButton) {
      const jobId = Number(openJobScanAddModalButton.dataset.openJobScanAddModal);
      jobScanAddModalJobId = jobId;
      jobScanAddMatchedPart = null;
      jobScanAddValue = '';
      collapsedJobs.delete(jobId);
      renderJobScanAddModal();
      return;
    }

    const openJobPullModalButton = event.target.closest('[data-open-job-pull-modal]');
    if (openJobPullModalButton) {
      const jobId = Number(openJobPullModalButton.dataset.openJobPullModal);
      jobPullModalJobId = jobId;
      jobPullScanValue = '';
      jobPullMatchedPart = null;
      collapsedJobs.delete(jobId);
      renderJobPullModal();
      return;
    }

    const closeJobPullModalButton = event.target.closest('[data-close-job-pull-modal]');
    if (closeJobPullModalButton) {
      closeJobPullModal();
      return;
    }

    const closeJobScanAddModalButton = event.target.closest('[data-close-job-scan-add-modal]');
    if (closeJobScanAddModalButton) {
      closeJobScanAddModal();
      return;
    }

    const completeJobButton = event.target.closest('[data-complete-job]');
    if (completeJobButton) {
      jobCompletionModalJobId = Number(completeJobButton.dataset.completeJob);
      jobCompletionPreview = null;
      document.querySelector('#job-completion-form')?.reset();
      renderJobCompletionModal();
      return;
    }

    const followUpServiceJobButton = event.target.closest('[data-create-followup-service-job]');
    if (followUpServiceJobButton) {
      const sourceJobId = Number(followUpServiceJobButton.dataset.createFollowupServiceJob);
      if (!window.confirm('Create a follow-up service job from this ticket?')) return;
      await postData(`/api/jobs/${sourceJobId}/follow-up`, { warehouseId: currentWarehouseId() })
        .then((data) => {
          syncState(data.state);
          collapsedJobs.delete(Number(data.createdJobId));
          renderAll();
          flashToast('Follow-up service job created.');
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const selectJobModalPartButton = event.target.closest('[data-select-job-modal-part]');
    if (selectJobModalPartButton) {
      jobPartModalSelectedPartId = Number(selectJobModalPartButton.dataset.selectJobModalPart);
      renderJobPartModal();
      return;
    }

    const jobScanAddConfirmButton = event.target.closest('[data-job-scan-add-confirm]');
    if (jobScanAddConfirmButton) {
      if (!jobScanAddMatchedPart?.id || !jobScanAddModalJobId) return;
      const quantity = Number(document.querySelector('#job-scan-add-quantity')?.value || 0);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      const part = jobScanAddMatchedPart;
      const promptMessage = part.assignedToJob
        ? `Increase the required quantity for ${part.partNumber} on this job by ${quantity}?`
        : `Add ${part.partNumber} to this job with required quantity ${quantity}?`;
      if (!window.confirm(promptMessage)) {
        return;
      }
      await postJson(`/api/jobs/${jobScanAddModalJobId}/parts`, {
        warehouseId: currentWarehouseId(),
        partId: Number(part.id),
        requiredQuantity: quantity,
      })
        .then(() => {
          collapsedJobs.delete(Number(jobScanAddModalJobId));
          flashToast(`${part.partNumber} added to the job.`);
          jobScanAddMatchedPart = null;
          jobScanAddValue = '';
          renderJobScanAddModal();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const editJobButton = event.target.closest('[data-edit-job]');
    if (editJobButton) {
      const jobId = Number(editJobButton.dataset.editJob);
      editingJobId = jobId;
      jobEditDirty = false;
      collapsedJobs.delete(jobId);
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
      document.querySelector('[data-view="jobs"]')?.classList.add('active');
      document.querySelector('#jobs-view')?.classList.add('active');
      renderAll();
      return;
    }

    const deleteJobPartButton = event.target.closest('[data-delete-job-part]');
    if (deleteJobPartButton) {
      const requirementId = Number(deleteJobPartButton.dataset.deleteJobPart);
      const requirement = state.jobRequirements.find((item) => Number(item.id) === requirementId);
      if (!window.confirm('Remove this part from the job?')) {
        return;
      }
      if (requirement) {
        collapsedJobs.delete(Number(requirement.job_id));
      }
      await postJson(`/api/job-parts/${requirementId}/delete`, {
        warehouseId: currentWarehouseId(),
      })
        .then(() => {
          if (requirement) collapsedJobs.delete(Number(requirement.job_id));
          renderJobsList();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const returnJobPartButton = event.target.closest('[data-return-job-part]');
    if (returnJobPartButton) {
      const requirement = state.jobRequirements.find(
        (item) => Number(item.id) === Number(returnJobPartButton.dataset.returnJobPart),
      );
      if (!requirement) return;
      const part = partById(requirement.part_id);
      const requested = window.prompt(
        `How many of ${part ? part.part_number : 'this part'} do you want to return to inventory?`,
        String(requirement.pulled_quantity),
      );
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      collapsedJobs.delete(Number(requirement.job_id));
      await postJson(`/api/job-parts/${requirement.id}/return`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: 'Returned from job card',
      })
        .then(() => {
          collapsedJobs.delete(Number(requirement.job_id));
          renderJobsList();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const poReceiveButton = event.target.closest('[data-po-receive]');
    if (poReceiveButton) {
      const poId = Number(poReceiveButton.dataset.poReceive);
      const lineInputs = [...document.querySelectorAll(`[data-po-line-receive^="${poId}:"]`)];
      const lineReceipts = Object.fromEntries(
        lineInputs.map((input) => {
          const [, lineId] = input.dataset.poLineReceive.split(':');
          const isVerified = verifiedReceiptLines.has(`${poId}:${lineId}`);
          return [lineId, isVerified ? Number(input.value || 0) : 0];
        }),
      );
      const lineVerifications = Object.fromEntries(
        lineInputs.map((input) => {
          const [, lineId] = input.dataset.poLineReceive.split(':');
          return [lineId, verifiedReceiptLines.has(`${poId}:${lineId}`)];
        }),
      );
      const overageLines = lineInputs
        .map((input) => {
          const [, lineId] = input.dataset.poLineReceive.split(':');
          const line = state.purchaseOrders
            .find((po) => Number(po.id) === poId)
            ?.lines?.find((entry) => Number(entry.id) === Number(lineId));
          const outstanding = Math.max(Number(line?.quantity_ordered || 0) - Number(line?.quantity_received || 0), 0);
          const amount = Number(lineReceipts[lineId] || 0);
          return amount > outstanding ? { lineId, amount, outstanding } : null;
        })
        .filter(Boolean);
      const requestedTotal = Object.entries(lineReceipts).reduce((sum, [lineId, value]) => {
        return lineVerifications[lineId] ? sum + Number(value || 0) : sum;
      }, 0);
      if (requestedTotal <= 0) {
        window.alert(
          'Verify at least one line item and enter the quantities that arrived before checking this order in.',
        );
        return;
      }
      if (
        overageLines.length &&
        !window.confirm(
          'One or more verified lines exceed the remaining quantity on the PO. Continue and record the over-received shipment?',
        )
      ) {
        return;
      }
      if (!window.confirm(`Check in ${requestedTotal} verified item(s) across this purchase order?`)) {
        return;
      }
      await postJson(`/api/purchase-orders/${poId}/receive`, {
        warehouseId: currentWarehouseId(),
        lineReceipts,
        lineVerifications,
        allowOverage: overageLines.length > 0,
        receivedBy: 'Inventory',
        notes: 'Checked in from PO tab',
      })
        .then(() => {
          [...verifiedReceiptLines]
            .filter((lineKey) => lineKey.startsWith(`${poId}:`))
            .forEach((lineKey) => verifiedReceiptLines.delete(lineKey));
          renderPurchaseOrders();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const receiveJobPartDirectButton = event.target.closest('[data-receive-job-part-direct]');
    if (receiveJobPartDirectButton) {
      const requirement = state.jobRequirements.find(
        (item) => Number(item.id) === Number(receiveJobPartDirectButton.dataset.receiveJobPartDirect),
      );
      if (!requirement) return;
      const part = partById(requirement.part_id);
      const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
      const requested = window.prompt(
        `How many of ${part ? part.part_number : 'this part'} should be received directly to this job?`,
        String(remaining),
      );
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      await postJson(`/api/job-parts/${requirement.id}/receive-direct`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: isNonStock(part) ? 'Special-order item received direct to job' : 'Received direct to job',
      })
        .then(() => {
          collapsedJobs.delete(Number(requirement.job_id));
          renderJobsList();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const pullJobPartButton = event.target.closest('[data-pull-job-part]');
    if (pullJobPartButton) {
      const requirement = state.jobRequirements.find(
        (item) => Number(item.id) === Number(pullJobPartButton.dataset.pullJobPart),
      );
      if (!requirement) return;
      const remaining = Math.max(requirement.required_quantity - requirement.pulled_quantity, 0);
      const part = partById(requirement.part_id);
      const requested = window.prompt(
        `How many of ${part ? part.part_number : 'this part'} do you want to mark as pulled?`,
        String(remaining),
      );
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      collapsedJobs.delete(Number(requirement.job_id));
      await postJson(`/api/job-parts/${requirement.id}/pull`, {
        warehouseId: currentWarehouseId(),
        quantity,
        notes: 'Pulled from job card',
      })
        .then(() => {
          collapsedJobs.delete(Number(requirement.job_id));
          renderJobsList();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const scanPullActionButton = event.target.closest('[data-scan-pull-action]');
    if (scanPullActionButton) {
      if (!jobPullMatchedPart?.part) return;
      const quantity = Number(document.querySelector('#job-pull-quantity')?.value || 0);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      const action = scanPullActionButton.dataset.scanPullAction;
      const match = jobPullMatchedPart.part;
      let confirmOverpull = false;
      if (action === 'job_requirement' && quantity > Number(match.quantityRemaining || 0)) {
        confirmOverpull = window.confirm(
          `This pull is ${quantity - Number(match.quantityRemaining || 0)} over the remaining quantity needed. Continue anyway?`,
        );
        if (!confirmOverpull) return;
      }
      if (
        action === 'add_to_job' &&
        !window.confirm(`Add ${match.partNumber} to this job with required quantity ${quantity} and pull it now?`)
      )
        return;
      if (
        action === 'misc_usage' &&
        !window.confirm(`Mark ${quantity} of ${match.partNumber} as miscellaneous or extra usage for this job?`)
      )
        return;
      await postScanPull(`/api/jobs/${jobPullModalJobId}/scan-pull`, {
        warehouseId: currentWarehouseId(),
        partId: Number(match.id),
        scanValue: jobPullScanValue,
        quantity,
        action,
        confirmOverpull,
      })
        .then((scanLogEntry) => {
          appendJobPullLog(jobPullModalJobId, scanLogEntry);
          jobPullMatchedPart = null;
          jobPullScanValue = '';
          renderJobPullModal();
          flashToast(`${scanLogEntry.partNumber} updated.`);
        })
        .catch((error) => window.alert(error.message));
      return;
    }
  });

  document.body.addEventListener('change', (event) => {
    const receiveInput = event.target.closest('[data-po-line-receive]');
    if (receiveInput) {
      const lineKey = String(receiveInput.dataset.poLineReceive);
      poLineReceiveDrafts.set(lineKey, Number(receiveInput.value || 0));
      return;
    }
    const verifyBox = event.target.closest('[data-po-line-verified]');
    if (!verifyBox) return;
    const lineKey = String(verifyBox.dataset.poLineVerified);
    if (verifyBox.checked) {
      verifiedReceiptLines.add(lineKey);
    } else {
      verifiedReceiptLines.delete(lineKey);
    }
    renderPurchaseOrders();
  });

  document.body.addEventListener('click', async (event) => {
    const partButton = event.target.closest('[data-edit-part]');
    if (partButton) {
      inlineEditors.partId =
        Number(inlineEditors.partId) === Number(partButton.dataset.editPart)
          ? null
          : Number(partButton.dataset.editPart);
      renderInventoryTable();
      return;
    }

    const addToOrderListButton = event.target.closest('[data-add-to-order-list]');
    if (addToOrderListButton) {
      const part = partById(addToOrderListButton.dataset.addToOrderList);
      if (!part) return;
      const suggested = isNonStock(part) ? 1 : Math.max(part.reorder_point * 2 - part.stock, 1);
      const requested = window.prompt(
        `How many of ${part.part_number} do you want to stage for ordering?`,
        String(suggested),
      );
      if (requested === null) return;
      const quantity = Number(requested);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      postJson('/api/order-list', {
        warehouseId: currentWarehouseId(),
        partId: part.id,
        quantity,
        notes: isNonStock(part)
          ? `Requested for specific need: ${part.part_number}`
          : `Low stock reorder for ${part.part_number}`,
      }).catch((error) => window.alert(error.message));
      return;
    }

    const vendorButton = event.target.closest('[data-edit-vendor]');
    if (vendorButton) {
      inlineEditors.vendorId =
        Number(inlineEditors.vendorId) === Number(vendorButton.dataset.editVendor)
          ? null
          : Number(vendorButton.dataset.editVendor);
      renderVendorTable();
      return;
    }

    const orderFormTemplateButton = event.target.closest('[data-edit-order-form-template]');
    if (orderFormTemplateButton) {
      inlineEditors.orderFormTemplateId =
        Number(inlineEditors.orderFormTemplateId) === Number(orderFormTemplateButton.dataset.editOrderFormTemplate)
          ? null
          : Number(orderFormTemplateButton.dataset.editOrderFormTemplate);
      renderOrderFormTemplateTable();
      return;
    }

    const openOrderFormPanelButton = event.target.closest('[data-open-order-form-panel]');
    if (openOrderFormPanelButton) {
      showForm(formPanels.orderForm);
      return;
    }

    const warehouseButton = event.target.closest('[data-edit-warehouse]');
    if (warehouseButton) {
      inlineEditors.warehouseId =
        Number(inlineEditors.warehouseId) === Number(warehouseButton.dataset.editWarehouse)
          ? null
          : Number(warehouseButton.dataset.editWarehouse);
      renderWarehouseTable();
      return;
    }

    const userToggleButton = event.target.closest('[data-user-toggle]');
    if (userToggleButton) {
      const user = userById(userToggleButton.dataset.userToggle);
      if (!user) return;
      await postJson('/api/users', {
        id: Number(user.id),
        username: user.username,
        displayName: user.display_name,
        role: user.role,
        isActive: userToggleButton.dataset.userActive === '1',
      }).catch((error) => window.alert(error.message));
      return;
    }

    const saveRolePermissionsButton = event.target.closest('[data-save-role-permissions]');
    if (saveRolePermissionsButton) {
      const role = saveRolePermissionsButton.dataset.saveRolePermissions;
      const roleConfig = (state.rolePermissions || []).find((item) => item.role === role);
      if (!roleConfig) return;
      const payload = {};
      Object.keys(roleConfig)
        .filter((key) => key !== 'role')
        .forEach((key) => {
          payload[key] = Boolean(document.querySelector(`[data-role-permission-input="${role}:${key}"]`)?.checked);
        });
      await postJson(`/api/role-permissions/${role}`, payload)
        .then(() => flashToast(`${roleLabel(role)} permissions saved.`))
        .catch((error) => window.alert(error.message));
      return;
    }

    const cancelButton = event.target.closest('[data-inline-cancel]');
    if (cancelButton) {
      const kind = cancelButton.dataset.inlineCancel;
      if (kind === 'part') {
        inlineEditors.partId = null;
        renderInventoryTable();
      } else if (kind === 'vendor') {
        inlineEditors.vendorId = null;
        renderVendorTable();
      } else if (kind === 'order-form-template') {
        inlineEditors.orderFormTemplateId = null;
        renderOrderFormTemplateTable();
      } else if (kind === 'warehouse') {
        inlineEditors.warehouseId = null;
        renderWarehouseTable();
      }
      return;
    }

    const editDraftJobPartButton = event.target.closest('[data-edit-draft-job-part]');
    if (editDraftJobPartButton) {
      const partId = Number(editDraftJobPartButton.dataset.editDraftJobPart);
      const draft = jobDraftRequirements.find((item) => Number(item.partId) === partId);
      if (!draft) return;
      const requested = window.prompt('Update the required quantity for this part.', String(draft.requiredQuantity));
      if (requested === null) return;
      const requiredQuantity = Number(requested);
      if (!Number.isInteger(requiredQuantity) || requiredQuantity <= 0) {
        window.alert('Enter a whole number greater than 0.');
        return;
      }
      draft.requiredQuantity = requiredQuantity;
      renderJobDraftRequirements();
      return;
    }

    const removeDraftJobPartButton = event.target.closest('[data-remove-draft-job-part]');
    if (removeDraftJobPartButton) {
      const partId = Number(removeDraftJobPartButton.dataset.removeDraftJobPart);
      jobDraftRequirements = jobDraftRequirements.filter((item) => Number(item.partId) !== partId);
      renderJobDraftRequirements();
      return;
    }
  });

  document.body.addEventListener('submit', async (event) => {
    const jobEditForm = event.target.closest('#job-edit-modal-form');
    if (jobEditForm) {
      event.preventDefault();
      const formData = new FormData(jobEditForm);
      const jobId = Number(editingJobId);
      const requirementInputs = [...jobEditForm.querySelectorAll('[data-job-part-qty]')];
      const requirementQuantities = requirementInputs.map((input) => ({
        requirementId: Number(input.dataset.jobPartQty),
        requiredQuantity: Number(input.value || 0),
      }));
      const invalidRequirement = requirementQuantities.find(
        (item) => !Number.isInteger(item.requiredQuantity) || item.requiredQuantity <= 0,
      );
      if (invalidRequirement) {
        window.alert('Enter a whole number greater than 0 for every required quantity.');
        return;
      }
      const submitButton = jobEditForm.querySelector('button[type="submit"]');
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Saving...';
      }
      await postJson(`/api/jobs/${jobId}`, {
        warehouseId: currentWarehouseId(),
        jobNumber: String(formData.get('jobNumber')).trim(),
        customerName: String(formData.get('customerName')).trim(),
        address: String(formData.get('address')).trim(),
        title: String(formData.get('title')).trim(),
        jobType: String(formData.get('jobType')).trim(),
        assignedUserId: Number(formData.get('assignedUserId') || 0) || null,
        technician: userById(Number(formData.get('assignedUserId') || 0) || null)?.display_name || '',
        scheduledFor: String(formData.get('scheduledFor')).trim(),
        notes: String(formData.get('notes')).trim(),
        requirementQuantities,
        ...servicePayloadFromFormData(formData),
        ...detailPayloadFromFormData(formData),
      })
        .then(() => {
          jobEditDirty = false;
          collapsedJobs.delete(jobId);
          editingJobId = null;
          renderAll();
          flashToast('Job changes saved.');
        })
        .catch((error) => window.alert(error.message))
        .finally(() => {
          if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = 'Save Job Changes';
          }
        });
      return;
    }

    const partForm = event.target.closest('[data-inline-part-form]');
    if (partForm) {
      event.preventDefault();
      const formData = new FormData(partForm);
      await postJson('/api/parts', {
        id: Number(formData.get('id')),
        warehouseId: currentWarehouseId(),
        partNumber: String(formData.get('partNumber')).trim(),
        scanCode: String(formData.get('scanCode') || '').trim(),
        description: String(formData.get('description')).trim(),
        category: String(formData.get('category')).trim(),
        itemType: String(formData.get('itemType') || 'stocked').trim(),
        stock: Number(formData.get('stock')),
        reorderPoint: Number(formData.get('reorderPoint')),
        vendorId: Number(formData.get('vendorId')),
        unitCost: Number(formData.get('unitCost')),
      })
        .then(() => {
          inlineEditors.partId = null;
          renderInventoryTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const vendorForm = event.target.closest('[data-inline-vendor-form]');
    if (vendorForm) {
      event.preventDefault();
      const formData = new FormData(vendorForm);
      await postJson('/api/vendors', {
        id: Number(formData.get('id')),
        warehouseId: currentWarehouseId(),
        name: String(formData.get('name')).trim(),
        contact: String(formData.get('contact')).trim(),
        email: String(formData.get('email')).trim(),
        phone: String(formData.get('phone')).trim(),
        leadTimeDays: Number(formData.get('leadTimeDays')),
        linkedTemplateId: String(formData.get('linkedTemplateId') || '').trim(),
      })
        .then(() => {
          inlineEditors.vendorId = null;
          renderVendorTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const orderFormTemplateForm = event.target.closest('[data-inline-order-form-template-form]');
    if (orderFormTemplateForm) {
      event.preventDefault();
      const formData = new FormData(orderFormTemplateForm);
      await postJson('/api/order-form-templates', {
        id: Number(formData.get('id')),
        warehouseId: currentWarehouseId(),
        templateId: String(formData.get('templateId')).trim(),
        name: String(formData.get('name')).trim(),
        formVariant: String(formData.get('formVariant')).trim(),
        notes: String(formData.get('notes') || '').trim(),
      })
        .then(() => {
          inlineEditors.orderFormTemplateId = null;
          renderOrderFormTemplateTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const warehouseForm = event.target.closest('[data-inline-warehouse-form]');
    if (warehouseForm) {
      event.preventDefault();
      const formData = new FormData(warehouseForm);
      await postJson('/api/warehouses', {
        id: Number(formData.get('id')),
        name: String(formData.get('name')).trim(),
        code: String(formData.get('code')).trim(),
      })
        .then(() => {
          inlineEditors.warehouseId = null;
          renderWarehouseTable();
        })
        .catch((error) => window.alert(error.message));
    }
  });

  document.body.addEventListener('click', async (event) => {
    const deletePartButton = event.target.closest('[data-inline-delete-part]');
    if (deletePartButton) {
      await postAction(
        `/api/parts/${deletePartButton.dataset.inlineDeletePart}/delete`,
        { warehouseId: currentWarehouseId() },
        'Delete this part? This only works if it has no history.',
      )
        .then(() => {
          inlineEditors.partId = null;
          renderInventoryTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const deleteVendorButton = event.target.closest('[data-inline-delete-vendor]');
    if (deleteVendorButton) {
      await postAction(
        `/api/vendors/${deleteVendorButton.dataset.inlineDeleteVendor}/delete`,
        { warehouseId: currentWarehouseId() },
        'Delete this vendor? This only works if nothing is using it.',
      )
        .then(() => {
          inlineEditors.vendorId = null;
          renderVendorTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const deleteOrderFormTemplateButton = event.target.closest('[data-inline-delete-order-form-template]');
    if (deleteOrderFormTemplateButton) {
      await postAction(
        `/api/order-form-templates/${deleteOrderFormTemplateButton.dataset.inlineDeleteOrderFormTemplate}/delete`,
        { warehouseId: currentWarehouseId() },
        'Delete this order form template? This only works if nothing is using it.',
      )
        .then(() => {
          inlineEditors.orderFormTemplateId = null;
          renderOrderFormTemplateTable();
        })
        .catch((error) => window.alert(error.message));
      return;
    }

    const archiveWarehouseButton = event.target.closest('[data-inline-archive-warehouse]');
    if (archiveWarehouseButton) {
      await postAction(
        `/api/warehouses/${archiveWarehouseButton.dataset.inlineArchiveWarehouse}/archive`,
        { warehouseId: currentWarehouseId() },
        'Toggle archive status for this warehouse?',
      )
        .then(() => {
          inlineEditors.warehouseId = null;
          renderWarehouseTable();
        })
        .catch((error) => window.alert(error.message));
    }
  });

  document.querySelector('#reset-demo').addEventListener('click', async () => {
    if (editingJobId) {
      window.alert('Save the current job before resetting demo data.');
      return;
    }
    await postJson('/api/reset', { warehouseId: currentWarehouseId() })
      .then(() => {
        clearPartForm();
        clearVendorForm();
        clearWarehouseForm();
      })
      .catch((error) => window.alert(error.message));
  });

  document.querySelector('#export-data').addEventListener('click', () => {
    if (editingJobId) {
      window.alert('Save the current job before leaving the edit view.');
      return;
    }
    window.location.href = `/api/export?warehouseId=${currentWarehouseId()}`;
  });
}

window.addEventListener('beforeunload', (event) => {
  if (!editingJobId) return;
  event.preventDefault();
  event.returnValue = '';
});

window.addEventListener('error', (event) => {
  const error = event.error instanceof Error ? event.error : new Error(event.message || 'Unexpected UI error');
  logClientError(
    'Unhandled window error',
    error,
    { filename: event.filename, lineno: event.lineno, colno: event.colno },
    'global',
  );
  flashToast('A screen error occurred, but the app is still running.', 'error');
});

window.addEventListener('unhandledrejection', (event) => {
  const rejection =
    event.reason instanceof Error ? event.reason : new Error(String(event.reason || 'Unhandled promise rejection'));
  logClientError('Unhandled promise rejection', rejection, {}, 'global');
  flashToast('A background request failed, but the app is still running.', 'error');
});

function initializeApp() {
  try {
    bindNavigation();
    bindForms();
    bindActions();
    bindAuth();
    loadApp();
  } catch (error) {
    logClientError('App initialization failed', error, {}, 'init');
    flashToast('The app hit a startup issue. Try refreshing the page.', 'error');
  }
}

initializeApp();
