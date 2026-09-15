// Default competitors and keywords
const DEFAULT_COMPETITORS = [
    "OpenAI",
    "Google",
    "Anthropic",
    "Microsoft",
    "Meta",
    "Amazon",
    "NVIDIA",
    "xAI"
];

const DEFAULT_KEYWORDS = [
    "artificial intelligence",
    "generative AI",
    "large language model"
];

// State
let competitors = [...DEFAULT_COMPETITORS];
let keywords = [...DEFAULT_KEYWORDS];

// DOM Elements
const competitorsTags = document.getElementById("competitors-tags");
const competitorInput = document.getElementById("competitor-input");
const keywordsTags = document.getElementById("keywords-tags");
const keywordInput = document.getElementById("keyword-input");
const runBtn = document.getElementById("run-radar");
const loading = document.getElementById("loading");
const results = document.getElementById("results");
const radarList = document.getElementById("radar-list");
const aiSummary = document.getElementById("ai-summary");
const detailedSummary = document.getElementById("detailed-summary");
const generatedAt = document.getElementById("generated-at");
const errorSection = document.getElementById("error");
const errorMessage = document.getElementById("error-message");
const statusDot = document.querySelector(".status-dot");
const statusText = document.getElementById("status-text");

// Initialize
function init() {
    renderTags(competitorsTags, competitors, "competitor");
    renderTags(keywordsTags, keywords, "keyword");
    checkHealth();
    setupInputHandlers();
}

// Render tags
function renderTags(container, items, type) {
    container.innerHTML = "";
    items.forEach((item, index) => {
        const tag = document.createElement("div");
        tag.className = "tag";
        tag.innerHTML = `
            <span>${escapeHtml(item)}</span>
            <button onclick="removeTag('${type}', ${index})" title="Remove">&times;</button>
        `;
        container.appendChild(tag);
    });
}

// Add tag on Enter
function setupInputHandlers() {
    competitorInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            addTag("competitor");
        }
    });

    keywordInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            addTag("keyword");
        }
    });

    runBtn.addEventListener("click", runRadar);
}

function addTag(type) {
    const input = type === "competitor" ? competitorInput : keywordInput;
    const value = input.value.trim();
    if (!value) return;

    if (type === "competitor") {
        if (!competitors.includes(value)) {
            competitors.push(value);
            renderTags(competitorsTags, competitors, "competitor");
        }
    } else {
        if (!keywords.includes(value)) {
            keywords.push(value);
            renderTags(keywordsTags, keywords, "keyword");
        }
    }
    input.value = "";
}

function removeTag(type, index) {
    if (type === "competitor") {
        competitors.splice(index, 1);
        renderTags(competitorsTags, competitors, "competitor");
    } else {
        keywords.splice(index, 1);
        renderTags(keywordsTags, keywords, "keyword");
    }
}

// Check API health
async function checkHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();
        if (data.status === "ok") {
            statusDot.classList.add("online");
            statusDot.classList.remove("offline");
            statusText.textContent = data.searchapi_configured
                ? "API Connected"
                : "API Key Required";
        } else {
            statusDot.classList.add("offline");
            statusText.textContent = "API Offline";
        }
    } catch (e) {
        statusDot.classList.add("offline");
        statusText.textContent = "API Offline";
    }
}

// Run radar
async function runRadar() {
    if (competitors.length === 0) {
        showError("Please add at least one competitor.");
        return;
    }

    // Show loading
    runBtn.disabled = true;
    loading.style.display = "flex";
    results.style.display = "none";
    errorSection.style.display = "none";

    try {
        const response = await fetch("/api/radar", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                competitors: competitors,
                keywords: keywords,
                days_back: 7,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Request failed: ${response.status}`);
        }

        const data = await response.json();
        renderResults(data);
    } catch (e) {
        showError(e.message);
    } finally {
        runBtn.disabled = false;
        loading.style.display = "none";
    }
}

// Render results
function renderResults(data) {
    results.style.display = "block";
    errorSection.style.display = "none";

    // Generated at
    const date = new Date(data.generated_at);
    generatedAt.textContent = `Generated ${date.toLocaleString()}`;

    // Radar list
    radarList.innerHTML = "";
    data.competitors.forEach((comp) => {
        const item = document.createElement("div");
        item.className = "radar-item";

        const movementLabel = comp.movement_level.charAt(0).toUpperCase() + comp.movement_level.slice(1);
        const movementEmoji = getMovementEmoji(comp.movement_level);

        // Build signal chips - show ALL signals (not just top 5)
        let signalsHtml = "";
        if (comp.signals.length > 0) {
            signalsHtml = `
                <div class="radar-signals">
                    ${comp.signals.map((s) => `
                        <span class="signal-chip ${s.severity}">
                            ${getSignalIcon(s.type)} ${escapeHtml(s.title)}
                        </span>
                    `).join("")}
                </div>
            `;
        } else {
            signalsHtml = `<div class="radar-signals"><span class="signal-chip">No significant signals detected</span></div>`;
        }

        // Build detailed summary section
        let detailedHtml = "";
        if (comp.detailed_summary) {
            detailedHtml = `
                <div class="detailed-summary-section">
                    <h4>Detailed Analysis</h4>
                    <div class="detailed-summary-text">${renderMarkdown(comp.detailed_summary)}</div>
                </div>
            `;
        }

        // Build raw results section
        let rawResultsHtml = "";
        if (comp.raw_results && comp.raw_results.length > 0) {
            rawResultsHtml = `
                <div class="raw-results-section">
                    <h4 onclick="toggleRawResults(this)">Raw Search Results (${comp.raw_results.length}) ▼</h4>
                    <div class="raw-results-content" style="display: none;">
                        ${comp.raw_results.map((r) => {
                            const url = safeUrl(r.url);
                            const thumb = safeUrl(r.thumbnail);
                            return `
                            <div class="raw-result-item">
                                ${thumb ? `<img class="raw-result-thumb" src="${escapeHtml(thumb)}" alt="" loading="lazy">` : ""}
                                <div class="raw-result-body">
                                    <div class="raw-result-head">
                                        ${r.position ? `<span class="raw-result-pos">#${escapeHtml(String(r.position))}</span>` : ""}
                                        <div class="raw-result-title">${escapeHtml(r.title || "(no title)")}</div>
                                    </div>
                                    <div class="raw-result-snippet">${escapeHtml(r.snippet || "")}</div>
                                    <div class="raw-result-meta">
                                        ${r.rating != null ? `<span class="raw-result-rating">★ ${escapeHtml(String(r.rating))}</span>` : ""}
                                        <span class="raw-result-source">${escapeHtml(r.source)}</span>
                                        <span class="raw-result-engine">${escapeHtml(r.engine)}</span>
                                        ${r.date ? `<span class="raw-result-date">${escapeHtml(r.date)}</span>` : ""}
                                        ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="raw-result-url">View Source</a>` : ""}
                                    </div>
                                </div>
                            </div>`;
                        }).join("")}
                    </div>
                </div>
            `;
        }

        // Build signal breakdown
        let breakdownHtml = "";
        if (comp.signal_breakdown && Object.keys(comp.signal_breakdown).length > 0) {
            const b = comp.signal_breakdown;
            const typeItems = Object.entries(b)
                .filter(([k]) => k.endsWith("_total"))
                .map(([k, v]) => `<span class="breakdown-chip">${prettyLabel(k.replace("_total", ""))} <b>${v}</b>&nbsp;</span>`)
                .join("");
            const sevItems = Object.entries(b)
                .filter(([k]) => k.startsWith("severity_"))
                .map(([k, v]) => {
                    const sev = k.replace("severity_", "");
                    return `<span class="breakdown-chip ${sev}">${prettyLabel(sev)} <b>${v}</b>&nbsp;</span>`;
                })
                .join("");
            breakdownHtml = `
                <div class="signal-breakdown">
                    <h4>Signal Breakdown</h4>
                    ${typeItems ? `<div class="breakdown-row"><span class="breakdown-label">By Type</span><div class="breakdown-chips">${typeItems}</div></div>` : ""}
                    ${sevItems ? `<div class="breakdown-row"><span class="breakdown-label">By Severity</span><div class="breakdown-chips">${sevItems}</div></div>` : ""}
                </div>
            `;
        }

        // Build search sources
        let sourcesHtml = "";
        if (comp.search_sources && comp.search_sources.length > 0) {
            sourcesHtml = `
                <div class="search-sources">
                    <h4>Search Sources</h4>
                    <div class="sources-list">${comp.search_sources.map(s => `<span class="source-chip">${escapeHtml(s)}</span>`).join("")}</div>
                </div>
            `;
        }

        item.innerHTML = `
            <div class="radar-item-header">
                <div class="radar-company">
                    <h3>${escapeHtml(comp.competitor)}</h3>
                    <span class="movement-badge ${comp.movement_level}">
                        ${movementEmoji} ${movementLabel} Movement
                    </span>
                </div>
                <span class="radar-score">Score: ${comp.score}</span>
            </div>
            ${signalsHtml}
            ${breakdownHtml}
            ${sourcesHtml}
            ${detailedHtml}
            ${rawResultsHtml}
        `;
        radarList.appendChild(item);
    });

    // AI Summary
    aiSummary.textContent = data.ai_executive_summary;

    // Detailed AI Summary
    if (detailedSummary) {
        detailedSummary.innerHTML = renderMarkdown(data.detailed_ai_summary || data.ai_executive_summary);
    }
}

function toggleRawResults(header) {
    const content = header.nextElementSibling;
    const isVisible = content.style.display === "block";
    content.style.display = isVisible ? "none" : "block";
    header.innerHTML = header.innerHTML.replace(/▼|▶/, isVisible ? "▼" : "▶");
}

function getMovementEmoji(level) {
    switch (level) {
        case "high": return "🔴";
        case "medium": return "🟠";
        case "low": return "🟡";
        default: return "⚪";
    }
}

function getSignalIcon(type) {
    const icons = {
        "strategic_announcement": "📢",
        "new_jobs": "💼",
        "new_product": "🚀",
        "seo_movement": "🔍",
        "news_activity": "📰",
        "press_release": "📄",
        "partnership": "🤝",
        "acquisition": "💰",
        "pricing": "💲",
        "regulatory": "⚖️",
    };
    return icons[type] || "📌";
}

// Show error
function showError(message) {
    errorSection.style.display = "block";
    errorMessage.textContent = message;
    results.style.display = "none";
}

// Escape HTML
function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Only allow http(s) URLs for href/src to prevent javascript: injection
function safeUrl(url) {
    if (!url) return "";
    const u = String(url).trim();
    return /^https?:\/\//i.test(u) ? u : "";
}

// Render lightweight markdown (headings, bold, lists, dividers) into safe HTML
function renderMarkdown(text) {
    if (!text) return "";
    const lines = text.split("\n");
    let html = "";
    let inList = false;

    const closeList = () => {
        if (inList) {
            html += "</ul>";
            inList = false;
        }
    };

    for (let raw of lines) {
        const line = raw.replace(/\s+$/, "");
        const trimmed = line.trim();

        if (trimmed === "") {
            closeList();
            continue;
        }

        // Horizontal rule: lines of repeated = or - characters
        if (/^[-=]{5,}$/.test(trimmed)) {
            closeList();
            html += "<hr class='md-hr'>";
            continue;
        }

        // Markdown headings ### / ## / #
        const heading = line.match(/^(#{1,3})\s+(.*)$/);
        if (heading) {
            closeList();
            const level = heading[1].length;
            html += `<h${level} class="md-h${level}">${inlineMd(heading[2])}</h${level}>`;
            continue;
        }

        // Numbered section heading like "1. EXECUTIVE OVERVIEW"
        const numbered = line.match(/^\d+\.\s+(.*)$/);
        if (numbered) {
            closeList();
            html += `<h3 class="md-h3 md-section">${inlineMd(numbered[1])}</h3>`;
            continue;
        }

        // Bullet list item (-, *, • with optional indentation)
        const bullet = line.match(/^\s*[-•*]\s+(.*)$/);
        if (bullet) {
            if (!inList) {
                closeList();
                html += "<ul class='md-ul'>";
                inList = true;
            }
            html += `<li>${inlineMd(bullet[1])}</li>`;
            continue;
        }

        // Paragraph
        closeList();
        html += `<p class="md-p">${inlineMd(line)}</p>`;
    }
    closeList();
    return html;
}

// Convert a snake_case key into a human-readable Title Case label
function prettyLabel(str) {
    return String(str)
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

// Inline markdown: escape first, then apply bold/italic and allow <br/> line breaks
function inlineMd(text) {
    let t = escapeHtml(text);
    t = t.replace(/&lt;br\s*\/?&gt;/gi, "<br/>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return t;
}

// Initialize on load
document.addEventListener("DOMContentLoaded", init);
