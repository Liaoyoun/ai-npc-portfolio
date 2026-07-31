import copy
import json
import random
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
    threat_level: Literal["無", "挑釁", "威脅", "攻擊"]
    relationship_change: int = Field(ge=-20, le=10)


EMOTION_ICONS = {
    "平靜": "😐",
    "開心": "😊",
    "好奇": "🤔",
    "警戒": "😠",
    "生氣": "😡",
    "悲傷": "😢",
}

WEAPONS = {
    "練習長劍": {
        "attack_bonus": 0,
        "description": "平衡、可靠，沒有額外傷害加成。",
    },
    "守衛長劍": {
        "attack_bonus": 4,
        "description": "王城守衛使用的長劍，攻擊傷害 +4。",
    },
    "秘法短杖": {
        "attack_bonus": 2,
        "description": "刻有符文的短杖，攻擊傷害 +2。",
    },
}

ARMORS = {
    "旅人斗篷": {
        "damage_reduction": 0,
        "description": "輕便的斗篷，沒有額外減傷。",
    },
    "獵人皮甲": {
        "damage_reduction": 3,
        "description": "結實的皮甲，每次受到傷害 -3。",
    },
    "守衛盾牌": {
        "damage_reduction": 5,
        "description": "厚實盾牌，每次受到傷害 -5。",
    },
}

QUEST_REWARDS = {
    "艾琳": {
        "id": "guardian_badge",
        "icon": "🏅",
        "name": "守護者徽章",
        "description": "艾琳交付的信任象徵，每次受到傷害額外 -1。",
        "damage_reduction": 1,
    },
    "洛恩": {
        "id": "barrier_amulet",
        "icon": "🪬",
        "name": "結界護符",
        "description": "洛恩製作的結界護符，每次受到傷害額外 -2。",
        "damage_reduction": 2,
    },
}

NPC_PROFILES = {
    "艾琳": {
        "name": "艾琳",
        "icon": "🧙",
        "identity": "王城圖書館守護者",
        "personality": "冷靜、謹慎、富有好奇心",
        "mission": "保護圖書館並協助可信任的訪客",
        "initial_emotion": "平靜 😐",
        "initial_action": "觀察玩家",
        "story": {
            "intro": "序章：圖書館的異常",
            "item": "封印魔法書",
            "item_icon": "📜",
            "search_label": "搜尋魔法書",
            "search_message": "我希望與你一起搜尋封印魔法書。",
            "search_denied": "尚未信任你，不會帶你進入封存書庫。",
            "found_stage": "第二章：封印的抉擇",
            "found_message": "你們在封存書庫找到了一本散發微光的魔法書。",
            "cooperate_label": "封印魔法書",
            "cooperate_message": "我願意與你完成封印魔法書的儀式。",
            "cooperate_denied": "仍不願把封印儀式交給你，需要更高的信任。",
            "cooperate_stage": "結局：守護者盟約",
            "cooperate_ending": "守護者盟約（合作結局）",
            "cooperate_result": "封印儀式完成。你受邀成為圖書館的新任盟友。",
            "hostile_label": "奪取魔法書",
            "hostile_message": "我奪取封印魔法書並拒絕交還。",
            "hostile_stage": "結局：圖書館的叛徒",
            "hostile_ending": "圖書館的叛徒（敵對結局）",
            "hostile_result": "你奪走魔法書，守衛已封鎖圖書館的出口。",
        },
    },
    "洛恩": {
        "name": "洛恩",
        "icon": "🔮",
        "identity": "古代封印術士",
        "personality": "理性、寡言、對失落魔法十分執著",
        "mission": "維持遺跡結界，阻止危險魔力外洩",
        "initial_emotion": "警戒 😠",
        "initial_action": "檢查封印結界",
        "story": {
            "intro": "序章：遺跡結界鬆動",
            "item": "結界核心",
            "item_icon": "🔮",
            "search_label": "調查結界",
            "search_message": "我希望與你一起調查遺跡結界的裂縫。",
            "search_denied": "不信任你，不會讓你接近遺跡深處。",
            "found_stage": "第二章：核心的抉擇",
            "found_message": "你們在遺跡深處找到了一枚不斷脈動的結界核心。",
            "cooperate_label": "修復結界",
            "cooperate_message": "我願意與你一起修復遺跡的結界。",
            "cooperate_denied": "尚未確信你能承受結界反噬，需要更高的信任。",
            "cooperate_stage": "結局：封印守望",
            "cooperate_ending": "封印守望（合作結局）",
            "cooperate_result": "結界重新穩定。你與洛恩成為遺跡的共同守望者。",
            "hostile_label": "破壞結界",
            "hostile_message": "我破壞結界，奪取其中的力量。",
            "hostile_stage": "結局：遺跡災變",
            "hostile_ending": "遺跡災變（敵對結局）",
            "hostile_result": "結界崩解，失控的魔力吞沒了遺跡入口。",
        },
    },
}

NPC_EVENTS = {
    "艾琳": [
        {
            "id": "masked_intruders",
            "title": "黑衣人闖入圖書館",
            "description": "一群黑衣人正試圖闖入封存書庫，訪客開始四處逃散。",
            "help_label": "協助疏散訪客",
            "help_message": "我協助艾琳疏散訪客，並守住封存書庫的入口。",
            "help_result": "訪客安全離開，艾琳對你的行動表示信任。",
            "help_affinity": 10,
            "observe_label": "保持距離觀察",
            "observe_message": "我先保持距離，觀察黑衣人的行動。",
            "observe_result": "你記下了黑衣人的特徵，但沒有直接介入。",
        },
        {
            "id": "lost_archive",
            "title": "失落檔案的求助者",
            "description": "一名年輕學者在圖書館哭泣，說他的研究檔案不見了。",
            "help_label": "協助尋找檔案",
            "help_message": "我協助艾琳安撫學者，並一起尋找遺失的研究檔案。",
            "help_result": "檔案在錯置書架後被找到，艾琳看見你的耐心。",
            "help_affinity": 8,
            "observe_label": "靜靜等待結果",
            "observe_message": "我暫時不介入，等待艾琳處理學者的求助。",
            "observe_result": "艾琳獨自處理了求助，事件平靜落幕。",
        },
    ],
    "洛恩": [
        {
            "id": "barrier_breach",
            "title": "遺跡結界裂縫擴張",
            "description": "結界發出刺耳聲響，裂縫中不斷滲出不穩定的魔力。",
            "help_label": "協助穩定結界",
            "help_message": "我協助洛恩布置符文，暫時穩定擴張的結界裂縫。",
            "help_result": "裂縫逐漸收束，洛恩承認你在壓力下仍值得信賴。",
            "help_affinity": 10,
            "observe_label": "保持安全距離",
            "observe_message": "我先保持安全距離，觀察結界裂縫的變化。",
            "observe_result": "洛恩獨自穩住裂縫，你則記下了魔力波動。",
        },
        {
            "id": "missing_scout",
            "title": "失聯的遺跡斥候",
            "description": "一名斥候進入遺跡後失去聯絡，只留下斷裂的通訊水晶。",
            "help_label": "協助追蹤斥候",
            "help_message": "我和洛恩依照通訊水晶的殘留魔力追蹤失聯斥候。",
            "help_result": "你們在側廊找到受傷的斥候，並帶他安全離開遺跡。",
            "help_affinity": 8,
            "observe_label": "留在入口戒備",
            "observe_message": "我選擇留在遺跡入口戒備，等待洛恩的消息。",
            "observe_result": "洛恩獨自帶回斥候，而入口也沒有出現新的危險。",
        },
    ],
}

NPC_STATE_KEYS = (
    "messages",
    "emotion",
    "action",
    "ai_status",
    "connection_warning",
    "affinity",
    "quest",
    "npc_hp",
    "battle_turn",
    "skill_cooldown",
    "story_stage",
    "magic_book_found",
    "ending",
    "combat_message",
    "active_event",
    "completed_events",
    "pending_action",
)


def create_default_npc_state(npc_key):
    """建立單一 NPC 的獨立對話、關係、戰鬥與劇情狀態。"""

    profile = NPC_PROFILES[npc_key]
    return {
        "messages": [],
        "emotion": profile["initial_emotion"],
        "action": profile["initial_action"],
        "ai_status": "規則模式",
        "connection_warning": False,
        "affinity": 0,
        "quest": "尚未解鎖",
        "npc_hp": 100,
        "battle_turn": 0,
        "skill_cooldown": 0,
        "story_stage": profile["story"]["intro"],
        "magic_book_found": False,
        "ending": "",
        "combat_message": "尚未進入戰鬥",
        "active_event": None,
        "completed_events": [],
        "pending_action": None,
    }


def get_active_profile():
    return NPC_PROFILES[st.session_state.active_npc]


def get_inventory_rewards():
    """取得背包中有效的任務獎勵資料。"""

    reward_by_id = {
        reward["id"]: reward for reward in QUEST_REWARDS.values()
    }
    return [
        reward_by_id[reward_id]
        for reward_id in st.session_state.inventory
        if reward_id in reward_by_id
    ]


def get_inventory_damage_reduction():
    """計算任務獎勵提供的額外減傷。"""

    return sum(reward["damage_reduction"] for reward in get_inventory_rewards())


def grant_current_npc_reward():
    """合作結局完成時發放目前 NPC 的專屬獎勵，並避免重複取得。"""

    reward = QUEST_REWARDS[st.session_state.active_npc]
    if reward["id"] in st.session_state.inventory:
        return f"{reward['icon']} 你已持有「{reward['name']}」。"

    st.session_state.inventory.append(reward["id"])
    return (
        f"{reward['icon']} 獲得任務獎勵「{reward['name']}」："
        f"{reward['description']}"
    )


def save_active_npc_state():
    """將目前畫面的 NPC 狀態存回瀏覽器工作階段。"""

    active_npc = st.session_state.active_npc
    st.session_state.npc_states[active_npc] = {
        key: copy.deepcopy(st.session_state[key]) for key in NPC_STATE_KEYS
    }


def switch_active_npc(next_npc):
    """切換 NPC 時保存舊角色，再載入新角色的獨立狀態。"""

    if next_npc == st.session_state.active_npc:
        return

    save_active_npc_state()
    if next_npc not in st.session_state.npc_states:
        st.session_state.npc_states[next_npc] = create_default_npc_state(next_npc)

    for key, value in st.session_state.npc_states[next_npc].items():
        st.session_state[key] = copy.deepcopy(value)
    st.session_state.active_npc = next_npc
    st.session_state.load_notice = ""


def initialize_state():
    """初始化玩家共用狀態，並將舊版艾琳資料遷移為可切換的 NPC 狀態。"""

    player_defaults = {
        "player_hp": 100,
        "potions": 3,
        "weapon": "練習長劍",
        "armor": "旅人斗篷",
        "inventory": [],
        "load_notice": "",
    }
    for key, value in player_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    active_npc = st.session_state.get("active_npc", "艾琳")
    if active_npc not in NPC_PROFILES:
        active_npc = "艾琳"
    st.session_state.active_npc = active_npc

    if "npc_states" not in st.session_state:
        default_state = create_default_npc_state(active_npc)
        st.session_state.npc_states = {
            active_npc: {
                key: copy.deepcopy(st.session_state.get(key, default_state[key]))
                for key in NPC_STATE_KEYS
            }
        }

    for npc_key in NPC_PROFILES:
        saved_state = st.session_state.npc_states.get(npc_key)
        if not isinstance(saved_state, dict):
            st.session_state.npc_states[npc_key] = create_default_npc_state(
                npc_key
            )
            continue

        default_state = create_default_npc_state(npc_key)
        for key, value in default_state.items():
            if key not in saved_state:
                saved_state[key] = copy.deepcopy(value)

    for key, value in st.session_state.npc_states[active_npc].items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def classify_relationship_intent(player_text, player_turn="talk"):
    """只判斷玩家是否明確把善惡行為指向目前 NPC。"""

    text = player_text.lower().replace(" ", "")
    profile = get_active_profile()
    story = profile["story"]

    if player_turn in {"attack", "heavy_attack"}:
        return "direct_attack"

    external_event_words = [
        "黑衣人",
        "盜賊",
        "怪物",
        "敵人",
        "有人出現",
        "有人闖入",
        "他們來了",
        "守衛來了",
    ]
    personal_need_words = ["肚子餓", "好餓", "沒吃", "食物", "受傷", "救命"]
    attack_words = ["攻擊", "砍", "刺", "射擊", "火球", "施放", "殺了", "殺死"]
    hostile_words = ["威脅", "摧毀", "偷走", "偷取", "奪取", "破壞", "搶走"]
    insult_words = ["討厭", "騙子", "笨蛋", "沒用", "廢物", "垃圾", "滾開"]
    direct_target_words = [profile["name"], "你", "妳", "守護者", "術士"]
    story_target_words = [story["item"], "圖書館", "結界"]
    player_actor_words = [
        "我要",
        "我會",
        "我想",
        "我已",
        "我把",
        "我準備",
        "我拔",
        "我朝",
        "讓我",
    ]

    mentions_external_event = any(word in text for word in external_event_words)
    targets_npc = any(word in text for word in direct_target_words)
    targets_story = any(word in text for word in story_target_words)
    player_is_actor = any(word in text for word in player_actor_words)

    # 「我砍黑衣人」是外部事件；「我砍你」才是攻擊 NPC。
    if mentions_external_event and not targets_npc:
        return "external_event"

    if player_is_actor and any(word in text for word in attack_words):
        if targets_npc or targets_story or not mentions_external_event:
            return "direct_attack"

    if player_is_actor and any(word in text for word in hostile_words):
        if targets_npc or targets_story or not mentions_external_event:
            return "direct_hostile"

    if targets_npc and any(word in text for word in insult_words):
        return "direct_insult"

    if any(word in text for word in ["道歉", "對不起", "原諒"]):
        return "apology"

    if any(word in text for word in ["謝謝", "感謝", "多謝"]):
        return "gratitude"

    if any(
        word in text
        for word in ["我會幫", "我來幫", "願意幫", "協助你", "保護你"]
    ):
        return "offer_help"

    if any(word in text for word in personal_need_words):
        return "personal_need"

    if mentions_external_event:
        return "external_event"

    return "neutral"


def relationship_change_from_intent(relationship_intent):
    """關係數值由明確行為決定，避免外部事件被誤判為玩家挑釁。"""

    changes = {
        "direct_attack": -20,
        "direct_hostile": -15,
        "direct_insult": -10,
        "apology": 5,
        "gratitude": 5,
        "offer_help": 5,
        "external_event": 0,
        "personal_need": 0,
        "neutral": 0,
    }
    return changes[relationship_intent]


def threat_level_from_intent(relationship_intent):
    """讓戰鬥只由真正針對 NPC 的攻擊觸發。"""

    if relationship_intent == "direct_attack":
        return "攻擊"
    if relationship_intent == "direct_hostile":
        return "威脅"
    if relationship_intent == "direct_insult":
        return "挑釁"
    return "無"


def decide_state(player_text, relationship_intent):
    """規則模式：依玩家對 NPC 的明確意圖決定情緒與行為。"""

    profile = get_active_profile()
    story = profile["story"]

    if relationship_intent == "direct_attack":
        return "生氣 😡", "進入戰鬥並反擊玩家"

    if relationship_intent == "direct_hostile":
        return "警戒 😠", f"守護{story['item']}並警告玩家"

    if relationship_intent == "direct_insult":
        return "生氣 😡", "拒絕與玩家合作"

    if relationship_intent == "external_event":
        return "警戒 😠", "留意外部威脅"

    if relationship_intent == "personal_need":
        return "平靜 😐", "評估玩家的需求"

    if relationship_intent in {"gratitude", "offer_help"}:
        return "開心 😊", "主動協助玩家"

    if relationship_intent == "apology":
        return "平靜 😐", "重新評估玩家的誠意"

    if story["item"] in player_text or "線索" in player_text:
        return "好奇 🤔", f"尋找{story['item']}的線索"

    return "平靜 😐", f"觀察玩家對{story['item']}的意圖"


def update_quest():
    """依關係、劇情物品與結局更新目前任務。"""

    profile = get_active_profile()
    npc_name = profile["name"]
    story = profile["story"]
    item_name = story["item"]

    if st.session_state.ending:
        st.session_state.quest = f"結局完成：{st.session_state.ending}"
        return

    if st.session_state.magic_book_found:
        if st.session_state.affinity >= 60:
            st.session_state.quest = (
                f"終章任務：與{npc_name}{story['cooperate_label']}"
            )
        elif st.session_state.affinity <= -20:
            st.session_state.quest = f"敵對事件：爭奪{item_name}"
        else:
            st.session_state.quest = f"第二章：{item_name}等待你的選擇"
        return

    if st.session_state.affinity >= 60:
        st.session_state.quest = f"盟友任務：{story['search_label']}"
    elif st.session_state.affinity >= 20:
        st.session_state.quest = (
            f"任務解鎖：請與{npc_name}一起{story['search_label']}"
        )
    elif st.session_state.affinity <= -60:
        st.session_state.quest = f"敵對事件：{npc_name}的追捕令"
    elif st.session_state.affinity <= -20:
        st.session_state.quest = f"{npc_name}拒絕與玩家合作"
    else:
        st.session_state.quest = "尚未解鎖"


def get_event_by_id(npc_key, event_id):
    """依事件識別碼找回指定 NPC 的事件設定。"""

    for event in NPC_EVENTS[npc_key]:
        if event["id"] == event_id:
            return event
    return None


def trigger_random_event():
    """為目前 NPC 觸發一個尚未解決的隨機事件。"""

    if st.session_state.active_event:
        return "⚠️ 目前已有進行中的事件，請先做出選擇。"

    completed_events = set(st.session_state.completed_events)
    available_events = [
        event
        for event in NPC_EVENTS[st.session_state.active_npc]
        if event["id"] not in completed_events
    ]
    if not available_events:
        return "🏁 這名 NPC 已沒有新的已知事件。"

    st.session_state.active_event = copy.deepcopy(
        random.choice(available_events)
    )
    return f"⚠️ 事件發生：{st.session_state.active_event['title']}"


def handle_event_action(player_turn):
    """處理玩家對目前隨機事件的協助或觀察選擇。"""

    if player_turn not in {"event_help", "event_observe"}:
        return ""

    event = st.session_state.active_event
    if not isinstance(event, dict):
        return "⚠️ 事件已結束，請觸發新的事件。"

    event_id = event.get("id")
    configured_event = get_event_by_id(
        st.session_state.active_npc,
        event_id,
    )
    if configured_event is None:
        st.session_state.active_event = None
        return "⚠️ 這個事件資料無法辨識，已自動結束。"

    if player_turn == "event_help":
        relationship_change = configured_event["help_affinity"]
        st.session_state.emotion = "開心 😊"
        st.session_state.action = "與玩家共同處理突發事件"
        result = configured_event["help_result"]
        effect = f"關係值 +{relationship_change}"
    else:
        relationship_change = 0
        st.session_state.emotion = "警戒 😠"
        st.session_state.action = "持續監控突發事件"
        result = configured_event["observe_result"]
        effect = "關係值不變"

    st.session_state.affinity = max(
        -100,
        min(100, st.session_state.affinity + relationship_change),
    )
    if event_id not in st.session_state.completed_events:
        st.session_state.completed_events.append(event_id)
    st.session_state.active_event = None
    update_quest()
    return f"🧭 {result}（{effect}）"


def handle_story_action(player_turn):
    """處理任務按鈕，讓關係值決定合作或敵對的劇情分支。"""

    profile = get_active_profile()
    npc_name = profile["name"]
    story = profile["story"]
    item_name = story["item"]
    item_icon = story["item_icon"]

    if player_turn not in {"search_book", "seal_book", "steal_book"}:
        return ""

    if st.session_state.ending:
        return f"🏁 劇情已完成：{st.session_state.ending}。"

    if player_turn == "search_book":
        if st.session_state.magic_book_found:
            return f"{item_icon} 你已經找到{item_name}。"
        if st.session_state.affinity < 20:
            st.session_state.emotion = "警戒 😠"
            st.session_state.action = f"拒絕交出{item_name}的線索"
            st.session_state.affinity = max(-100, st.session_state.affinity - 5)
            update_quest()
            return f"{item_icon} {npc_name}{story['search_denied']}"

        st.session_state.magic_book_found = True
        st.session_state.story_stage = story["found_stage"]
        st.session_state.emotion = "好奇 🤔"
        st.session_state.action = f"與玩家研究{item_name}"
        update_quest()
        return f"{item_icon} 你與{npc_name}{story['found_message']}"

    if player_turn == "seal_book":
        if not st.session_state.magic_book_found:
            return f"{item_icon} 你還沒有找到{item_name}，無法繼續任務。"
        if st.session_state.affinity < 60:
            return f"{item_icon} {npc_name}{story['cooperate_denied']}"

        st.session_state.story_stage = story["cooperate_stage"]
        st.session_state.ending = story["cooperate_ending"]
        st.session_state.emotion = "開心 😊"
        st.session_state.action = f"與玩家共同完成{story['cooperate_label']}"
        st.session_state.affinity = min(100, st.session_state.affinity + 10)
        update_quest()
        reward_message = grant_current_npc_reward()
        return f"{item_icon} {story['cooperate_result']}\n\n{reward_message}"

    if not st.session_state.magic_book_found:
        return f"{item_icon} 你還沒有找到{item_name}，無法採取敵對行動。"

    st.session_state.story_stage = story["hostile_stage"]
    st.session_state.ending = story["hostile_ending"]
    st.session_state.emotion = "生氣 😡"
    st.session_state.action = "啟動防衛機制追捕玩家"
    st.session_state.affinity = -100
    update_quest()
    return f"{item_icon} {story['hostile_result']}"


def clamp_integer(value, default, minimum, maximum):
    """讀取存檔數值時限制範圍，避免錯誤資料破壞遊戲狀態。"""

    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def clean_messages(messages):
    """只保留格式正確且最近的對話記憶。"""

    if not isinstance(messages, list):
        return []

    valid_messages = []
    for message in messages[-30:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            valid_messages.append({"role": role, "content": content})
    return valid_messages


def normalise_npc_state(raw_state, npc_key):
    """將新舊存檔中的單一 NPC 狀態整理為安全、完整的格式。"""

    default_state = create_default_npc_state(npc_key)
    if not isinstance(raw_state, dict):
        return default_state

    state = copy.deepcopy(default_state)
    state["messages"] = clean_messages(raw_state.get("messages", []))
    state["emotion"] = str(raw_state.get("emotion", state["emotion"]))
    state["action"] = str(raw_state.get("action", state["action"]))
    state["ai_status"] = "規則模式"
    state["connection_warning"] = False
    state["affinity"] = clamp_integer(
        raw_state.get("affinity", 0),
        0,
        -100,
        100,
    )
    state["quest"] = str(raw_state.get("quest", state["quest"]))
    state["npc_hp"] = clamp_integer(
        raw_state.get("npc_hp", 100),
        100,
        0,
        100,
    )
    state["battle_turn"] = clamp_integer(
        raw_state.get("battle_turn", 0),
        0,
        0,
        99,
    )
    state["skill_cooldown"] = clamp_integer(
        raw_state.get("skill_cooldown", 0),
        0,
        0,
        2,
    )
    state["story_stage"] = str(
        raw_state.get("story_stage", state["story_stage"])
    )
    state["magic_book_found"] = (
        raw_state.get("magic_book_found") is True
    )
    state["ending"] = str(raw_state.get("ending", ""))
    state["combat_message"] = str(
        raw_state.get("combat_message", state["combat_message"])
    )
    valid_event_ids = {
        event["id"] for event in NPC_EVENTS[npc_key]
    }
    raw_completed_events = raw_state.get("completed_events", [])
    if not isinstance(raw_completed_events, list):
        raw_completed_events = []
    state["completed_events"] = []
    for event_id in raw_completed_events:
        if (
            isinstance(event_id, str)
            and event_id in valid_event_ids
            and event_id not in state["completed_events"]
        ):
            state["completed_events"].append(event_id)

    raw_active_event = raw_state.get("active_event")
    active_event_id = (
        raw_active_event.get("id")
        if isinstance(raw_active_event, dict)
        else None
    )
    active_event = get_event_by_id(npc_key, active_event_id)
    state["active_event"] = (
        copy.deepcopy(active_event) if active_event is not None else None
    )
    state["pending_action"] = None
    return state


def apply_npc_state_to_screen(npc_key):
    """把指定 NPC 的已保存狀態載入目前 Streamlit 畫面。"""

    for key, value in st.session_state.npc_states[npc_key].items():
        st.session_state[key] = copy.deepcopy(value)


def create_save_data():
    """建立包含所有 NPC 與玩家共用狀態的完整世界存檔。"""

    save_active_npc_state()
    npc_states = copy.deepcopy(st.session_state.npc_states)
    for npc_state in npc_states.values():
        npc_state["pending_action"] = None

    return {
        "save_version": 8,
        "active_npc": st.session_state.active_npc,
        "npc_states": npc_states,
        "player_state": {
            "player_hp": st.session_state.player_hp,
            "potions": st.session_state.potions,
            "weapon": st.session_state.weapon,
            "armor": st.session_state.armor,
            "inventory": st.session_state.inventory,
        },
    }


def load_save_data(data):
    """載入完整世界存檔，並相容舊版只存目前 NPC 的存檔。"""

    if not isinstance(data, dict):
        raise ValueError("存檔格式不是 JSON 物件")

    save_active_npc_state()
    saved_npc = str(data.get("active_npc", "艾琳"))
    if saved_npc not in NPC_PROFILES:
        saved_npc = "艾琳"

    raw_npc_states = data.get("npc_states")
    if isinstance(raw_npc_states, dict):
        st.session_state.npc_states = {
            npc_key: normalise_npc_state(
                raw_npc_states.get(npc_key),
                npc_key,
            )
            for npc_key in NPC_PROFILES
        }
    else:
        # 版本 7 與更早的存檔只記錄當時正在交談的 NPC。
        st.session_state.npc_states = {
            npc_key: create_default_npc_state(npc_key)
            for npc_key in NPC_PROFILES
        }
        legacy_npc_state = {
            key: data[key] for key in NPC_STATE_KEYS if key in data
        }
        st.session_state.npc_states[saved_npc] = normalise_npc_state(
            legacy_npc_state,
            saved_npc,
        )

    st.session_state.active_npc = saved_npc
    apply_npc_state_to_screen(saved_npc)

    player_state = data.get("player_state", data)
    if not isinstance(player_state, dict):
        player_state = {}
    st.session_state.player_hp = clamp_integer(
        player_state.get("player_hp", 100),
        100,
        0,
        100,
    )
    st.session_state.potions = clamp_integer(
        player_state.get("potions", 3),
        3,
        0,
        9,
    )
    saved_weapon = str(player_state.get("weapon", "練習長劍"))
    saved_armor = str(player_state.get("armor", "旅人斗篷"))
    st.session_state.weapon = (
        saved_weapon if saved_weapon in WEAPONS else "練習長劍"
    )
    st.session_state.armor = saved_armor if saved_armor in ARMORS else "旅人斗篷"
    valid_reward_ids = {
        reward["id"] for reward in QUEST_REWARDS.values()
    }
    saved_inventory = player_state.get("inventory", [])
    if not isinstance(saved_inventory, list):
        saved_inventory = []
    st.session_state.inventory = []
    for reward_id in saved_inventory:
        if (
            isinstance(reward_id, str)
            and reward_id in valid_reward_ids
            and reward_id not in st.session_state.inventory
        ):
            st.session_state.inventory.append(reward_id)

    update_quest()
    save_active_npc_state()


def update_affinity_by_rules(relationship_intent):
    """規則模式：只用明確針對 NPC 的行為更新關係值。"""

    change = relationship_change_from_intent(relationship_intent)

    st.session_state.affinity = max(
        -100,
        min(100, st.session_state.affinity + change),
    )
    update_quest()


def create_rule_reply(player_text, relationship_intent):
    """本機 AI 未啟用或無法連線時的備援回覆。"""

    profile = get_active_profile()
    story = profile["story"]

    if relationship_intent == "external_event":
        return "我會先留意周遭動靜。那不是你的過錯，我們應先確認外部威脅。"

    if relationship_intent == "personal_need":
        return "我明白你的需求。先照顧好自己，再告訴我你需要什麼協助。"

    if st.session_state.emotion.startswith("開心"):
        return (
            f"你的善意讓我很高興。若你願意協助，"
            f"我們可以一起處理{story['item']}的事。"
        )

    if st.session_state.emotion.startswith("好奇"):
        return f"這件事引起了我的興趣。我會尋找關於{story['item']}的線索。"

    if st.session_state.emotion.startswith(("警戒", "生氣")):
        return (
            f"請立刻停止。身為{profile['identity']}，"
            f"我不會允許你危害{story['item']}。"
        )

    return f"我聽見你說「{player_text}」。請說明你對{story['item']}的意圖。"


def detect_threat_by_rules(relationship_intent):
    """規則模式：只有玩家直接針對 NPC 的行為才算威脅。"""

    return threat_level_from_intent(relationship_intent)


def prepare_player_action(player_turn):
    """先處理玩家按下的遊戲動作，讓 AI 能看見最新生命值。"""

    cooldown_note = ""
    if (
        player_turn in {"attack", "defend", "heal"}
        and st.session_state.skill_cooldown > 0
    ):
        st.session_state.skill_cooldown -= 1
        cooldown_note = (
            f"⚡ 重擊冷卻中，剩餘 {st.session_state.skill_cooldown} 個行動。"
        )

    if player_turn == "heavy_attack":
        if st.session_state.skill_cooldown > 0:
            return (
                "⚡ 重擊尚在冷卻，請先進行其他行動。",
                False,
            )
        st.session_state.skill_cooldown = 2
        return (
            "⚡ 玩家施展重擊：命中率較低，但傷害更高。"
            "重擊將冷卻 2 個行動。",
            True,
        )

    if player_turn == "defend":
        return (
            "\n\n".join(
                filter(
                    None,
                    [
                        "🛡️ 玩家採取防禦姿態，下一次反擊傷害會減半。",
                        cooldown_note,
                    ],
                )
            ),
            True,
        )

    if player_turn != "heal":
        return cooldown_note, True

    if st.session_state.potions <= 0:
        return "\n\n".join(filter(None, ["🩹 治療藥水已用完。", cooldown_note])), True

    if st.session_state.player_hp >= 100:
        return (
            "\n\n".join(
                filter(
                    None,
                    ["🩹 玩家生命值已滿，不需要使用治療藥水。", cooldown_note],
                )
            ),
            True,
        )

    recovered_hp = min(25, 100 - st.session_state.player_hp)
    st.session_state.player_hp += recovered_hp
    st.session_state.potions -= 1
    return (
        "\n\n".join(
            filter(
                None,
                [
                    f"🩹 玩家使用治療藥水，恢復 {recovered_hp} 點生命值。",
                    cooldown_note,
                ],
            )
        ),
        True,
    )


def resolve_combat(threat_level, player_turn="talk", action_result=""):
    """由遊戲規則處理命中、傷害與反擊，不讓玩家自行宣告結果。"""

    combat_lines = [action_result] if action_result else []
    npc_name = get_active_profile()["name"]
    weapon = WEAPONS.get(st.session_state.weapon, WEAPONS["練習長劍"])
    armor = ARMORS.get(st.session_state.armor, ARMORS["旅人斗篷"])
    reward_reduction = get_inventory_damage_reduction()
    reward_names = "、".join(
        reward["name"] for reward in get_inventory_rewards()
    )
    combat_active = (
        st.session_state.npc_hp < 100 or st.session_state.player_hp < 100
    )
    player_attacks = threat_level == "攻擊"
    npc_can_counter = player_attacks or (
        combat_active and player_turn in {"defend", "heal"}
    )

    if not player_attacks and not npc_can_counter:
        result = "\n\n".join(combat_lines)
        if result:
            st.session_state.combat_message = result
        return result

    if st.session_state.npc_hp <= 0:
        return f"⚔️ {npc_name}已經倒下，無法繼續戰鬥。請重置遊戲。"

    if st.session_state.player_hp <= 0:
        return "⚔️ 玩家已失去戰鬥能力。請重置遊戲。"

    st.session_state.battle_turn += 1
    combat_lines.append(f"⚔️ 戰鬥第 {st.session_state.battle_turn} 回合。")

    # 重擊命中率較低但傷害較高；普通攻擊則較穩定。
    if player_attacks:
        if player_turn == "heavy_attack":
            hit_chance = 50
            base_damage = random.randint(18, 30)
            attack_name = "⚡ 重擊"
        else:
            hit_chance = 70
            base_damage = random.randint(8, 18)
            attack_name = "⚔️ 攻擊"

        if random.randint(1, 100) <= hit_chance:
            player_damage = base_damage + weapon["attack_bonus"]
            st.session_state.npc_hp = max(
                0,
                st.session_state.npc_hp - player_damage,
            )
            combat_lines.append(
                f"{attack_name}命中！玩家使用{st.session_state.weapon}對{npc_name}造成 "
                f"{player_damage} 點傷害。"
            )
        else:
            combat_lines.append(f"{attack_name}落空，{npc_name}避開了攻擊。")
    else:
        combat_lines.append("🛡️ 玩家本回合沒有發動攻擊。")

    if st.session_state.npc_hp <= 0:
        st.session_state.emotion = "悲傷 😢"
        st.session_state.action = "失去戰鬥能力"
        combat_lines.append(f"💀 {npc_name}的生命值歸零，戰鬥結束。")
        result = "\n\n".join(combat_lines)
        st.session_state.combat_message = result
        return result

    # NPC 有 75% 機率反擊；防禦姿態與防具都會降低傷害。
    if random.randint(1, 100) <= 75:
        npc_damage = random.randint(6, 15)
        damage_notes = []
        if player_turn == "defend":
            reduced_damage = max(1, npc_damage // 2)
            damage_notes.append(f"防禦姿態：{npc_damage}→{reduced_damage}")
            npc_damage = reduced_damage
        armor_reduction = armor["damage_reduction"]
        if armor_reduction:
            reduced_damage = max(1, npc_damage - armor_reduction)
            damage_notes.append(
                f"{st.session_state.armor}：{npc_damage}→{reduced_damage}"
            )
            npc_damage = reduced_damage
        if reward_reduction:
            reduced_damage = max(1, npc_damage - reward_reduction)
            damage_notes.append(
                f"任務獎勵（{reward_names}）：{npc_damage}→{reduced_damage}"
            )
            npc_damage = reduced_damage
        if damage_notes:
            combat_lines.append("🛡️ " + "；".join(damage_notes) + "。")
        st.session_state.player_hp = max(
            0,
            st.session_state.player_hp - npc_damage,
        )
        combat_lines.append(f"🛡️ {npc_name}反擊成功，玩家受到 {npc_damage} 點傷害。")
    else:
        combat_lines.append(f"🛡️ 玩家躲過了{npc_name}的反擊。")

    if st.session_state.player_hp <= 0:
        st.session_state.action = "制服玩家"
        combat_lines.append("☠️ 玩家失去戰鬥能力，戰鬥結束。")

    result = "\n\n".join(combat_lines)
    st.session_state.combat_message = result
    return result


def apply_rule_decision(player_text, relationship_intent):
    """執行規則式情緒、行為、關係與回覆判斷。"""

    emotion, action = decide_state(player_text, relationship_intent)
    st.session_state.emotion = emotion
    st.session_state.action = action
    update_affinity_by_rules(relationship_intent)
    return create_rule_reply(player_text, relationship_intent)


def create_ai_decision(player_message, relationship_intent):
    """要求 Qwen3 同時產生台詞、情緒、行為與關係變化。"""

    profile = get_active_profile()
    story = profile["story"]
    system_prompt = f"""
你是奇幻王城中的 NPC「{profile["name"]}」。

角色設定：
- 身分：{profile["identity"]}
- 個性：{profile["personality"]}
- 使命：{profile["mission"]}
- 目前情緒：{st.session_state.emotion}
- 目前行為：{st.session_state.action}
- 與玩家的關係值：{st.session_state.affinity}，範圍是 -100 到 100
- 目前事件：{st.session_state.quest}
- 劇情章節：{st.session_state.story_stage}
- 是否已找到{story['item']}：{st.session_state.magic_book_found}
- 目前結局：{st.session_state.ending or "尚未決定"}
- 目前隨機事件：{st.session_state.active_event['title'] if st.session_state.active_event else "無"}
- {profile["name"]}生命值：{st.session_state.npc_hp} / 100
- 玩家生命值：{st.session_state.player_hp} / 100
- 玩家武器：{st.session_state.weapon}，額外攻擊傷害 +{WEAPONS[st.session_state.weapon]["attack_bonus"]}
- 玩家防具：{st.session_state.armor}，每次受到傷害 -{ARMORS[st.session_state.armor]["damage_reduction"]}
- 任務獎勵額外減傷：-{get_inventory_damage_reduction()}
- 戰鬥回合：{st.session_state.battle_turn}
- 重擊冷卻：{st.session_state.skill_cooldown} 個行動（0 代表可使用）

本輪玩家的最新訊息：
<latest_player_message>
{player_message}
</latest_player_message>

遊戲系統判定的玩家意圖：{relationship_intent}

決策規則：
- 必須主要判斷 latest_player_message 的完整語意
- 舊對話只能作為背景，不可取代最新訊息
- 真誠友善、協助或道歉，可以增加 1 到 10
- 普通中立對話可以改變 0 到 2
- 嘲諷、辱罵、欺騙或無禮，應降低 5 到 15
- 偷竊、攻擊、殺害或威脅，應降低 15 到 20
- 玩家宣稱已攻擊、傷害或殺死{profile["name"]}，也必須判定為「攻擊」
- 玩家用括號描述的動作仍然算是實際行動，不能當成無關文字
- 玩家描述黑衣人、怪物、盜賊、其他第三者、環境事件，或自己的飢餓與受傷時，這不是對你的挑釁；不得因此降低關係值
- 當玩家意圖是 external_event 或 personal_need 時，threat_level 必須是「無」，relationship_change 必須是 0
- 只有玩家明確把辱罵、威脅、偷竊、破壞或攻擊指向你、你的使命或你的任務物品時，才能給負的 relationship_change
- 挑釁的 threat_level 是「挑釁」
- 威脅尚未實際動手時，threat_level 是「威脅」
- 已經動手、施放攻擊或宣稱造成傷害時，threat_level 是「攻擊」
- 不可自行決定攻擊是否命中、造成多少傷害或誰死亡
- 戰鬥結果會由遊戲系統在你回覆後另外計算
- 帶有禮貌詞的諷刺或辱罵仍是負面行為
- 真誠道歉可以小幅修復關係，但不會立刻消除全部仇恨
- 玩家態度改變時，情緒與行為也必須合理改變
- 不可重複先前使用過的完整回覆

回覆規則：
- 永遠使用繁體中文
- 保持{profile["name"]}的角色身分，不要說自己是 AI
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
    st.header("NPC 選擇")
    npc_options = list(NPC_PROFILES)
    selected_npc = st.selectbox(
        "目前交談的 NPC",
        npc_options,
        index=npc_options.index(st.session_state.active_npc),
        format_func=lambda npc_key: (
            f"{NPC_PROFILES[npc_key]['icon']} {NPC_PROFILES[npc_key]['name']}"
        ),
    )
    if selected_npc != st.session_state.active_npc:
        switch_active_npc(selected_npc)
        st.rerun()

    profile = get_active_profile()
    st.header(f"{profile['icon']} 角色設定")
    st.write(f"名字：{profile['name']}")
    st.write(f"身分：{profile['identity']}")
    st.write(f"個性：{profile['personality']}")
    st.caption(f"使命：{profile['mission']}")

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
    st.subheader("生命與戰鬥")
    st.write(f"{profile['name']}生命值：{st.session_state.npc_hp} / 100")
    st.progress(st.session_state.npc_hp)
    st.write(f"玩家生命值：{st.session_state.player_hp} / 100")
    st.progress(st.session_state.player_hp)
    st.write(f"治療藥水：{st.session_state.potions} 瓶")
    st.write(f"戰鬥回合：{st.session_state.battle_turn}")
    if st.session_state.skill_cooldown:
        st.caption(f"⚡ 重擊冷卻：{st.session_state.skill_cooldown} 個行動")
    else:
        st.caption("⚡ 重擊：可使用")
    st.caption(st.session_state.combat_message)

    st.divider()
    st.subheader("玩家裝備")

    weapon_options = list(WEAPONS)
    selected_weapon = st.selectbox(
        "選擇武器",
        weapon_options,
        index=weapon_options.index(st.session_state.weapon),
    )
    st.session_state.weapon = selected_weapon
    weapon_stats = WEAPONS[selected_weapon]
    st.caption(
        f"⚔️ 攻擊傷害 +{weapon_stats['attack_bonus']}｜"
        f"{weapon_stats['description']}"
    )

    armor_options = list(ARMORS)
    selected_armor = st.selectbox(
        "選擇防具",
        armor_options,
        index=armor_options.index(st.session_state.armor),
    )
    st.session_state.armor = selected_armor
    armor_stats = ARMORS[selected_armor]
    st.caption(
        f"🛡️ 受到傷害 -{armor_stats['damage_reduction']}｜"
        f"{armor_stats['description']}"
    )

    st.divider()
    st.subheader("玩家背包")
    inventory_rewards = get_inventory_rewards()
    if inventory_rewards:
        for reward in inventory_rewards:
            st.write(f"{reward['icon']} {reward['name']}")
            st.caption(reward["description"])
        st.caption(
            f"🛡️ 任務獎勵總減傷：-{get_inventory_damage_reduction()}"
        )
    else:
        st.caption("背包目前沒有任務獎勵。完成合作結局即可獲得專屬道具。")

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

    st.divider()
    st.subheader("劇情進度")
    st.write(f"目前章節：{st.session_state.story_stage}")
    st.write(
        f"{profile['story']['item']}："
        + (
            f"已找到 {profile['story']['item_icon']}"
            if st.session_state.magic_book_found
            else "尚未找到"
        )
    )
    if st.session_state.ending:
        st.success(f"已達成結局：{st.session_state.ending}")
    else:
        st.caption(f"先取得{profile['name']}的信任，再從對話框上方選擇劇情行動。")

    st.divider()
    st.subheader("事件紀錄")
    if st.session_state.active_event:
        st.warning(
            f"進行中：{st.session_state.active_event['title']}"
        )
    else:
        event_count = len(st.session_state.completed_events)
        total_events = len(NPC_EVENTS[st.session_state.active_npc])
        st.caption(f"已解決事件：{event_count} / {total_events}")

    if st.button("清除所有進度並重置遊戲"):
        st.session_state.npc_states = {
            npc_key: create_default_npc_state(npc_key)
            for npc_key in NPC_PROFILES
        }
        apply_npc_state_to_screen(st.session_state.active_npc)
        st.session_state.player_hp = 100
        st.session_state.potions = 3
        st.session_state.weapon = "練習長劍"
        st.session_state.armor = "旅人斗篷"
        st.session_state.inventory = []
        st.session_state.load_notice = ""
        st.rerun()

    st.divider()
    st.subheader("存檔管理")

    save_json = json.dumps(
        create_save_data(),
        ensure_ascii=False,
        indent=2,
    )
    st.download_button(
        "下載目前存檔",
        data=save_json,
        file_name="ai_npc_save.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_save = st.file_uploader(
        "選擇先前的 JSON 存檔",
        type=["json"],
    )

    if st.button(
        "載入選取的存檔",
        disabled=uploaded_save is None,
        use_container_width=True,
    ):
        try:
            save_data = json.loads(uploaded_save.getvalue().decode("utf-8"))
            load_save_data(save_data)
            st.session_state.load_notice = "存檔載入成功。"
            st.rerun()
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            st.session_state.load_notice = "存檔無法讀取，請確認檔案格式。"

    if st.session_state.load_notice:
        st.info(st.session_state.load_notice)

npc_name = get_active_profile()["name"]
st.subheader(f"與{npc_name}交談")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

st.caption("隨機事件：外部事件有自己的選項與結果，不會被視為你在挑釁 NPC。")
active_event = st.session_state.active_event
if active_event:
    st.warning(f"⚠️ {active_event['title']}\n\n{active_event['description']}")
    event_col1, event_col2 = st.columns(2)
    if event_col1.button(
        f"🛟 {active_event['help_label']}",
        use_container_width=True,
    ):
        st.session_state.pending_action = {
            "type": "event_help",
            "message": active_event["help_message"],
        }
        st.rerun()
    if event_col2.button(
        f"👁️ {active_event['observe_label']}",
        use_container_width=True,
    ):
        st.session_state.pending_action = {
            "type": "event_observe",
            "message": active_event["observe_message"],
        }
        st.rerun()
else:
    resolved_event_count = len(st.session_state.completed_events)
    total_event_count = len(NPC_EVENTS[st.session_state.active_npc])
    if resolved_event_count < total_event_count:
        if st.button("🎲 探索周遭並觸發事件", use_container_width=True):
            st.session_state.combat_message = trigger_random_event()
            st.rerun()
    else:
        st.caption("🏁 這名 NPC 的已知事件都已解決。")

st.caption("劇情行動：關係值會決定你能走向合作或敵對結局。")
story_col1, story_col2, story_col3 = st.columns(3)
story_finished = bool(st.session_state.ending)
story = get_active_profile()["story"]

if story_col1.button(
    f"{story['item_icon']} {story['search_label']}",
    disabled=st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "search_book",
        "message": story["search_message"],
    }
    st.rerun()

if story_col2.button(
    f"✨ {story['cooperate_label']}",
    disabled=not st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "seal_book",
        "message": story["cooperate_message"],
    }
    st.rerun()

if story_col3.button(
    f"💥 {story['hostile_label']}",
    disabled=not st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "steal_book",
        "message": story["hostile_message"],
    }
    st.rerun()

st.caption("遊戲動作：按鈕位於輸入框上方，按下後會自動送出指令。")
action_col1, action_col2, action_col3, action_col4 = st.columns(4)

if action_col1.button("⚔️ 攻擊", use_container_width=True):
    st.session_state.pending_action = {
        "type": "attack",
        "message": f"我拔出長劍，朝{npc_name}發動攻擊。",
    }
    st.rerun()

if action_col2.button("🛡️ 防禦", use_container_width=True):
    st.session_state.pending_action = {
        "type": "defend",
        "message": "我舉起盾牌，採取防禦姿態。",
    }
    st.rerun()

if action_col3.button("🩹 使用藥水", use_container_width=True):
    st.session_state.pending_action = {
        "type": "heal",
        "message": "我使用一瓶治療藥水，先處理自己的傷勢。",
    }
    st.rerun()

heavy_attack_label = (
    "⚡ 重擊" if st.session_state.skill_cooldown == 0 else "⚡ 重擊冷卻中"
)
if action_col4.button(
    heavy_attack_label,
    disabled=st.session_state.skill_cooldown > 0,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "heavy_attack",
        "message": f"我集中力量，朝{npc_name}施展重擊。",
    }
    st.rerun()

player_message = st.chat_input(f"輸入你想對{npc_name}說的話")
player_turn = "talk"

if st.session_state.pending_action:
    player_turn = st.session_state.pending_action["type"]
    player_message = st.session_state.pending_action["message"]
    st.session_state.pending_action = None

if player_message:
    action_result, action_is_available = prepare_player_action(player_turn)
    relationship_intent = classify_relationship_intent(
        player_message,
        player_turn,
    )
    if player_turn in {"event_help", "event_observe"}:
        relationship_intent = "neutral"
    if not action_is_available:
        relationship_intent = "neutral"

    event_result = handle_event_action(player_turn)
    story_result = handle_story_action(player_turn)
    action_result = "\n\n".join(
        filter(None, [action_result, event_result, story_result])
    )
    st.session_state.messages.append(
        {
            "role": "user",
            "content": player_message,
        }
    )

    threat_level = "無"

    if use_local_ai:
        try:
            with st.spinner(f"{npc_name}正在判斷你的意圖……"):
                decision = create_ai_decision(
                    player_message,
                    relationship_intent,
                )

            npc_reply = decision.reply
            final_emotion = decision.emotion
            final_action = decision.action
            threat_level = threat_level_from_intent(relationship_intent)
            relationship_change = relationship_change_from_intent(
                relationship_intent
            )

            # 關係與戰鬥屬於遊戲硬規則，避免模型誤把外部事件算在玩家頭上。
            if relationship_intent == "direct_attack":
                final_emotion = "生氣"
                final_action = "進入戰鬥並反擊玩家"
            elif relationship_intent == "direct_hostile":
                final_emotion = "警戒"
                final_action = "準備防衛並警告玩家"
            elif relationship_intent == "direct_insult":
                final_emotion = "生氣"
                final_action = "拒絕與玩家合作"
            elif relationship_intent == "external_event":
                final_emotion = "警戒"
                final_action = "留意外部威脅"
            elif relationship_intent == "personal_need":
                final_emotion = "平靜"
                final_action = "評估玩家的需求"

            st.session_state.emotion = (
                f"{final_emotion} {EMOTION_ICONS[final_emotion]}"
            )
            st.session_state.action = final_action
            st.session_state.affinity = max(
                -100,
                min(
                    100,
                    st.session_state.affinity + relationship_change,
                ),
            )
            update_quest()
            st.session_state.ai_status = "Qwen3 8B（AI 決策）"
            st.session_state.connection_warning = False
        except Exception:
            npc_reply = apply_rule_decision(
                player_message,
                relationship_intent,
            )
            threat_level = detect_threat_by_rules(relationship_intent)
            st.session_state.ai_status = "規則模式（自動備援）"
            st.session_state.connection_warning = True
    else:
        npc_reply = apply_rule_decision(
            player_message,
            relationship_intent,
        )
        threat_level = detect_threat_by_rules(relationship_intent)
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False

    if event_result and player_turn == "event_help":
        st.session_state.emotion = "開心 😊"
        st.session_state.action = "與玩家共同處理突發事件"
    elif event_result and player_turn == "event_observe":
        st.session_state.emotion = "警戒 😠"
        st.session_state.action = "持續監控突發事件"

    combat_result = resolve_combat(threat_level, player_turn, action_result)
    if combat_result:
        npc_reply = f"{npc_reply}\n\n---\n\n{combat_result}"

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": npc_reply,
        }
    )
    st.rerun()
