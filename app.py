import streamlit as st
from ollama import chat

st.set_page_config(
    page_title="AI NPC 對話系統",
    page_icon="🧙",
)

# 建立 NPC 的初始狀態
if "messages" not in st.session_state:
    st.session_state.messages = []

if "emotion" not in st.session_state:
    st.session_state.emotion = "平靜 😐"

if "action" not in st.session_state:
    st.session_state.action = "觀察玩家"

if "ai_status" not in st.session_state:
    st.session_state.ai_status = "規則模式"

if "connection_warning" not in st.session_state:
    st.session_state.connection_warning = False


def decide_state(player_text):
    """根據玩家輸入，決定 NPC 的情緒與行為。"""

    text = player_text.lower()

    if any(word in text for word in ["謝謝", "感謝", "幫助", "thank"]):
        return "開心 😊", "主動協助玩家"

    if any(word in text for word in ["魔法書", "秘密", "線索", "寶藏"]):
        return "好奇 🤔", "搜尋圖書館紀錄"

    if any(word in text for word in ["攻擊", "殺", "偷", "威脅"]):
        return "警戒 😠", "保護圖書館"

    return "平靜 😐", "繼續觀察玩家"


def create_rule_reply(player_text):
    """當本機 AI 未啟用或無法連線時，產生備援回覆。"""

    if st.session_state.emotion.startswith("開心"):
        return "你的善意讓我很高興。告訴我吧，你需要什麼協助？"

    if st.session_state.emotion.startswith("好奇"):
        return "這件事引起了我的興趣。我會替你搜尋圖書館的古老紀錄。"

    if st.session_state.emotion.startswith("警戒"):
        return "請立刻停止。身為守護者，我不會允許你危害這座圖書館。"

    return f"我聽見你說「{player_text}」。請繼續說下去。"


st.title("🧙 AI NPC 對話系統")
st.caption("具備角色設定、短期記憶、情緒與行為決策的 MVP")

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
        st.warning("無法連接本機 Ollama，已自動使用規則模式。")

    st.divider()

    st.subheader("即時狀態")
    st.write(f"目前情緒：{st.session_state.emotion}")
    st.write(f"目前行為：{st.session_state.action}")
    st.write(f"回覆來源：{st.session_state.ai_status}")

    if st.button("清除對話並重置"):
        st.session_state.messages = []
        st.session_state.emotion = "平靜 😐"
        st.session_state.action = "觀察玩家"
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False
        st.rerun()

st.subheader("與艾琳交談")

# 顯示短期記憶中的對話
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

player_message = st.chat_input("輸入你想對艾琳說的話")

if player_message:
    # 先根據玩家訊息更新 NPC 狀態
    emotion, action = decide_state(player_message)
    st.session_state.emotion = emotion
    st.session_state.action = action

    # 將玩家訊息保存至短期記憶
    st.session_state.messages.append(
        {
            "role": "user",
            "content": player_message,
        }
    )

    npc_reply = ""

    if use_local_ai:
        system_prompt = f"""
你是奇幻王城圖書館的守護者艾琳。

角色設定：
- 個性冷靜、謹慎、富有好奇心
- 使命是保護圖書館，並協助可信任的訪客
- 目前情緒：{st.session_state.emotion}
- 目前行為：{st.session_state.action}

回覆規則：
- 永遠使用繁體中文
- 保持角色身分，不要說自己是 AI
- 根據目前情緒與行為回覆
- 每次回答二到四句
- 不要顯示思考過程
"""

        # 只傳送最近八則訊息，避免記憶占用過多 VRAM
        model_messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        model_messages.extend(st.session_state.messages[-8:])

        try:
            with st.spinner("艾琳正在思考……"):
                response = chat(
                    model="qwen3:8b",
                    messages=model_messages,
                    think=False,
                    options={
                        "temperature": 0.8,
                        "num_predict": 180,
                    },
                )

            npc_reply = response.message.content.strip()

            if not npc_reply:
                raise ValueError("模型沒有產生回覆")

            st.session_state.ai_status = "Qwen3 8B（本機 GPU）"
            st.session_state.connection_warning = False

        except Exception:
            npc_reply = create_rule_reply(player_message)
            st.session_state.ai_status = "規則模式（自動備援）"
            st.session_state.connection_warning = True

    else:
        npc_reply = create_rule_reply(player_message)
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False

    # 保存 NPC 回覆
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": npc_reply,
        }
    )

    st.rerun()