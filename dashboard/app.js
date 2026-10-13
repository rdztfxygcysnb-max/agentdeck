/* AgentDeck dashboard — 渲染 collector 快照 */
(function () {
  "use strict";

  var deck = document.getElementById("deck");
  var liveDot = document.getElementById("liveDot");
  var liveText = document.getElementById("liveText");
  var tpl = document.getElementById("cardTpl");

  var BRIDGE_LABEL = { prisma: "Prisma Bridge", railway: "Railway Box" };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function fmtTime(iso) {
    try {
      var d = new Date(iso);
      return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    } catch (e) { return ""; }
  }

  function renderBridge(b, collectedAt) {
    var node = tpl.content.cloneNode(true);
    var card = node.querySelector(".card");
    card.classList.add(b.ok ? "up" : "down");

    node.querySelector(".name").textContent = BRIDGE_LABEL[b.bridge] || b.bridge;
    node.querySelector(".stamp").textContent = fmtTime(collectedAt);

    if (b.ok) {
      var tools = node.querySelector(".tools");
      (b.tools || []).forEach(function (t) { tools.appendChild(el("code", null, t)); });

      var notes = node.querySelector(".notes");
      var list = b.notes || [];
      if (!list.length) {
        card.querySelector(".empty").textContent = "连接正常，暂无活动记录";
      }
      list.slice(0, 8).forEach(function (n) {
        var text = typeof n === "string" ? n : JSON.stringify(n);
        notes.appendChild(el("li", null, text.length > 280 ? text.slice(0, 280) + "…" : text));
      });
    } else {
      var err = el("p", "err", "连接失败：" + (b.error || "未知错误"));
      card.appendChild(err);
    }
    deck.appendChild(node);
  }

  function setLive(ok, label) {
    liveDot.classList.toggle("ok", !!ok);
    liveText.textContent = label;
  }

  // 快照与页面同目录（../collector/snapshots/latest.json），Cloudflare Pages 上同样路径可用
  fetch("../collector/snapshots/latest.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (snap) {
      var bridges = snap.bridges || [];
      var anyUp = bridges.some(function (b) { return b.ok; });
      setLive(anyUp, anyUp ? "在线" : "全部离线");
      if (!bridges.length) {
        deck.appendChild(el("p", "err", "快照为空，等待 collector 下一次运行。"));
        return;
      }
      bridges.forEach(function (b) { renderBridge(b, snap.collected_at); });
    })
    .catch(function (e) {
      setLive(false, "无数据");
      deck.appendChild(el("p", "err", "读取快照失败（" + e.message + "）：collector 可能还未运行。"));
    });
})();
