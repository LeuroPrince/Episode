let projectId = null;
let pages = [];

const fileInput = document.querySelector("#fileInput");
const dropZone = document.querySelector("#dropZone");
const pageGrid = document.querySelector("#pages");
const pageCount = document.querySelector("#pageCount");
const statusLine = document.querySelector("#status");
const newProjectButton = document.querySelector("#newProjectButton");
const exportButton = document.querySelector("#exportButton");
const openFolderButton = document.querySelector("#openFolderButton");
const filenameInput = document.querySelector("#filename");
const downloadLink = document.querySelector("#downloadLink");
const unifySizeButton = document.querySelector("#unifySizeButton");
const pageToolStatus = document.querySelector("#pageToolStatus");
const convertFileInput = document.querySelector("#convertFileInput");
const convertButton = document.querySelector("#convertButton");
const openConvertedFolderButton = document.querySelector("#openConvertedFolderButton");
const convertPreview = document.querySelector("#convertPreview");
const convertPreviewFrame = document.querySelector("#convertPreviewFrame");
const convertPreviewName = document.querySelector("#convertPreviewName");
const convertStatus = document.querySelector("#convertStatus");
const projectHistory = document.querySelector("#projectHistory");
let lastExportFilename = null;
let lastExportPath = null;
let lastConvertedFolderName = null;
let convertPreviewUrl = null;
let thumbnailVersion = 0;
const selectedPageIds = new Set();

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "操作失败");
  }
  return data;
}

function setStatus(message) {
  statusLine.textContent = message;
}

function clearSavedFileActions() {
  lastExportFilename = null;
  lastExportPath = null;
  downloadLink.hidden = true;
  downloadLink.removeAttribute("href");
  openFolderButton.hidden = true;
  openFolderButton.textContent = "";
}

function clearConvertedFolderAction() {
  lastConvertedFolderName = null;
  openConvertedFolderButton.hidden = true;
  openConvertedFolderButton.textContent = "";
}

function clearConvertPreview() {
  if (convertPreviewUrl) {
    URL.revokeObjectURL(convertPreviewUrl);
    convertPreviewUrl = null;
  }
  convertPreview.hidden = true;
  convertPreviewFrame.removeAttribute("src");
  convertPreviewName.textContent = "PDF 预览";
}

function showConvertPreview(file) {
  clearConvertPreview();
  if (!file) return;
  convertPreviewUrl = URL.createObjectURL(file);
  convertPreviewName.textContent = file.name;
  convertPreviewFrame.src = convertPreviewUrl;
  convertPreview.hidden = false;
}

async function ensureProject() {
  if (projectId) return projectId;
  const data = await requestJson("/api/project", { method: "POST" });
  projectId = data.projectId;
  await refreshHistory();
  return projectId;
}

async function startNewProject() {
  const data = await requestJson("/api/project", { method: "POST" });
  projectId = data.projectId;
  pages = [];
  selectedPageIds.clear();
  fileInput.value = "";
  clearSavedFileActions();
  renderPages();
  await refreshHistory();
  setStatus("已新建空白工作区");
}

function renderHistory(projects) {
  projectHistory.innerHTML = "";
  if (!projects.length) {
    projectHistory.innerHTML = '<p class="history-empty">暂无历史项目</p>';
    return;
  }

  for (const project of projects) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "history-item";
    item.dataset.id = project.id;
    item.innerHTML = `
      <strong>${project.name}</strong>
      <span>${project.pageCount} 页</span>
      <small>${project.updatedAt}</small>
    `;
    if (project.id === projectId) {
      item.classList.add("active");
    }
    projectHistory.appendChild(item);
  }
}

async function refreshHistory() {
  const data = await requestJson("/api/projects");
  renderHistory(data.projects);
}

async function loadProject(projectIdToLoad) {
  const data = await requestJson(`/api/project/${projectIdToLoad}`);
  projectId = data.projectId;
  pages = data.pages;
  selectedPageIds.clear();
  fileInput.value = "";
  clearSavedFileActions();
  renderPages();
  renderHistory((await requestJson("/api/projects")).projects);
  setStatus(`已恢复项目：${data.project.name}`);
}

function renderPages() {
  thumbnailVersion += 1;
  const currentPageIds = new Set(pages.map((page) => page.id));
  for (const id of selectedPageIds) {
    if (!currentPageIds.has(id)) {
      selectedPageIds.delete(id);
    }
  }

  pageCount.textContent = `${pages.length} 页`;
  pageGrid.classList.toggle("empty", pages.length === 0);
  pageGrid.innerHTML = "";

  if (!pages.length) {
    pageGrid.innerHTML = "<p>还没有页面</p>";
    return;
  }

  for (const [index, page] of pages.entries()) {
    const card = document.createElement("article");
    card.className = selectedPageIds.has(page.id) ? "page-card selected" : "page-card";
    card.draggable = true;
    card.dataset.id = page.id;
    card.innerHTML = `
      <button type="button" class="page-select-button" data-action="select" aria-pressed="${selectedPageIds.has(page.id)}">
        ${selectedPageIds.has(page.id) ? "已选择" : "选择"}
      </button>
      <div class="thumb-wrap">
        <img src="${page.thumbnailUrl}?v=${page.rotation}-${thumbnailVersion}" alt="第 ${index + 1} 页缩略图">
      </div>
      <p class="page-title">${index + 1}. ${page.label}</p>
      <div class="page-orientation-tools" aria-label="页面朝向调整">
        <button type="button" data-action="left">左转</button>
        <button type="button" data-action="right">右转</button>
      </div>
      <button type="button" class="page-delete-button danger" data-action="delete">删除</button>
    `;
    pageGrid.appendChild(card);
  }
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList);
  if (!files.length) return;

  await ensureProject();
  const formData = new FormData();
  formData.append("projectId", projectId);
  for (const file of files) {
    formData.append("files", file);
  }

  setStatus("正在导入文件...");
  const data = await requestJson("/api/upload", {
    method: "POST",
    body: formData,
  });
  projectId = data.projectId;
  pages = data.pages;
  selectedPageIds.clear();
  clearSavedFileActions();
  renderPages();
  await refreshHistory();
  setStatus("导入完成");
}

async function persistOrder() {
  if (!projectId || !pages.length) return;
  const data = await requestJson("/api/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ projectId, pageIds: pages.map((page) => page.id) }),
  });
  pages = data.pages;
  renderPages();
  await refreshHistory();
  setStatus("页面顺序已更新");
}

async function applyPageTool(url, payload, messageBuilder) {
  await ensureProject();
  const data = await requestJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ projectId, ...payload }),
  });
  pages = data.pages;
  renderPages();
  await refreshHistory();
  clearSavedFileActions();
  const message = messageBuilder(data);
  pageToolStatus.textContent = message;
  setStatus(message);
}

function getDragAfterElement(container, x, y) {
  const cards = [...container.querySelectorAll(".page-card:not(.dragging)")];
  if (!cards.length) return null;

  const rows = [];
  for (const card of cards) {
    const box = card.getBoundingClientRect();
    let row = rows.find((item) => Math.abs(item.top - box.top) < 8);
    if (!row) {
      row = { top: box.top, bottom: box.bottom, cards: [] };
      rows.push(row);
    }
    row.top = Math.min(row.top, box.top);
    row.bottom = Math.max(row.bottom, box.bottom);
    row.cards.push({ element: card, box });
  }

  rows.sort((a, b) => a.top - b.top);
  for (const row of rows) {
    row.cards.sort((a, b) => a.box.left - b.box.left);
  }

  const targetRow = rows.find((row) => y <= row.bottom) || rows[rows.length - 1];
  if (y > targetRow.bottom && targetRow === rows[rows.length - 1]) {
    return null;
  }

  const targetCard = targetRow.cards.find((card) => x < card.box.left + card.box.width / 2);
  if (targetCard) {
    return targetCard.element;
  }

  const nextRow = rows[rows.indexOf(targetRow) + 1];
  return nextRow ? nextRow.cards[0].element : null;
}

fileInput.addEventListener("change", () => uploadFiles(fileInput.files).catch((error) => setStatus(error.message)));

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, () => dropZone.classList.remove("drag-over"));
}

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadFiles(event.dataTransfer.files).catch((error) => setStatus(error.message));
});

pageGrid.addEventListener("dragstart", (event) => {
  const card = event.target.closest(".page-card");
  if (!card) return;
  if (!selectedPageIds.has(card.dataset.id)) {
    selectedPageIds.clear();
    selectedPageIds.add(card.dataset.id);
    for (const item of pageGrid.querySelectorAll(".page-card.selected")) {
      item.classList.remove("selected");
    }
    card.classList.add("selected");
  }
  for (const item of pageGrid.querySelectorAll(".page-card")) {
    if (selectedPageIds.has(item.dataset.id)) {
      item.classList.add("dragging");
    }
  }
  event.dataTransfer.effectAllowed = "move";
});

pageGrid.addEventListener("dragend", async (event) => {
  const card = event.target.closest(".page-card");
  if (!card) return;
  for (const item of pageGrid.querySelectorAll(".page-card.dragging")) {
    item.classList.remove("dragging");
  }
  const orderedIds = [...pageGrid.querySelectorAll(".page-card")].map((item) => item.dataset.id);
  pages = orderedIds.map((id) => pages.find((page) => page.id === id));
  await persistOrder().catch((error) => setStatus(error.message));
});

pageGrid.addEventListener("dragover", (event) => {
  event.preventDefault();
  const draggingCards = [...pageGrid.querySelectorAll(".page-card.dragging")];
  if (!draggingCards.length) return;
  const afterElement = getDragAfterElement(pageGrid, event.clientX, event.clientY);
  if (afterElement == null) {
    for (const dragging of draggingCards) {
      pageGrid.appendChild(dragging);
    }
  } else {
    for (const dragging of draggingCards) {
      pageGrid.insertBefore(dragging, afterElement);
    }
  }
});

pageGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  const card = event.target.closest(".page-card");
  if (!button || !card) return;

  const action = button.dataset.action;
  const pageId = card.dataset.id;
  if (action === "select") {
    if (selectedPageIds.has(pageId)) {
      selectedPageIds.delete(pageId);
    } else {
      selectedPageIds.add(pageId);
    }
    renderPages();
    setStatus(selectedPageIds.size ? `已选择 ${selectedPageIds.size} 页，可拖动其中任意一页移动整组。` : "已清空页面选择");
    return;
  }

  try {
    if (action === "delete") {
      const data = await requestJson(`/api/page/${pageId}/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId }),
      });
      pages = data.pages;
      selectedPageIds.delete(pageId);
      renderPages();
      await refreshHistory();
      setStatus("页面已删除");
      return;
    }

    const degrees = action === "left" ? -90 : 90;
    const data = await requestJson(`/api/page/${pageId}/rotate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, degrees }),
    });
    pages = data.pages;
    renderPages();
    await refreshHistory();
    setStatus("页面方向已调整");
  } catch (error) {
    setStatus(error.message);
  }
});

newProjectButton.addEventListener("click", () => {
  startNewProject().catch((error) => setStatus(error.message));
});

unifySizeButton.addEventListener("click", () => {
  applyPageTool("/api/pages/unify-size", {}, (data) => {
    const width = data.project.uniformWidth;
    const height = data.project.uniformHeight;
    return `保存时将统一为 ${width} × ${height} pt。`;
  }).catch((error) => {
    pageToolStatus.textContent = error.message;
    setStatus(error.message);
  });
});

projectHistory.addEventListener("click", (event) => {
  const item = event.target.closest(".history-item");
  if (!item) return;
  loadProject(item.dataset.id).catch((error) => setStatus(error.message));
});

exportButton.addEventListener("click", async () => {
  try {
    await ensureProject();
    setStatus("正在保存 PDF...");
    const data = await requestJson("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, filename: filenameInput.value }),
    });
    lastExportFilename = data.outputName || filenameInput.value;
    lastExportPath = data.path;
    downloadLink.href = data.downloadUrl;
    downloadLink.hidden = false;
    openFolderButton.textContent = `定位到输出 PDF：${data.path}`;
    openFolderButton.hidden = false;
    await refreshHistory();
    setStatus(`已保存：${data.path}`);
  } catch (error) {
    setStatus(error.message);
  }
});

convertButton.addEventListener("click", async () => {
  const file = convertFileInput.files[0];
  if (!file) {
    convertStatus.textContent = "请先选择一个 PDF 文件。";
    return;
  }

  try {
    clearConvertedFolderAction();
    convertStatus.textContent = "正在转换 PDF...";
    const formData = new FormData();
    formData.append("file", file);
    const data = await requestJson("/api/convert-pdf-to-images", {
      method: "POST",
      body: formData,
    });
    lastConvertedFolderName = data.folderName;
    openConvertedFolderButton.textContent = `打开图片文件夹：${data.folderPath}`;
    openConvertedFolderButton.hidden = false;
    convertStatus.textContent = `已转换 ${data.count} 张 PNG 图片。`;
  } catch (error) {
    convertStatus.textContent = error.message;
  }
});

convertFileInput.addEventListener("change", () => {
  const file = convertFileInput.files[0];
  clearConvertedFolderAction();
  if (!file) {
    clearConvertPreview();
    convertStatus.textContent = "转换后的图片会保存到 exports 文件夹。";
    return;
  }
  showConvertPreview(file);
  convertStatus.textContent = "已加入 PDF，可预览后转换。";
});

openConvertedFolderButton.addEventListener("click", async () => {
  if (!lastConvertedFolderName) return;
  try {
    convertStatus.textContent = "正在打开图片文件夹...";
    const data = await requestJson("/api/open-converted-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folderName: lastConvertedFolderName }),
    });
    convertStatus.textContent = `已打开：${data.path}`;
  } catch (error) {
    convertStatus.textContent = error.message;
  }
});

openFolderButton.addEventListener("click", async () => {
  if (!lastExportFilename && !lastExportPath) return;
  try {
    setStatus("正在请求资源管理器选中输出 PDF...");
    const data = await requestJson("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: lastExportFilename, path: lastExportPath }),
    });
    setStatus(`已请求选中：${data.path}`);
  } catch (error) {
    setStatus(error.message);
  }
});

ensureProject().then(refreshHistory).catch((error) => setStatus(error.message));
