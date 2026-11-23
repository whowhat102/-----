# -*- coding: utf-8 -*-
"""小熙客服 API 冒烟测试：覆盖六大模块核心链路。"""
import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

B = "http://127.0.0.1:8000"
passed, failed = 0, 0


def call(method, path, body=None):
    req = urllib.request.Request(B + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data) as r:
        return json.loads(r.read().decode("utf-8"))


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name} {extra}")
    else:
        failed += 1
        print(f"  FAIL  {name} {extra}")


print("== 重置演示数据 ==")
check("重置成功", call("POST", "/api/dev/reset")["ok"] is True)

print("== 对话链路（售前·个人消费者）==")
persons = call("GET", "/api/personas")
scen = call("GET", "/api/scenarios")
auds = call("GET", "/api/audiences")
pid, sid, aid = persons[0]["id"], scen[0]["id"], auds[0]["id"]
s = call("POST", "/api/sessions",
         {"persona_id": pid, "scenario_id": sid, "audience_id": aid})
check("建会话", s["id"] > 0 and "售前" in s["title"], s["title"])

r1 = call("POST", "/api/chat", {"session_id": s["id"], "message": "你好，在吗"})
check("打招呼→开场问候", "小雅" in r1["reply"] or "哈喽" in r1["reply"], repr(r1["reply"][:40]))

r2 = call("POST", "/api/chat", {"session_id": s["id"], "message": "你们家卡包多少钱呀"})
check("问价→命中价格知识", "168" in r2["reply"] and any("价格" in t for t in r2["matched_knowledge"]),
      f"命中={r2['matched_knowledge']}")

r3 = call("POST", "/api/chat", {"session_id": s["id"], "message": "钱包防水吗 会不会淋雨"})
check("防水→命中纠错答案", r3["engine"] == "mock" and ("怕水" in r3["reply"] or "水印" in r3["reply"]),
      repr(r3["reply"][:40]))

r4 = call("POST", "/api/chat", {"session_id": s["id"], "message": "我要投诉你们！假货！"})
check("投诉→转人工标记", r4["needs_human"] is True and "[转人工]" not in r4["reply"],
      repr(r4["reply"][:36]))

msgs = call("GET", f"/api/sessions/{s['id']}/messages")
check("消息持久化", len(msgs) == 8 and msgs[-1]["role"] == "bot")

print("== 评分与训练中心 ==")
bad_id = [m for m in msgs if m["role"] == "bot"][1]["id"]
call("POST", "/api/feedback",
     {"message_id": bad_id, "rating": -1, "correction": "亲，咱们卡包 168 起，看你想要长款还是短款哈~"})
corr = call("GET", "/api/corrections")
check("纠错入库", any("卡包 168 起" in c["corrected_reply"] for c in corr), f"共{len(corr)}条")
r5 = call("POST", "/api/chat", {"session_id": s["id"], "message": "卡包大概啥价位"})
check("相似问题→用上纠错答案", "168" in r5["reply"], repr(r5["reply"][:40]))

print("== 合作场景（标签加权检索）==")
s2 = call("POST", "/api/sessions",
          {"persona_id": pid, "scenario_id": scen[1]["id"], "audience_id": auds[2]["id"]})
r6 = call("POST", "/api/chat", {"session_id": s2["id"], "message": "我想做你们的代理，怎么个合作法"})
check("代理咨询→合作政策", any("合作" in t or "代理" in t for t in r6["matched_knowledge"]),
      f"命中={r6['matched_knowledge']}")
check("合作话术含折扣", "折" in r6["reply"], repr(r6["reply"][:60]))

print("== 知识库 CRUD + 批量导入 ==")
k = call("POST", "/api/knowledge", {"title": "门店地址", "content": "工作室在杭州西湖区转塘街道 88 号，可预约到店体验。", "tags": ["门店"]})
call("PUT", f"/api/knowledge/{k['id']}", {"title": "门店地址", "content": "工作室在杭州西湖区转塘街道 88 号，周末可预约到店体验。", "tags": ["门店", "体验"]})
imp = call("POST", "/api/knowledge/import", {"text": "会员制度 | 满 500 自动成为银卡会员，享 95 折 | 会员\n刻字示例 | 常见刻姓名缩写如 ZY、生日如 0521 | 定制"})
check("新增+修改+导入", imp["imported"] == 2 and imp["failed"] == 0)
r7 = call("POST", "/api/chat", {"session_id": s["id"], "message": "你们门店在哪 能来体验吗"})
check("新知识即时生效", "转塘" in r7["reply"], repr(r7["reply"][:36]))

print("== 人设/话术/场景/人群 CRUD ==")
p = call("POST", "/api/personas", {"name": "阿凯", "identity": "拾光的男客服，懂皮具工艺", "greeting": "你好，我是阿凯", "catchphrases": ["兄弟"], "emoji_style": "none", "colloquial": 80, "warmth": 60, "formality": 20, "is_default": 0})
check("建人设", p["name"] == "阿凯")
sc = call("POST", "/api/scripts", {"stage": "报价", "name": "分期话术", "content": "{产品名}可以分期哈，3 期免手续费~"})
check("建话术", sc["id"] > 0)
scn = call("POST", "/api/scenarios", {"name": "老客复购", "description": "买过的客户回来", "strategy": "认出老客，主动提会员折扣和新品。"})
aud = call("POST", "/api/audiences", {"name": "中年商务人士", "description": "40+ 注重品质", "tone_guide": "稳重克制，重点讲工艺和耐用。"})
check("建场景/人群", scn["id"] > 0 and aud["id"] > 0)
for e in [(f"/api/personas/{p['id']}",), (f"/api/scripts/{sc['id']}",), (f"/api/scenarios/{scn['id']}",), (f"/api/audiences/{aud['id']}",), (f"/api/knowledge/{k['id']}",), (f"/api/sessions/{s2['id']}",)]:
    call("DELETE", e[0])
check("清理测试数据", True)

print("== 设置 ==")
st = call("GET", "/api/settings")
check("默认模拟模式", st["mode"] == "mock")
t = call("POST", "/api/settings/test", {"mode": "llm", "api_base_url": "https://api.openai.com/v1", "api_key": "", "api_model": "gpt-4o-mini", "api_temperature": 0.7, "disclose_bot": 0, "product_name": "小熙客服"})
check("空Key测试连接→友好报错", t["ok"] is False and "Key" in t["message"], t["message"][:30])
st2 = call("PUT", "/api/settings", {"mode": "mock", "api_base_url": "https://api.openai.com/v1", "api_key": "", "api_model": "gpt-4o-mini", "api_temperature": 0.7, "disclose_bot": 1, "product_name": "小熙客服"})
check("合规开关可保存", st2["disclose_bot"] == 1)
call("PUT", "/api/settings", {"mode": "mock", "api_base_url": "https://api.openai.com/v1", "api_key": "", "api_model": "gpt-4o-mini", "api_temperature": 0.7, "disclose_bot": 0, "product_name": "小熙客服"})

print(f"\n结果：{passed} 通过 / {failed} 失败")
exit(1 if failed else 0)
