<div align="center">
  <h1>💎 HexSkin Studio</h1>
  <p><strong>LoL Loot Crafter, Disenchanter, Auto-Equipper & Arena Bravery Synchronizer</strong></p>

  <p>
    <img src="https://img.shields.io/badge/Vibe--Coded-100%25-FF69B4?style=flat&logo=sparkles&logoColor=white" alt="Vibe Coded" />
    <img src="https://img.shields.io/badge/Fun%20Project-Non--Commercial-blueviolet?style=flat" alt="Fun Project" />
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python Version" />
    <img src="https://img.shields.io/badge/League%20Client-LCU%20API-C8AA6E?style=flat&logo=leagueoflegends&logoColor=white" alt="LCU API" />
    <img src="https://img.shields.io/badge/Vanguard%20Safe-100%25-2ECC71?style=flat" alt="Vanguard Safe" />
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License" />
  </p>
</div>

> [!NOTE]
> ### 🎮 A Note from the Author
> This project is **100% "Vibe Coded"** and built purely as a **fun community project**. It is completely free, open-source, and non-commercial. I do not earn any money with this. It was created simply to fix the frustrating Arena Bravery skin selection issue and make Hextech loot crafting fast and effortless for League players! ✨

---

## 🚀 1-Click Download (For Beginners)

No Python, coding knowledge, or command line required!

1. Go to the **[Latest Release (v1.0.1)](https://github.com/zaryar/1Skin/releases/tag/v1.0.1)**.
2. Download **`HexSkinStudio_v1.0.1_Windows.zip`**.
3. Extract the ZIP folder anywhere on your PC.
4. Make sure League of Legends is running, then double-click **`HexSkinStudio.exe`**.
5. Your browser will automatically pop open with the HexSkin Studio dashboard!


> [!TIP]
> **Windows SmartScreen Note:** Because this is an open-source, community-built `.exe` without an expensive paid corporate certificate, Windows Defender / SmartScreen might show a blue prompt on the first launch. Simply click **"More info"** &rarr; **"Run anyway"**.

---

## 🌟 Overview

**HexSkin Studio & HexSocial Hub** is a unified, Hextech-themed single-page web suite designed for League of Legends players:

1. **HexSkin Studio**: Intelligently crafts missing champion skins with Orange Essence, bulk disenchants extra shards, and provides real-time champion select auto-equipping alongside an automated synchronizer for **Arena Bravery**.
2. **HexSocial (Friend Manager)**: A dedicated, full-featured Social Hub providing advanced folder/group management, batch organization of friends, rich real-time presence indicators, friend requests management (in/out), blocked players manager, and live profile hovercard inspections.

---

## 📸 Modules & Features

### 🛠️ 1. Skin Crafter (Missing Skins)
> Finds all owned champions where you **own 0 skins** and allows you to unlock them with Orange Essence in 1 click.

---

### 💎 2. Smart Disenchanter (Extra Shards)
> Identifies loot shards for champions where you **already own at least one skin**, letting you safely disenchant duplicates for maximum Orange Essence gain.

---

### 🎨 3. Auto-Equipper Loadouts
> Select your favorite skin for any champion. A lightweight background listener automatically equips your chosen skin during Champion Select across SoloQ, ARAM, Normal, and Arena.

---

### 👥 4. HexSocial: Friend Manager
> A dedicated social manager providing:
> - **Folder & Group Management**: Create, rename, delete custom folders and categorize friends.
> - **Batch Operations**: Multi-select friends and move them between folders in 1 click.
> - **Real-Time Live Presence**: Track friends in-game with match timer, champion played, game mode (Ranked, Arena, ARAM, TFT), and party status.
> - **Profile Inspector & Hovercard**: View ranked tier, win/loss stats, mastery, and edit private notes/nicknames.
> - **Friend Requests & Blocked Manager**: Accept/decline incoming requests, cancel outgoing requests, and manage blocked users.
> - **Personal Status Controller**: Change your online status (Online, Away, DND, Invisible/Offline) and custom status message.

---

### ⚡ 5. Arena Bravery Skin Sync
> In **Arena Bravery**, Riot server-side locks champions instantly, defaulting to your *last used skin*. This automated tool creates a quick custom lobby loop that locks in and selects all your configured favorite skins on Riot's backend account database in under 2 minutes.

---

### 🚽 6. Smart Break Delay (Restroom Break & Reconnect Controller)
> Safely pauses loading into the match after Champ Select so you can take a quick bathroom break without fear of remakes:
> - **100% Vanguard Safe**: Uses the official League client reconnect API (`POST /lol-gameflow/v1/reconnect`) without memory hooks or DLL injections.
> - **Configurable Safety Timer**: Set a safe delay (e.g. 75 seconds, well before the 1:05 minion spawn and 1:30 remake threshold).
> - **1-Click Instant Reconnect**: Big **`[ 🚀 RECONNECT NOW ]`** button with live countdown digits and progress bar. Auto-reconnects safely if you run out of time.

---

## ✨ Features

- **Smart Break Delay (Bio Break)**: Pauses the loading screen launch after Champ Select with a safe countdown timer and 1-click Reconnect.
- **Dynamic Recipe Checking**: Queries `GET /lol-loot/v1/recipes/initial-item/{loot_id}` to dynamically verify recipe slot requirements (e.g. 2-slot `[loot_id, "CURRENCY_cosmetic"]` for upgrades and 1-slot `[loot_id]` for disenchanting).
- **Real-Time Auto-Equipper**: Seamless background thread polling `GET /lol-champ-select/v1/session` to auto-equip your saved skin preference when locking in a champion.
- **Arena Bravery 1-Click Sync**: Fully automated Custom Game loop (`POST /lol-lobby/v1/lobby/custom/start-champ-select` & `cancel-champ-select`) to persist preferred skins across Riot's servers for Bravery picks.
- **Live Hextech Header**: Real-time display of summoner level, icon, and wallet balances (**Orange Essence**, **Blue Essence**, **Mythic Essence**, and **RP**).
- **Audio Feedback**: Optional toggleable Hextech sound alerts when a skin is automatically equipped.

---

## 🛡️ Anti-Cheat & Vanguard Safety

- **100% Safe & Not Bannable**: HexSkin Studio interacts exclusively with the local **League Client Update (LCU) HTTPS/WAMP REST API** running on `127.0.0.1`.
- **Zero Game Memory Modification**: It **never** reads, writes, or injects code into `League of Legends.exe`.
- It uses the exact same client endpoints as certified third-party companion apps such as **Blitz.gg, Porofessor, Mobalytics, and RuneBook**.

---

## 💻 Running from Source (For Developers)

### Prerequisites
- Windows 10 / 11
- [Python 3.10+](https://www.python.org/downloads/)
- League of Legends client running and logged in

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/zaryar/1Skin.git
   cd 1Skin
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch HexSkin Studio:**
   - **Double-click:** `start_app.bat`
   - **Or run via terminal:**
     ```bash
     python app.py
     ```

4. **Open your browser:**
   Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

## ⚡ Arena Bravery Sync Usage

To synchronize your favorite skins for **Arena Bravery**:
1. Open the League of Legends client and create a **Custom Game** lobby (Blind Pick).
2. Open HexSkin Studio at `http://127.0.0.1:5000` and switch to the **Auto-Equipper** tab.
3. Click **⚡ Bravery Sync** in the top right, then click **Start Sync**.
4. Alternatively, you can run `sync_bravery.bat` or `python sync_bravery_skins.py` from your terminal.

---

## 📁 Project Structure

```
├── app.py                   # Main Flask application and background listener
├── lcu_client.py            # LCU connection manager, lockfile parser & recipe handler
├── sync_bravery_skins.py    # Automated Custom Game skin synchronizer for Arena Bravery
├── loadout.json             # Saved user skin preferences (Champion ID -> Skin ID)
├── start_app.bat            # 1-Click Windows web app launcher
├── sync_bravery.bat         # 1-Click Windows Bravery synchronizer launcher
├── requirements.txt         # Python package dependencies
├── templates/
│   └── index.html           # Single Page Application HTML markup
├── static/
│   ├── css/
│   │   └── style.css        # Hextech-themed modern responsive CSS
│   └── js/
│       └── app.js           # Client-side routing, data polling & UI state
└── docs/
    └── screenshots/         # UI showcase images
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
