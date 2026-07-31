# AI NPC 對話系統

使用 Python、Streamlit 與本機大型語言模型打造的互動式 AI NPC 作品集專案。

玩家可以在瀏覽器中與王城圖書館守護者「艾琳」對話。艾琳會根據完整語意調整情緒、行為與關係值，並能進入戰鬥、解鎖事件，以及保存遊戲進度。

## 線上展示

[立即開啟 AI NPC 對話系統](https://ai-npc-portfolio-7s6r7unl6twecq5bhpkjac.streamlit.app/)

> 公開網站使用規則式備援模式。本機安裝 Ollama 與 Qwen3 後，可啟用完整的生成式 AI 決策。

## 主要功能

- 瀏覽器即時對話介面
- NPC 角色背景與個性設定
- 最近對話的短期記憶
- Qwen3 8B 本機生成式對話
- AI 自主判斷情緒、行為與關係變化
- `-100～100` 雙向關係值
- 盟友任務與敵對事件
- 玩家與 NPC 生命值
- 命中、閃避、傷害與反擊機制
- 可點擊的攻擊、防禦與治療藥水行動
- 可選武器與防具，分別影響攻擊傷害與受到的傷害
- 規則式離線／雲端備援模式
- JSON 遊戲進度下載與載入
- 一鍵清除對話並重置狀態

## NPC 設定

- 名字：艾琳
- 身分：王城圖書館守護者
- 個性：冷靜、謹慎、富有好奇心
- 使命：保護圖書館並協助可信任的訪客

## 系統流程

玩家送出訊息後，系統會：

1. 保存最新訊息至短期記憶。
2. 判斷玩家是在友善交流、挑釁、威脅或攻擊。
3. 更新 NPC 的情緒、行為與關係值。
4. 產生符合角色與目前狀態的回覆。
5. 將目前選擇的武器、防具與生命值帶入戰鬥計算。
6. 若使用攻擊、防禦或治療藥水，Python 會套用對應的遊戲規則。
7. 若發生戰鬥，由 Python 計算命中、傷害、減傷與反擊。
8. 更新生命值、任務與敵對事件。

AI 負責理解語意與角色表現；Python 負責數值範圍、戰鬥結果和狀態一致性，避免玩家只用文字自行宣告攻擊成功。

## 使用技術

- Python 3.13
- Streamlit 1.60
- Ollama
- Qwen3 8B
- Pydantic Structured Outputs
- Streamlit Session State
- Git 與 GitHub
- Streamlit Community Cloud

## 執行模式

### 規則模式

- 不需要本機大型語言模型。
- 適用於 Streamlit 公開網站。
- 使用關鍵詞規則產生情緒、關係與行為結果。

### 本機 Qwen3 AI 模式

- 需要先安裝 Ollama 並下載 `qwen3:8b`。
- 使用本機 NVIDIA GPU 執行生成式對話。
- Qwen3 會回傳結構化的台詞、情緒、行為、威脅等級與關係變化。
- AI 無法連線或輸出格式錯誤時，自動切換至規則模式。

## 在 Windows 本機執行

### 1. 下載專案

```powershell
git clone https://github.com/Liaoyoun/ai-npc-portfolio.git
cd ai-npc-portfolio
```

### 2. 建立虛擬環境

```powershell
python -m venv .venv
```

### 3. 啟用虛擬環境

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4. 安裝 Python 套件

```powershell
python -m pip install -r requirements.txt
```

### 5. 啟動網站

```powershell
python -m streamlit run app.py
```

開啟瀏覽器：

```text
http://localhost:8501
```

## 啟用本機 Qwen3

1. 安裝 [Ollama for Windows](https://ollama.com/download/windows)。
2. 在 PowerShell 下載模型：

```powershell
ollama pull qwen3:8b
```

3. 確認模型存在：

```powershell
ollama list
```

4. 啟動 Streamlit 後，在左側開啟「啟用本機 Qwen3 AI」。

## 存檔與讀檔

- 點擊「下載目前存檔」取得 `ai_npc_save.json`。
- 存檔包含對話、關係值、任務、生命值、治療藥水、武器、防具與最近戰鬥結果。
- 在「選擇先前的 JSON 存檔」上傳檔案，再點擊載入。
- 為控制檔案大小，讀檔時最多保留最近 30 則對話。
- 存檔不包含 API 金鑰或其他機密資料。

## 專案結構

```text
ai-npc-portfolio/
├── app.py
├── README.md
├── requirements.txt
└── .gitignore
```

## 目前限制

- Streamlit Community Cloud 無法直接使用玩家電腦上的 Ollama，因此公開版預設使用規則模式。
- 遊戲狀態預設存於瀏覽器工作階段；需要長期保存時須下載 JSON 存檔。
- 戰鬥系統目前採用簡化的隨機命中與傷害計算。

## 未來規劃

- 玩家技能樹與特殊招式
- 多名 NPC 與角色選擇
- 正式任務流程與分支結局
- SQLite 長期記憶
- NPC 頭像、場景與音效
- 自動化測試與模組化專案結構
