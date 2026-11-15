"""SQLite 数据库：建表、种子数据、请求级连接。

数据文件落在 <项目根>/data/chatbot.db，首次启动自动建表并灌入演示数据
（"拾光皮具工作室"完整示例：1 个人设、12 条知识、10 条话术、4 场景、4 人群）。
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chatbot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    identity TEXT DEFAULT '',
    greeting TEXT DEFAULT '',
    catchphrases TEXT DEFAULT '[]',
    emoji_style TEXT DEFAULT 'light',        -- none / light / rich
    colloquial INTEGER DEFAULT 60,           -- 口语化 0-100
    warmth INTEGER DEFAULT 70,               -- 热情度 0-100
    formality INTEGER DEFAULT 30,            -- 正式度 0-100
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,                     -- 开场/引导/报价/促成/收尾
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    strategy TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tone_guide TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT '新会话',
    persona_id INTEGER REFERENCES personas(id),
    scenario_id INTEGER REFERENCES scenarios(id),
    audience_id INTEGER REFERENCES audiences(id),
    needs_human INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                      -- user / bot
    content TEXT NOT NULL,
    rating INTEGER DEFAULT 0,                -- 0 未评 / 1 好 / -1 差
    meta TEXT DEFAULT '{}',                  -- 引擎、命中知识等元信息
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    bad_reply TEXT DEFAULT '',
    corrected_reply TEXT NOT NULL,
    session_id INTEGER,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mode TEXT DEFAULT 'mock',                -- mock / llm
    api_base_url TEXT DEFAULT 'https://api.openai.com/v1',
    api_key TEXT DEFAULT '',
    api_model TEXT DEFAULT 'gpt-4o-mini',
    api_temperature REAL DEFAULT 0.7,
    disclose_bot INTEGER DEFAULT 0,          -- 合规：是否声明机器人身份
    product_name TEXT DEFAULT '灵犀客服'
);
"""

# ---------------------------------------------------------------- 演示种子数据
SEED_PERSONA = (
    "小雅",
    "拾光皮具工作室的客服小妹，96 年，做了三年手工皮具客服，对每款产品都特别熟",
    "哈喽~我是拾光的小雅😊 想看看哪款呀？",
    json.dumps(["哈喽", "讲真", "跟你讲"], ensure_ascii=False),
    "light", 75, 80, 25, 1,
)

SEED_KNOWLEDGE = [
    ("品牌介绍", "「拾光皮具」是 2018 年成立的手工皮具工作室，主打意大利植鞣革，全部手工裁切缝制，不做机器流水线货。", ["品牌"]),
    ("主要产品", "目前在售：卡包、短款钱包、长款钱包、皮带、手拿包、手机腰包，共 6 个品类 30 多个款式，大部分支持免费刻字。", ["产品"]),
    ("价格区间", "卡包 168-228，短款钱包 288-368，长款钱包 398-568，皮带 258-338，手拿包 498-698，手机腰包 228-298。", ["价格", "产品"]),
    ("定制服务", "免费刻字（姓名缩写/纪念日），图案定制加 50-100，定制款周期 5-7 个工作日，改款不支持退换会提前说明。", ["定制", "价格"]),
    ("材质工艺", "意大利进口植鞣革 + 法国手缝蜡线，saddle stitch 骑马钉缝线，五金是纯铜镀厚金，用久了会氧化成复古色。", ["工艺"]),
    ("发货说明", "现货 48 小时内顺丰包邮发出，定制款 5-7 个工作日，偏远地区补运费差价，可以指定发货时间。", ["物流"]),
    ("售后政策", "7 天无理由退换（不影响二次销售），一年内免费保修（断线、五金问题），终身付费保养翻新，默认送运费险。", ["售后"]),
    ("合作：一件代发", "代理门槛低：一件代发代理价 7 折，累计满 3000 元升级银牌代理 65 折，满 1 万升级金牌代理 6 折，提供素材图和详情页。", ["合作", "价格"]),
    ("合作：批发", "批发 10 件起，批发价 6 折可混款；支持贴牌定制，MOQ 50 件，打样费 300（下单可抵）。", ["合作", "价格"]),
    ("合作：社群团购", "团长价 65 折，单场满 20 单额外返 5%，提供团购素材包、开团话术和发货售后一条龙。", ["合作"]),
    ("保养知识", "植鞣革忌水忌暴晒，淋雨马上用干布吸干阴干；每月薄涂一次貂油，用两年会自然包浆变色，越用越好看。", ["保养"]),
    ("礼盒服务", "精美礼盒 +20 元，附手写贺卡；情人节/母亲节节日款要提前 10 天预订，刻字节日款提前 7 天。", ["礼盒"]),
]

SEED_SCRIPTS = [
    ("开场", "默认开场", "哈喽~我是拾光皮具的小雅😊 想看看哪款呀？"),
    ("开场", "活动开场", "你好呀~最近工作室周年庆，部分款有活动价，想了解哪类呀？"),
    ("引导", "用途引导", "你平时是自用还是送人呀？送人的话我帮你选包装好看点的~"),
    ("引导", "预算引导", "大概预算在什么区间呀？我帮你圈两款最值的~"),
    ("报价", "标准报价", "{产品名}现在是{价格}，顺丰包邮，送运费险哈~"),
    ("报价", "活动报价", "{产品名}现在是活动价{价格}，这两天下单还送一块护理蜡，很实用的~"),
    ("促成", "库存促成", "这款库存不多了，喜欢的话建议先拍，不合适 7 天无理由退，没风险的~"),
    ("促成", "优先发货", "今天下单我帮你备注优先发货，明天就能寄出~"),
    ("收尾", "友好收尾", "有任何问题随时找我哈，我一般都在~😊"),
    ("收尾", "收货回访", "收到货记得跟我说下感受哦，不合适随时退换，别客气~"),
]

SEED_SCENARIOS = [
    ("售前咨询", "客户咨询产品、价格、材质",
     "先弄清自用还是送礼、预算多少，再推 1-2 款最匹配的；报价时主动带出赠品或活动；回复保持 1-3 句聊天风格，不刷屏。"),
    ("合作洽谈", "想做代理、批发、团购的商务来询",
     "先感谢对方认可，问清合作类型和预计体量，按知识库政策对应档位介绍；涉及独家、大额、合同条款时收集联系方式并标记转人工。"),
    ("议价周旋", "客户砍价、比价",
     "不轻易降价：先用赠品、包邮、活动价回应；订单量大可引导到代理价思路；对方仍坚持就说明手工成本摆在那，可标记转人工申请特殊价。"),
    ("售后处理", "退换、维修、质量问题",
     "先道歉安抚、问清具体问题；小问题（线头、五金松动）指导处理或补发配件；退换按政策走；涉及赔偿或对方情绪激动必须转人工。"),
]

SEED_AUDIENCES = [
    ("个人消费者", "自用或送朋友的散客",
     "轻松口语像朋友聊天，偶尔一个表情，推荐时多讲质感、使用场景和性价比。"),
    ("企业采购", "公司礼品、员工福利采购",
     "相对正式、条理清晰，主动提供发票、对公转账、批量报价，回复可稍长但不啰嗦。"),
    ("批发商/代理", "有渠道想拿货压价的商家",
     "直接务实少用表情，重点讲政策档位、利润空间和支持素材，数字说清楚。"),
    ("年轻学生党", "预算有限的年轻人",
     "活泼一点可以带点网络用语（不过度），重点讲性价比、颜值和平价款。"),
]

SEED_CORRECTIONS = [
    ("你们家钱包防水吗",
     "亲，我们的产品采用优质皮革材料，具有良好的防水性能，请放心购买哦。",
     "说实话哈，植鞣革最怕水😅 淋到要马上用干布擦干阴干，不然会留水印。日常背完全没事，就是别淋大雨~"),
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI 依赖：每请求一个连接，用完即关。"""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def get_settings(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO settings (id) VALUES (1)")
        conn.commit()
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return row


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT 1 FROM settings LIMIT 1").fetchone() is None:
            reseed(conn)
    finally:
        conn.close()


def reseed(conn: sqlite3.Connection) -> None:
    """清空业务数据并重灌演示种子（首次初始化与 /api/dev/reset 共用）。"""
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM corrections")
    conn.execute("DELETE FROM scripts")
    conn.execute("DELETE FROM knowledge")
    conn.execute("DELETE FROM scenarios")
    conn.execute("DELETE FROM audiences")
    conn.execute("DELETE FROM personas")
    conn.execute(
        "INSERT OR REPLACE INTO settings (id, mode, api_base_url, api_key, api_model,"
        " api_temperature, disclose_bot, product_name)"
        " VALUES (1, 'mock', 'https://api.openai.com/v1', '', 'gpt-4o-mini',"
        " 0.7, 0, '灵犀客服')"
    )
    conn.execute(
        "INSERT INTO personas (name, identity, greeting, catchphrases,"
        " emoji_style, colloquial, warmth, formality, is_default)"
        " VALUES (?,?,?,?,?,?,?,?,?)", SEED_PERSONA)
    for title, content, tags in SEED_KNOWLEDGE:
        conn.execute("INSERT INTO knowledge (title, content, tags) VALUES (?,?,?)",
                     (title, content, json.dumps(tags, ensure_ascii=False)))
    for stage, name, content in SEED_SCRIPTS:
        conn.execute("INSERT INTO scripts (stage, name, content) VALUES (?,?,?)",
                     (stage, name, content))
    for name, desc, strategy in SEED_SCENARIOS:
        conn.execute("INSERT INTO scenarios (name, description, strategy) VALUES (?,?,?)",
                     (name, desc, strategy))
    for name, desc, tone in SEED_AUDIENCES:
        conn.execute("INSERT INTO audiences (name, description, tone_guide) VALUES (?,?,?)",
                     (name, desc, tone))
    for q, bad, good in SEED_CORRECTIONS:
        conn.execute("INSERT INTO corrections (question, bad_reply, corrected_reply, active)"
                     " VALUES (?,?,?,1)", (q, bad, good))
    conn.commit()
