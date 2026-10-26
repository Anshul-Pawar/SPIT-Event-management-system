/* SPIT Events: shared client. Talks to the Django JSON API at /api (same origin). */
(function () {
  "use strict";

  const API = "/api";
  const KEY = "spit.token", ME = "spit.me";

  /* ---------- tiny helpers ---------- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode: session just won't persist */ } },
    del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
  };

  /* ---------- formatting ---------- */
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  function parseDate(d) {
    if (!d) return null;
    const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  const day = (d) => { const x = parseDate(d); return x ? String(x.getDate()).padStart(2, "0") : "--"; };
  const mon = (d) => { const x = parseDate(d); return x ? MONTHS[x.getMonth()] : "TBA"; };
  const dateLong = (d) => { const x = parseDate(d); return x ? `${x.getDate()} ${MONTHS[x.getMonth()]} ${x.getFullYear()}` : "TBA"; };
  function time(t) {
    if (t === null || t === undefined || t === "") return "";
    if (typeof t === "number") { const s = Math.round(t); return `${String(Math.floor(s / 3600) % 24).padStart(2, "0")}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}`; }
    const m = String(t).match(/(\d{1,2}):(\d{2})/);
    return m ? `${m[1].padStart(2, "0")}:${m[2]}` : String(t);
  }
  const money = (v) => { const n = Number(v); return n > 0 ? "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "FREE"; };
  const moneyPlain = (v) => "₹" + Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  function stamp(dt) {
    if (!dt) return "";
    const d = new Date(String(dt).replace(" ", "T"));
    if (isNaN(d)) return String(dt);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} · ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }
  const isPast = (d) => { const x = parseDate(d); if (!x) return false; const t = new Date(); t.setHours(0, 0, 0, 0); return x < t; };

  /* A category's colour + shape. Unknown categories fall back to a stable pick. */
  const CATS = {
    technical: { c: "blue", shape: "" },
    workshop: { c: "yellow", shape: "circle" },
    seminar: { c: "red", shape: "tri" },
    cultural: { c: "ink", shape: "half" },
    social: { c: "white", shape: "ring" },
  };
  const FALLBACK = [{ c: "blue", shape: "" }, { c: "yellow", shape: "circle" }, { c: "red", shape: "tri" }, { c: "ink", shape: "half" }];
  function catStyle(name) {
    const k = String(name || "").toLowerCase();
    if (CATS[k]) return CATS[k];
    let h = 0; for (const ch of k) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return FALLBACK[h % FALLBACK.length];
  }
  const shapeEl = (cls, extra = "") => `<span class="shape ${cls} ${extra}" aria-hidden="true"></span>`;

  /* ---------- session ---------- */
  const Session = {
    get token() { return store.get(KEY); },
    get user() { try { return JSON.parse(store.get(ME) || "null"); } catch { return null; } },
    set(token, user) { store.set(KEY, token); store.set(ME, JSON.stringify(user)); },
    clear() { store.del(KEY); store.del(ME); },
    get isStudent() { const u = this.user; return !!u && (u.role === "student" || u.role === "council"); },
  };

  /* ---------- api ---------- */
  function errorText(data, status) {
    if (!data) return status ? `Something went wrong (${status}).` : "Could not reach the server.";
    if (typeof data === "string") return data;
    if (data.error) return data.error;
    if (data.detail) return data.detail;
    const parts = [];
    const walk = (v, key) => {
      if (Array.isArray(v)) v.forEach((x) => walk(x, key));
      else if (v && typeof v === "object") Object.entries(v).forEach(([k, x]) => walk(x, k));
      else parts.push(key && key !== "non_field_errors" ? `${key.replace(/_/g, " ")}: ${v}` : String(v));
    };
    walk(data);
    return parts.join(" · ") || `Something went wrong (${status}).`;
  }

  class ApiError extends Error { constructor(message, status, data) { super(message); this.status = status; this.data = data; } }

  async function api(path, { method = "GET", body, retried = false } = {}) {
    const headers = { Accept: "application/json" };
    const token = Session.token;
    if (token) headers.Authorization = "Token " + token;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res;
    try {
      res = await fetch(API + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch {
      throw new ApiError("Could not reach the server. Is it running?", 0, null);
    }
    let data = null;
    if (res.status !== 204) { try { data = await res.json(); } catch { data = null; } }
    if (res.status === 401 && token) {
      // Token expired or was revoked. Drop it; a public page can simply retry as a guest.
      Session.clear();
      if (!retried && method === "GET") return api(path, { method, body, retried: true });
    }
    if (!res.ok) throw new ApiError(errorText(data, res.status), res.status, data);
    return data;
  }

  async function refreshMe() {
    if (!Session.token) return null;
    try {
      const me = await api("/auth/me");
      store.set(ME, JSON.stringify(me));
      return me;
    } catch (e) {
      if (e.status === 401 || e.status === 403) Session.clear();
      return Session.user;
    }
  }

  /* ---------- toasts ---------- */
  function toast(message, kind = "ok", ms = 5000) {
    let box = $("#toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
    const t = document.createElement("div");
    t.className = "toast " + kind;
    t.textContent = message;
    box.appendChild(t);
    setTimeout(() => t.remove(), ms);
  }
  const fail = (e) => toast(e && e.message ? e.message : String(e), "err", 7000);

  /* ---------- chrome (header + footer) ---------- */
  function renderChrome(active) {
    const u = Session.user;
    const links = [["index.html", "events", "Events"]];
    if (u) {
      if (Session.isStudent) links.push(["my.html", "my", "My tickets"]);
      if (u.role === "committee") links.push(["committee.html", "committee", "Committee"]);
      if (u.is_approver) links.push(["approvals.html", "approvals", "Approvals"]);
      if (u.is_approver) links.push(["admin.html", "admin", "Dashboard"]);
    }
    const nav = links.map(([href, key, label]) => `<a href="${href}"${key === active ? ' aria-current="page"' : ""}>${label}</a>`).join("");
    const auth = u
      ? `<span class="who">${esc(u.name)} · ${esc(u.role)}</span><button type="button" id="logout">Log out</button>`
      : `<a class="login" href="login.html?next=${encodeURIComponent(location.pathname.split("/").pop() + location.search)}">Log in</a>`;
    const head = document.createElement("header");
    head.className = "site-head";
    head.innerHTML = `<div class="wrap">
      <a class="brand" href="index.html" aria-label="SPIT Events home">
        <span class="mark"><i></i><i></i><i></i></span><b>SPIT<span>Events</span></b></a>
      <nav class="nav" aria-label="Main">${nav}${auth}</nav></div>`;
    document.body.prepend(head);
    const foot = document.createElement("footer");
    foot.className = "site-foot";
    foot.innerHTML = `<div class="wrap"><span>SPIT · Event management</span><span class="mark"><i></i><i></i><i></i></span></div>`;
    document.body.appendChild(foot);
    const out = $("#logout");
    if (out) out.addEventListener("click", async () => {
      try { await api("/auth/logout", { method: "POST" }); } catch { /* token may already be gone */ }
      Session.clear();
      location.href = "index.html";
    });
  }

  /**
   * Every page calls boot(). opts.require: "login" | "approver" | "committee" | "student".
   * Returns the user (or null for guests) once the guard has passed; redirects otherwise.
   */
  async function boot(active, opts = {}) {
    if (Session.token) await refreshMe();
    const u = Session.user;
    const bounce = () => { location.replace("login.html?next=" + encodeURIComponent(location.pathname.split("/").pop() + location.search)); };
    if (opts.require && !u) { bounce(); return new Promise(() => {}); }
    renderChrome(active);
    const deny = (msg) => {
      $("main").innerHTML = `<div class="wrap section"><div class="empty">${shapeEl("tri", "s-red lg")}<h2>Not for this account</h2><p class="muted" style="margin-top:10px">${esc(msg)}</p><p style="margin-top:20px"><a class="btn" href="index.html">Back to events</a></p></div></div>`;
      return new Promise(() => {});
    };
    if (opts.require === "approver" && !u.is_approver) return deny("Only the student council or an admin can open this page.");
    if (opts.require === "committee" && !(u.committees && u.committees.length)) return deny("Only a committee's own account can post events. Ask the council to set yours up.");
    if (opts.require === "student" && !Session.isStudent) return deny("Only students have tickets.");
    return u;
  }

  /* tabs: buttons[role=tab] with data-tab, panels with id */
  function tabs(root, onChange) {
    const btns = $$('[role="tab"]', root);
    const show = (name) => {
      btns.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
      btns.forEach((b) => { const p = document.getElementById(b.dataset.tab); if (p) p.classList.toggle("hidden", b.dataset.tab !== name); });
      if (onChange) onChange(name);
    };
    btns.forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
    return show;
  }

  const statusChip = (s) => {
    const m = { Approved: "blue", Pending: "yellow", Rejected: "red", Registered: "blue", Cancelled: "ink",
      Active: "blue", Suspended: "yellow", Removed: "red" };
    return `<span class="chip ${m[s] || ""}">${esc(s)}</span>`;
  };

  window.App = { $, $$, esc, api, ApiError, Session, boot, toast, fail, tabs, refreshMe,
    fmt: { day, mon, dateLong, time, money, moneyPlain, stamp, isPast, parseDate },
    catStyle, shapeEl, statusChip };
})();
