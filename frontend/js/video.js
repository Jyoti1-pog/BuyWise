/**
 * video.js — Video analysis panel: URL input + file upload → Gemini Vision.
 * Supports YouTube, Instagram Reels, TikTok, and uploaded MP4/WebM files.
 */

const Video = {
  _sessionId: null,
  _panelVisible: false,
  _panel: null,
  _chatController: null,   // reference to Chat so we can append messages

  setSession(sessionId) {
    this._sessionId = sessionId;
  },

  setChatController(chat) {
    this._chatController = chat;
  },

  // ── Init ──────────────────────────────────────────────────────────────────
  init() {
    this._panel = document.getElementById("video-panel");

    document.getElementById("video-toggle-btn")?.addEventListener("click", () => {
      this.togglePanel();
    });

    document.getElementById("video-url-submit")?.addEventListener("click", () => {
      const url = document.getElementById("video-url-input")?.value?.trim();
      if (url) this.analyzeUrl(url);
    });

    document.getElementById("video-url-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const url = e.target.value.trim();
        if (url) this.analyzeUrl(url);
      }
    });

    document.getElementById("video-file-input")?.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      if (file) this.analyzeFile(file);
    });

    document.getElementById("video-upload-area")?.addEventListener("click", () => {
      document.getElementById("video-file-input")?.click();
    });

    // Drag & drop
    const uploadArea = document.getElementById("video-upload-area");
    if (uploadArea) {
      uploadArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadArea.classList.add("drag-over");
      });
      uploadArea.addEventListener("dragleave", () => {
        uploadArea.classList.remove("drag-over");
      });
      uploadArea.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadArea.classList.remove("drag-over");
        const file = e.dataTransfer.files?.[0];
        if (file) this.analyzeFile(file);
      });
    }
  },

  // ── Panel toggle ──────────────────────────────────────────────────────────
  togglePanel() {
    if (!this._panel) return;
    this._panelVisible = !this._panelVisible;
    this._panel.classList.toggle("hidden", !this._panelVisible);
    const btn = document.getElementById("video-toggle-btn");
    if (btn) {
      btn.classList.toggle("active", this._panelVisible);
      btn.title = this._panelVisible ? "Close video panel" : "Analyze a product video";
    }
  },

  closePanel() {
    if (this._panel) this._panel.classList.add("hidden");
    this._panelVisible = false;
    document.getElementById("video-toggle-btn")?.classList.remove("active");
  },

  // ── URL Analysis ──────────────────────────────────────────────────────────
  async analyzeUrl(url) {
    this._setLoading(true, "Analyzing video with Gemini AI…");

    try {
      const data = await API.analyzeVideo({
        session_id: this._sessionId,
        video_url: url,
        guest_id: Session.getGuestId(),
      });

      this._sessionId = data.session_id || this._sessionId;
      this.closePanel();
      this._renderResult(data, url);

    } catch (err) {
      this._setLoading(false);
      Toast.error("Video analysis failed", err.message);
    }
  },

  // ── File Analysis ─────────────────────────────────────────────────────────
  async analyzeFile(file) {
    // Validate file type
    const allowed = ["video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"];
    if (!allowed.includes(file.type) && !file.name.match(/\.(mp4|webm|mov|avi)$/i)) {
      Toast.error("Unsupported format", "Please upload an MP4, WebM, or MOV file.");
      return;
    }

    // Show file name in UI
    const label = document.getElementById("video-file-label");
    if (label) label.textContent = `📹 ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`;

    this._setLoading(true, `Uploading ${file.name}…`);

    try {
      const data = await API.analyzeVideoFile({
        session_id: this._sessionId,
        file,
        guest_id: Session.getGuestId(),
      });

      this._sessionId = data.session_id || this._sessionId;
      this.closePanel();
      this._renderResult(data, file.name);

    } catch (err) {
      this._setLoading(false);
      Toast.error("Upload failed", err.message);
    }
  },

  // ── Render Result in Chat ─────────────────────────────────────────────────
  _renderResult(data, source) {
    if (!this._chatController) return;

    const chat = this._chatController;
    const analysis = data.analysis;
    const product = data.matched_product;

    // AI message
    chat.appendBubble("ai", data.reply || "Here's what I found in the video!");

    // Video analysis card
    const card = this._buildVideoCard(analysis, source);
    chat._messagesArea.appendChild(card);

    // Matched product card (if found)
    if (product) {
      chat.appendBubble("ai", `I also found a matching product in our catalog:`);
      chat.appendProducts([product]);
    }

    chat._scrollBottom();

    // Toast confirmation
    const name = analysis.extracted_product_name || "product";
    Toast.info(`🎬 Identified: ${name}`, analysis.confidence === "high" ? "High confidence" : "Review video for confirmation");
  },

  // ── Video Card DOM Builder ────────────────────────────────────────────────
  _buildVideoCard(analysis, source) {
    const wrapper = document.createElement("div");
    wrapper.className = "video-analysis-card animate-fade-in";

    const confBadge = {
      high:   { cls: "conf-high",   label: "🎯 High confidence" },
      medium: { cls: "conf-medium", label: "🔍 Medium confidence" },
      low:    { cls: "conf-low",    label: "❓ Low confidence" },
    }[analysis.confidence] || { cls: "conf-low", label: "❓ Unknown" };

    const videoTypeEmoji = {
      review:        "⭐ Review",
      unboxing:      "📦 Unboxing",
      advertisement: "📢 Ad",
      tutorial:      "🎓 Tutorial",
      other:         "🎬 Video",
    }[analysis.video_type] || "🎬 Video";

    const sourceLabel = this._formatSource(source);
    const specsHTML = (analysis.extracted_specs || []).slice(0, 5)
      .map(s => `<span class="spec-pill">${s}</span>`).join("");

    const thumbHTML = analysis.thumbnail_url
      ? `<img src="${analysis.thumbnail_url}" alt="Video thumbnail" class="video-thumb-img" onerror="this.style.display='none'">`
      : `<div class="video-thumb-placeholder">🎬</div>`;

    wrapper.innerHTML = `
      <div class="video-card-header">
        <span class="video-card-icon">🎬</span>
        <span class="video-card-title">Video Analysis</span>
        <span class="video-conf-badge ${confBadge.cls}">${confBadge.label}</span>
      </div>
      <div class="video-card-body">
        <div class="video-thumb">${thumbHTML}</div>
        <div class="video-info">
          <div class="video-product-name">${analysis.extracted_product_name || "Unknown product"}</div>
          <div class="video-meta">
            ${analysis.extracted_brand ? `<span class="video-brand">${analysis.extracted_brand}</span>` : ""}
            ${analysis.extracted_price_hint ? `<span class="video-price">${analysis.extracted_price_hint}</span>` : ""}
            <span class="video-type-badge">${videoTypeEmoji}</span>
          </div>
          ${specsHTML ? `<div class="card-specs" style="margin-top:8px">${specsHTML}</div>` : ""}
          ${analysis.video_summary ? `<p class="video-summary">${analysis.video_summary}</p>` : ""}
          <div class="video-source-row">
            <span class="video-source-label">Source</span>
            <span class="video-source-val">${sourceLabel}</span>
          </div>
        </div>
      </div>
    `;

    return wrapper;
  },

  _formatSource(source) {
    if (!source) return "Unknown";
    if (source.includes("youtube.com") || source.includes("youtu.be")) return "📺 YouTube";
    if (source.includes("instagram.com")) return "📸 Instagram Reel";
    if (source.includes("tiktok.com")) return "🎵 TikTok";
    if (source.match(/\.(mp4|webm|mov|avi)$/i)) return `📁 ${source}`;
    return source;
  },

  // ── Loading State ─────────────────────────────────────────────────────────
  _setLoading(isLoading, message = "Analyzing…") {
    const submitBtn = document.getElementById("video-url-submit");
    const loadingEl = document.getElementById("video-loading");
    const loadingMsg = document.getElementById("video-loading-msg");

    if (submitBtn) submitBtn.disabled = isLoading;
    if (loadingEl) loadingEl.style.display = isLoading ? "flex" : "none";
    if (loadingMsg) loadingMsg.textContent = message;

    if (!isLoading) {
      const input = document.getElementById("video-url-input");
      if (input) input.value = "";
      const label = document.getElementById("video-file-label");
      if (label) label.textContent = "Drop a video or click to upload";
    }
  },
};

window.Video = Video;
