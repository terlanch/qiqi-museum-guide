(function () {
  var SESSION_KEY = "louvre_access_v1";
  var SESSION_EXP_KEY = "louvre_access_expires";

  var SCRIPT = document.currentScript;

  function siteRootUrl() {
    var el = SCRIPT || document.querySelector('script[src*="gate.js"]');
    if (el && el.src) {
      return el.src.replace(/\/?gate\.js(\?.*)?$/i, "");
    }
    return "";
  }

  function assetPath(rel) {
    rel = String(rel || "").replace(/^\//, "");
    var root = siteRootUrl();
    if (!root) return "./" + rel;
    return root + "/" + rel;
  }

  function loadAppScript() {
    if (window.__louvreAppLoaded) return;
    window.__louvreAppLoaded = true;
    var s = document.createElement("script");
    s.src = assetPath("app.js");
    document.body.appendChild(s);
  }

  function unlock() {
    try {
      sessionStorage.setItem(SESSION_KEY, "1");
    } catch (e) {}
    document.documentElement.classList.add("access-pre");
    var gate = document.getElementById("access-gate");
    var shell = document.getElementById("app-shell");
    if (gate) {
      gate.setAttribute("hidden", "");
      gate.setAttribute("aria-hidden", "true");
    }
    if (shell) {
      shell.removeAttribute("hidden");
    }
    loadAppScript();
  }

  function setErr(msg) {
    var el = document.getElementById("access-code-err");
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.hidden = false;
    } else {
      el.textContent = "";
      el.hidden = true;
    }
  }

  function normalizeInput(s) {
    return String(s || "").trim();
  }

  /** ISO 日期 YYYY-MM-DD，含当日 23:59:59.999（本地时区）前有效 */
  function isExpired(isoDate) {
    if (!isoDate) return false;
    var end = new Date(String(isoDate).trim() + "T23:59:59.999");
    return Date.now() > end.getTime();
  }

  function clearSession() {
    try {
      sessionStorage.removeItem(SESSION_KEY);
      sessionStorage.removeItem(SESSION_EXP_KEY);
    } catch (e) {}
    document.documentElement.classList.remove("access-pre");
  }

  function sha256Hex(str) {
    var buf = new TextEncoder().encode(str);
    return crypto.subtle.digest("SHA-256", buf).then(function (hash) {
      var arr = new Uint8Array(hash);
      var hex = "";
      for (var i = 0; i < arr.length; i++) {
        hex += ("0" + arr[i].toString(16)).slice(-2);
      }
      return hex;
    });
  }

  function showExpiredUI(data) {
    var form = document.getElementById("access-gate-form");
    var expired = document.getElementById("access-gate-expired");
    var dateEl = document.getElementById("access-expired-date");
    var linkEl = document.getElementById("access-merchant-link");
    var hint = document.querySelector(".access-gate__hint");
    if (hint) hint.hidden = true;
    if (form) form.hidden = true;
    if (dateEl) dateEl.textContent = data.expiresAt || "";
    if (linkEl && data.merchantConsultUrl) {
      linkEl.href = data.merchantConsultUrl;
    }
    if (expired) {
      expired.hidden = false;
    }
    setErr("");
  }

  var codesPromise = null;
  function loadAccessData() {
    if (!codesPromise) {
      codesPromise = fetch(assetPath("data/access_codes.json"), {
        cache: "no-store",
      }).then(function (r) {
        if (!r.ok) throw new Error("load");
        return r.json();
      });
    }
    return codesPromise;
  }

  function verify(data) {
    setErr("");
    var $in = document.getElementById("access-code-input");
    var raw = normalizeInput($in ? $in.value : "");
    if (raw.length !== 16) {
      setErr("请输入 16 位验证码（区分大小写）。");
      return;
    }
    var hashes = data.hashes;
    if (!hashes || !hashes.length) {
      setErr("校验数据格式错误。");
      return;
    }
    var $btn = document.getElementById("access-code-submit");
    if ($btn) $btn.disabled = true;

    sha256Hex(raw)
      .then(function (hex) {
        var ok = false;
        for (var i = 0; i < hashes.length; i++) {
          if (hashes[i] === hex) {
            ok = true;
            break;
          }
        }
        if (ok) {
          try {
            if (data.expiresAt) {
              sessionStorage.setItem(SESSION_EXP_KEY, data.expiresAt);
            }
          } catch (e) {}
          unlock();
        } else {
          setErr("验证码无效，请核对后重试。");
        }
      })
      .catch(function () {
        setErr("当前环境无法完成校验（请使用 HTTPS 或 localhost 打开本站）。");
      })
      .finally(function () {
        if ($btn) $btn.disabled = false;
      });
  }

  function bindForm(data) {
    var $input = document.getElementById("access-code-input");
    var $btn = document.getElementById("access-code-submit");
    if (!$btn) return;
    $btn.onclick = function () {
      verify(data);
    };
    if ($input) {
      $input.onkeydown = function (ev) {
        if (ev.key === "Enter") verify(data);
      };
      $input.focus();
    }
  }

  loadAccessData()
    .then(function (data) {
      if (isExpired(data.expiresAt)) {
        clearSession();
        showExpiredUI(data);
        return;
      }

      try {
        if (sessionStorage.getItem(SESSION_KEY) === "1") {
          var savedExp = sessionStorage.getItem(SESSION_EXP_KEY);
          if (savedExp && data.expiresAt && savedExp !== data.expiresAt) {
            clearSession();
          } else {
            if (!savedExp && data.expiresAt) {
              try {
                sessionStorage.setItem(SESSION_EXP_KEY, data.expiresAt);
              } catch (e2) {}
            }
            unlock();
            return;
          }
        }
      } catch (e) {}

      var $gate = document.getElementById("access-gate");
      var $input = document.getElementById("access-code-input");
      if (!$gate || !$input) {
        loadAppScript();
        return;
      }

      bindForm(data);
    })
    .catch(function () {
      setErr("无法加载校验数据，请确认通过网站根路径访问（勿用 file:// 打开）。");
    });
})();
