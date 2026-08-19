/* Kampff Analyze webview — one-click dossier + live progress */
(function () {
  const vscode = acquireVsCodeApi();
  const $ = (id) => document.getElementById(id);

  let platforms = [];
  let allTargets = [];
  let applying = false;
  let probeTimer = 0;
  let selectedListId = "";

  function setStatus(d) {
    const st = $("status");
    if (!st) return;
    st.className = "";
    if (d && d.ok === false) st.className = "bad";
    else if (d && d.busy) st.className = "busy";
    else if (d && d.ok) st.className = "ok";
    st.textContent = (d && d.text) || "—";
    st.dataset.busy = d && d.text && d.ok !== undefined ? "1" : "";
  }

  function siteId() {
      return ($("site") && $("site").value) || "x";
    }
    function siteMeta() {
      const id = siteId();
      const list = platforms && platforms.length ? platforms : [];
      for (let i = 0; i < list.length; i++) {
        if (list[i].id === id) return list[i];
      }
      return { id: id, kind: "generic", baseUrl: id === "x" ? "https://x.com" : "" };
    }
      function currentId() {
    return (($("authorId") && $("authorId").value) || "")
      .trim()
      .split(/[\s|,]+/)[0] || "";
  }

  function fillSites(def) {
      const sel = $("site");
      if (!sel) return;
      const prev = sel.value;
      const cur = prev || def || "x";
      const list =
        platforms && platforms.length
          ? platforms
          : [{ id: "x", label: "X", kind: "generic", baseUrl: "https://x.com" }];
      sel.innerHTML = "";
      list.forEach((p) => {
        const o = document.createElement("option");
        o.value = p.id;
        const bits = [p.label || p.id];
        if (p.baseUrl) bits.push(p.baseUrl.replace(/^https?:\/\//i, "").replace(/\/$/, ""));
        if (p.hasPassword) bits.push("🔑");
        o.textContent = bits.join(" · ");
        sel.appendChild(o);
      });
      if ([].some.call(sel.options, (o) => o.value === cur)) sel.value = cur;
      else if (sel.options.length) sel.selectedIndex = 0;
      onSiteChange();
    }

  function onSiteChange() {
            const nickRow = $("nickRow");
      if (nickRow) nickRow.classList.toggle("hide", true);
      const title = $("idTitle");
      if (title) title.textContent = "대상";
      paintScope();
      fillTargets();
      paintCtx();
      scheduleProbe();
    }

    function currentUrl() {
      return (($("url") && $("url").value) || "").trim();
    }

    function isHttpUrl(s) {
      return /^https?:\/\//i.test((s || "").trim());
    }

    
    /** If user pasted a post URL into the ID box, move it to URL and switch to thread. */
    function rescueUrlFromIdBox() {
      const aid = $("authorId");
      if (!aid) return false;
      const v = (aid.value || "").trim();
      if (!isHttpUrl(v)) return false;
      if ($("url") && !currentUrl()) $("url").value = v;
      
      aid.value = "";
      setSeg("mode", "thread");
      const root = $("modeSeg");
      if (root) root.dataset.touched = "1";
      return true;
    }

    function paintScope() {
      const mode = getSeg("mode");
            const id = currentId();
      const url = currentUrl();
      // Only member | thread in UI. (legacy profile/auto → person unless thread)
      const thready = mode === "thread";

      const personFields = $("personFields");
      const urlField = $("urlField");
      if (personFields) {
        personFields.classList.toggle("hide", thready);
        personFields.classList.toggle("emphasis", !thready);
        personFields.classList.remove("muted-opt");
      }
      if (urlField) {
        urlField.classList.toggle("hide", !thready);
        urlField.classList.toggle("emphasis", thready);
        urlField.classList.remove("muted-opt");
      }

      const lbl = $("lblAuthorId");
      if (lbl && !thready) {
        // Don't rewrite every keystroke — only when label text wrong
        const want = "Handle (예: elonmusk · example only)";
        if (!lbl.dataset.base || lbl.dataset.base !== want) {
          lbl.dataset.base = want;
          lbl.innerHTML =
            want +
            '<span class="req" id="reqId">*</span> <span class="term help-ico" data-term="authorid" tabindex="0">?</span>';
        }
      }

      const aid = $("authorId");
      if (aid) {
        aid.placeholder = "예: elonmusk · example only";
        aid.readOnly = false;
        aid.disabled = false;
        aid.classList.add("primary-field");
      }
      const urlInp = $("url");
      if (urlInp) {
        urlInp.placeholder = "https://x.com/elonmusk · example only";
        urlInp.readOnly = false;
        urlInp.disabled = false;
        urlInp.classList.toggle("primary-field", thready);
      }

      const idHint = $("idHint");
      if (idHint) {
        idHint.textContent = "핸들/회원 ID (예: elonmusk · example only)";
      }

      const banner = $("scopeBanner");
      if (banner) {
        let text = "";
        let kind = "info";
        if (thready) {
          if (url) {
            text =
              "이 글 · " +
              url.replace(/^https?:\/\/(www\.)?/i, "").slice(0, 72);
            kind = "thread";
          } else {
            text = "글 URL을 붙여넣으세요.";
            kind = "warn";
          }
        } else if (id) {
          text =
            "이 사람 · " +
            id +
            "";
          kind = "person";
        } else {
          text = "이 사람 · 핸들 입력";
          kind = "info";
        }
        banner.textContent = text;
        banner.dataset.kind = kind;
      }

      const btnT = $("btnGoTitle");
      const btnS = $("btnGoSub");
      if (btnT) {
        btnT.textContent = thready ? "① 이 글 분석 시작" : "① 이 사람 분석 시작";
      }
      if (btnS) {
        btnS.textContent = thready
          ? "게시글 URL 기준 · 끝나면 dossier"
          : "회원 ID 기준 4축 · 끝나면 dossier";
      }
    }

    function requireTarget() {
      rescueUrlFromIdBox();
      // ID box got a URL → already flipped to thread
      let mode = getSeg("mode");
      let id = currentId();
      let url = currentUrl();

      // Smart: empty id + URL pasted in url field while on member → thread
      if (mode !== "thread" && !id && url && isHttpUrl(url)) {
        setSeg("mode", "thread");
        const root = $("modeSeg");
        if (root) root.dataset.touched = "1";
        mode = "thread";
      }

      paintScope();
      mode = getSeg("mode");
      id = currentId();
      url = currentUrl();

      if (mode === "thread") {
        if (!url) {
          setStatus({ ok: false, text: "이 글: 게시글 URL을 붙여넣으세요" });
          if ($("url")) $("url").focus();
          return false;
        }
        if (!isHttpUrl(url)) {
          setStatus({ ok: false, text: "URL은 http:// 또는 https:// 로 시작" });
          if ($("url")) $("url").focus();
          return false;
        }
        return true;
      }

      if (!id) {
        setStatus({
          ok: false,
          text: "이 사람: 핸들/회원 ID (예: elonmusk · example only)",
        });
        if ($("authorId")) $("authorId").focus();
        return false;
      }
      // reject pure hangul nick in id box without id
      if (/^[가-힣\s]+$/.test(id)) {
        setStatus({
          ok: false,
          text: "닉네임이 아니라 회원 ID가 필요합니다. ID는 영문/숫자.",
        });
        if ($("authorId")) $("authorId").focus();
        return false;
      }
      return true;
    }

    function requireId() {
      // back-compat alias
      return requireTarget();
    }

  function filteredTargets() {
      const plat = siteId();
      const q = (($("targetFilter") && $("targetFilter").value) || "")
        .trim()
        .toLowerCase();
      let list = allTargets.slice();
      if (false) {
        const same = list.filter(
          (t) => t.platform === plat
        );
        if (same.length) list = same;
      } else {
        const same = list.filter((t) => t.platform === plat);
        list = same.length
          ? same.concat(list.filter((t) => t.platform !== plat))
          : list;
      }
      if (q)
        list = list.filter((t) =>
          (t.id + " " + (t.nick || "") + " " + t.label).toLowerCase().includes(q)
        );
      return list;
    }

  function fillTargets() {
    const box = $("targetList");
    if (!box) return;
    const list = filteredTargets();
    box.innerHTML = "";
    if (!list.length) {
      box.innerHTML =
        '<div style="padding:12px;color:var(--dim);font-size:11px">알려진 ID 없음 · 위에 직접 입력</div>';
      return;
    }
    list.forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className =
        "list-item" +
        (selectedListId === t.id || currentId() === t.id ? " active" : "");
      b.dataset.id = t.id;
      b.dataset.nick = t.nick || "";
      const left = document.createElement("div");
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = t.nick && t.nick !== t.id ? t.nick : t.id;
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent =
        t.nick && t.nick !== t.id ? t.id : t.label || t.id;
      left.appendChild(name);
      left.appendChild(meta);
      b.appendChild(left);
      if (t.source) {
        const src = document.createElement("span");
        src.className = "src";
        src.textContent = t.source;
        b.appendChild(src);
      }
      b.onclick = () => {
        selectedListId = t.id;
        if ($("authorId")) $("authorId").value = t.id;
        if (t.nick && $("nick")) $("nick").value = t.nick;
        setSeg("mode", "member");
        const root = $("modeSeg");
        if (root) root.dataset.touched = "1";
        fillTargets();
        paintScope();
        paintCtx();
        scheduleProbe();
        try {
          $("authorId") && $("authorId").focus();
        } catch (e) {}
      };
      box.appendChild(b);
    });
  }

  function collectLinks() {
    const rows = [];
    document.querySelectorAll("input[data-plat]").forEach((inp) => {
      const v = (inp.value || "").trim();
      if (!v) return;
      const plat = inp.getAttribute("data-plat");
      if (/^https?:\/\//i.test(v)) rows.push({ platform: plat, url: v });
      else rows.push({ platform: plat, handle: v });
    });
    return rows;
  }

  function getSeg(name) {
    const on = document.querySelector(
      '.seg[data-name="' + name + '"] button.on'
    );
    return on ? on.dataset.v : name === "mode" ? "member" : "quick";
  }

  function setSeg(name, value) {
    const root = document.querySelector('.seg[data-name="' + name + '"]');
    if (!root) return;
    root.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("on", b.dataset.v === value);
    });
  }

  function payload() {
      return {
        platform: siteId(),
        authorId: ($("authorId") && $("authorId").value) || "",
        nick: ($("nick") && $("nick").value) || "",
        url: ($("url") && $("url").value) || "",
        targetId: ($("authorId") && $("authorId").value) || "",
        targetNick: ($("nick") && $("nick").value) || "",
        mode: getSeg("mode"),
        depth: getSeg("depth"),
        note: ($("note") && $("note").value) || "",
        customUrl: ($("customUrl") && $("customUrl").value) || "",
        links: collectLinks(),
      };
    }

    function setPill(el, state, label) {
      if (!el) return;
      const term = el.getAttribute("data-term") || "";
      el.className =
        "pill term " +
        (state === true ? "on" : state === false ? "off" : "unk");
      if (term) el.setAttribute("data-term", term);
      const pretty =
        label === "analysis"
          ? "분석데이터"
          : label === "report"
            ? "보고서"
            : label;
      el.textContent =
        pretty + (state === true ? " 있음" : state === false ? " 없음" : " …");
      if (window.KampffGlossary && window.KampffGlossary.bindAll) {
        window.KampffGlossary.bindAll(el.parentElement || document);
      }
    }

  function paintCtx(d) {
      const id = currentId() || (d && d.activeId) || "";
      const url = currentUrl();
      const nick =
        (($("nick") && $("nick").value) || "").trim() ||
        (d && d.activeNick) ||
        "";
      const mode = getSeg("mode");
      const thready = mode === "thread" || (mode === "auto" && url && !id);
      let who = "—";
      if (thready && url) {
        who = "글 · " + url.replace(/^https?:\/\/(www\.)?/i, "").slice(0, 40);
      } else if (id) {
        who = nick && nick !== id ? nick + " · " + id : id;
      } else if (url) {
        who = "URL only";
      }
      if ($("ctxWho")) $("ctxWho").textContent = who;
      if (d && id && d.activeId === id) {
        setPill($("tagA"), d.activeHasAnalysis, "analysis");
        setPill($("tagR"), d.activeHasReport, "report");
      } else if (!id) {
        setPill($("tagA"), null, "analysis");
        setPill($("tagR"), null, "report");
      }
    }

  function scheduleProbe() {
    clearTimeout(probeTimer);
    const id = currentId();
    if (!id) {
      paintCtx();
      return;
    }
    setPill($("tagA"), null, "analysis");
    setPill($("tagR"), null, "report");
    probeTimer = setTimeout(() => {
      vscode.postMessage({ type: "probe", authorId: id });
    }, 220);
  }

  function paintProgress(p) {
    if (!p) return;
    const card = $("progressCard");
    const fill = $("pfill");
    const pct = $("pctLabel");
    const msg = $("progressMsg");
    const phaseEl = $("humanPhase");
    const who = $("progWho");
    const elapsed = $("progElapsed");
    const hint = $("progHint");
    const live = $("progLive");
    const phase = p.phase || "idle";

    function oneLine(s, max) {
      const t = String(s || "")
        .replace(/\s+/g, " ")
        .trim();
      if (!t) return "";
      return t.length > max ? t.slice(0, max - 1) + "…" : t;
    }

    if (card) {
      card.dataset.phase = phase;
      card.dataset.live = p.live ? "1" : "0";
    }

    // L1: phase · who · pct · elapsed  (single row, fixed)
    if (phaseEl) {
      phaseEl.textContent = oneLine(p.humanPhase || p.message || phase, 18);
    }
    if (who) {
      const id = p.targetId || "";
      const nick = p.nick || "";
      who.textContent = id
        ? nick && nick !== id
          ? oneLine(nick + " · " + id, 28)
          : oneLine(id, 28)
        : "—";
    }
    if (pct) pct.textContent = (p.pct != null ? p.pct : 0) + "%";
    if (elapsed) {
      const sec = p.elapsedSec != null ? Math.floor(p.elapsedSec) : 0;
      const m = Math.floor(sec / 60);
      const r = sec % 60;
      elapsed.textContent = m > 0 ? m + "m" + r + "s" : r + "s";
    }

    // L2: bar only
    if (fill) fill.style.width = (p.pct != null ? p.pct : 0) + "%";

    // L3: live activity + materials (multi-line when collecting)
    let l3 = "";
    if (phase === "idle") l3 = "ID 입력 후 ① 시작";
    else if (phase === "done") l3 = oneLine(p.message || "완료", 120);
    else if (phase === "error" || phase === "cancelled")
      l3 = oneLine(p.error || p.detail || p.message || phase, 160);
    else if (phase === "paused") l3 = oneLine(p.detail || "일시정지 · 다시 누르면 재개", 120);
    else {
      const act = p.activity || "";
      const det = String(p.detail || "").trim();
      if (act && det && det.indexOf(act) === 0) l3 = det;
      else if (act && det) l3 = act + "\n" + det;
      else l3 = act || det || p.message || "진행 중";
      // keep readable — hard cap chars not one-line collapse
      if (l3.length > 280) l3 = l3.slice(0, 279) + "…";
    }
    if (msg) {
      msg.textContent = l3 || "—";
      msg.title = [p.message, p.activity, p.detail, p.error].filter(Boolean).join("\n");
      if (phase !== "idle" && phase !== "done" && (p.activity || (p.materials && p.materials.length)))
        msg.classList.add("is-live-detail");
      else msg.classList.remove("is-live-detail");
    }
    if (hint) {
      hint.textContent = l3;
    }
    const mat = $("progMaterials");
    if (mat) {
      const list = Array.isArray(p.materials) ? p.materials.filter(Boolean) : [];
      if (list.length && phase !== "idle" && phase !== "done" && phase !== "error" && phase !== "cancelled") {
        mat.hidden = false;
        mat.replaceChildren();
        for (const row of list.slice(0, 8)) {
          const li = document.createElement("li");
          li.textContent = String(row);
          mat.appendChild(li);
        }
      } else {
        mat.hidden = true;
        mat.replaceChildren();
      }
    }

    if (live) {
      if (p.live || (phase !== "idle" && phase !== "done" && phase !== "error" && phase !== "cancelled"))
        live.removeAttribute("hidden");
      else live.setAttribute("hidden", "hidden");
    }

    // keep steps DOM empty/hidden (3-line window only)
    const list = $("steps");
    if (list) list.innerHTML = "";

    // hardBusy = engine actually owning the run (locks Go)
        // paused = freeze only; Go stays on so user can start a fresh job
        const hardBusy =
          phase === "running" ||
          phase === "analysis" ||
          phase === "render" ||
          phase === "queued";
        const showJobActions = hardBusy || phase === "paused";
        const b = $("btnGo");
        if (b) {
          b.disabled = !!hardBusy;
          if (
            phase === "idle" ||
            phase === "done" ||
            phase === "error" ||
            phase === "cancelled" ||
            phase === "paused"
          ) {
            b.disabled = false;
          }
        }
        // sticky only while hard-busy — paused sticky was covering Go
        if (card) card.classList.toggle("is-live", !!(hardBusy || (p.live && hardBusy)));

        const actions = $("progActions");
        const btnToggle = $("btnPauseToggle");
        const btnCancel = $("btnCancel");
        if (actions) {
          if (showJobActions) actions.removeAttribute("hidden");
          else actions.setAttribute("hidden", "hidden");
        }
        if (btnToggle) {
          const paused = phase === "paused";
          btnToggle.dataset.paused = paused ? "1" : "0";
          btnToggle.textContent = paused ? "재개" : "일시정지";
          btnToggle.title = paused ? "이어서 진행" : "프로세스 멈춤 (다시 누르면 재개)";
          if (showJobActions) btnToggle.removeAttribute("hidden");
          else btnToggle.setAttribute("hidden", "hidden");
        }
        if (btnCancel) {
          if (showJobActions) btnCancel.removeAttribute("hidden");
          else btnCancel.setAttribute("hidden", "hidden");
        }
      }

  function go() {
    if (!requireId()) return;
    const b = $("btnGo");
    if (b) b.disabled = true;
    setTimeout(() => {
      if ($("btnGo")) $("btnGo").disabled = false;
    }, 2500);

    setStatus({ ok: true, busy: true, text: "① 분석 시작… 확장으로 전송" });
    paintProgress({
      phase: "queued",
      pct: 5,
      live: true,
      humanPhase: "접수 중",
      message: "버튼을 눌렀어요. 확장에 전달 중…",
      targetId: currentId(),
      steps: [
        { id: "queue", label: "접수", state: "active" },
        { id: "run", label: "분석 엔진", state: "pending" },
        { id: "analysis", label: "dossier 데이터", state: "pending" },
        { id: "report", label: "HTML 보고서", state: "pending" },
        { id: "open", label: "열기", state: "pending" },
      ],
    });

    const pl = payload();
    try {
      vscode.postMessage(Object.assign({ type: "analyze" }, pl));
      vscode.postMessage({ type: "ping", t: Date.now(), id: currentId() });
    } catch (err) {
      setStatus({ ok: false, text: "전송 실패: " + err });
      vscode.postMessage({
        type: "clientError",
        text: String((err && err.message) || err),
      });
    }
  }

  function render() {
    if (!requireId()) return;
    setStatus({ ok: true, busy: true, text: "② HTML dossier…" });
    vscode.postMessage(Object.assign({ type: "renderReport" }, payload()));
  }
  function openThis() {
    if (!requireId()) return;
    vscode.postMessage(Object.assign({ type: "openThisReport" }, payload()));
  }
  function communityThis() {
    if (!requireId()) return;
    vscode.postMessage(Object.assign({ type: "communityThis" }, payload()));
  }

  function on(id, ev, fn) {
    const el = $(id);
    if (!el) {
      console.warn("[kampff] missing #" + id);
      return;
    }
    el[ev] = fn;
  }

  on("site", "onchange", onSiteChange);
    on("targetFilter", "oninput", fillTargets);
    on("authorId", "oninput", () => {
      if (rescueUrlFromIdBox()) {
        /* moved URL → thread */
      }
      selectedListId = currentId();
      paintScope();
      paintCtx();
      scheduleProbe();
    });
    on("nick", "oninput", () => {
      paintCtx();
      paintScope();
    });
    on("url", "oninput", () => {
      const u = currentUrl();
      // Paste post URL while on member → switch to "이 글만" unless user locked another mode? 
      // Auto-switch mode when URL looks like a post URL.
      if (u && isHttpUrl(u)) {
        const mode = getSeg("mode");
        if (mode === "member" || mode === "auto") {
          // If they also have an id, keep member and treat URL as trigger — don't steal.
          // If no id, flip to thread.
          if (!currentId()) {
            setSeg("mode", "thread");
            const root = $("modeSeg");
            if (root) root.dataset.touched = "1";
          }
        }
      }
      paintScope();
    });
    on("btnGo", "onclick", function (e) {
    try {
      if (e && e.preventDefault) e.preventDefault();
      go();
    } catch (err) {
      console.error(err);
      setStatus({ ok: false, text: "버튼 오류: " + err });
      vscode.postMessage({
        type: "clientError",
        text: String((err && err.message) || err),
      });
    }
  });
  on("btnRender", "onclick", render);
  on("btnOpenThis", "onclick", openThis);
  on("btnDesk", "onclick", () => {
    if (!requireId()) return;
    vscode.postMessage(Object.assign({ type: "openDesk" }, payload()));
  });
  on("btnGraph", "onclick", () => {
    vscode.postMessage(Object.assign({ type: "openGraph" }, payload()));
  });
  on("btnOpenQuickBrowser", "onclick", () => {
    if (!requireId()) return;
    vscode.postMessage(
      Object.assign({ type: "openThisReportBrowser", depth: "quick" }, payload())
    );
  });
  on("btnOpenFullBrowser", "onclick", () => {
    if (!requireId()) return;
    vscode.postMessage(
      Object.assign({ type: "openThisReportBrowser", depth: "full" }, payload())
    );
  });
  on("btnCPost", "onclick", communityThis);
  on("btnOutLatest", "onclick", () =>
    vscode.postMessage({ type: "openOutLatest" })
  );
  on("btnQueue", "onclick", () => vscode.postMessage({ type: "openQueue" }));
    on("btnSetup", "onclick", () => vscode.postMessage({ type: "openSetup" }));
  on("btnSites", "onclick", () => vscode.postMessage({ type: "manageSites" }));
    on("btnPauseToggle", "onclick", () => {
      const paused = $("btnPauseToggle") && $("btnPauseToggle").dataset.paused === "1";
      vscode.postMessage({ type: "togglePauseJob" });
      setStatus({ ok: true, text: paused ? "재개 요청…" : "일시정지 요청…" });
    });
    on("btnCancel", "onclick", () => {
      if (
        !window.confirm(
          "완전 종료할까요?\n수집/엔진을 kill 합니다. 재개 불가. raw는 남습니다.\n(잠깐 쉴 거면 일시정지를 쓰세요.)"
        )
      ) {
        return;
      }
      vscode.postMessage({ type: "cancelJob" });
      setStatus({ ok: true, text: "중단 요청…" });
    });
    on("btnRefresh", "onclick", () =>
    vscode.postMessage({ type: "refreshCatalog" })
  );
  on("btnSettings", "onclick", () =>
    vscode.postMessage({ type: "openSettings" })
  );

  document.querySelectorAll(".seg").forEach((root) => {
      root.querySelectorAll("button").forEach((b) => {
        b.onclick = () => {
          root.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
          b.classList.add("on");
          root.dataset.touched = "1";
          if (root.dataset.name === "mode" || root.id === "modeSeg") {
            paintScope();
            // focus the primary field for the chosen scope
            const mode = b.dataset.v;
            setTimeout(() => {
              try {
                if (mode === "thread" && $("url")) $("url").focus();
                else if ($("authorId")) $("authorId").focus();
              } catch (e) {}
            }, 10);
          }
        };
      });
    });

  if ($("launch")) {
    $("launch").onchange = () => {
      if (!applying)
        vscode.postMessage({
          type: "setConfig",
          key: "analyzeLaunch",
          value: $("launch").value,
        });
    };
  }

  if ($("authorId")) {
    $("authorId").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        go();
      }
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      go();
    }
  });

  window.addEventListener("message", (ev) => {
    const msg = ev.data || {};
    if (msg.type === "config") {
      applying = true;
      const d = msg.data || {};
      const keepId = ($("authorId") && $("authorId").value) || "";
      const keepNick = ($("nick") && $("nick").value) || "";
      const keepUrl = ($("url") && $("url").value) || "";
      const keepNote = ($("note") && $("note").value) || "";
      platforms =
        d.platforms && d.platforms.length ? d.platforms : platforms;
      allTargets = d.targets || [];
      fillSites(d.defaultPlatform || "x");
      if (d.defaultMode && $("modeSeg") && !$("modeSeg").dataset.touched) {
        const dm =
          d.defaultMode === "thread" ? "thread" : "member";
        setSeg("mode", dm);
      }
      if (d.defaultDepth && $("depthSeg") && !$("depthSeg").dataset.touched)
        setSeg("depth", d.defaultDepth);
      if (d.analyzeLaunch && $("launch")) $("launch").value = d.analyzeLaunch;
      if (keepId && $("authorId")) $("authorId").value = keepId;
      else if (d.activeId && $("authorId")) $("authorId").value = d.activeId;
      if (keepNick && $("nick")) $("nick").value = keepNick;
      else if (d.activeNick && $("nick")) $("nick").value = d.activeNick;
      if (keepUrl && $("url")) $("url").value = keepUrl;
      if (keepNote && $("note")) $("note").value = keepNote;
      selectedListId = currentId();
      fillTargets();
      const om = $("outMeta");
      if (om) {
        om.innerHTML = d.outLatestLabel
          ? "out mtime 최신: <b>" +
            escapeHtml(d.outLatestLabel) +
            "</b> · 폼 대상과 다를 수 있음"
          : "out 리포트 없음";
      }
      const st = $("status");
      if (st && !st.dataset.busy) {
        st.className = "";
        st.textContent = [
          d.dataRootOk ? "dataRoot OK" : "⚠ Setup으로 dataRoot 설정",
          d.dataRoot || "",
          d.wikiRootOk ? "wikiRoot OK" : "wikiRoot (없음 — 최종 저장/prior 병합 약함)",
          d.wikiRoot || "",
          d.peopleRoot ? "people: " + d.peopleRoot : "",
          "known: " + allTargets.length,
          d.activeLabel
            ? "마지막 작업: " + d.activeLabel
            : "마지막 작업: (없음)",
        ]
          .filter(Boolean)
          .join("\n");
      }
      paintCtx(d);
      scheduleProbe();
      applying = false;
      if (false && d.focusId && $("authorId")) {
        setTimeout(() => {
          try {
            $("authorId").focus();
          } catch (e) {}
        }, 30);
      }
    } else if (msg.type === "progress") {
      paintProgress(msg.data || {});
    } else if (msg.type === "status") {
      setStatus(msg.data || {});
    } else if (msg.type === "probeResult") {
      const d = msg.data || {};
      if (d.id && d.id === currentId()) {
        setPill($("tagA"), !!d.hasAnalysis, "analysis");
        setPill($("tagR"), !!d.hasReport, "report");
      }
    }
  });

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  fillSites("x");
      paintScope();
      paintProgress({
        phase: "idle",
        pct: 0,
        live: false,
        humanPhase: "준비",
        message: "대기 중",
        detail: "이 사람 전체=ID · 이 글만=URL 후 ①",
        steps: [
          { id: "queue", label: "접수", state: "pending" },
          { id: "run", label: "분석 엔진", state: "pending" },
          { id: "analysis", label: "dossier 데이터", state: "pending" },
          { id: "report", label: "HTML 보고서", state: "pending" },
          { id: "open", label: "열기", state: "pending" },
        ],
      });

    // Contextual glossary: dashed terms + guide list
    try {
      if (window.KampffGlossary) {
        window.KampffGlossary.renderGuideList(document.getElementById("glossList"));
        window.KampffGlossary.init({ root: document.body, autoMark: true });
        const g = document.getElementById("guideBox");
                if (g) {
                  try {
                    const saved = vscode.getState && vscode.getState();
                    if (saved && saved.guideOpen === false) g.open = false;
                  } catch (e) {}
                  g.addEventListener("toggle", () => {
                    try {
                      const prev = (vscode.getState && vscode.getState()) || {};
                      vscode.setState(Object.assign({}, prev, { guideOpen: g.open }));
                    } catch (e) {}
                  });
                }
      }
    } catch (e) {
      console.warn("[kampff] glossary init", e);
    }

    vscode.postMessage({ type: "ready" });
  })();
