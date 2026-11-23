/* 小熙客服 · 前端单页应用 */
"use strict";

/* ---------------- 工具 ---------------- */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmtTime = t => {
  if (!t) return "";
  const d = new Date(String(t).replace(" ", "T"));
  return isNaN(d) ? t : d.toLocaleString("zh-CN",
    {month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false});
};

const api = {
  async req(method, url, body) {
    const r = await fetch(url, {
      method,
      headers: body ? {"Content-Type": "application/json"} : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `请求失败（${r.status}）`);
    return data;
  },
  get: url => api.req("GET", url),
  post: (url, body) => api.req("POST", url, body),
  put: (url, body) => api.req("PUT", url, body),
  del: url => api.req("DELETE", url),
};

function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  $("#toast-root").appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function openModal(title, bodyHTML) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal"><h3>${esc(title)}</h3><div class="m-body">${bodyHTML}</div></div>`;
  root.onclick = e => { if (e.target === root) closeModal(); };
  return root.querySelector(".m-body");
}
function closeModal() { $("#modal-root").innerHTML = ""; }

const options = (list, selected) => list.map(x =>
  `<option value="${x.id}" ${x.id == selected ? "selected" : ""}>${esc(x.name)}</option>`).join("");

/* ---------------- 全局状态 ---------------- */
const state = {
  view: "chat",
  sessions: [],
  curSession: null,
  personas: [], scenarios: [], audiences: [],
  settings: null,
  sending: false,
};

const STAGES = ["开场", "引导", "报价", "促成", "收尾"];

/* ---------------- 启动 ---------------- */
async function init() {
  try { state.settings = await api.get("/api/settings"); } catch (e) { /* 后端未就绪 */ }
  updateFoot();
  $("#nav").addEventListener("click", e => {
    const b = e.target.closest(".nav-btn");
    if (b) showView(b.dataset.view);
  });
  await showView("chat");
}

function updateFoot() {
  const s = state.settings;
  const el = $("#foot-mode");
  if (!el) return;
  if (s && s.mode === "llm") { el.textContent = "真实大模型"; el.className = "chip chip-ghost"; }
  else { el.textContent = "模拟模式"; el.className = "chip chip-ghost"; }
  if (s) $("#product-name").textContent = s.product_name || "小熙客服";
}

const views = {
  chat: renderChat, knowledge: renderKnowledge, personas: renderPersonas,
  scripts: renderScripts, targets: renderTargets, training: renderTraining,
  settings: renderSettings,
};

async function showView(name) {
  state.view = name;
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  $("#main").innerHTML = '<div class="loading">加载中…</div>';
  try { await views[name](); }
  catch (e) { $("#main").innerHTML = `<div class="loading" style="color:var(--danger)">加载失败：${esc(e.message)}</div>`; }
}

/* ================================================================
 * 💬 对话测试
 * ================================================================ */
async function renderChat() {
  [state.personas, state.scenarios, state.audiences, state.settings, state.sessions] =
    await Promise.all([
      api.get("/api/personas"), api.get("/api/scenarios"), api.get("/api/audiences"),
      api.get("/api/settings"), api.get("/api/sessions"),
    ]);
  updateFoot();

  $("#main").innerHTML = `
  <div class="chat-layout">
    <div class="sessions-pane">
      <div class="sp-head"><button class="btn btn-primary" id="btn-new-session" style="width:100%">＋ 新建会话</button></div>
      <div id="new-session-form">
        <div class="field"><label>人设</label><select id="ns-persona">${options(state.personas, defPersonaId())}</select></div>
        <div class="field"><label>场景</label><select id="ns-scenario">${options(state.scenarios)}</select></div>
        <div class="field"><label>人群</label><select id="ns-audience">${options(state.audiences)}</select></div>
        <button class="btn btn-primary" id="btn-create-session" style="width:100%">创建</button>
      </div>
      <div id="session-list"></div>
    </div>
    <div class="chat-pane">
      <div class="chat-head">
        <div class="sel-group"><label>人设</label><select id="sel-persona">${options(state.personas)}</select></div>
        <div class="sel-group"><label>场景</label><select id="sel-scenario">${options(state.scenarios)}</select></div>
        <div class="sel-group"><label>人群</label><select id="sel-audience">${options(state.audiences)}</select></div>
        <div class="head-badges">
          <span id="badge-engine" class="chip chip-gray">模拟模式</span>
          <span id="badge-human" class="chip chip-warn" style="display:none">⚠ 需转人工</span>
          <button class="btn btn-sm" id="btn-export-session" title="导出当前会话">导出</button>
        </div>
      </div>
      <div id="chat-msgs"></div>
      <div class="composer-hint">Enter 发送 · Shift+Enter 换行 · 请以「来访者」身份输入消息</div>
      <div class="chat-composer">
        <textarea id="composer" placeholder="例如：你好 / 卡包多少钱 / 我想做你们的代理…"></textarea>
        <button class="btn btn-primary" id="btn-send">发送</button>
      </div>
    </div>
  </div>`;

  $("#btn-new-session").onclick = () => $("#new-session-form").classList.toggle("open");
  $("#btn-create-session").onclick = createSession;
  $("#btn-send").onclick = sendMessage;
  $("#composer").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  for (const id of ["sel-persona", "sel-scenario", "sel-audience"]) {
    $("#"+id).onchange = updateSessionConfig;
  }

  renderSessionList();
  updateEngineBadge();
  const first = state.sessions[0];
  if (first) await loadSession(first.id);
  else renderMessages([]);
}

function defPersonaId() {
  const p = state.personas.find(x => x.is_default) || state.personas[0];
  return p ? p.id : "";
}

async function createSession() {
  const body = {
    persona_id: +$("#ns-persona").value || null,
    scenario_id: +$("#ns-scenario").value || null,
    audience_id: +$("#ns-audience").value || null,
  };
  const s = await api.post("/api/sessions", body);
  state.sessions = await api.get("/api/sessions");
  renderSessionList();
  $("#new-session-form").classList.remove("open");
  await loadSession(s.id);
  $("#composer").focus();
}

function renderSessionList() {
  $("#session-list").innerHTML = state.sessions.map(s => `
    <div class="session-item ${state.curSession && s.id === state.curSession.id ? "active" : ""}" data-id="${s.id}">
      <span class="s-title">${s.needs_human ? "🟠 " : ""}${esc(s.title)}</span>
      <button class="s-del" title="删除会话">✕</button>
    </div>`).join("") ||
    '<div style="padding:14px;color:var(--muted);font-size:12px">还没有会话，点上方新建一个吧</div>';
  $$("#session-list .session-item").forEach(el => {
    el.onclick = e => {
      if (e.target.classList.contains("s-del")) return;
      loadSession(+el.dataset.id);
    };
    el.querySelector(".s-del").onclick = async () => {
      if (!confirm("删除这个会话及全部消息？")) return;
      await api.del(`/api/sessions/${el.dataset.id}`);
      if (state.curSession && state.curSession.id === +el.dataset.id) {
        state.curSession = null; renderMessages([]);
        syncHeaderSelects();
      }
      state.sessions = await api.get("/api/sessions");
      renderSessionList();
    };
  });
}

async function loadSession(id) {
  const [s, msgs] = await Promise.all([
    api.get(`/api/sessions/${id}`).catch(() => null),
    api.get(`/api/sessions/${id}/messages`).catch(() => []),
  ]);
  if (!s) return;
  state.curSession = s;
  renderSessionList();
  syncHeaderSelects();
  renderMessages(msgs);
}

function syncHeaderSelects() {
  const s = state.curSession;
  $("#sel-persona").value = s && s.persona_id ? s.persona_id : "";
  $("#sel-scenario").value = s && s.scenario_id ? s.scenario_id : "";
  $("#sel-audience").value = s && s.audience_id ? s.audience_id : "";
  $("#badge-human").style.display = s && s.needs_human ? "" : "none";
}

async function updateSessionConfig() {
  if (!state.curSession) { toast("请先新建会话", "err"); return; }
  state.curSession = await api.put(`/api/sessions/${state.curSession.id}`, {
    persona_id: +$("#sel-persona").value || null,
    scenario_id: +$("#sel-scenario").value || null,
    audience_id: +$("#sel-audience").value || null,
  });
  state.sessions = await api.get("/api/sessions");
  renderSessionList();
  syncHeaderSelects();
}

function updateEngineBadge() {
  const s = state.settings;
  const el = $("#badge-engine");
  if (!el) return;
  if (s && s.mode === "llm") { el.textContent = `真实大模型 · ${s.api_model}`; el.className = "chip chip-info"; }
  else { el.textContent = "模拟模式"; el.className = "chip chip-gray"; }
}

async function reloadMessages() {
  if (!state.curSession) return;
  const msgs = await api.get(`/api/sessions/${state.curSession.id}/messages`);
  renderMessages(msgs);
}

function renderMessages(msgs) {
  const box = $("#chat-msgs");
  if (!box) return;
  if (!msgs.length) {
    box.innerHTML = `<div class="chat-empty"><div class="big">💬</div>
      没有消息<br>左上角新建会话后，以来访者身份发条消息试试</div>`;
    return;
  }
  box.innerHTML = msgs.map(m => m.role === "user" ? `
    <div class="msg user">
      <div class="bubble">${esc(m.content)}</div>
      <div class="msg-time">${fmtTime(m.created_at)}</div>
    </div>` : botMsgHTML(m)).join("");
  bindBotMsgEvents(msgs);
  box.scrollTop = box.scrollHeight;
}

function engineChip(engine) {
  if (engine === "llm") return `<span class="chip chip-info">大模型</span>`;
  if (engine === "mock(fallback)") return `<span class="chip chip-warn" title="大模型调用失败，已降级为模拟回复">降级模拟</span>`;
  return `<span class="chip chip-gray">模拟</span>`;
}

function botMsgHTML(m) {
  const meta = m.meta || {};
  const chips = [
    engineChip(meta.engine),
    ...(meta.knowledge || []).map(t => `<span class="chip">📚 ${esc(t)}</span>`),
    meta.used_correction ? `<span class="chip">🎓 纠错答案</span>` : "",
    meta.error ? `<span class="chip chip-danger" title="${esc(meta.error)}">⚠ 引擎异常</span>` : "",
  ].join("");
  return `
  <div class="msg bot" data-mid="${m.id}">
    <div class="bubble">${esc(m.content)}</div>
    <div class="msg-time">${fmtTime(m.created_at)}</div>
    <div class="msg-meta">
      ${chips}
      <span style="flex:1"></span>
      <button class="rate-btn rb-good ${m.rating === 1 ? "on-good" : ""}" title="回复得好">👍</button>
      <button class="rate-btn rb-bad ${m.rating === -1 ? "on-bad" : ""}" title="回复得差，纠错训练">👎</button>
    </div>
    <div class="corr-form">
      <div class="cf-title">✍️ 这条回复应该怎么答？写好后保存，机器人下次遇到类似问题就会按这个标准来</div>
      <textarea class="cf-input" placeholder="写下理想的回复…"></textarea>
      <div class="cf-actions">
        <button class="btn btn-sm cf-save">保存纠错</button>
        <button class="btn btn-sm cf-cancel">取消</button>
      </div>
    </div>
  </div>`;
}

function bindBotMsgEvents(msgs) {
  $$("#chat-msgs .msg.bot").forEach(el => {
    const mid = +el.dataset.mid;
    const m = msgs.find(x => x.id === mid);
    if (!m) return;
    el.querySelector(".rb-good").onclick = async () => {
      await api.post("/api/feedback", {message_id: mid, rating: m.rating === 1 ? 0 : 1});
      await reloadMessages();
    };
    el.querySelector(".rb-bad").onclick = () => {
      const form = el.querySelector(".corr-form");
      if (!form.classList.contains("open")) {
        form.querySelector(".cf-input").value = m.content;
      }
      form.classList.toggle("open");
    };
    el.querySelector(".cf-cancel").onclick = () => el.querySelector(".corr-form").classList.remove("open");
    el.querySelector(".cf-save").onclick = async () => {
      const val = el.querySelector(".cf-input").value.trim();
      if (!val) { toast("先写下理想回复哈", "err"); return; }
      await api.post("/api/feedback", {message_id: mid, rating: -1, correction: val});
      toast("已保存，机器人学到了 ✅", "ok");
      await reloadMessages();
    };
  });
}

async function sendMessage() {
  const box = $("#composer");
  const text = box.value.trim();
  if (!text) return;
  if (!state.curSession) { toast("先新建一个会话", "err"); return; }
  if (state.sending) return;
  state.sending = true;
  $("#btn-send").disabled = true;

  const msgsBox = $("#chat-msgs");
  msgsBox.querySelector(".chat-empty")?.remove();
  const userEl = document.createElement("div");
  userEl.className = "msg user";
  userEl.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  msgsBox.appendChild(userEl);

  const typingEl = document.createElement("div");
  typingEl.className = "msg bot";
  typingEl.innerHTML = `<div class="bubble"><span class="stream-text"></span><span class="typing-dots"><i></i><i></i><i></i></span></div>`;
  msgsBox.appendChild(typingEl);
  msgsBox.scrollTop = msgsBox.scrollHeight;
  box.value = "";

  let meta = null;
  let replyText = "";
  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: state.curSession.id, message: text}),
    });
    if (!response.ok) throw new Error(`请求失败（${response.status}）`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const packets = buffer.split("\n\n");
      buffer = packets.pop() || "";
      for (const packet of packets) {
        const eventLine = packet.split("\n").find(line => line.startsWith("event:"));
        const dataLine = packet.split("\n").find(line => line.startsWith("data:"));
        if (!eventLine || !dataLine) continue;
        const event = eventLine.slice(6).trim();
        const data = JSON.parse(dataLine.slice(5).trim());
        if (event === "meta") meta = data;
        if (event === "delta") {
          replyText += data.text;
          typingEl.querySelector(".stream-text").textContent = replyText;
          msgsBox.scrollTop = msgsBox.scrollHeight;
        }
        if (event === "done") {
          typingEl.querySelector(".typing-dots")?.remove();
          if (meta?.error) toast(`大模型调用失败已降级：${meta.error}`, "err");
          if (data.needs_human) $("#badge-human").style.display = "";
        }
      }
    }

    await reloadMessages();
    state.sessions = await api.get("/api/sessions");
    state.curSession = state.sessions.find(s => s.id === state.curSession.id) || state.curSession;
    renderSessionList();
    syncHeaderSelects();
  } catch (e) {
    toast(e.message, "err");
    typingEl.remove();
  } finally {
    state.sending = false;
    $("#btn-send").disabled = false;
    box.focus();
  }
}

function exportCurrentSession() {
  if (!state.curSession) { toast("请先选择会话", "err"); return; }
  window.location.href = `/api/sessions/${state.curSession.id}/export`;
}

/* ================================================================
 * 📚 知识库
 * ================================================================ */
async function renderKnowledge() {
  const [list, categories] = await Promise.all([
    api.get("/api/knowledge"),
    api.get("/api/knowledge/categories"),
  ]);
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head">
      <h2>📚 知识库</h2><span class="sub">共 ${list.length} 条 · 机器人只依据这里的知识回答产品问题</span>
      <span class="spacer"></span>
      <select id="kb-category" style="width:130px"><option value="">全部分组</option>${categories.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
      <input type="text" id="kb-search" placeholder="搜索标题 / 内容 / 标签…" style="width:220px">
      <button class="btn" id="btn-kb-import">批量导入</button>
      <button class="btn btn-primary" id="btn-kb-add">＋ 新增知识</button>
    </div>
    <div class="page-body">
      <div class="panel"><table class="tbl">
        <thead><tr><th style="width:140px">分组</th><th style="width:160px">标题</th><th style="width:150px">标签</th><th>内容</th><th style="width:110px">操作</th></tr></thead>
        <tbody id="kb-body">
        ${list.map(k => `
          <tr data-category="${esc(k.category || "未分组")}">
            <td><span class="chip chip-gray">${esc(k.category || "未分组")}</span></td>
            <td><b>${esc(k.title)}</b></td>
            <td>${k.tags.map(t => `<span class="chip chip-gray">${esc(t)}</span>`).join(" ")}</td>
            <td style="max-width:420px;color:#556">${esc(k.content.length > 96 ? k.content.slice(0, 96) + "…" : k.content)}</td>
            <td class="actions">
              <button class="btn btn-sm" data-act="edit" data-id="${k.id}">编辑</button>
              <button class="btn btn-sm btn-danger-ghost" data-act="del" data-id="${k.id}">删除</button>
            </td>
          </tr>`).join("") || '<tr><td colspan="5" style="color:var(--muted)">暂无知识，点右上角新增</td></tr>'}
        </tbody>
      </table></div>
    </div>
  </div>`;

  const applyFilters = () => {
    const q = $("#kb-search").value.trim().toLowerCase();
    const category = $("#kb-category").value;
    $$("#kb-body tr").forEach(tr => {
      const textMatch = !q || tr.textContent.toLowerCase().includes(q);
      const categoryMatch = !category || tr.dataset.category === category;
      tr.style.display = textMatch && categoryMatch ? "" : "none";
    });
  };
  $("#kb-search").oninput = applyFilters;
  $("#kb-category").onchange = applyFilters;
  $("#btn-kb-add").onclick = () => knowledgeForm(null, categories);
  $("#btn-kb-import").onclick = knowledgeImportForm;
  $$("#kb-body [data-act]").forEach(btn => {
    const item = list.find(k => k.id === +btn.dataset.id);
    btn.onclick = () => btn.dataset.act === "edit"
      ? knowledgeForm(item, categories)
      : confirm(`删除知识「${item.title}」？`) && api.del(`/api/knowledge/${item.id}`).then(showView.bind(null, "knowledge"));
  });
}

function knowledgeForm(item, categories) {
  const body = openModal(item ? "编辑知识" : "新增知识", `
    <div class="field"><label>分组</label><input type="text" id="kf-category" list="kf-category-list" value="${esc(item?.category || "未分组")}"><datalist id="kf-category-list">${categories.map(c => `<option value="${esc(c)}"></option>`).join("")}</datalist></div>
    <div class="field"><label>标题</label><input type="text" id="kf-title" value="${esc(item?.title || "")}"></div>
    <div class="field"><label>内容</label><textarea id="kf-content" style="min-height:110px">${esc(item?.content || "")}</textarea></div>
    <div class="field"><label>标签（逗号分隔，如：价格,产品）</label><input type="text" id="kf-tags" value="${esc((item?.tags || []).join(","))}"></div>
    <div class="m-actions"><button class="btn" onclick="closeModal()">取消</button><button class="btn btn-primary" id="kf-save">保存</button></div>`);
  body.querySelector("#kf-save").onclick = async () => {
    const payload = {
      category: body.querySelector("#kf-category").value.trim() || "未分组",
      title: body.querySelector("#kf-title").value.trim(),
      content: body.querySelector("#kf-content").value.trim(),
      tags: body.querySelector("#kf-tags").value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    };
    if (!payload.title || !payload.content) { toast("标题和内容都要填", "err"); return; }
    item ? await api.put(`/api/knowledge/${item.id}`, payload)
         : await api.post("/api/knowledge", payload);
    closeModal(); toast("已保存", "ok"); showView("knowledge");
  };
}

/* ================================================================
 * 🎭 人设管理
 * ================================================================ */
async function renderPersonas() {
  const list = await api.get("/api/personas");
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head">
      <h2>🎭 人设管理</h2><span class="sub">机器人的身份、口头禅和说话风格</span>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="btn-p-add">＋ 新建人设</button>
    </div>
    <div class="page-body"><div class="card-grid">
      ${list.map(p => `
      <div class="card">
        <h3>${esc(p.name)} ${p.is_default ? '<span class="chip">默认</span>' : ""}</h3>
        <p>${esc(p.identity || "（未填身份）")}</p>
        <p style="margin-top:8px">💬 ${esc(p.greeting || "（未设开场问候）")}</p>
        <p style="margin-top:8px">${p.catchphrases.map(c => `<span class="chip chip-gray">${esc(c)}</span>`).join(" ")}</p>
        <p style="margin-top:10px">口语 ${p.colloquial} · 热情 ${p.warmth} · 正式 ${p.formality} · 表情 ${({none: "不用", light: "轻量", rich: "丰富"})[p.emoji_style] || p.emoji_style}</p>
        <div class="card-actions">
          <button class="btn btn-sm" data-act="edit" data-id="${p.id}">编辑</button>
          ${p.is_default ? "" : `<button class="btn btn-sm" data-act="default" data-id="${p.id}">设为默认</button>`}
          <span class="spacer"></span>
          <button class="btn btn-sm btn-danger-ghost" data-act="del" data-id="${p.id}">删除</button>
        </div>
      </div>`).join("") || '<div style="color:var(--muted)">还没有人设</div>'}
    </div></div>
  </div>`;
  $("#btn-p-add").onclick = () => personaForm(null, list);
  $$("[data-act]").forEach(btn => {
    const p = list.find(x => x.id === +btn.dataset.id);
    if (!p) return;
    btn.onclick = async () => {
      const act = btn.dataset.act;
      if (act === "edit") personaForm(p, list);
      else if (act === "default") {
        await api.put(`/api/personas/${p.id}`, {...p, is_default: 1});
        toast("已设为默认", "ok"); showView("personas");
      } else if (act === "del" && confirm(`删除人设「${p.name}」？`)) {
        await api.del(`/api/personas/${p.id}`); showView("personas");
      }
    };
  });
}

function personaForm(p, list) {
  const body = openModal(p ? `编辑人设 · ${p.name}` : "新建人设", `
    <div class="field"><label>名字</label><input type="text" id="pf-name" value="${esc(p?.name || "")}"></div>
    <div class="field"><label>身份介绍（她会怎么介绍自己/背景）</label><input type="text" id="pf-identity" value="${esc(p?.identity || "")}" placeholder="如：xx工作室的客服小妹，做了三年，对产品超熟"></div>
    <div class="field"><label>开场问候</label><input type="text" id="pf-greeting" value="${esc(p?.greeting || "")}" placeholder="如：哈喽~我是xx的小雅😊 想看看哪款呀？"></div>
    <div class="field"><label>口头禅（逗号分隔）</label><input type="text" id="pf-catch" value="${esc((p?.catchphrases || []).join(","))}" placeholder="如：哈喽,讲真,跟你讲"></div>
    <div class="field"><label>表情风格</label>
      <select id="pf-emoji">
        <option value="none" ${p?.emoji_style === "none" ? "selected" : ""}>不用表情</option>
        <option value="light" ${!p || p.emoji_style === "light" ? "selected" : ""}>轻量（偶尔 1 个）</option>
        <option value="rich" ${p?.emoji_style === "rich" ? "selected" : ""}>丰富（最多 2 个）</option>
      </select></div>
    <div class="field"><label>口语化 <span class="hint" style="display:inline">越高越像微信打字</span></label>
      <div class="range-row"><input type="range" id="pf-col" min="0" max="100" value="${p?.colloquial ?? 70}"><span class="rv" id="pf-col-v">${p?.colloquial ?? 70}</span></div></div>
    <div class="field"><label>热情度</label>
      <div class="range-row"><input type="range" id="pf-warm" min="0" max="100" value="${p?.warmth ?? 70}"><span class="rv" id="pf-warm-v">${p?.warmth ?? 70}</span></div></div>
    <div class="field"><label>正式度</label>
      <div class="range-row"><input type="range" id="pf-form" min="0" max="100" value="${p?.formality ?? 30}"><span class="rv" id="pf-form-v">${p?.formality ?? 30}</span></div></div>
    <div class="field"><label style="display:flex;align-items:center;gap:8px;cursor:pointer">
      <input type="checkbox" id="pf-default" style="width:auto" ${p?.is_default || !list.some(x => x.is_default) ? "checked" : ""}> 设为默认人设</label></div>
    <div class="m-actions"><button class="btn" onclick="closeModal()">取消</button><button class="btn btn-primary" id="pf-save">保存</button></div>`);

  for (const [r, v] of [["pf-col", "pf-col-v"], ["pf-warm", "pf-warm-v"], ["pf-form", "pf-form-v"]]) {
    const range = body.querySelector("#"+r);
    range.oninput = () => body.querySelector("#"+v).textContent = range.value;
  }
  body.querySelector("#pf-save").onclick = async () => {
    const payload = {
      name: body.querySelector("#pf-name").value.trim(),
      identity: body.querySelector("#pf-identity").value.trim(),
      greeting: body.querySelector("#pf-greeting").value.trim(),
      catchphrases: body.querySelector("#pf-catch").value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
      emoji_style: body.querySelector("#pf-emoji").value,
      colloquial: +body.querySelector("#pf-col").value,
      warmth: +body.querySelector("#pf-warm").value,
      formality: +body.querySelector("#pf-form").value,
      is_default: body.querySelector("#pf-default").checked ? 1 : 0,
    };
    if (!payload.name) { toast("名字要填", "err"); return; }
    p ? await api.put(`/api/personas/${p.id}`, payload)
      : await api.post("/api/personas", payload);
    closeModal(); toast("已保存", "ok"); showView("personas");
  };
}

/* ================================================================
 * 📝 话术模板
 * ================================================================ */
async function renderScripts() {
  const list = await api.get("/api/scripts");
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head">
      <h2>📝 话术模板</h2><span class="sub">按对话阶段组织，机器人学的是语气和结构，不逐字照搬</span>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="btn-sc-add">＋ 新增话术</button>
    </div>
    <div class="page-body">
      ${STAGES.map(stage => {
        const items = list.filter(s => s.stage === stage);
        return `
        <div class="stage-group">
          <div class="stage-title">${stage} <span class="chip chip-gray">${items.length}</span></div>
          <div class="panel"><table class="tbl">
            <thead><tr><th style="width:130px">名称</th><th>内容</th><th style="width:110px">操作</th></tr></thead>
            <tbody>
            ${items.map(s => `
              <tr><td><b>${esc(s.name)}</b></td><td style="color:#556">${esc(s.content)}</td>
              <td class="actions">
                <button class="btn btn-sm" data-act="edit" data-id="${s.id}">编辑</button>
                <button class="btn btn-sm btn-danger-ghost" data-act="del" data-id="${s.id}">删除</button>
              </td></tr>`).join("") ||
              '<tr><td colspan="3" style="color:var(--muted)">本阶段暂无话术</td></tr>'}
            </tbody>
          </table></div>
        </div>`;
      }).join("")}
    </div>
  </div>`;
  $("#btn-sc-add").onclick = () => scriptForm(null);
  $$(".stage-group [data-act]").forEach(btn => {
    const s = list.find(x => x.id === +btn.dataset.id);
    if (!s) return;
    btn.onclick = () => btn.dataset.act === "edit"
      ? scriptForm(s)
      : confirm(`删除话术「${s.name}」？`) && api.del(`/api/scripts/${s.id}`).then(showView.bind(null, "scripts"));
  });
}

function scriptForm(s) {
  const body = openModal(s ? `编辑话术 · ${s.name}` : "新增话术", `
    <div class="field"><label>阶段</label>
      <select id="sf-stage">${STAGES.map(t =>
        `<option value="${t}" ${s?.stage === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="field"><label>名称</label><input type="text" id="sf-name" value="${esc(s?.name || "")}" placeholder="如：预算引导"></div>
    <div class="field"><label>内容（支持变量 {产品名} {价格} {称呼}）</label>
      <textarea id="sf-content">${esc(s?.content || "")}</textarea></div>
    <div class="m-actions"><button class="btn" onclick="closeModal()">取消</button><button class="btn btn-primary" id="sf-save">保存</button></div>`);
  body.querySelector("#sf-save").onclick = async () => {
    const payload = {
      stage: body.querySelector("#sf-stage").value,
      name: body.querySelector("#sf-name").value.trim(),
      content: body.querySelector("#sf-content").value.trim(),
    };
    if (!payload.name || !payload.content) { toast("名称和内容都要填", "err"); return; }
    s ? await api.put(`/api/scripts/${s.id}`, payload)
      : await api.post("/api/scripts", payload);
    closeModal(); toast("已保存", "ok"); showView("scripts");
  };
}

/* ================================================================
 * 🎯 场景与人群
 * ================================================================ */
async function renderTargets() {
  const [scenarios, audiences] = await Promise.all([
    api.get("/api/scenarios"), api.get("/api/audiences")]);
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head"><h2>🎯 场景与人群</h2>
      <span class="sub">同一套知识，不同场景不同人，说法完全不一样</span>
      <span class="spacer"></span>
      <button class="btn" id="btn-t-aud">＋ 新增人群</button>
      <button class="btn btn-primary" id="btn-t-scn">＋ 新增场景</button>
    </div>
    <div class="page-body">
      <div class="stage-group"><div class="stage-title">场景 <span class="chip chip-gray">${scenarios.length}</span></div>
        <div class="card-grid">${scenarios.map(s => `
          <div class="card">
            <h3>${esc(s.name)}</h3><p>${esc(s.description)}</p>
            <p style="margin-top:8px;background:var(--brand-soft);border-radius:8px;padding:8px 10px;color:#0b7a52">${esc(s.strategy)}</p>
            <div class="card-actions"><span class="spacer"></span>
              <button class="btn btn-sm" data-kind="scenario" data-act="edit" data-id="${s.id}">编辑</button>
              <button class="btn btn-sm btn-danger-ghost" data-kind="scenario" data-act="del" data-id="${s.id}">删除</button>
            </div>
          </div>`).join("")}</div></div>
      <div class="stage-group"><div class="stage-title">人群 <span class="chip chip-gray">${audiences.length}</span></div>
        <div class="card-grid">${audiences.map(a => `
          <div class="card">
            <h3>${esc(a.name)}</h3><p>${esc(a.description)}</p>
            <p style="margin-top:8px;background:var(--info-soft);border-radius:8px;padding:8px 10px;color:#1d4ed8">${esc(a.tone_guide)}</p>
            <div class="card-actions"><span class="spacer"></span>
              <button class="btn btn-sm" data-kind="audience" data-act="edit" data-id="${a.id}">编辑</button>
              <button class="btn btn-sm btn-danger-ghost" data-kind="audience" data-act="del" data-id="${a.id}">删除</button>
            </div>
          </div>`).join("")}</div></div>
    </div>
  </div>`;
  $("#btn-t-scn").onclick = () => targetForm("scenario", null);
  $("#btn-t-aud").onclick = () => targetForm("audience", null);
  $$("[data-kind]").forEach(btn => {
    const src = btn.dataset.kind === "scenario" ? scenarios : audiences;
    const item = src.find(x => x.id === +btn.dataset.id);
    if (!item) return;
    btn.onclick = () => btn.dataset.act === "edit"
      ? targetForm(btn.dataset.kind, item)
      : confirm(`删除「${item.name}」？`) &&
        api.del(`/api/${btn.dataset.kind}s/${item.id}`).then(showView.bind(null, "targets"));
  });
}

function targetForm(kind, item) {
  const isScn = kind === "scenario";
  const body = openModal(`${item ? "编辑" : "新增"}${isScn ? "场景" : "人群"}${item ? " · " + esc(item.name) : ""}`, `
    <div class="field"><label>名称</label><input type="text" id="tf-name" value="${esc(item?.name || "")}"
      placeholder="${isScn ? "如：售前咨询" : "如：企业采购"}"></div>
    <div class="field"><label>${isScn ? "场景描述" : "人群描述"}</label>
      <input type="text" id="tf-desc" value="${esc(item?.description || "")}"></div>
    <div class="field"><label>${isScn ? "应对策略（机器人会按这个思路接话）" : "语气调整（机器人对这类人这样说话）"}</label>
      <textarea id="tf-guide" style="min-height:96px">${esc(item ? (isScn ? item.strategy : item.tone_guide) : "")}</textarea></div>
    <div class="m-actions"><button class="btn" onclick="closeModal()">取消</button><button class="btn btn-primary" id="tf-save">保存</button></div>`);
  body.querySelector("#tf-save").onclick = async () => {
    const payload = {
      name: body.querySelector("#tf-name").value.trim(),
      description: body.querySelector("#tf-desc").value.trim(),
      [isScn ? "strategy" : "tone_guide"]: body.querySelector("#tf-guide").value.trim(),
    };
    if (!payload.name) { toast("名称要填", "err"); return; }
    item ? await api.put(`/api/${kind}s/${item.id}`, payload)
         : await api.post(`/api/${kind}s`, payload);
    closeModal(); toast("已保存", "ok"); showView("targets");
  };
}

/* 🛠️ 训练中心
================================================ */
async function renderTraining() {
  const list = await api.get("/api/corrections");
  const active = list.filter(c => c.active).length;
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head"><h2>🛠️ 训练中心</h2>
      <span class="sub">聊天里点 👎 写下理想回复，就会沉淀到这里；生效中的纠错会在遇到类似问题时教机器人正确答法</span>
    </div>
    <div class="page-body">
      <div class="stat-row">
        <div class="stat"><b>${list.length}</b><span>纠错总数</span></div>
        <div class="stat"><b>${active}</b><span>生效中</span></div>
      </div>
      <div class="panel"><table class="tbl">
        <thead><tr><th style="width:170px">来访者问题</th><th style="width:200px">被批评的回复</th><th>标准答案</th><th style="width:150px">操作</th></tr></thead>
        <tbody>
        ${list.map(c => `
          <tr>
            <td><b>${esc(c.question || "（未记录）")}</b></td>
            <td style="color:var(--danger)">${esc(c.bad_reply.length > 60 ? c.bad_reply.slice(0, 60) + "…" : c.bad_reply)}</td>
            <td style="color:#0b7a52">${esc(c.corrected_reply)}</td>
            <td class="actions">
              <button class="btn btn-sm" data-act="toggle" data-id="${c.id}">${c.active ? "停用" : "启用"}</button>
              <button class="btn btn-sm btn-danger-ghost" data-act="del" data-id="${c.id}">删除</button>
              ${c.active ? '<span class="chip" style="margin-left:6px">生效中</span>' : '<span class="chip chip-gray" style="margin-left:6px">已停用</span>'}
            </td>
          </tr>`).join("") || '<tr><td colspan="4" style="color:var(--muted)">还没有纠错记录。去「对话测试」里给不满意的回复点个 👎 吧</td></tr>'}
        </tbody>
      </table></div>
    </div>
  </div>`;
  $$(".page-body [data-act]").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.dataset.id;
      if (btn.dataset.act === "toggle") {
        const c = list.find(x => x.id === +id);
        await api.put(`/api/corrections/${id}`, {active: c.active ? 0 : 1});
      } else if (confirm("删除这条纠错记录？")) {
        await api.del(`/api/corrections/${id}`);
      } else return;
      showView("training");
    };
  });
}

/* ================================================================
 * ⚙️ 设置
 * ================================================================ */
async function renderSettings() {
  state.settings = await api.get("/api/settings");
  const s = state.settings;
  $("#main").innerHTML = `
  <div class="page">
    <div class="page-head"><h2>⚙️ 设置</h2><span class="sub">回复引擎与合规选项</span></div>
    <div class="page-body"><div class="settings-wrap">
      <div class="field"><label>回复引擎</label>
        <div class="mode-cards">
          <div class="mode-card ${s.mode !== "llm" ? "sel" : ""}" data-mode="mock">
            <b>🧪 内置模拟引擎</b><p>无需任何配置即可演示全流程：规则匹配 + 话术套用。适合先熟悉产品。</p>
          </div>
          <div class="mode-card ${s.mode === "llm" ? "sel" : ""}" data-mode="llm">
            <b>🤖 真实大模型</b><p>接入 OpenAI 兼容接口（智谱 / DeepSeek / OpenAI / Ollama 等），回复以假乱真。</p>
          </div>
        </div>
      </div>

      <div id="llm-fields" style="display:${s.mode === "llm" ? "" : "none"}">
        <div class="panel" style="padding:16px 18px;margin-bottom:16px">
          <div class="field"><label>快捷预设</label>
            <button class="btn" type="button" id="btn-preset-deepseek">一键填入 DeepSeek 官方配置</button>
            <div class="hint">填入 Base URL 与模型名；Key 可留在下方，或改用环境变量 DEEPSEEK_API_KEY（优先级更高）</div></div>
          <div class="field"><label>API Base URL（OpenAI 兼容地址）</label>
            <input type="text" id="st-base" value="${esc(s.api_base_url)}" placeholder="如 https://api.deepseek.com"></div>
          <div class="field"><label>API Key</label>
            <input type="password" id="st-key" value="${esc(s.api_key)}" placeholder="sk-…">
            <div class="hint">Key 只保存在本机数据库；设置环境变量 DEEPSEEK_API_KEY 后此处可留空</div></div>
          <div class="field"><label>模型名称</label>
            <input type="text" id="st-model" value="${esc(s.api_model)}" placeholder="如 deepseek-flash / deepseek-v4-pro / glm-4-flash"></div>
          <div class="field"><label>温度 <span id="st-temp-v" style="color:var(--brand-dark);font-weight:600">${s.api_temperature}</span>（越高越有个性，越低越稳）</label>
            <input type="range" id="st-temp" min="0" max="1.5" step="0.1" value="${s.api_temperature}"></div>
        </div>
      </div>

      <div class="panel" style="padding:16px 18px;margin-bottom:16px">
        <div class="field"><label>产品名称</label>
          <input type="text" id="st-product" value="${esc(s.product_name)}"></div>
        <div class="switch-row">
          <label class="switch"><input type="checkbox" id="st-disclose" ${s.disclose_bot ? "checked" : ""}><span class="slider"></span></label>
          <div class="sw-text"><b>合规：声明机器人身份</b>
            <span>开启后机器人会在开场自然说明自己是智能助手。部分地区/平台法规要求披露，请按你的使用场景决定</span></div>
        </div>
      </div>

      <div style="display:flex;gap:10px">
        <button class="btn" id="btn-test">测试大模型连接</button>
        <span class="spacer" style="flex:1"></span>
        <button class="btn btn-primary" id="btn-save-settings">保存设置</button>
      </div>
      <div id="test-result" style="margin-top:12px;font-size:13px"></div>
    </div></div>
  </div>`;

  let mode = s.mode;
  $$(".mode-card").forEach(c => c.onclick = () => {
    mode = c.dataset.mode;
    $$(".mode-card").forEach(x => x.classList.toggle("sel", x === c));
    $("#llm-fields").style.display = mode === "llm" ? "" : "none";
  });
  $("#st-temp").oninput = e => $("#st-temp-v").textContent = e.target.value;
  $("#btn-preset-deepseek").onclick = () => {
    $("#st-base").value = "https://api.deepseek.com";
    $("#st-model").value = "deepseek-flash";
    toast("已填入 DeepSeek 官方参数，请填写 Key 或设置环境变量", "ok");
  };

  const collect = () => ({
    mode, api_base_url: $("#st-base")?.value.trim() || s.api_base_url,
    api_key: $("#st-key")?.value ?? s.api_key,
    api_model: $("#st-model")?.value.trim() || s.api_model,
    api_temperature: +($("#st-temp")?.value ?? s.api_temperature),
    disclose_bot: $("#st-disclose").checked ? 1 : 0,
    product_name: $("#st-product").value.trim() || "小熙客服",
  });

  $("#btn-save-settings").onclick = async () => {
    state.settings = await api.put("/api/settings", collect());
    updateFoot(); toast("设置已保存", "ok");
  };
  $("#btn-test").onclick = async () => {
    const el = $("#test-result");
    el.innerHTML = '<span style="color:var(--muted)">测试中…</span>';
    try {
      const res = await api.post("/api/settings/test", collect());
      el.innerHTML = res.ok
        ? `<span style="color:var(--brand-dark)">✅ ${esc(res.message)}</span>`
        : `<span style="color:var(--danger)">❌ ${esc(res.message)}</span>`;
    } catch (e) { el.innerHTML = `<span style="color:var(--danger)">❌ ${esc(e.message)}</span>`; }
  };
}

/* ---------------- 出发 ---------------- */
init();
