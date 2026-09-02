const $ = (id) => document.getElementById(id);

const state = {
  locked: false,
  voices: [],
  recChunks: [],
  recorder: null,
  recordedBlob: null,
};

function show(el, on) {
  el.classList.toggle("hidden", !on);
}

function setError(node, msg) {
  if (!msg) {
    show(node, false);
    node.textContent = "";
    return;
  }
  node.textContent = msg;
  show(node, true);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...opts,
    headers: {
      ...(opts.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(opts.headers || {}),
    },
  });
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (res.status === 401) {
    const err = new Error((data && data.detail) || "Password required.");
    err.code = 401;
    throw err;
  }
  if (!res.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed.");
  }
  return data;
}

function estimateSeconds(text, speed) {
  const chars = text.replace(/\s+/g, " ").trim().length;
  if (!chars) return 0;
  return chars / 14 / Math.max(Number(speed) || 1, 0.25);
}

function fmtTime(sec) {
  if (sec < 60) return `~${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `~${m}m ${s}s`;
}

function updateEstimate() {
  const text = $("script").value;
  const speed = Number($("speed").value);
  const chars = text.trim().length;
  const sec = estimateSeconds(text, speed);
  $("charCount").textContent = `${chars} chars`;
  const el = $("estTime");
  el.textContent = `${fmtTime(sec)}  ·  30s / 60s / 90s`;
  el.classList.toggle("over", sec > 90);
}

function fillVoices(selected) {
  const sel = $("voice");
  sel.innerHTML = "";
  if (!state.voices.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No voices yet — open Voice setup";
    sel.appendChild(opt);
    return;
  }
  for (const v of state.voices) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = v.title + (v.state && v.state !== "trained" ? ` (${v.state})` : "");
    if (selected ? selected === v.id : v.local) opt.selected = true;
    sel.appendChild(opt);
  }
}

function renderVoiceList() {
  const ul = $("voiceList");
  ul.innerHTML = "";
  if (!state.voices.length) {
    ul.innerHTML = "<li>None yet.</li>";
    return;
  }
  for (const v of state.voices) {
    const li = document.createElement("li");
    li.innerHTML = `<p><strong>${escapeHtml(v.title)}</strong><br><span class="sub">${escapeHtml(v.id)}</span></p>`;
    const actions = document.createElement("div");
    actions.className = "actions";
    const del = document.createElement("button");
    del.className = "danger";
    del.type = "button";
    del.textContent = "Delete";
    del.onclick = async () => {
      if (!confirm("Delete this voice?")) return;
      try {
        await api(`/api/voices/${encodeURIComponent(v.id)}`, { method: "DELETE" });
        await refreshVoices();
      } catch (err) {
        setError($("enrollError"), err.message);
      }
    };
    actions.appendChild(del);
    li.appendChild(actions);
    ul.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderHistory(items) {
  const ul = $("history");
  ul.innerHTML = "";
  if (!items.length) {
    ul.innerHTML = "<li>No takes yet.</li>";
    return;
  }
  for (const rec of items) {
    const li = document.createElement("li");
    const preview = (rec.text || "").slice(0, 90);
    li.innerHTML = `<p>${escapeHtml(preview)}${(rec.text || "").length > 90 ? "…" : ""}<br>
      <span class="sub">${escapeHtml(rec.voice_title || "")} · ${rec.duration}s · ${rec.format}</span></p>`;
    const actions = document.createElement("div");
    actions.className = "actions";
    const play = document.createElement("button");
    play.type = "button";
    play.textContent = "Play";
    play.onclick = () => useGeneration(rec);
    const dl = document.createElement("a");
    dl.href = `/api/audio/${rec.id}`;
    dl.textContent = "Download";
    dl.style.cssText = "min-height:44px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--text);padding:10px 14px;display:inline-flex;align-items:center;";
    const del = document.createElement("button");
    del.className = "danger";
    del.type = "button";
    del.textContent = "Delete";
    del.onclick = async () => {
      await api(`/api/generations/${rec.id}`, { method: "DELETE" });
      await refreshHistory();
    };
    actions.append(play, dl, del);
    li.appendChild(actions);
    ul.appendChild(li);
  }
}

function useGeneration(rec) {
  const url = `/api/audio/${rec.id}`;
  $("player").src = url;
  $("downloadLink").href = url;
  $("downloadLink").download = rec.filename || `voiceclone.${rec.format || "mp3"}`;
  $("downloadLink").textContent = `Download ${String(rec.format || "mp3").toUpperCase()}`;
  show($("playerBox"), true);
  $("player").play().catch(() => {});
}

async function refreshVoices() {
  const data = await api("/api/voices");
  state.voices = data.voices || [];
  fillVoices($("voice").value);
  renderVoiceList();
}

async function refreshHistory() {
  const data = await api("/api/generations");
  renderHistory(data.generations || []);
}

async function boot() {
  try {
    const st = await api("/api/status");
    state.locked = false;
    show($("loginCard"), false);
    show($("app"), true);
    $("keyDot").className = "status-dot " + (st.key_set ? "on" : "off");
    let line = st.key_set ? "Fish API connected" : "Add FISH_API_KEY to .env on the Mac";
    if (st.credits && st.credits.credit != null) line += ` · ${st.credits.credit} credits`;
    $("statusLine").textContent = line;
    $("model").innerHTML = (st.models || []).map((m) => {
      const labels = {
        "s2.1-pro-free": "s2.1-pro-free (recommended, $0)",
        "s2.1-pro": "s2.1-pro (paid, same voice)",
        "s2-pro": "s2-pro (older, paid)",
        s1: "s1 (older, paid)",
      };
      const sel = m === st.default_model ? " selected" : "";
      return `<option value="${m}"${sel}>${labels[m] || m}</option>`;
    }).join("");
    try { await refreshVoices(); } catch (err) { console.warn(err); fillVoices(); }
    try { await refreshHistory(); } catch (err) { console.warn(err); }
  } catch (err) {
    if (err.code === 401) {
      state.locked = true;
      show($("loginCard"), true);
      show($("app"), false);
      $("statusLine").textContent = "Locked";
      return;
    }
    $("statusLine").textContent = err.message;
    $("keyDot").className = "status-dot off";
  }
}

$("loginBtn").onclick = async () => {
  setError($("loginError"), "");
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: $("password").value }),
    });
    await boot();
  } catch (err) {
    setError($("loginError"), err.message);
  }
};

$("password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("loginBtn").click();
});

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    show($("studio"), tab === "studio");
    show($("setup"), tab === "setup");
  };
});

$("script").addEventListener("input", updateEstimate);
$("speed").addEventListener("input", () => {
  $("speedVal").textContent = Number($("speed").value).toFixed(2);
  updateEstimate();
});
$("volume").addEventListener("input", () => {
  $("volumeVal").textContent = $("volume").value;
});

$("generateBtn").onclick = async () => {
  setError($("genError"), "");
  const text = $("script").value.trim();
  const voice_id = $("voice").value;
  if (!text) return setError($("genError"), "Paste a script first.");
  if (!voice_id) return setError($("genError"), "Create a voice in Voice setup.");
  $("generateBtn").disabled = true;
  $("generateBtn").textContent = "Generating…";
  try {
    const rec = await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        text,
        voice_id,
        model: $("model").value,
        speed: Number($("speed").value),
        volume: Number($("volume").value),
        format: $("format").value,
      }),
    });
    useGeneration(rec);
    await refreshHistory();
  } catch (err) {
    setError($("genError"), err.message);
  } finally {
    $("generateBtn").disabled = false;
    $("generateBtn").textContent = "Generate";
  }
};

function pickMime() {
  const types = ["audio/mp4", "audio/aac", "audio/webm;codecs=opus", "audio/webm"];
  for (const t of types) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

$("recBtn").onclick = async () => {
  setError($("enrollError"), "");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = pickMime();
    state.recChunks = [];
    state.recordedBlob = null;
    state.recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    state.recorder.ondataavailable = (e) => {
      if (e.data && e.data.size) state.recChunks.push(e.data);
    };
    state.recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      state.recordedBlob = new Blob(state.recChunks, { type: state.recorder.mimeType || "audio/mp4" });
      const url = URL.createObjectURL(state.recordedBlob);
      $("preview").src = url;
      show($("preview"), true);
    };
    state.recorder.start();
    $("recBtn").disabled = true;
    $("stopBtn").disabled = false;
    $("recBtn").textContent = "Recording…";
  } catch (err) {
    setError($("enrollError"), "Mic blocked. Use HTTPS (tunnel) or upload a file.");
  }
};

$("stopBtn").onclick = () => {
  if (state.recorder && state.recorder.state !== "inactive") state.recorder.stop();
  $("recBtn").disabled = false;
  $("stopBtn").disabled = true;
  $("recBtn").textContent = "Record";
};

$("enrollBtn").onclick = async () => {
  setError($("enrollError"), "");
  show($("enrollOk"), false);
  const title = $("voiceTitle").value.trim() || "My voice";
  const files = [...($("sampleFile").files || [])];
  const form = new FormData();
  form.append("title", title);
  if (files.length) {
    for (const file of files) form.append("files", file, file.name);
  } else if (state.recordedBlob) {
    const blob = state.recordedBlob;
    const name = `recording.${(blob.type || "").includes("webm") ? "webm" : "m4a"}`;
    form.append("files", blob, name);
  } else {
    return setError($("enrollError"), "Upload a file or record a sample.");
  }
  const transcripts = $("transcripts").value.split("\n").map((s) => s.trim()).filter(Boolean);
  for (const line of transcripts) form.append("texts", line);
  $("enrollBtn").disabled = true;
  try {
    await api("/api/voices", { method: "POST", body: form });
    show($("enrollOk"), true);
    await refreshVoices();
  } catch (err) {
    setError($("enrollError"), err.message);
  } finally {
    $("enrollBtn").disabled = false;
  }
};

updateEstimate();
boot();
