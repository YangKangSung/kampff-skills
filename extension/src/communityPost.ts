/**
 * Optional community *draft* export — NOT the person dossier.
 * Tone SoT: vault Agents/Kampff/community-post-tone.md
 * Never invent generic market/semiconductor filler when seed is empty.
 * Write like a human peer (ksyang): 합니다/봅니다, no AI meta, no ops tags.
 */

export type CommunityTone = "peer" | "short" | "board";

export interface CommunityPostSeed {
  nick?: string;
  id?: string;
  platform?: string;
  board?: string;
  tldr?: string;
  one_line?: string;
  trigger?: string;
  recommendation?: string;
  point?: string;
  claim?: string;
  mechanism?: string;
  anchor?: string;
  quotes?: string[];
  /** Full board-ready body */
  preset?: string;
  /** Optional short body for tone=short */
  preset_short?: string;
  tone?: string;
}

const OPS =
  /\b(caution|avoid|engage|ops|ROI|distance|worldview|alliance|stability|drift|risk|L[1-5]|MBTI|ACH|CIA|SAT|Big ?Five|clinical|diagnosis|doxx?|CONFIRMED|PROBABLE|SPECULATIVE)\b/gi;

const AI_META =
  /(이 한 줄은|전반 분석|독시어|dossier 요약|게시용으로 다듬|다음과 같습니다|나아가|결론적으로|요약하자면|정리하면 다음과|AI가|언어모델)/gi;

export function normalizeTone(t?: string): CommunityTone {
  const v = String(t || "peer")
    .trim()
    .toLowerCase();
  if (v === "short" || v === "s" || v === "brief" || v === "댓글") return "short";
  if (v === "board" || v === "b" || v === "full" || v === "modeb" || v === "본문")
    return "board";
  return "peer";
}

export function looksLikeTagSalad(s: string): boolean {
  const t = (s || "").trim();
  if (!t || t.length < 8) return true;
  const hasStop = /[.。?!]|다\.|요\.|임\.|음\.|습니다|거든요|봅니다/.test(t);
  const parts = t.split(/[\s·|/,:;]+/).filter(Boolean);
  if (!hasStop && parts.length >= 3 && parts.every((p) => p.length <= 12)) return true;
  if (/\b(park|kin|use|cm_stock|hongbo)\b/i.test(t) && !hasStop) return true;
  if (
    /(공유형|논객형|생활형|문제해결형|열기\s*중간|공손\s*톤|뉴스공유)/.test(t) &&
    !hasStop
  ) {
    return true;
  }
  return false;
}

function cleanOps(s: string): string {
  return (s || "")
    .replace(OPS, "")
    .replace(AI_META, "")
    .replace(
      /(표본|수집분?|분석\s*결과|리포트|dossier|권고\s*태그|matrix|honesty|bundle|harvest)/gi,
      ""
    )
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** Strip AI/ops leftovers from a full preset while keeping voice. */
function humanizePreset(s: string): string {
  let t = (s || "").trim();
  if (!t) return "";
  t = t
    .replace(AI_META, "")
    .replace(
      /^>\s*.+$/gm,
      ""
    ) // markdown callouts
    .replace(
      /^(#+\s*|##\s*본문.*|##\s*짧은.*|##\s*법적.*).*$/gm,
      ""
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  // drop leading ops tables if whole draft is multi-section md
  if (/^#\s/.test(t) || /\n##\s/.test(t)) {
    const m = t.match(/##\s*본문[^\n]*\n([\s\S]*?)(?=\n##\s|$)/);
    if (m && m[1].trim().length >= 40) t = m[1].trim();
  }
  return t.trim();
}

export function distillPoint(seed: CommunityPostSeed): string {
  const candidates = [
    seed.point,
    seed.mechanism,
    seed.claim,
    seed.one_line,
    seed.tldr,
    seed.trigger,
  ]
    .map((s) => cleanOps(s || ""))
    .filter(Boolean);

  for (const raw of candidates) {
    if (looksLikeTagSalad(raw)) continue;
    const parts = raw
      .split(/(?<=[.。?!]|다\.|요\.|습니다\.|거든요\.)\s+/)
      .map((x) => x.replace(/^[\s,.:;·/-]+|[\s,.:;·/-]+$/g, "").trim())
      .filter(Boolean);
    const tryList = parts.length ? parts : [raw];
    for (let t of tryList) {
      if (looksLikeTagSalad(t)) continue;
      if (t.length > 110) t = t.slice(0, 108).replace(/\s+\S*$/, "") + "…";
      if (t.length >= 16) return t;
    }
  }
  return "";
}

const REFUSE =
  "[게시 초안 생성 불가]\n" +
  "이 버튼은 회원 전반 분석(dossier)이 아닙니다.\n" +
  "analysis에 쓸 만한 문장(seed)이 없어 일반 템플릿으로 채우지 않습니다.\n" +
  "→ 위 리포트 TL;DR · L1–L5 · Distance · Evidence 가 본 분석입니다.\n" +
  "→ 게시 초안이 필요하면 analysis.community_post 에 문장을 넣거나, dossier를 보고 직접 쓰세요.";

function endHuman(s: string): string {
  s = String(s || "").trim();
  if (!s) return s;
  if (/[다요임]$|[.。]$|습니다$|거든요$|봅니다$|생각합니다$/.test(s)) return s;
  return `${s}.`;
}

function whoLabel(seed: CommunityPostSeed): string {
  const nick = (seed.nick || "").trim();
  const id = (seed.id || "").trim();
  if (nick && id && nick !== id) return `${nick}(id ${id})`;
  return nick || id || "";
}

function peerBody(
  mech: string,
  claim: string,
  anchor: string,
  point: string,
  seed: CommunityPostSeed
): string {
  const who = whoLabel(seed);
  const nickOnly = (seed.nick || "").trim() || who.split("(")[0];
  let m = endHuman(mech);
  if (who && nickOnly && !m.includes(nickOnly)) {
    m = `${who} 님 쪽 공개 글을 기준으로만 보면, ${m}`;
  }

  const c = stripQuotes(claim || point);
  const mid = c
    ? `그래서 ${c}만 보고 단정까지는 잘 안 갑니다.`
    : "그래서 겉으로 보이는 빈도만 보고 단정까지는 잘 안 갑니다.";

  let a: string;
  if (anchor) {
    const tail = /쪽|근거|원문|분포|공시|실적|가격/.test(anchor) ? "" : " 쪽";
    a = `판단은 ${anchor}${tail}에 두는 편이 낫다고 봅니다.`;
  } else {
    a = "판단은 확인 가능한 원문·날짜 쪽에 두는 편이 낫다고 봅니다.";
  }

  return [m, "", mid, a, "전제 다른 부분 있으면 그 부분만 짚어 주시면 됩니다."].join(
    "\n"
  );
}

function shortBody(
  mech: string,
  claim: string,
  anchor: string,
  point: string
): string {
  const line1 = endHuman(mech || point);
  const c = stripQuotes(claim || point);
  const line2 = c
    ? `그래서 ${c}만 보고 단정까지는 잘 안 갑니다.`
    : "단정까지는 잘 안 갑니다.";
  const line3 = anchor
    ? `판단은 ${anchor}${/쪽|근거|원문/.test(anchor) ? "" : " 쪽"}에 두는 편이 낫다고 봅니다.`
    : "판단은 확인 가능한 근거 쪽에 두는 편이 낫다고 봅니다.";
  return [line1, line2, line3].filter(Boolean).join("\n");
}

/**
 * Optional export only. Empty/weak seed → refuse (no fake analysis tone).
 * @param toneOverride UI select; else seed.tone; else peer
 */
export function generateCommunityPost(
  seed: CommunityPostSeed,
  toneOverride?: string
): string {
  const tone = normalizeTone(toneOverride || seed.tone);

  const fullPreset = humanizePreset(seed.preset || "");
  const shortPreset = humanizePreset(seed.preset_short || "");

  // board: prefer full preset as-is (already human draft)
  if (tone === "board") {
    if (
      fullPreset &&
      fullPreset.length >= 24 &&
      fullPreset.length <= 8000 &&
      !looksLikeTagSalad(fullPreset)
    ) {
      return fullPreset;
    }
    // fall through to build from parts
  }

  if (tone === "short" && shortPreset && shortPreset.length >= 16) {
    return shortPreset;
  }

  // peer/short: long preset OK if human and not salad (mode B seed)
  if (
    fullPreset &&
    fullPreset.length >= 24 &&
    fullPreset.length <= 8000 &&
    !looksLikeTagSalad(fullPreset)
  ) {
    if (tone === "short") {
      // first 2 paragraphs
      const paras = fullPreset.split(/\n\s*\n/).filter((p) => p.trim());
      if (paras.length >= 2) return paras.slice(0, 2).join("\n\n");
      const lines = fullPreset.split(/\n/).filter((l) => l.trim());
      return lines.slice(0, 3).join("\n");
    }
    return fullPreset;
  }

  const mech = cleanOps(seed.mechanism || "");
  const claim = cleanOps(seed.claim || "");
  const anchor = cleanOps(seed.anchor || "");
  const point = distillPoint(seed);

  if (mech && (claim || point)) {
    return tone === "short"
      ? shortBody(mech, claim, anchor, point)
      : peerBody(mech, claim, anchor, point, seed);
  }

  if (point && !looksLikeTagSalad(point)) {
    // weak seed: still human, no "this is a draft meta"
    if (tone === "short") {
      return [
        endHuman(point),
        "판단은 확인 가능한 근거 쪽에 두는 편이 낫다고 봅니다.",
      ].join("\n");
    }
    return peerBody(point, "", anchor, point, seed);
  }

  return REFUSE;
}

function stripQuotes(s: string): string {
  return s.replace(/^["'「『]|["'」』]$/g, "").trim();
}
