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

NPC_PROFILES = {
    "艾琳": {
        "name": "艾琳",
        "icon": "🧙",
        "identity": "王城圖書館守護者",
        "personality": "冷靜、謹慎、富有好奇心",
        "mission": "保護圖書館並協助可信任的訪客",
        "initial_emotion": "平靜 😐",
        "initial_action": "觀察玩家",
    },
    "洛恩": {
        "name": "洛恩",
        "icon": "🔮",
        "identity": "古代封印術士",
        "personality": "理性、寡言、對失落魔法十分執著",
        "mission": "阻止封印魔法書落入危險之人手中",
        "initial_emotion": "警戒 😠",
        "initial_action": "檢查封印結界",
    },
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
        "story_stage": "序章：圖書館的異常",
        "magic_book_found": False,
        "ending": "",
        "combat_message": "尚未進入戰鬥",
        "pending_action": None,
    }


def get_active_profile():
    return NPC_PROFILES[st.session_state.active_npc]


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

    if active_npc not in st.session_state.npc_states:
        st.session_state.npc_states[active_npc] = create_default_npc_state(active_npc)

    for key, value in st.session_state.npc_states[active_npc].items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


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
    """依關係、劇情物品與結局更新目前任務。"""

    npc_name = get_active_profile()["name"]

    if st.session_state.ending:
        st.session_state.quest = f"結局完成：{st.session_state.ending}"
        return

    if st.session_state.magic_book_found:
        if st.session_state.affinity >= 60:
            st.session_state.quest = f"終章任務：與{npc_name}封印魔法書"
        elif st.session_state.affinity <= -20:
            st.session_state.quest = "敵對事件：爭奪封印魔法書"
        else:
            st.session_state.quest = "第二章：魔法書等待你的選擇"
        return

    if st.session_state.affinity >= 60:
        st.session_state.quest = "盟友任務：尋找封印魔法書"
    elif st.session_state.affinity >= 20:
        st.session_state.quest = f"任務解鎖：請與{npc_name}一起搜尋魔法書"
    elif st.session_state.affinity <= -60:
        st.session_state.quest = "敵對事件：守護者追捕令"
    elif st.session_state.affinity <= -20:
        st.session_state.quest = f"{npc_name}拒絕與玩家合作"
    else:
        st.session_state.quest = "尚未解鎖"


def handle_story_action(player_turn):
    """處理任務按鈕，讓關係值決定合作或敵對的劇情分支。"""

    npc_name = get_active_profile()["name"]

    if player_turn not in {"search_book", "seal_book", "steal_book"}:
        return ""

    if st.session_state.ending:
        return f"🏁 劇情已完成：{st.session_state.ending}。"

    if player_turn == "search_book":
        if st.session_state.magic_book_found:
            return "📜 你已經找到封印魔法書。"
        if st.session_state.affinity < 20:
            st.session_state.emotion = "警戒 😠"
            st.session_state.action = "拒絕交出圖書館線索"
            st.session_state.affinity = max(-100, st.session_state.affinity - 5)
            update_quest()
            return f"📜 {npc_name}尚未信任你，不會帶你進入封存書庫。"

        st.session_state.magic_book_found = True
        st.session_state.story_stage = "第二章：封印的抉擇"
        st.session_state.emotion = "好奇 🤔"
        st.session_state.action = "與玩家研究封印魔法書"
        update_quest()
        return f"📜 你與{npc_name}在封存書庫找到了一本散發微光的魔法書。"

    if player_turn == "seal_book":
        if not st.session_state.magic_book_found:
            return "✨ 你還沒有找到魔法書，無法進行封印。"
        if st.session_state.affinity < 60:
            return f"✨ {npc_name}仍不願把封印儀式交給你，需要更高的信任。"

        st.session_state.story_stage = "結局：守護者盟約"
        st.session_state.ending = "守護者盟約（合作結局）"
        st.session_state.emotion = "開心 😊"
        st.session_state.action = "與玩家共同完成封印儀式"
        st.session_state.affinity = min(100, st.session_state.affinity + 10)
        update_quest()
        return f"✨ 封印儀式完成。{npc_name}邀請你成為圖書館的新任盟友。"

    if not st.session_state.magic_book_found:
        return "📕 你還沒有找到魔法書，無法奪取它。"

    st.session_state.story_stage = "結局：圖書館的叛徒"
    st.session_state.ending = "圖書館的叛徒（敵對結局）"
    st.session_state.emotion = "生氣 😡"
    st.session_state.action = "啟動守衛追捕玩家"
    st.session_state.affinity = -100
    update_quest()
    return f"📕 你奪走魔法書。{npc_name}啟動圖書館的守衛封鎖出口。"


def create_save_data():
    """整理可攜式 JSON 存檔需要保存的遊戲狀態。"""

    save_active_npc_state()

    return {
        "save_version": 6,
        "active_npc": st.session_state.active_npc,
        "messages": st.session_state.messages,
        "emotion": st.session_state.emotion,
        "action": st.session_state.action,
        "affinity": st.session_state.affinity,
        "quest": st.session_state.quest,
        "npc_hp": st.session_state.npc_hp,
        "player_hp": st.session_state.player_hp,
        "potions": st.session_state.potions,
        "weapon": st.session_state.weapon,
        "armor": st.session_state.armor,
        "battle_turn": st.session_state.battle_turn,
        "skill_cooldown": st.session_state.skill_cooldown,
        "story_stage": st.session_state.story_stage,
        "magic_book_found": st.session_state.magic_book_found,
        "ending": st.session_state.ending,
        "combat_message": st.session_state.combat_message,
    }


def load_save_data(data):
    """驗證並載入 JSON 存檔，避免錯誤數值破壞遊戲狀態。"""

    if not isinstance(data, dict):
        raise ValueError("存檔格式不是 JSON 物件")

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("對話記憶格式不正確")

    save_active_npc_state()
    saved_npc = str(data.get("active_npc", "艾琳"))
    if saved_npc not in NPC_PROFILES:
        saved_npc = "艾琳"
    st.session_state.active_npc = saved_npc

    valid_messages = []
    for message in messages[-30:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            valid_messages.append({"role": role, "content": content})

    st.session_state.messages = valid_messages
    st.session_state.emotion = str(data.get("emotion", "平靜 😐"))
    st.session_state.action = str(data.get("action", "觀察玩家"))
    st.session_state.affinity = max(-100, min(100, int(data.get("affinity", 0))))
    st.session_state.npc_hp = max(0, min(100, int(data.get("npc_hp", 100))))
    st.session_state.player_hp = max(
        0,
        min(100, int(data.get("player_hp", 100))),
    )
    st.session_state.potions = max(0, min(9, int(data.get("potions", 3))))
    saved_weapon = str(data.get("weapon", "練習長劍"))
    saved_armor = str(data.get("armor", "旅人斗篷"))
    st.session_state.weapon = (
        saved_weapon if saved_weapon in WEAPONS else "練習長劍"
    )
    st.session_state.armor = saved_armor if saved_armor in ARMORS else "旅人斗篷"
    st.session_state.battle_turn = max(
        0,
        min(99, int(data.get("battle_turn", 0))),
    )
    st.session_state.skill_cooldown = max(
        0,
        min(2, int(data.get("skill_cooldown", 0))),
    )
    st.session_state.story_stage = str(
        data.get("story_stage", "序章：圖書館的異常")
    )
    st.session_state.magic_book_found = bool(data.get("magic_book_found", False))
    st.session_state.ending = str(data.get("ending", ""))
    st.session_state.combat_message = str(
        data.get("combat_message", "尚未進入戰鬥")
    )
    st.session_state.ai_status = "規則模式"
    st.session_state.connection_warning = False
    update_quest()
    save_active_npc_state()


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


def detect_threat_by_rules(player_text):
    """規則模式：判斷玩家文字是否包含挑釁、威脅或實際攻擊。"""

    text = player_text.lower()

    attack_words = [
        "攻擊",
        "擊中",
        "施放",
        "砍",
        "刺",
        "射擊",
        "火球",
        "殺了",
        "打倒",
    ]
    threat_words = ["威脅", "否則", "我要摧毀", "我要殺", "準備攻擊"]
    insult_words = ["討厭", "騙子", "笨蛋", "沒用", "滾開"]

    if any(word in text for word in attack_words):
        return "攻擊"
    if any(word in text for word in threat_words):
        return "威脅"
    if any(word in text for word in insult_words):
        return "挑釁"
    return "無"


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


def apply_rule_decision(player_text):
    """執行規則式情緒、行為、關係與回覆判斷。"""

    emotion, action = decide_state(player_text)
    st.session_state.emotion = emotion
    st.session_state.action = action
    update_affinity_by_rules(player_text)
    return create_rule_reply(player_text)


def create_ai_decision(player_message):
    """要求 Qwen3 同時產生台詞、情緒、行為與關係變化。"""

    profile = get_active_profile()
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
- 是否已找到封印魔法書：{st.session_state.magic_book_found}
- 目前結局：{st.session_state.ending or "尚未決定"}
- {profile["name"]}生命值：{st.session_state.npc_hp} / 100
- 玩家生命值：{st.session_state.player_hp} / 100
- 玩家武器：{st.session_state.weapon}，額外攻擊傷害 +{WEAPONS[st.session_state.weapon]["attack_bonus"]}
- 玩家防具：{st.session_state.armor}，每次受到傷害 -{ARMORS[st.session_state.armor]["damage_reduction"]}
- 戰鬥回合：{st.session_state.battle_turn}
- 重擊冷卻：{st.session_state.skill_cooldown} 個行動（0 代表可使用）

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
- 玩家宣稱已攻擊、傷害或殺死{profile["name"]}，也必須判定為「攻擊」
- 玩家用括號描述的動作仍然算是實際行動，不能當成無關文字
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
        "封印魔法書："
        + ("已找到 📜" if st.session_state.magic_book_found else "尚未找到")
    )
    if st.session_state.ending:
        st.success(f"已達成結局：{st.session_state.ending}")
    else:
        st.caption(f"先取得{profile['name']}的信任，再從對話框上方選擇劇情行動。")

    if st.button(f"清除{profile['name']}的對話並重置"):
        st.session_state.messages = []
        st.session_state.emotion = profile["initial_emotion"]
        st.session_state.action = profile["initial_action"]
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False
        st.session_state.affinity = 0
        st.session_state.quest = "尚未解鎖"
        st.session_state.npc_hp = 100
        st.session_state.player_hp = 100
        st.session_state.potions = 3
        st.session_state.weapon = "練習長劍"
        st.session_state.armor = "旅人斗篷"
        st.session_state.battle_turn = 0
        st.session_state.skill_cooldown = 0
        st.session_state.story_stage = "序章：圖書館的異常"
        st.session_state.magic_book_found = False
        st.session_state.ending = ""
        st.session_state.combat_message = "尚未進入戰鬥"
        st.session_state.pending_action = None
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

st.caption("劇情行動：關係值會決定你能走向合作或敵對結局。")
story_col1, story_col2, story_col3 = st.columns(3)
story_finished = bool(st.session_state.ending)

if story_col1.button(
    "📜 搜尋魔法書",
    disabled=st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "search_book",
        "message": "我希望與你一起搜尋封印魔法書。",
    }
    st.rerun()

if story_col2.button(
    "✨ 封印魔法書",
    disabled=not st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "seal_book",
        "message": "我願意與你完成封印魔法書的儀式。",
    }
    st.rerun()

if story_col3.button(
    "📕 奪取魔法書",
    disabled=not st.session_state.magic_book_found or story_finished,
    use_container_width=True,
):
    st.session_state.pending_action = {
        "type": "steal_book",
        "message": "我奪取封印魔法書並拒絕交還。",
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
    story_result = handle_story_action(player_turn)
    if story_result:
        action_result = "\n\n".join(filter(None, [action_result, story_result]))
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
                decision = create_ai_decision(player_message)

            npc_reply = decision.reply
            threat_level = decision.threat_level
            final_emotion = decision.emotion
            final_action = decision.action
            relationship_change = decision.relationship_change

            # 戰鬥屬於遊戲硬規則，避免模型把真正攻擊輕描淡寫。
            if decision.threat_level == "攻擊" or (
                player_turn in {"attack", "heavy_attack"}
                and action_is_available
            ):
                threat_level = "攻擊"
                final_emotion = "生氣"
                final_action = "進入戰鬥並反擊玩家"
                relationship_change = -20
            elif decision.threat_level == "威脅":
                final_emotion = "警戒"
                final_action = "準備防衛並警告玩家"
                relationship_change = min(relationship_change, -15)
            elif decision.threat_level == "挑釁":
                relationship_change = min(relationship_change, -5)

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
            npc_reply = apply_rule_decision(player_message)
            threat_level = detect_threat_by_rules(player_message)
            if player_turn in {"attack", "heavy_attack"} and action_is_available:
                threat_level = "攻擊"
            st.session_state.ai_status = "規則模式（自動備援）"
            st.session_state.connection_warning = True
    else:
        npc_reply = apply_rule_decision(player_message)
        threat_level = detect_threat_by_rules(player_message)
        if player_turn in {"attack", "heavy_attack"} and action_is_available:
            threat_level = "攻擊"
        st.session_state.ai_status = "規則模式"
        st.session_state.connection_warning = False

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
