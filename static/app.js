const newsGrid = document.getElementById("news-grid");
const newsMeta = document.getElementById("news-meta");
const newsFilter = document.getElementById("news-filter");
const sourceFilter = document.getElementById("source-filter");
const refreshBtn = document.getElementById("refresh-btn");
const statusPill = document.getElementById("status-pill");
const twitterBanner = document.getElementById("twitter-banner");
const cardTemplate = document.getElementById("card-template");

const draftText = document.getElementById("draft-text");
const resultText = document.getElementById("result-text");
const transformBtn = document.getElementById("transform-btn");
const copyBtn = document.getElementById("copy-btn");
const transformMeta = document.getElementById("transform-meta");

let allItems = [];
let feedMeta = {};

function formatDate(value) {
  if (!value) return "Date unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function placeholderThumb(source) {
  const colors = ["1a2030", "241a18", "18241f", "1f1824"];
  const color = colors[source.length % colors.length];
  const label = encodeURIComponent(source.slice(0, 12));
  return `https://placehold.co/640x360/${color}/9aa3b5?text=${label}`;
}

function setStatus(health) {
  const parts = ["Online", "X mirrors"];
  if (health.openai_configured) parts.push("AI editor");
  statusPill.textContent = parts.join(" · ");
  statusPill.classList.add("ok");
}

function updateBanner() {
  const count = feedMeta.twitter_count ?? allItems.length;
  const accounts = feedMeta.mirror_accounts ?? "—";
  twitterBanner.hidden = false;
  twitterBanner.className = "twitter-banner ok";
  twitterBanner.textContent = `Polling ${accounts} primary @handles via public mirrors · ${count} videos found (no API key, no date cutoff).`;
}

async function fetchHealth() {
  try {
    const res = await fetch("/api/health");
    setStatus(await res.json());
  } catch {
    statusPill.textContent = "Offline";
  }
}

function populateSourceFilter() {
  const handles = [...new Set(allItems.map((i) => i.author?.username).filter(Boolean))].sort();
  sourceFilter.innerHTML = `
    <option value="">All accounts</option>
    <option value="primary">Primary sources only</option>
  `;
  for (const handle of handles) {
    const opt = document.createElement("option");
    opt.value = handle;
    opt.textContent = `@${handle}`;
    sourceFilter.appendChild(opt);
  }
}

function filteredItems() {
  const q = newsFilter.value.trim().toLowerCase();
  const source = sourceFilter.value;

  return allItems.filter((item) => {
    if (source === "primary" && !item.is_primary_source) return false;
    if (source && source !== "primary" && item.author?.username !== source) return false;

    if (!q) return true;
    const author = item.author?.username || "";
    const hay = `${item.title} ${item.source} ${author} ${item.description || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderBadges(item, container) {
  container.innerHTML = "";
  if (item.is_primary_source) {
    container.innerHTML += '<span class="badge badge-primary">Primary source</span>';
  }
}

function renderNews() {
  const items = filteredItems();
  newsGrid.innerHTML = "";

  if (!items.length) {
    newsGrid.innerHTML = '<div class="empty-state">No videos match your filters.</div>';
    newsMeta.textContent = `${allItems.length} videos loaded · showing 0`;
    return;
  }

  const primaryCount = items.filter((i) => i.is_primary_source).length;
  newsMeta.textContent = `${allItems.length} loaded · ${primaryCount} primary sources in view · showing ${items.length}`;

  for (const item of items) {
    const node = cardTemplate.content.cloneNode(true);
    const thumb = node.querySelector(".card-thumb");
    const title = node.querySelector(".card-title");
    const desc = node.querySelector(".card-desc");
    const time = node.querySelector(".card-time");
    const source = node.querySelector(".card-source");
    const badges = node.querySelector(".card-badges");
    const stats = node.querySelector(".card-stats");
    const openLink = node.querySelector(".card-open");
    const downloadBtn = node.querySelector(".card-download");

    title.textContent = item.title;
    desc.textContent = item.description
      || `From @${item.author?.username || "unknown"} — download and add your overlay text.`;
    time.textContent = formatDate(item.published);
    source.textContent = item.source;
    openLink.href = item.url;

    renderBadges(item, badges);
    stats.innerHTML = "";

    thumb.src = item.thumbnail || placeholderThumb(item.source);
    thumb.alt = item.title;
    thumb.onerror = () => {
      thumb.src = placeholderThumb(item.source);
    };

    downloadBtn.addEventListener("click", () => downloadVideo(item.url, downloadBtn));
    newsGrid.appendChild(node);
  }
}

async function loadNews() {
  refreshBtn.classList.add("loading");
  refreshBtn.disabled = true;
  newsGrid.innerHTML = `
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
  `;

  try {
    const res = await fetch("/api/news/videos");
    if (!res.ok) throw new Error("Feed request failed");
    const data = await res.json();
    allItems = data.items || [];
    feedMeta = data;
    updateBanner();
    populateSourceFilter();
    renderNews();
  } catch (err) {
    newsGrid.innerHTML = `<div class="empty-state">Could not load feed. ${err.message}</div>`;
    newsMeta.textContent = "";
  } finally {
    refreshBtn.classList.remove("loading");
    refreshBtn.disabled = false;
  }
}

async function downloadVideo(url, button) {
  const original = button.textContent;
  button.classList.add("loading");
  button.disabled = true;
  button.textContent = "Downloading…";

  try {
    const res = await fetch("/api/video/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Download failed");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "video.mp4";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    alert(`Download failed: ${err.message}`);
  } finally {
    button.classList.remove("loading");
    button.disabled = false;
    button.textContent = original;
  }
}

async function transformText() {
  const text = draftText.value.trim();
  if (!text) return;

  const mode = document.querySelector('input[name="mode"]:checked')?.value || "headline";
  transformBtn.classList.add("loading");
  transformBtn.disabled = true;
  transformMeta.textContent = "Working…";

  try {
    const res = await fetch("/api/text/transform", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Transform failed");
    }
    const data = await res.json();
    resultText.value = data.result;
    copyBtn.disabled = !data.result;
    const modeLabels = { headline: "Headline", shorten: "Shortened", rewrite: "Rewritten" };
    const modeLabel = modeLabels[mode] || mode;
    transformMeta.textContent = `${modeLabel} via ${data.engine} · ${data.original_words} → ${data.result_words} words`;
  } catch (err) {
    transformMeta.textContent = err.message;
  } finally {
    transformBtn.classList.remove("loading");
    transformBtn.disabled = false;
  }
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = {
    news: document.getElementById("panel-news"),
    editor: document.getElementById("panel-editor"),
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.classList.toggle("active", t === tab);
        t.setAttribute("aria-selected", t === tab ? "true" : "false");
      });
      Object.entries(panels).forEach(([key, panel]) => {
        const active = key === tab.dataset.tab;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      });
    });
  });
}

newsFilter.addEventListener("input", renderNews);
sourceFilter.addEventListener("change", renderNews);
refreshBtn.addEventListener("click", loadNews);
transformBtn.addEventListener("click", transformText);
copyBtn.addEventListener("click", async () => {
  if (!resultText.value) return;
  await navigator.clipboard.writeText(resultText.value);
  copyBtn.textContent = "Copied";
  setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
});

setupTabs();
fetchHealth();
loadNews();
