"""系统提示词组装 —— 本产品的核心竞争力所在。

把 人设风格 + 场景策略 + 人群语气 + 检索知识 + 阶段话术 + 纠错示例 + 铁律
拼装成一份让大模型"像真人客服"的系统提示词。
"""
import json
import sqlite3
from typing import Dict, List, Optional

from .retrieve import match_corrections, retrieve_knowledge

CLOSING_WORDS = ("谢谢", "感谢", "再见", "拜拜", "不用了", "下次再", "已拍", "已下单")


def stage_for(bot_count: int, user_msg: str, hits: List[Dict]) -> str:
    """根据对话进度与命中内容，判断当前应参考哪个阶段的话术。"""
    if any(w in user_msg for w in CLOSING_WORDS):
        return "收尾"
    if bot_count == 0:
        return "开场"
    if hits and any(t in ("价格", "合作") for h in hits for t in h["tags"]):
        return "报价"
    if bot_count >= 4:
        return "促成"
    return "引导"


def _style_directives(p: sqlite3.Row) -> List[str]:
    col, warm, form = p["colloquial"], p["warmth"], p["formality"]
    d = []
    if col >= 85:
        d.append("说话非常口语化，像微信打字：短句、有省略、偶尔带点小俏皮")
    elif col >= 55:
        d.append("口语化聊天，短句为主，自然不书面")
    else:
        d.append("用词平实自然，可以略微书面，但不要播音腔")
    if warm >= 80:
        d.append("语气热情，会主动关心对方需求，但不油腻不谄媚")
    elif warm >= 50:
        d.append("语气友好，适度热情")
    else:
        d.append("语气平和简洁，公事公办但不冷冰冰")
    if form >= 60:
        d.append("用词偏正式、克制，少用语气词和表情")
    elif form <= 30:
        d.append("随意自然，像熟人在聊，可以用语气词（哈/呀/~）")
    else:
        d.append("正式度适中，专业但不说教")
    emoji = p["emoji_style"]
    if emoji == "rich":
        d.append("可以适度用表情符号，每条消息最多 2 个")
    elif emoji == "light":
        d.append("偶尔用 1 个表情（如 😊），每条最多 1 个，别刷屏")
    else:
        d.append("不用任何表情符号")
    catchphrases = json.loads(p["catchphrases"] or "[]")
    if catchphrases:
        d.append("你的口头禅/常用词：「" + "」「".join(catchphrases) + "」，偶尔自然带出，别每句都用")
    return d


def _identity_rule(disclose: bool) -> str:
    if disclose:
        return ("合规模式已开启：在第一条回复里用一句自然的话说明你是智能助手"
                "（例如'先说下哈，我是店里的智能小助手'），说明一次即可，之后正常聊天，不要反复提")
    return ("你就是一名真人客服，绝不暴露或暗示自己是 AI、机器人、程序或大模型，"
            "回复里不能出现'作为AI''我是机器人''我是语言模型'之类的字样")


def build_system_prompt(conn: sqlite3.Connection,
                        persona: Optional[sqlite3.Row],
                        scenario: Optional[sqlite3.Row],
                        audience: Optional[sqlite3.Row],
                        user_msg: str,
                        bot_count: int,
                        disclose: bool) -> Dict:
    """返回 {prompt, hits, corrections}，hits/corrections 供消息元信息展示。"""
    p_name = persona["name"] if persona else "客服"
    p_identity = persona["identity"] if persona else "线上客服"

    hits = retrieve_knowledge(conn, user_msg)
    corrections = match_corrections(conn, user_msg)
    stage = stage_for(bot_count, user_msg, hits)

    lines = []
    a_name = audience["name"] if audience else "来访者"
    a_desc = audience["description"] if audience else ""
    s_name = scenario["name"] if scenario else "在线咨询"
    lines.append(f"你是{p_name}，{p_identity}。你正在线上接待一位{a_name}"
                 f"（{a_desc}），当前场景是「{s_name}」。像真人一样回复对方的消息。")

    if persona:
        lines.append("\n【你的说话风格】")
        lines += [f"- {x}" for x in _style_directives(persona)]

    if scenario and scenario["strategy"]:
        lines.append(f"\n【场景应对策略】\n{scenario['strategy']}")

    if audience and audience["tone_guide"]:
        lines.append(f"\n【对这类人怎么说话】\n{audience['tone_guide']}")

    if hits:
        lines.append("\n【业务知识】（产品信息只依据这里，没有的不编造）")
        for i, h in enumerate(hits, 1):
            lines.append(f"{i}. {h['title']}：{h['content']}")

    scripts = conn.execute("SELECT * FROM scripts WHERE stage = ?", (stage,)).fetchall()
    if scripts:
        lines.append(f"\n【话术参考·{stage}】（学语气和结构，别逐字照搬）")
        for s in scripts:
            lines.append(f"· {s['name']}：{s['content']}")

    if corrections:
        lines.append("\n【过往纠错示例】（类似问题按这个标准来答）")
        for c in corrections:
            lines.append(f"问：{c['question']}")
            if c["bad_reply"]:
                lines.append(f"（之前这样答被批评了，别再这样：{c['bad_reply']}）")
            lines.append(f"标准答案：{c['corrected_reply']}")

    lines.append(f"""
【必须遵守的铁律】
1. {_identity_rule(disclose)}
2. 杜绝机器腔：不说"亲，很高兴为您服务""您的问题已收到""感谢您的咨询"这类模板客服话术；不排比、不堆砌形容词、不动不动列 1234。
3. 每次回复像聊天软件打字：一般 1~3 句，短句为主，可以有口语化省略。
4. 产品信息只能依据上面的【业务知识】，知识里没有的不编造；不确定就坦诚说"帮你确认一下"。
5. 遇到以下任一情况——知识库里没有的问题、售后纠纷或赔偿、大额/独家/合同类合作条款、对方情绪激动或投诉倾向——先礼貌安抚并要对方联系方式（微信/电话），然后在这条回复的最后单独一行输出标记：[转人工]
6. 用第一人称"我"说话，别自称"本店""客服系统"。""")

    return {"prompt": "\n".join(lines), "hits": hits, "corrections": corrections, "stage": stage}
