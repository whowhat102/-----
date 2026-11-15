"""规则模拟引擎（无需 API Key 的演示模式）。

定位：跑通产品全流程的演示引擎——关键词/二元组匹配知识库 →
按人设风格改写 → 按场景补跟进话术；无匹配或命中敏感词时礼貌收集联系方式并转人工。
真实回复质量请到「设置」切换为真实大模型模式。
"""
import json
import random
import re
import sqlite3
from typing import Dict, List, Optional, Tuple

from .retrieve import match_corrections, retrieve_knowledge

GREET_WORDS = ("你好", "您好", "在吗", "在不在", "哈喽", "嗨", "hi", "hello",
               "早上好", "下午好", "晚上好")
PRICE_WORDS = ("多少钱", "价格", "价位", "贵", "便宜", "优惠", "折扣", "打折", "活动", "低价")
COOP_WORDS = ("代理", "批发", "合作", "团购", "加盟", "一件代发", "贴牌", "拿货", "分销")
HUMAN_WORDS = ("投诉", "赔偿", "举报", "12315", "工商", "律师", "独家", "合同",
               "退款不", "骗子", "假货")

EMOJI_POOL = ["😊", "😄", "✨", "👍", "🥰", "😅"]

FOLLOWUPS = {
    "售前": ["你平时自用还是送人呀？我帮你看看哪款合适~",
             "预算大概多少呀？我推荐几款性价比高的给你~",
             "想要哪类的呀？钱包还是卡包？我发你细节图~"],
    "合作": ["你大概想做哪种体量呀？我把对应档位的政策发你~",
             "方便说下你那边的渠道吗？我看看帮你申请哪个档位~",
             "你倾向一件代发还是批量拿货呀？政策不一样的~"],
    "议价": ["价格真是成本价了哈，不过今天下单我送你块护理蜡，很实用的~",
             "这样，我帮你申请顺丰包邮加免费刻字，这个真挺有诚意了😊",
             "手工的东西成本摆在那哈，不过送你个礼盒包装，送人特有面子~"],
    "售后": ["不好意思哈，你先别急，具体什么问题拍个照给我看下？",
             "抱歉抱歉，我马上帮你处理！是线头还是五金的问题呀？",
             "给你添麻烦了🙏 你先说说具体情况，我记下来今天给你方案~"],
}
GENERIC_FOLLOWUP = ["还有什么想了解的呀~", "你还有哪款想看下细节的吗~"]


def _pick(pool: List[str]) -> str:
    return random.choice(pool)


def _followup(scenario_name: str) -> str:
    for key, pool in FOLLOWUPS.items():
        if key in scenario_name:
            return _pick(pool)
    return _pick(GENERIC_FOLLOWUP)


def _shorten(text: str, limit: int = 88) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "；", "，"):
        idx = cut.rfind(sep)
        if idx > limit // 2:
            return cut[:idx + 1] + "剩下的细节你要哪款我发你哈~"
    return cut + "…剩下的你要哪款我发你细节~"


def stylize(text: str, persona: Optional[sqlite3.Row],
            first_reply: bool = False, disclose: bool = False) -> str:
    """按人设三滑杆 + 表情风格给回复加'人味儿'。"""
    text = str(text).strip()
    if not text:
        return text
    # 知识句常以句号结尾，聊天里去掉更自然，避免"298。喽"这种拼接
    while text.endswith(("。", ".",)):
        text = text[:-1].rstrip()
    if not text:
        return text
    head = ""
    if first_reply and disclose:
        head = "（先说下哈，我是店里的智能小助手~）"

    if persona is None:
        return f"{head}{text}"

    col, form = persona["colloquial"], persona["formality"]
    casual = col >= 55 and form < 60

    prefix = ""
    if casual and random.random() < 0.35:
        catchphrases = json.loads(persona["catchphrases"] or "[]")
        if catchphrases:
            prefix = _pick(catchphrases) + "，"

    tail = ""
    # 文本已以语气词/波浪号收尾时就不再追加，避免"哈~呀~"叠加
    if casual and random.random() < 0.5 and not re.search(r"[~～哈呀喽哦啦嗯]$", text):
        tail += _pick(["~", "哈", "呀", "喽"])
        if tail != "~":
            tail += "~"

    emoji = persona["emoji_style"]
    if emoji == "rich":
        tail += _pick(EMOJI_POOL) + (_pick(EMOJI_POOL) if random.random() < 0.4 else "")
    elif emoji == "light" and random.random() < 0.55:
        tail += _pick(EMOJI_POOL)

    return f"{head}{prefix}{text}{tail}"


def mock_reply(conn: sqlite3.Connection,
               persona: Optional[sqlite3.Row],
               scenario: Optional[sqlite3.Row],
               bot_count: int,
               user_msg: str,
               disclose: bool) -> Tuple[str, List[str], bool, bool]:
    """返回 (回复文本, 命中知识标题, 恒为False[转人工走文本标记], 是否用了纠错答案)。"""
    scen_name = scenario["name"] if scenario else ""

    # 1) 敏感/超纲词 → 安抚 + 收集联系方式 + 转人工（统一用文本标记，由路由解析）
    if any(w in user_msg for w in HUMAN_WORDS):
        text = stylize("这个我必须认真帮你处理，你留个微信或电话，我马上让负责人直接联系你",
                       persona, first_reply=(bot_count == 0), disclose=disclose)
        return text + "\n[转人工]", [], False, False

    # 2) 纠错记录强匹配 → 直接采用标准答案（体现"训练有效"）
    corr = match_corrections(conn, user_msg, k=1)
    if corr:
        return stylize(corr[0]["corrected_reply"], persona,
                       first_reply=(bot_count == 0), disclose=disclose), [], False, True

    # 3) 首条且是打招呼 → 开场（人设问候语优先，其次开场话术）
    if bot_count == 0 and any(w in user_msg.lower() for w in GREET_WORDS):
        if persona and persona["greeting"]:
            text = persona["greeting"]
        else:
            row = conn.execute("SELECT content FROM scripts WHERE stage='开场'").fetchone()
            text = row["content"] if row else "哈喽~有什么想了解的呀？"
        if disclose:
            text = "（先说下哈，我是店里的智能小助手~）" + text
        return text, [], False, False

    # 4) 知识检索：合作/价格类问题给查询词加权，命中对应标签条目
    query = user_msg
    if any(w in user_msg for w in COOP_WORDS):
        query += " 合作 代理 批发 政策 折扣 团购"
    elif any(w in user_msg for w in PRICE_WORDS):
        query += " 价格 多少钱 优惠 区间"
    hits = retrieve_knowledge(conn, query)

    if hits:
        best = hits[0]
        answer = _shorten(best["content"])
        reply = stylize(answer, persona, first_reply=(bot_count == 0), disclose=disclose)
        # 议价场景不再追问价格，直接给"周旋"话术
        followup = "" if ("议价" in scen_name and any(w in user_msg for w in PRICE_WORDS)) \
            else " " + _followup(scen_name)
        return reply + followup, [h["title"] for h in hits], False, False

    # 5) 无匹配 → 礼貌收集联系方式 + 转人工
    text = stylize("这个我帮你问下具体的哈，你留个微信，我问清楚了马上找你",
                   persona, first_reply=(bot_count == 0), disclose=disclose)
    return text + "\n[转人工]", [], False, False
