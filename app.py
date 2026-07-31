import streamlit as st

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

st.title("🧙 AI NPC 對話系統")
st.caption("具備角色設定、短期記憶、情緒與行為決策的 MVP")

# 左側角色狀態面板
with st.sidebar:
    st.header("角色設定")
    st.write("名字：艾琳")
    st.write("身分：王城圖書館守護者")
    st.write("個性：冷靜、謹慎、富有好奇心")

    st.divider()

    st.subheader("即時狀態")
    st.write(f"目前情緒：{st.session_state.emotion}")
    st.write(f"目前行為：{st.session_state.action}")

    if st.button("清除對話並重置"):
        st.session_state.messages = []
        st.session_state.emotion = "平靜 😐"
        st.session_state.action = "觀察玩家"
        st.rerun()

st.subheader("與艾琳交談")

# 顯示記憶中的對話
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

player_message = st.chat_input("輸入你想對艾琳說的話")

if player_message:
    # 保存玩家訊息
    st.session_state.messages.append(
        {
            "role": "user",
            "content": player_message,
        }
    )

    # 將訊息轉成小寫，方便判斷英文關鍵字
    text = player_message.lower()

    # 根據玩家訊息做出情緒與行為決策
    if any(word in text for word in ["謝謝", "感謝", "幫助", "thank"]):
        st.session_state.emotion = "開心 😊"
        st.session_state.action = "主動協助玩家"
        npc_reply = "你的善意讓我很高興。告訴我吧，你需要什麼協助？"

    elif any(word in text for word in ["魔法書", "秘密", "線索", "寶藏"]):
        st.session_state.emotion = "好奇 🤔"
        st.session_state.action = "搜尋圖書館紀錄"
        npc_reply = "這件事引起了我的興趣。我會替你搜尋圖書館的古老紀錄。"

    elif any(word in text for word in ["攻擊", "殺", "偷", "威脅"]):
        st.session_state.emotion = "警戒 😠"
        st.session_state.action = "保護圖書館"
        npc_reply = "請立刻停止。身為守護者，我不會允許你危害這座圖書館。"

    else:
        st.session_state.emotion = "平靜 😐"
        st.session_state.action = "繼續觀察玩家"
        npc_reply = f"我聽見你說「{player_message}」。請繼續說下去。"

    # 在回覆中加入短期記憶資訊
    player_messages = [
        message["content"]
        for message in st.session_state.messages
        if message["role"] == "user"
    ]

    if len(player_messages) > 1:
        previous_message = player_messages[-2]
        npc_reply += f"\n\n我也記得你上一句說的是：「{previous_message}」。"

    # 保存 NPC 回覆
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": npc_reply,
        }
    )

    # 重新執行頁面，讓左側狀態立刻更新
    st.rerun()