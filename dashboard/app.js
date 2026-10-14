/* AgentDeck dashboard — 渲染 collector 快照 (Day 2 polish) */
(function () {
  "use strict";

  var deck = document.getElementById("deck");
  var liveDot = document.getElementById("liveDot");
  var liveText = document.getElementById("liveText");
  var fleetSub = document.getElementById("fleetSub");
  var tpl = document.getElementById("cardTpl");

  // 快照与 dashboard 的相对位置：repo 内 ../collector/snapshots/，
  // 若只部署 dashboard/ 目录则回退到同级 snapshots/。
  var SNAP_URLS = [
    "../collector/snapshots/latest.json",
    "snapshots/latest.json"
  ];

  var BRIDGE_META = {
    prisma:  { label: "Prisma 中继", sub: "云端 · 东京 · 手机 agent 直连" },
    railway: { label: "Railway 盒子", sub: "试用 VM · 需手机 agent 拉起" }
  };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function relTime(iso) {
    var t;
    try { t = new Date(iso).getTime(); } catch (e) { return ""; }
    if (isNaN(t)) return "";
    var s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return "刚刚";
    var m = Math.floor(s / 60);
    if (m < 60) return m + " 分钟前";
    var h = Math.floor(m / 60);
    if (h < 24) return h + " 小时前";
    return Math.floor(h / 24) + " 天前";
  }

  function cleanNotes(list) {
    return (list || []).filter(function (n) {
      var t = typeof n === "string" ? n.trim() : "";
      return t && t !== "(none)" && t.toLowerCase() !== "none";
    });
  }

  function trunc(s, n) {
    s = String(s);
    return s.length > n ? s.slice(0, n) + "…" : s;
  }

  function renderBridge(b, collectedAt, idx) {
    var meta = BRIDGE_META[b.bridge] || { label: b.bridge, sub: "" };
    var node = tpl.content.cloneNode(true);
    var card = node.querySelector(".card");
    card.classList.add(b.ok ? "up" : "down");
    card.style.animationDelay = (idx * 0.09) + "s";

    node.querySelector(".name").textContent = meta.label;
    node.querySelector(".site-sub").textContent = meta.sub;
    var stamp = node.querySelector(".stamp");
    stamp.textContent = relTime(collectedAt) + "同步";
    stamp.setAttribute("datetime", collectedAt || "");

    var nowBox = node.querySelector(".now");
    var nowLabel = node.querySelector(".now-label");
    var nowText = node.querySelector(".now-text");
    var timeline = node.querySelector(".timeline");
    var caps = node.querySelector(".caps");
    var capsSum = node.querySelector(".caps-sum");
    var toolsBox = node.querySelector(".tools");
    var empty = node.querySelector(".empty");

    if (b.ok) {
      var notes = cleanNotes(b.notes);
      if (notes.length) {
        nowText.textContent = trunc(notes[0], 300);
        notes.slice(1, 9).forEach(function (n, i) {
          var li = el("li", null, trunc(n, 220));
          li.style.animationDelay = (0.15 + idx * 0.09 + i * 0.06) + "s";
          timeline.appendChild(li);
        });
      } else {
        nowLabel.textContent = "状态";
        nowText.textContent = "桥接正常，agent 暂时没有新动态。";
      }
      var tools = b.tools || [];
      if (tools.length) {
        capsSum.textContent = "能力 · " + tools.length + " 个工具";
        tools.forEach(function (t) { toolsBox.appendChild(el("code", null, t)); });
      } else {
        caps.remove();
      }
    } else {
      nowLabel.textContent = "状态";
      nowText.textContent = "站点离线，等待重连。collector 每小时会重试。";
      caps.remove();
      empty.remove();
      var det = el("details", "err-detail", null);
      var sum = el("summary", null, "查看错误详情");
      var pre = el("pre", null, trunc(b.error || "未知错误", 600));
      det.appendChild(sum); det.appendChild(pre);
      card.appendChild(det);
      if (window.console && console.warn) console.warn("[agentdeck] bridge down:", b.bridge, b.error);
    }
    deck.appendChild(node);
  }

  function setLive(ok, label) {
    liveDot.classList.toggle("ok", !!ok);
    liveText.textContent = label;
  }

  function render(snap) {
    deck.innerHTML = "";
    var bridges = snap.bridges || [];
    var up = bridges.filter(function (b) { return b.ok; }).length;
    var anyUp = up > 0;
    setLive(anyUp, anyUp ? "在线" : "全部离线");
    fleetSub.textContent = bridges.length
      ? bridges.length + " 个站点 · " + up + " 在线 · " + relTime(snap.collected_at) + "同步"
      : "暂无站点数据";
    if (!bridges.length) {
      deck.appendChild(el("p", "deck-err", "快照为空，等待 collector 下一次运行。"));
      return;
    }
    bridges.forEach(function (b, i) { renderBridge(b, snap.collected_at, i); });
  }

  function fail(msg) {
    deck.innerHTML = "";
    setLive(false, "无数据");
    fleetSub.textContent = "读取快照失败";
    deck.appendChild(el("p", "deck-err", "读取快照失败（" + msg + "）：collector 可能还未运行。"));
    if (window.console && console.error) console.error("[agentdeck]", msg);
  }

  function tryFetch(i) {
    if (i >= SNAP_URLS.length) { fail("无可用快照路径"); return; }
    fetch(SNAP_URLS[i], { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(render)
      .catch(function () { tryFetch(i + 1); });
  }

  tryFetch(0);
})();
