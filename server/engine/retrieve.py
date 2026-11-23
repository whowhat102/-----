"""轻量中文检索：字符二元组 + 实义词命中率。

MVP 不引入向量库：把查询切成二元组（过滤寒暄虚词），
统计每个二元组是否出现在目标文本中，命中率即相似度。
对短知识条目和纠错问题的召回足够用，后续可平滑升级 embedding。
"""
import re
import sqlite3
from typing import Dict, List

# 寒暄/虚词二元组：命中它们不算相似度（避免"你们家"导致误匹配）
STOP_GRAMS = {
    "你们", "们家", "我家", "请问", "一下", "这个", "那个", "怎么", "么个",
    "什么", "多少", "是不是", "有没有", "可以", "能不", "不能", "还是",
    "或者", "们店", "店里", "他们", "我们", "咱们", "就是", "真的",
    "你好", "您好", "谢谢", "麻烦", "帮忙", "想问", "咨询",
}

# 领域话题词：查询里出现这些词时，启用"话题词命中"通道，
# 避免口语噪音字组稀释相似度（客服场景的主题词是有限集合）
TOPIC_WORDS = [
    "多少钱", "价格", "价位", "贵", "便宜", "优惠", "折扣", "打折", "活动",
    "代理", "批发", "合作", "团购", "加盟", "一件代发", "贴牌", "拿货", "分销", "利润", "门槛",
    "发货", "物流", "快递", "包邮", "运费",
    "退换", "退货", "退款", "售后", "保修", "维修", "质量问题",
    "材质", "工艺", "皮革", "植鞣", "五金", "缝线",
    "定制", "刻字", "礼盒", "贺卡",
    "保养", "貂油", "防水", "淋雨", "包浆",
    "地址", "门店", "体验", "预约", "会员",
]


def _grams(text: str) -> set:
    text = text.lower()
    grams = set()
    # 中文按相邻两字切分
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cjk) - 1):
        grams.add(cjk[i] + cjk[i + 1])
    # 英文/数字按词
    grams.update(re.findall(r"[a-z0-9]+", text))
    return grams


def similarity(query: str, target: str) -> float:
    """实义二元组命中率：query 的实义 gram 中有多少出现在 target 里。"""
    q = {g for g in _grams(query) if g not in STOP_GRAMS}
    if not q:
        return 0.0
    hit = sum(1 for g in q if g in target)
    return hit / len(q)


def topic_similarity(query: str, target: str) -> float:
    """话题词命中率：query 中出现的话题词有多少出现在 target 里。

    与 similarity 取 max 使用——口语里"我想做你们的代理怎么个合作法"
    字组噪音多，但话题词 [代理, 合作] 一击即中。
    """
    present = [w for w in TOPIC_WORDS if w in query]
    if not present:
        return 0.0
    hit = sum(1 for w in present if w in target)
    return hit / len(present)


def retrieve_knowledge(conn: sqlite3.Connection, query: str, k: int = 3,
                       min_score: float = 0.12) -> List[Dict]:
    """按 标题+标签(权重 0.6) / 正文(权重 0.4) 打分，话题词通道取最大，返回前 k 条。"""
    hits = []
    for row in conn.execute("SELECT * FROM knowledge"):
        tags = " ".join(_parse_json(row["tags"]))
        category = row["category"] if "category" in row.keys() else ""
        head_target = f"{row['title']} {tags} {category}"
        head = similarity(query, head_target)
        body = similarity(query, row["content"])
        topic = max(topic_similarity(query, head_target),
                    topic_similarity(query, row["content"]))
        score = max(head * 0.6 + body * 0.4, topic)
        if score >= min_score:
            hits.append({"id": row["id"], "title": row["title"],
                         "content": row["content"], "tags": _parse_json(row["tags"]),
                         "score": round(score, 3)})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


def match_corrections(conn: sqlite3.Connection, query: str, k: int = 2,
                      min_score: float = 0.15) -> List[Dict]:
    """匹配历史纠错记录，作为 few-shot 示例注入提示词。"""
    hits = []
    for row in conn.execute("SELECT * FROM corrections WHERE active = 1"):
        score = similarity(query, row["question"])
        if score >= min_score:
            hits.append({"id": row["id"], "question": row["question"],
                         "bad_reply": row["bad_reply"],
                         "corrected_reply": row["corrected_reply"],
                         "score": round(score, 3)})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


def _parse_json(raw: str) -> list:
    try:
        import json
        return json.loads(raw) if raw else []
    except Exception:
        return []
