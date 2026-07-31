from typing import Literal

import streamlit as st
from ollama import chat
from pydantic import BaseModel, Field


st.set_page_config(
    page_title="AI NPC 對話系統",
    page_icon="🧙",
)


class NPCDecision(BaseModel):
    """Qwen3 每輪對話必須回傳的決策格式。"""

    reply: str
    emotion: Literal["平靜", "開心", "好奇", "警戒", "生氣", "悲傷"]
    action: str
    relationship_change: int = Field(ge=-20, le=10)


EMOTION_ICONS = {
    "平靜": "😐",
    "開心": "😊",
    "好奇": "🤔",
    "警戒": "😠",
    "生氣": "😡",
    "悲傷": "😢",
}


def initialize_state():
    """只在第一次開啟頁面時建立遊戲狀態。"""

    defaults = {
        "messages": [],
        "emotion": "平靜 😐",
        "action": "觀察玩家",
        "ai_status": "規則模式",
        "connection_warning": False,
        "affinity": 0,
        "quest": "尚未解鎖",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def decide_state(player_text):
    """規則模式：根據關鍵詞決定 NPC 的情緒與行為。"""

    text = player_text.lower()

    if any(word in text for word in ["攻擊", "殺", "偷", "威脅", "摧毀"]):
        return "警戒 😠", "保護圖書館"

    if any(word in text for word in ["討厭", "騙子", "笨蛋", "滾開"]):
        return "生氣 😡", "拒絕與玩家合作"

    if any(word in text for word in ["謝謝", "感謝", "幫助", "thank"]):
        return "開心 😊", "主動協助玩家"

    if any(word in text for word in ["魔法書", "秘密", "線索", "寶藏"]):
        return "好奇 🤔", "搜尋圖書館紀錄"

    return "平靜 😐", "繼續觀察玩家"


def update_quest():
    """根據關係值更新任務或敵對事件。"""

    if st.session_state.affinity >= 60:
        st.session_state.quest = "盟友任務：封印魔法書"
    elif st.session_state.affinity >= 20:
        st.session_state.quest = "艾琳開始信任玩家"
    elif st.session_state.affinity <= -60:
        st.session_state.quest = "敵對事件：守護者追捕令"
    elif st.session_state.affinity <= -20:
        st.session_state.quest = "艾琳拒絕與玩家合作"
    else:
        st.session_state.quest = "尚未解鎖"


def update_affinity_by_rules(player_text):
    """規則模式：根據玩家言行更新 -100～100 的關係值。"""

    text = player_text.lower()

    if any(word in text for word in ["攻擊", "殺", "偷", "威脅", "摧毀"]):
        change = -20
    elif any(word in text for word in ["討厭", "騙子", "笨蛋", "滾開"]):
        change = -10
    elif any(word in text for word in ["道歉", "對不起", "原諒"]):
        change = 5
    elif any(word in text for word in ["謝謝", "感謝", "相信", "幫助"]):
        change = 10
    elif any(word in text for word in ["魔法書", "秘密", "線索"]):
        change = 3
    else:
        change = 1

    st.session_state.affinity = max(
        -100,
        min(100, st.session_state.affinity + change),
    )
    update_quest()


def create_rule_reply(player_text):
    """本機 AI 未啟用或無法連線時的備援回覆。"""

    if st.session_state.emotion.startswith("開心"):
        return "你的善意讓我很高興。告訴我吧，你需要什麼協助？"

    if st.session_state.emotion.startswith("好奇"):
        return "這件事引起了我的興趣。我會替你搜尋圖書館的古老紀錄。"

    if st.session_state.emotion.startswith(("警戒", "生氣")):
        return "請立刻停止。身為守護者，我不會允許你危害這座圖書館。"

    return f"我聽見你說「{player_text}」。請繼續說下去。"


def apply_rule_decision(player_text):
    """執行規則式情緒、行為、關係與回覆判斷。"""

    emotion, action = decide_state(player_text)
    st.session_state.emotion = emotion
    st.session_state.action = action
    update_affinity_by_rules(player_text)
    return create_rule_reply(player_text)


def create_ai_decision(player_message):
    """要求 Qwen3 同時產生台詞、情緒、行為與關係變化。"""

    system_prompt = f"""
你是奇幻王城圖書館的守護者艾琳。

角色設定：
- 個性冷靜、謹慎、富有好奇心
- 使命是保護圖書館，並協助可信任的訪客
- 目前情緒：{st.session_state.emotion}
- 目前行為：{st.session_state.action}
- 與玩家的關係值：{st.session_state.affinity}，範圍是 -100 到 100
- 目前事件：{st.session_state.quest}

本輪玩家的最新訊息：
<latest_player_message>
{player_message}
</latest_player_message>

決策規則：
- 必須主要判斷 latest_player_message 的完整語意
- 舊對話只能作為背景，不可取代最新訊息
- 真誠友善、協助或道歉，可以增加 1 到 10
- 普通中立對話可以改變 0 到 2
- 嘲諷、辱罵、欺騙或無禮，應降低 5 到 15
- 偷竊、攻擊、殺害或威脅，應降低 15 到 20
- 帶有禮貌詞的諷刺或辱罵仍是負面行為
- 真誠道歉可以小幅修復關係，但不會立刻消除全部仇恨
- 玩家態度改變時，情緒與行為也必須合理改變
- 不可重複先前使用過的完整回覆

回覆規則：
- 永遠使用繁體中文
- 保持艾琳的角色身分，不要說自己是 AI
- 根據目前關係、情緒與行為回覆
- 每次回答二到四句
- 不要顯示思考過程
"""

    history_messages = st.session_state.messages[:-1][-6:]
    model_messages = [{"role": "system", "content": system_prompt}]
    model_messages.extend(history_messages)
    model_messages.append({"role": "user", "content": player_message})

    response = chat(
        model="qwen3:8b",
        messages=model_messages,
        think=False,
        format=NPCDecision.model_json_schema(),
        options={
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_predict": 220,
        },
    )

    return NPCDecision.model_validate_json(response.message.content)


initialize_state()

st.title("🧙 AI NPC 對話系統")
st.caption("具備角色設定、短期記憶、情緒、關係與行為決策的 MVP")

with st.sidebar:
    st.header("角色設定")
    st.write("名字：艾琳")
    st.write("身分：王城圖書館守護者")
    st.write("個性：冷靜、謹慎、富有好奇心")

    st.divider()

    use_local_ai = st.toggle(
        "啟用本機 Qwen3 AI",
        value=False,
        help="只在已安裝 Ollama 的本機電腦啟用。",
    )

    if use_local_ai:
        st.caption("🟢 本機 AI 模式")
    else:
        st.caption("🟡 規則模式")

    if st.session_state.connection_warning:
        st.warning("AI 決策失敗，這一輪已自動使用規則模式。")

    st.divider()

    st.subheader("即時狀態")
    st.write(f"目前情緒：{st.session_state.emotion}")
    st.write(f"目前行為：{st.session_state.action}")
    st.write(f"回覆來源：{st.session_state.ai_status}")

    st.divider()
    st.subheader("關係與任務")

    if st.session_state.affinity >= 60:
        relationship = "盟友 🤝"
    elif st.session_state.affinity >= 20:
        relationship = "友善 🙂"
    elif st.session_state.affinity <= -60:
        relationship = "仇敵 💀"
    elif st.session_state.affinity <= -20:
        relationship = "敵視 😡"
    else:
        relationship = "中立 😐"

    st.write(f"關係狀態：{relationship}")
    st.write(f"關係值：{st.session_state.affinity}")

    progress_value = int((st.session_state.affinity + 100) / 2)
    st.progress(progress_value)
    st.write(f"事件狀態：{st.session_state.quest}")

    if st.button("清除對話並重置"):
        st.session_state.messages = []
        st.session_state.emotion = "平靜 😐"
        st.session_state.action = "觀察玩家"
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False
        st.session_state.affinity = 0
        st.session_state.quest = "尚未解鎖"
        st.rerun()

st.subheader("與艾琳交談")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

player_message = st.chat_input("輸入你想對艾琳說的話")

if player_message:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": player_message,
        }
    )

    if use_local_ai:
        try:
            with st.spinner("艾琳正在判斷你的意圖……"):
                decision = create_ai_decision(player_message)

            npc_reply = decision.reply
            st.session_state.emotion = (
                f"{decision.emotion} {EMOTION_ICONS[decision.emotion]}"
            )
            st.session_state.action = decision.action
            st.session_state.affinity = max(
                -100,
                min(
                    100,
                    st.session_state.affinity + decision.relationship_change,
                ),
            )
            update_quest()
            st.session_state.ai_status = "Qwen3 8B（AI 決策）"
            st.session_state.connection_warning = False
        except Exception:
            npc_reply = apply_rule_decision(player_message)
            st.session_state.ai_status = "規則模式（自動備援）"
            st.session_state.connection_warning = True
    else:
        npc_reply = apply_rule_decision(player_message)
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": npc_reply,
        }
    )
    st.rerun()
