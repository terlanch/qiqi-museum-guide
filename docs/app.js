(function () {
  /**
   * 同步执行时 document.currentScript 即本文件，比 querySelector 更可靠（避免选错别的 script）
   */
  var THIS_SCRIPT = document.currentScript;

  /**
   * GitHub Pages：一般留空，由 app.js 的绝对地址推导站点根。
   * 仅当自动推导失败时再填，例如 "/opc"
   */
  var MANUAL_BASE = "";

  /** 站点根 URL（无末尾斜杠）；推导失败时返回空串，改用相对路径 ./ */
  function siteRootUrl() {
    if (MANUAL_BASE) {
      var p = MANUAL_BASE.replace(/^\/+|\/+$/g, "");
      return p ? location.origin + "/" + p : location.origin;
    }
    var el = THIS_SCRIPT || document.querySelector('script[src*="app.js"]');
    if (el && el.src) {
      return el.src.replace(/\/?app\.js(\?.*)?$/i, "");
    }
    return "";
  }

  function assetPath(rel) {
    rel = String(rel || "").replace(/^\//, "");
    var root = siteRootUrl();
    if (!root) return "./" + rel;
    return root + "/" + rel;
  }

  const $wing = document.getElementById("filter-wing");
  const $floor = document.getElementById("filter-floor");
  const $q = document.getElementById("q");
  const $status = document.getElementById("status");
  const $results = document.getElementById("results");
  const $clear = document.getElementById("btn-clear");

  function normalize(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[\s./\-_]+/g, "");
  }

  function loadData() {
    var primary = assetPath("data/catalog.json");
    var fallback = assetPath("data/works.json");
    return fetch(primary, { cache: "no-store" }).then(function (r) {
      if (r.ok) return r.json();
      return fetch(fallback, { cache: "no-store" }).then(function (r2) {
        if (!r2.ok) throw new Error("无法加载 catalog.json / works.json");
        return r2.json();
      });
    });
  }

  function fillFilters(works) {
    if (!$wing || !$floor) return;

    while ($wing.options.length > 1) {
      $wing.remove(1);
    }
    while ($floor.options.length > 1) {
      $floor.remove(1);
    }

    var wings = {};
    var floors = {};
    (works || []).forEach(function (w) {
      if (!w) return;
      var wk = (w.wingKey && String(w.wingKey).trim()) || "unknown";
      var wlab = (w.wingZh && String(w.wingZh).trim()) || "";
      if (!wlab) wlab = wk === "unknown" ? "馆区未识别" : wk;
      wings[wk] = wlab;

      var fl = w.floor;
      if (fl !== undefined && fl !== null && String(fl).trim() !== "") {
        var fk = String(fl).trim();
        var flab = (w.floorLabel && String(w.floorLabel).trim()) || fk + " 层";
        floors[fk] = flab;
      }
    });

    var wingOrder = ["sully", "denon", "richelieu", "unknown"];
    wingOrder.forEach(function (k) {
      if (!wings[k]) return;
      var opt = document.createElement("option");
      opt.value = k;
      opt.textContent = wings[k];
      $wing.appendChild(opt);
    });
    Object.keys(wings).forEach(function (k) {
      if (wingOrder.indexOf(k) >= 0) return;
      var opt = document.createElement("option");
      opt.value = k;
      opt.textContent = wings[k];
      $wing.appendChild(opt);
    });

    Object.keys(floors)
      .sort(function (a, b) {
        return parseInt(a, 10) - parseInt(b, 10);
      })
      .forEach(function (f) {
        var opt = document.createElement("option");
        opt.value = f;
        opt.textContent = floors[f];
        $floor.appendChild(opt);
      });
  }

  function matchSearch(w, rawQ) {
    var q = (rawQ || "").trim().toLowerCase();
    if (!q) return true;
    var blob =
      (w.titleZh || "") +
      " " +
      (w.titleFr || "") +
      " " +
      (w.inventory || []).map(function (x) {
        return x.value;
      }).join(" ");
    if (blob.toLowerCase().indexOf(q) >= 0) return true;
    var nq = normalize(q);
    if (nq && w.nameSearch && w.nameSearch.indexOf(nq) >= 0) return true;
    if (nq && w.inventorySearch && normalize(w.inventorySearch).indexOf(nq) >= 0)
      return true;
    return false;
  }

  function applyFilters(works) {
    var wk = $wing.value;
    var fl = $floor.value;
    return works.filter(function (w) {
      var itemWing = (w.wingKey && String(w.wingKey).trim()) || "unknown";
      if (wk && itemWing !== wk) return false;
      if (fl !== "" && String(w.floor) !== fl) return false;
      return matchSearch(w, $q.value);
    });
  }

  function render(works) {
    var list = applyFilters(works);

    $results.innerHTML = "";
    if (!list.length) {
      $results.innerHTML =
        '<p class="hint">没有匹配的藏品。可更换馆区/楼层筛选，或调整搜索词。</p>';
      return;
    }

    list.forEach(function (w) {
      var card = document.createElement("article");
      card.className = "card";

      var h2 = document.createElement("h2");
      h2.textContent = w.titleZh || w.titleFr || w.id;
      card.appendChild(h2);

      var sub = document.createElement("p");
      sub.className = "meta sub-title";
      if (w.titleFr && w.titleFr !== w.titleZh) sub.textContent = w.titleFr;
      else sub.textContent = "";
      if (sub.textContent) card.appendChild(sub);

      var locLine = document.createElement("p");
      locLine.className = "meta";
      var parts = [w.wingZh, w.floorLabel, w.galleryLabel].filter(Boolean);
      locLine.textContent = parts.length ? "位置：" + parts.join(" · ") : "";
      if (locLine.textContent) card.appendChild(locLine);

      var meta = document.createElement("p");
      meta.className = "meta";
      var inv = (w.inventory || [])
        .map(function (x) {
          return x.value;
        })
        .join(" · ");
      meta.textContent = [w.collectionFr, inv].filter(Boolean).join(" — ");
      if (meta.textContent) card.appendChild(meta);

      if (w.inventory && w.inventory.length) {
        var badges = document.createElement("div");
        badges.className = "badges";
        w.inventory.forEach(function (x) {
          var b = document.createElement("span");
          b.className = "badge";
          b.textContent = x.value;
          badges.appendChild(b);
        });
        card.appendChild(badges);
      }

      if (w.narrationPreview) {
        var txt = w.narrationPreview;
        var foldThreshold = 96;
        if (txt.length <= foldThreshold) {
          var shortP = document.createElement("p");
          shortP.className = "preview";
          shortP.textContent = txt;
          card.appendChild(shortP);
        } else {
          var fold = document.createElement("div");
          fold.className = "narration-fold";
          var body = document.createElement("div");
          body.className = "narration-text";
          body.textContent = txt;
          var toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "narration-toggle";
          toggle.setAttribute("aria-expanded", "false");
          toggle.textContent = "展开全文";
          toggle.addEventListener("click", function () {
            var open = fold.classList.toggle("expanded");
            toggle.textContent = open ? "收起" : "展开全文";
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
          });
          fold.appendChild(body);
          fold.appendChild(toggle);
          card.appendChild(fold);
        }
      }

      if (w.audio) {
        var audio = document.createElement("audio");
        audio.controls = true;
        audio.preload = "none";
        audio.src = assetPath(w.audio);
        card.appendChild(audio);
      } else {
        var na = document.createElement("p");
        na.className = "no-audio";
        na.textContent = "暂无音频";
        card.appendChild(na);
      }

      var link = document.createElement("p");
      link.className = "meta";
      var a = document.createElement("a");
      a.href = w.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "藏品详情";
      link.appendChild(a);
      card.appendChild(link);

      $results.appendChild(card);
    });
  }

  loadData()
    .then(function (data) {
      var works = data.works || [];
      fillFilters(works);
      var wingOpts = Math.max(0, $wing.options.length - 1);
      var floorOpts = Math.max(0, $floor.options.length - 1);
      $status.textContent =
        "已加载 " +
        works.length +
        " 条。馆区 " +
        wingOpts +
        " 个、楼层 " +
        floorOpts +
        " 种可选；可配合搜索。";

      function refresh() {
        render(works);
      }

      $wing.addEventListener("change", refresh);
      $floor.addEventListener("change", refresh);
      $q.addEventListener("input", refresh);
      $clear.addEventListener("click", function () {
        $q.value = "";
        $wing.value = "";
        $floor.value = "";
        refresh();
      });

      refresh();
    })
    .catch(function (e) {
      $status.textContent = "加载失败";
      $results.innerHTML =
        '<p class="hint">请通过网站地址访问本页（勿用本地直接双击打开 HTML）。</p>';
    });
})();
