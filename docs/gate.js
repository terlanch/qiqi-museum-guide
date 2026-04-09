(function () {
  var SESSION_KEY = "louvre_access_v1";
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

  if (document.documentElement.classList.contains("access-pre")) {
    unlock();
    return;
  }

  var $gate = document.getElementById("access-gate");
  var $input = document.getElementById("access-code-input");
  var $btn = document.getElementById("access-code-submit");
  if (!$gate || !$input || !$btn) {
    loadAppScript();
    return;
  }

  var codesPromise = null;
  function loadCodes() {
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

  function verify() {
    setErr("");
    var raw = normalizeInput($input.value);
    if (raw.length !== 16) {
      setErr("请输入 16 位验证码（区分大小写）。");
      return;
    }
    $btn.disabled = true;
    loadCodes()
      .then(function (data) {
        var list = data.codes || [];
        var ok = false;
        for (var i = 0; i < list.length; i++) {
          if (list[i] === raw) {
            ok = true;
            break;
          }
        }
        if (ok) {
          unlock();
        } else {
          setErr("验证码无效，请核对后重试。");
        }
      })
      .catch(function () {
        setErr("无法加载验证码列表，请确认通过网站根路径访问（勿用 file:// 打开）。");
      })
      .finally(function () {
        $btn.disabled = false;
      });
  }

  $btn.addEventListener("click", verify);
  $input.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") verify();
  });
  $input.focus();
})();
