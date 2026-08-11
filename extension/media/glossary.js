/* Kampff term glossary — hover / focus / click tooltips */
(function (global) {
  /** @type {Record<string, { title: string, body: string, also?: string }>} */
  const TERMS = {
    dossier: {
      title: "dossier (도씨에)",
      body: "한 사람에 대해 모아 둔 종합 분석 묶음입니다. 글·댓글·프로필·거리 판단이 한 리포트로 정리됩니다.",
      also: "한글로는 ‘인물 분석 묶음’ 정도로 읽으면 됩니다.",
    },
    analysis: {
      title: "analysis (분석 데이터)",
      body: "엔진이 남긴 원본 결과 파일(analysis.json)입니다. 기계가 읽기 좋은 JSON이고, HTML 보고서의 재료입니다.",
    },
    report: {
      title: "report (보고서)",
      body: "사람이 읽도록 만든 HTML 결과물(…-report.html)입니다. 사이드바 Reports에서 엽니다.",
    },
    distance: {
      title: "distance (거리)",
      body: "나와 그 사람 사이의 관계·태도 거리 요약입니다. align/near(가깝다) · neutral · caution/watch · hostile/far 같은 라벨이 붙습니다. 절대 진리가 아니라 분석 가설입니다.",
    },
    confidence: {
      title: "confidence (확신도)",
      body: "그 판단이 얼마나 단단한지 표시합니다. 데이터가 얇으면 낮게 나옵니다.",
    },
    accumulate: {
      title: "accumulate / people",
      body: "같은 사람을 여러 번 분석할 때 메모·이력을 people/{사이트}/{id} 아래에 쌓는 단계입니다. People 뷰가 그 폴더를 보여 줍니다.",
    },
    people: {
      title: "People",
      body: "사람별 누적 폴더 트리입니다. NOTES, 프로필, 과거 분석 흔적이 여기에 모입니다.",
    },
    queue: {
      title: "queue (큐)",
      body: "‘이 사람 분석’을 눌렀을 때 생기는 작업 요청 파일 모음입니다. 실행기가 이 파일을 보고 분석을 돌립니다.",
    },
    hermes: {
      title: "Hermes",
      body: "분석을 실제로 수행하는 AI 에이전트 CLI입니다. analyzeLaunch가 auto/hermes면 확장이 Hermes를 띄워 돌립니다.",
    },
    dataroot: {
      title: "dataRoot (runtime)",
      body: "임시·작업용 KAMPFF_DATA입니다. inbox / queue / out 만 둡니다. Obsidian vault가 아닙니다. Setup에서 지정합니다.",
    },
    wikiroot: {
      title: "wikiRoot (LLM Wiki)",
      body: "오래 남길 결과 선반입니다. people/ 와 reports/ 가 여기 생깁니다. 재분석 때 이전 자료를 여기서 읽어 합칩니다. 끝나면 out 결과를 여기로 복사합니다.",
    },
    inbox: {
      title: "Inbox",
      body: "수집 원본 번들이 들어오는 곳입니다. 아직 보고서로 안 만든 재료에 가깝습니다.",
    },
    raw: {
      title: "Raw",
      body: "사이트에서 긁어 온 원시 수집 트리입니다. 디버깅·재분석용입니다.",
    },
    out: {
      title: "out",
      body: "런타임 작업 출력(HTML/JSON). 잡이 끝나면 wiki reports/ 로도 복사됩니다. Reports 뷰는 out + wiki를 같이 봅니다.",
    },
    member: {
      title: "이 사람 전체 (member)",
      body: "author id만 넣습니다. 글 URL 필요 없음. 게시글·댓글·공감글·공감댓글 네 축으로 ‘한 사람’을 봅니다.",
    },
    thread: {
      title: "이 글만 (thread)",
      body: "게시·프로필 URL 하나. 예: https://x.com/elonmusk (example only · 공개 프로필 형식). 그 대상만 봅니다.",
    },
    profile: {
      title: "프로필 (profile)",
      body: "프로필 페이지 정보 위주로 보는 모드입니다. 활동 로그가 적을 때 씁니다.",
    },
    depth: {
      title: "깊이 (depth)",
      body: "얼마나 깊게 모을지입니다. 빠른(quick)=가볍게, FULL=더 많이 수집(시간↑).",
    },
    quick: {
      title: "빠른 (quick)",
      body: "짧은 수집·요약. 먼저 감을 볼 때 씁니다.",
    },
    full: {
      title: "FULL",
      body: "가능한 한 넓게 모읍니다. 시간·토큰이 더 듭니다.",
    },
    authorid: {
      title: "author id / 대상 ID",
      body: "사이트 핸들/회원 id. X 예: elonmusk (example only — 결과 샘플 아님). ‘이 사람’이면 ID만. 특정 글은 ‘이 글’+URL. 모든 사이트에 rate limit 있음.",
    },
    nick: {
      title: "닉네임",
      body: "화면에 보이는 이름입니다. ID와 다를 수 있어 라벨용으로 같이 적습니다.",
    },
    launch: {
      title: "실행기 (launch)",
      body: "큐 파일을 만든 뒤 무엇을 할지입니다. auto/hermes=자동 실행, none=파일만, terminal=안내만.",
    },
    mtime: {
      title: "mtime",
      body: "파일이 마지막으로 바뀐 시각입니다. ‘out 최신’은 이 시각 기준이라, 지금 폼에 적은 사람과 다를 수 있습니다.",
    },
    clinical: {
      title: "clinical_psych",
      body: "임상심리 렌즈로 읽기 요청입니다. 진단·의료 판정이 아닙니다. 설정에서 끌 수 있습니다.",
    },
    authorship: {
      title: "authorship_integrity",
      body: "계정 매매·대필·조직형 활동 같은 ‘이 글이 그 사람 맞나’ 쪽 신호입니다. 확정이 아니라 가설입니다.",
    },
    setup: {
      title: "Setup",
      body: "dataRoot(런타임)·wikiRoot(LLM Wiki)·skillsDevRoot 경로를 잡는 마법사입니다. 빨간 경고가 뜨면 여기를 먼저 하세요.",
    },
    platform: {
      title: "사이트 / 플랫폼",
      body: "분석 대상 사이트. 기본 시드 X. 추가 등록 가능. X 포함 모든 곳이 rate-limit 합니다.",
    },
    tldr: {
      title: "TL;DR",
      body: "Too Long; Didn't Read — 한 줄·짧은 요약입니다.",
    },
    communitypost: {
      title: "게시글 초안",
      body: "분석이 끝난 뒤, 커뮤니티에 올릴 글을 골라 만드는 선택 기능입니다. 분석 본체와 별개입니다.",
    },
    skillsdev: {
      title: "skillsDevRoot",
      body: "harvest/render 스크립트가 있는 kampff-skills-dev 루트입니다.",
    },
  };

  const ALIASES = {
    "도씨에": "dossier",
    "인물 분석": "dossier",
    "분석 데이터": "analysis",
    analysisjson: "analysis",
    "analysis.json": "analysis",
    보고서: "report",
    "report.html": "report",
    거리: "distance",
    확신도: "confidence",
    큐: "queue",
    접수: "queue",
    people: "people",
    누적: "accumulate",
    accumulate_person: "accumulate",
    dataRoot: "dataroot",
    dataroot: "dataroot",
    "data root": "dataroot",
    wikiRoot: "wikiroot",
    wikiroot: "wikiroot",
    "wiki root": "wikiroot",
    "llm wiki": "wikiroot",
    Inbox: "inbox",
    Raw: "raw",
    out: "out",
    "회원 전반": "member",
    "이 사람 전체": "member",
    member: "member",
    "글·스레드": "thread",
    "이 글만": "thread",
    thread: "thread",
    프로필: "profile",
    profile: "profile",
    깊이: "depth",
    depth: "depth",
    빠른: "quick",
    quick: "quick",
    FULL: "full",
    full: "full",
    "author id": "authorid",
    authorid: "authorid",
    "대상 ID": "authorid",
    닉네임: "nick",
    nick: "nick",
    실행기: "launch",
    launch: "launch",
    analyzeLaunch: "launch",
    mtime: "mtime",
    clinical_psych: "clinical",
    authorship_integrity: "authorship",
    Setup: "setup",
    setup: "setup",
    플랫폼: "platform",
    Site: "platform",
    Hermes: "hermes",
    hermes: "hermes",
    "TL;DR": "tldr",
    tldr: "tldr",
    "게시글 초안": "communitypost",
    "게시 초안": "communitypost",
    skillsDevRoot: "skillsdev",
  };

  function resolveKey(raw) {
    if (!raw) return "";
    const s = String(raw).trim();
    if (TERMS[s]) return s;
    if (ALIASES[s]) return ALIASES[s];
    const low = s.toLowerCase();
    if (TERMS[low]) return low;
    if (ALIASES[low]) return ALIASES[low];
    return "";
  }

  function getTerm(raw) {
    const k = resolveKey(raw);
    return k ? TERMS[k] : null;
  }

  function allTerms() {
    return Object.keys(TERMS).map((k) => ({ id: k, ...TERMS[k] }));
  }

  function ensureTipEl() {
    let el = document.getElementById("kampff-tip");
    if (el) return el;
    el = document.createElement("div");
    el.id = "kampff-tip";
    el.className = "tip-pop";
    el.setAttribute("role", "tooltip");
    el.hidden = true;
    el.innerHTML =
      '<div class="tip-title"></div><div class="tip-body"></div><div class="tip-also"></div>';
    document.body.appendChild(el);
    return el;
  }

  let hideTimer = 0;
  let pinned = false;

  function hideTip(force) {
    if (pinned && !force) return;
    const el = document.getElementById("kampff-tip");
    if (el) {
      el.hidden = true;
      el.classList.remove("show");
    }
    pinned = false;
  }

  function placeTip(el, anchor) {
    const r = anchor.getBoundingClientRect();
    const tw = el.offsetWidth || 240;
    const th = el.offsetHeight || 80;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(8, Math.min(left, vw - tw - 8));
    let top = r.bottom + 8;
    if (top + th > vh - 8 && r.top > th + 12) {
      top = r.top - th - 8;
      el.dataset.place = "above";
    } else {
      el.dataset.place = "below";
    }
    el.style.left = left + "px";
    el.style.top = top + "px";
  }

  function showTip(anchor, termKey, opts) {
    const term = getTerm(termKey || anchor.getAttribute("data-term"));
    if (!term) return;
    clearTimeout(hideTimer);
    const el = ensureTipEl();
    el.querySelector(".tip-title").textContent = term.title;
    el.querySelector(".tip-body").textContent = term.body;
    const also = el.querySelector(".tip-also");
    if (term.also) {
      also.hidden = false;
      also.textContent = term.also;
    } else {
      also.hidden = true;
      also.textContent = "";
    }
    el.hidden = false;
    el.classList.add("show");
    pinned = !!(opts && opts.pin);
    // measure then place
    placeTip(el, anchor);
    requestAnimationFrame(() => placeTip(el, anchor));
  }

  function bindAnchor(node) {
    if (!node || node._kampffTipBound) return;
    node._kampffTipBound = true;
    if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "0");
    if (!node.getAttribute("aria-label") && node.getAttribute("data-term")) {
      const t = getTerm(node.getAttribute("data-term"));
      if (t) node.setAttribute("aria-label", t.title + " 설명");
    }
    node.addEventListener("mouseenter", () => showTip(node));
    node.addEventListener("mouseleave", () => {
      hideTimer = setTimeout(() => hideTip(false), 120);
    });
    node.addEventListener("focus", () => showTip(node));
    node.addEventListener("blur", () => hideTip(true));
    node.addEventListener("click", (e) => {
      // Don't steal clicks from real actions (seg / primary buttons).
      if (
        node.matches("button.btn, .seg button") ||
        node.closest(".seg button")
      ) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      const el = document.getElementById("kampff-tip");
      if (el && !el.hidden && pinned) hideTip(true);
      else showTip(node, null, { pin: true });
    });
  }

  /** Wrap plain-text matches inside a root (skips .term / script / style / input). */
  function autoMark(root, extraKeys) {
    const keys = (extraKeys || Object.keys(TERMS).concat(Object.keys(ALIASES)))
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    if (!keys.length) return;
    const re = new RegExp(
      "(" +
        keys
          .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
          .join("|") +
        ")",
      "g"
    );

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        const p = n.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        const tag = p.tagName;
        if (
          tag === "SCRIPT" ||
          tag === "STYLE" ||
          tag === "TEXTAREA" ||
          tag === "INPUT" ||
          tag === "OPTION" ||
          tag === "CODE" ||
          tag === "KBD"
        )
          return NodeFilter.FILTER_REJECT;
        if (p.closest(".term, .tip-pop, .no-term, #kampff-tip, .list"))
          return NodeFilter.FILTER_REJECT;
        if (!re.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        re.lastIndex = 0;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((textNode) => {
      const text = textNode.nodeValue;
      re.lastIndex = 0;
      if (!re.test(text)) return;
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0;
      let m;
      while ((m = re.exec(text))) {
        if (m.index > last) {
          frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        }
        const key = resolveKey(m[0]);
        if (key) {
          const span = document.createElement("span");
          span.className = "term";
          span.setAttribute("data-term", key);
          span.textContent = m[0];
          frag.appendChild(span);
        } else {
          frag.appendChild(document.createTextNode(m[0]));
        }
        last = m.index + m[0].length;
      }
      if (last < text.length) {
        frag.appendChild(document.createTextNode(text.slice(last)));
      }
      textNode.parentNode.replaceChild(frag, textNode);
    });
  }

  function bindAll(root) {
    (root || document)
      .querySelectorAll(".term[data-term], [data-term].term, [data-tip]")
      .forEach((el) => {
        if (el.hasAttribute("data-tip") && !el.hasAttribute("data-term")) {
          el.setAttribute("data-term", el.getAttribute("data-tip"));
          el.classList.add("term");
        }
        bindAnchor(el);
      });
  }

  function init(opts) {
    const root = (opts && opts.root) || document.body;
    if (opts && opts.autoMark !== false) autoMark(root);
    bindAll(root);
    ensureTipEl();
    document.addEventListener("click", (e) => {
      if (e.target && e.target.closest && e.target.closest(".term, #kampff-tip"))
        return;
      hideTip(true);
    });
    window.addEventListener(
      "scroll",
      () => {
        if (!pinned) hideTip(true);
      },
      true
    );
  }

  function renderGuideList(container) {
    if (!container) return;
    container.innerHTML = "";
    allTerms()
      .sort((a, b) => a.title.localeCompare(b.title, "ko"))
      .forEach((t) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "gloss-row";
        row.innerHTML =
          '<span class="gloss-k"></span><span class="gloss-v"></span>';
        row.querySelector(".gloss-k").textContent = t.title;
        row.querySelector(".gloss-v").textContent = t.body;
        row.addEventListener("click", () => {
          showTip(row, t.id, { pin: true });
        });
        container.appendChild(row);
      });
  }

  global.KampffGlossary = {
    TERMS,
    getTerm,
    allTerms,
    init,
    bindAll,
    autoMark,
    showTip,
    hideTip,
    renderGuideList,
  };
})(window);
