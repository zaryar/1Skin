import base64
import json
import logging
import os
import requests
import sys
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


LOCKFILE_PATH = r"C:\Riot Games\League of Legends\lockfile"

def get_data_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

LOADOUT_FILE = os.path.join(get_data_dir(), "loadout.json")

logger = logging.getLogger("lcu_client")


def get_lcu_session():
    """
    Reads the LCU lockfile and returns an authenticated requests.Session and base_url.
    Returns (None, None) if lockfile does not exist.
    """
    if not os.path.exists(LOCKFILE_PATH):
        return None, None
    try:
        with open(LOCKFILE_PATH, "r") as f:
            data = f.read().split(":")
            if len(data) < 5:
                return None, None
            port, password, protocol = data[2], data[3], data[4]

        session = requests.Session()
        token = base64.b64encode(f"riot:{password}".encode("ascii")).decode("ascii")
        session.headers.update({
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        session.verify = False
        return session, f"{protocol}://127.0.0.1:{port}"
    except Exception as e:
        logger.error(f"Error reading lockfile or initializing session: {e}")
        return None, None

def load_loadout():
    """Loads saved skin preferences from loadout.json."""
    if os.path.exists(LOADOUT_FILE):
        try:
            with open(LOADOUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {LOADOUT_FILE}: {e}")
            return {}
    return {}

def save_loadout(data):
    """Saves skin preferences to loadout.json."""
    try:
        with open(LOADOUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {LOADOUT_FILE}: {e}")
        return False

def get_player_status():
    """
    Fetches summoner details, currencies (OE, BE, RP, ME), and LCU status.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {
            "connected": False,
            "message": "League of Legends Client nicht gefunden. Bitte starte das Spiel."
        }

    try:
        summoner_res = session.get(f"{base_url}/lol-summoner/v1/current-summoner", timeout=3)
        if summoner_res.status_code != 200:
            return {"connected": False, "message": "Summoner konnte nicht geladen werden."}
        
        summoner = summoner_res.json()
        name = summoner.get("gameName") or summoner.get("displayName") or "Summoner"
        tag = summoner.get("tagLine") or ""
        icon_id = summoner.get("profileIconId", 29)
        level = summoner.get("summonerLevel", 1)

        # Loot / Currencies
        loot_res = session.get(f"{base_url}/lol-loot/v1/player-loot", timeout=4)
        oe = 0
        be = 0
        rp = 0
        me = 0
        
        if loot_res.status_code == 200:
            for item in loot_res.json():
                lname = item.get("lootName", "")
                cnt = item.get("count", 0)
                if lname == "CURRENCY_cosmetic":
                    oe = cnt
                elif lname == "CURRENCY_champion":
                    be = cnt
                elif lname == "CURRENCY_RP":
                    rp = cnt
                elif lname == "CURRENCY_mythic":
                    me = cnt

        # Check Champ Select Status
        cs_res = session.get(f"{base_url}/lol-champ-select/v1/session", timeout=2)
        in_champ_select = (cs_res.status_code == 200)

        return {
            "connected": True,
            "summoner": {
                "id": summoner.get("summonerId"),
                "name": name,
                "tag": tag,
                "displayName": f"{name}#{tag}" if tag else name,
                "level": level,
                "iconId": icon_id,
                "iconUrl": f"/lcu-img/lol-game-data/assets/v1/profile-icons/{icon_id}.jpg"
            },
            "currencies": {
                "oe": oe,
                "be": be,
                "rp": rp,
                "me": me
            },
            "inChampSelect": in_champ_select
        }
    except Exception as e:
        logger.error(f"Error in get_player_status: {e}")
        return {"connected": False, "message": str(e)}

def get_crafter_data():
    """
    Finds owned champions without non-base skins that have matching skin shards in loot.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        summoner_res = session.get(f"{base_url}/lol-summoner/v1/current-summoner")
        summoner_id = summoner_res.json().get("summonerId")

        # 1. Fetch champions
        champs_res = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions")
        if champs_res.status_code != 200:
            return {"success": False, "error": "Champions could not be loaded"}
        
        champions = champs_res.json()
        champs_without_skins = {}

        for champ in champions:
            champ_id = champ.get("id")
            if champ_id == -1 or not champ.get("ownership", {}).get("owned", False):
                continue
            
            has_skin = any(
                skin.get("ownership", {}).get("owned")
                for skin in champ.get("skins", [])
                if not skin.get("isBase")
            )
            
            if not has_skin:
                portrait = champ.get("squarePortraitPath") or champ.get("portraitPath") or f"/lol-game-data/assets/v1/champion-icons/{champ_id}.png"
                champs_without_skins[champ_id] = {
                    "id": champ_id,
                    "name": champ.get("name"),
                    "img": portrait
                }

        # 2. Fetch loot & filter skin shards
        loot_res = session.get(f"{base_url}/lol-loot/v1/player-loot")
        if loot_res.status_code != 200:
            return {"success": False, "error": "Loot could not be loaded"}
        
        loot = loot_res.json()
        oe_count = 0
        shards_by_champ = {}

        for item in loot:
            if item.get("lootName") == "CURRENCY_cosmetic":
                oe_count = item.get("count", 0)
                continue

            item_type = item.get("type")
            if item_type in ["SKIN_RENTAL", "CHAMPION_SKIN_RENTAL", "SKIN"]:
                champ_id = item.get("parentStoreItemId")
                if champ_id in champs_without_skins:
                    if champ_id not in shards_by_champ:
                        shards_by_champ[champ_id] = {
                            "champ": champs_without_skins[champ_id],
                            "shards": []
                        }
                    
                    shards_by_champ[champ_id]["shards"].append({
                        "lootId": item.get("lootId"),
                        "lootName": item.get("lootName"),
                        "skinName": item.get("itemDesc"),
                        "splashPath": item.get("splashPath") or item.get("tilePath"),
                        "cost": item.get("upgradeEssenceValue", 0),
                        "disenchantValue": item.get("disenchantValue", 0),
                        "count": item.get("count", 1),
                        "rarity": item.get("rarity", "")
                    })

        return {
            "success": True,
            "oe": oe_count,
            "champions": list(shards_by_champ.values())
        }
    except Exception as e:
        logger.error(f"Error in get_crafter_data: {e}")
        return {"success": False, "error": str(e)}

def get_disenchanter_data():
    """
    Finds skin shards in loot for champions where the player ALREADY owns at least one skin.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        summoner_res = session.get(f"{base_url}/lol-summoner/v1/current-summoner")
        summoner_id = summoner_res.json().get("summonerId")

        # 1. Fetch champions
        champs_res = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions")
        if champs_res.status_code != 200:
            return {"success": False, "error": "Champions could not be loaded"}
        
        champions = champs_res.json()
        champs_with_skins = {}

        for champ in champions:
            champ_id = champ.get("id")
            if champ_id == -1:
                continue
            
            owned_skins = []
            for skin in champ.get("skins", []):
                if skin.get("ownership", {}).get("owned") and not skin.get("isBase"):
                    splash = skin.get("splashPath") or skin.get("uncenteredSplashPath") or skin.get("tilePath")
                    owned_skins.append({
                        "id": skin.get("id"),
                        "name": skin.get("name"),
                        "img": splash
                    })
            
            if owned_skins:
                champs_with_skins[champ_id] = {
                    "id": champ_id,
                    "name": champ.get("name"),
                    "portrait": champ.get("squarePortraitPath") or champ.get("portraitPath"),
                    "ownedSkins": owned_skins
                }

        # 2. Loot items
        loot_res = session.get(f"{base_url}/lol-loot/v1/player-loot")
        if loot_res.status_code != 200:
            return {"success": False, "error": "Loot could not be loaded"}

        loot = loot_res.json()
        oe_count = 0
        shards_to_disenchant = []

        for item in loot:
            if item.get("lootName") == "CURRENCY_cosmetic":
                oe_count = item.get("count", 0)
                continue

            item_type = item.get("type")
            if item_type in ["SKIN_RENTAL", "CHAMPION_SKIN_RENTAL", "SKIN"]:
                champ_id = item.get("parentStoreItemId")
                if champ_id in champs_with_skins:
                    shards_to_disenchant.append({
                        "lootId": item.get("lootId"),
                        "lootName": item.get("lootName"),
                        "champId": champ_id,
                        "champName": champs_with_skins[champ_id]["name"],
                        "champPortrait": champs_with_skins[champ_id]["portrait"],
                        "skinName": item.get("itemDesc"),
                        "splashPath": item.get("splashPath") or item.get("tilePath"),
                        "disenchantValue": item.get("disenchantValue", 0),
                        "upgradeCost": item.get("upgradeEssenceValue", 0),
                        "count": item.get("count", 1),
                        "ownedSkins": champs_with_skins[champ_id]["ownedSkins"]
                    })

        return {
            "success": True,
            "oe": oe_count,
            "shards": shards_to_disenchant
        }
    except Exception as e:
        logger.error(f"Error in get_disenchanter_data: {e}")
        return {"success": False, "error": str(e)}

def get_loadouts_data():
    """
    Returns all owned champions with owned skins and their saved favorite skin selection.
    Automatically assigns favorite if champ has exactly 1 skin and not yet configured.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        summoner_res = session.get(f"{base_url}/lol-summoner/v1/current-summoner")
        summoner_id = summoner_res.json().get("summonerId")

        champs_res = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions")
        if champs_res.status_code != 200:
            return {"success": False, "error": "Champions could not be loaded"}

        champions = champs_res.json()
        loadout = load_loadout()
        loadout_changed = False

        configured_list = []
        unconfigured_list = []

        for champ in champions:
            champ_id = champ.get("id")
            if champ_id == -1 or not champ.get("ownership", {}).get("owned", False):
                continue
            
            champ_id_str = str(champ_id)
            owned_skins = []
            
            for skin in champ.get("skins", []):
                if skin.get("ownership", {}).get("owned", False) and not skin.get("isBase", False):
                    splash = skin.get("splashPath") or skin.get("uncenteredSplashPath") or skin.get("tilePath")
                    owned_skins.append({
                        "id": skin.get("id"),
                        "name": skin.get("name"),
                        "img": splash
                    })

            if not owned_skins:
                continue

            # Auto-assign single skin if exactly 1 skin is owned
            if len(owned_skins) == 1:
                single_skin_id = owned_skins[0]["id"]
                if loadout.get(champ_id_str) != single_skin_id:
                    loadout[champ_id_str] = single_skin_id
                    loadout_changed = True

            selected_skin_id = loadout.get(champ_id_str)
            
            champ_entry = {
                "id": champ_id_str,
                "name": champ.get("name"),
                "img": champ.get("squarePortraitPath") or champ.get("portraitPath") or f"/lol-game-data/assets/v1/champion-icons/{champ_id}.png",
                "skins": owned_skins,
                "selectedSkinId": selected_skin_id,
                "isConfigured": (selected_skin_id is not None and selected_skin_id in [s["id"] for s in owned_skins])
            }

            if champ_entry["isConfigured"]:
                configured_list.append(champ_entry)
            else:
                unconfigured_list.append(champ_entry)

        if loadout_changed:
            save_loadout(loadout)


        # Sort alphabetically by name
        configured_list.sort(key=lambda x: x["name"])
        unconfigured_list.sort(key=lambda x: x["name"])

        return {
            "success": True,
            "loadouts": loadout,
            "configured": configured_list,
            "unconfigured": unconfigured_list,
            "totalChampionsWithSkins": len(configured_list) + len(unconfigured_list)
        }
    except Exception as e:
        logger.error(f"Error in get_loadouts_data: {e}")
        return {"success": False, "error": str(e)}

def execute_loot_recipe(loot_id, recipe_type="UPGRADE", repeat=1):
    """
    Safely and dynamically queries recipe details for a given loot item,
    checks required slots, and sends crafting request to LCU.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        # 1. Fetch available recipes for this item
        recipe_url = f"{base_url}/lol-loot/v1/recipes/initial-item/{loot_id}"
        rec_res = session.get(recipe_url)
        
        if rec_res.status_code != 200:
            return {"success": False, "error": f"Failed to fetch recipes: {rec_res.text}"}

        recipes = rec_res.json()
        target_recipe = None

        for r in recipes:
            if r.get("type") == recipe_type:
                target_recipe = r
                break
        
        # Fallback recipe names if not found by type
        if not target_recipe:
            if recipe_type == "UPGRADE":
                for r in recipes:
                    if "upgrade" in r.get("recipeName", "").lower():
                        target_recipe = r
                        break
            elif recipe_type == "DISENCHANT":
                for r in recipes:
                    if "disenchant" in r.get("recipeName", "").lower():
                        target_recipe = r
                        break

        if not target_recipe:
            return {"success": False, "error": f"No recipe found for type '{recipe_type}' and item '{loot_id}'"}

        recipe_name = target_recipe.get("recipeName")
        slots = target_recipe.get("slots", [])
        
        # Build payload based on recipe slots
        payload = []
        for idx, slot in enumerate(slots):
            if idx == 0:
                payload.append(loot_id)
            else:
                # Typically slot 1 is Orange Essence currency
                loot_ids = slot.get("lootIds", [])
                if loot_ids and len(loot_ids) == 1:
                    payload.append(loot_ids[0])
                else:
                    payload.append("CURRENCY_cosmetic")

        # Fallback for standard recipes if slots was empty
        if not payload:
            if recipe_type == "UPGRADE":
                payload = [loot_id, "CURRENCY_cosmetic"]
            else:
                payload = [loot_id]

        craft_url = f"{base_url}/lol-loot/v1/recipes/{recipe_name}/craft?repeat={repeat}"
        craft_res = session.post(craft_url, json=payload)

        if craft_res.status_code in (200, 204):
            return {
                "success": True,
                "recipeName": recipe_name,
                "payload": payload,
                "result": craft_res.json() if craft_res.content else {}
            }
        else:
            return {
                "success": False,
                "status_code": craft_res.status_code,
                "recipeName": recipe_name,
                "payload": payload,
                "error": craft_res.text
            }
    except Exception as e:
        logger.error(f"Error executing recipe for {loot_id}: {e}")
        return {"success": False, "error": str(e)}

def auto_equip_monitor_step(last_champ_state, sound_enabled=True):
    """
    Executes a single check cycle for champ select and auto-equips if needed.
    Returns the new last_champ_state (champ_id).
    """
    session, base_url = get_lcu_session()
    if not session:
        return None

    try:
        res = session.get(f"{base_url}/lol-champ-select/v1/session", timeout=2)
        if res.status_code != 200:
            return None

        cs_data = res.json()
        local_cell_id = cs_data.get("localPlayerCellId")
        my_team = cs_data.get("myTeam", [])
        my_selection = next((m for m in my_team if m.get("cellId") == local_cell_id), None)

        if not my_selection:
            return None

        champ_id_raw = my_selection.get("championId")
        if not champ_id_raw or int(champ_id_raw) <= 0:
            return None

        champ_id = str(champ_id_raw)
        current_skin = my_selection.get("selectedSkinId")

        if champ_id != last_champ_state:
            # New champion detected!
            loadout = load_loadout()
            target_skin = loadout.get(champ_id)

            if not target_skin:
                # If not explicitly in loadout, check if user owns exactly 1 skin for this champ
                try:
                    summoner_res = session.get(f"{base_url}/lol-summoner/v1/current-summoner", timeout=1)
                    if summoner_res.status_code == 200:
                        s_id = summoner_res.json().get("summonerId")
                        c_res = session.get(f"{base_url}/lol-champions/v1/inventories/{s_id}/champions/{champ_id}", timeout=1)
                        if c_res.status_code == 200:
                            c_data = c_res.json()
                            owned_skins = [s for s in c_data.get("skins", []) if s.get("ownership", {}).get("owned") and not s.get("isBase")]
                            if len(owned_skins) == 1:
                                target_skin = owned_skins[0]["id"]
                                loadout[champ_id] = target_skin
                                save_loadout(loadout)
                except Exception:
                    pass

            if target_skin and current_skin != target_skin:
                patch_url = f"{base_url}/lol-champ-select/v1/session/my-selection"
                session.patch(patch_url, json={"selectedSkinId": target_skin})
                logger.info(f"[Auto-Equip] Equipped skin {target_skin} for champion {champ_id}")


            if sound_enabled:
                try:
                    import winsound
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception:
                    pass

            return champ_id
        
        return last_champ_state
    except Exception:
        return None

# =========================================================================
# Social & Friend Manager LCU Services
# =========================================================================

QUEUE_TYPE_NAMES = {
    "RANKED_SOLO_5x5": "Ranked Solo/Duo",
    "RANKED_FLEX_SR": "Ranked Flex",
    "RANKED_TFT": "Ranked TFT",
    "NORMAL": "Normal (Blind/Draft)",
    "NORMAL_5X5_BLIND": "Blind Pick",
    "NORMAL_5X5_DRAFT": "Draft Pick",
    "ARAM": "ARAM",
    "CHERRY": "Arena",
    "KIWI": "TFT",
    "BOT": "Co-op vs AI",
    "PRACTICETOOL": "Practice Tool",
    "CUSTOM": "Custom Game",
    "URF": "URF",
    "ARURF": "ARURF",
    "ONEFORALL": "One for All",
    "NEXUSBLITZ": "Nexus Blitz",
    "SWIFTPLAY": "Swiftplay"
}

def format_presence_details(friend):
    """
    Parses complex LCU friend 'lol' presence dictionary into a clean, human-readable summary.
    """
    availability = friend.get("availability", "offline")
    status_msg = friend.get("statusMessage", "")
    lol = friend.get("lol", {}) or {}
    product_name = friend.get("productName", "")

    if availability in ("offline", "mobile"):
        return {
            "statusType": "offline" if availability == "offline" else "mobile",
            "statusLabel": "Offline" if availability == "offline" else "Mobile App",
            "detail": status_msg or ("Mobile" if availability == "mobile" else "Offline"),
            "gameStatus": "offline",
            "gameMode": "",
            "championName": "",
            "championId": "",
            "gameTimeMinutes": None,
            "tier": "",
            "division": "",
            "rankText": "Unranked",
            "party": None
        }

    game_status = lol.get("gameStatus", "")
    game_mode = lol.get("gameMode", "") or lol.get("gameQueueType", "")
    champ_id = lol.get("championId", "")
    champ_name = lol.get("skinname", "") or ""
    time_stamp_str = lol.get("timeStamp", "")

    # Clean queue/mode name
    mode_name = QUEUE_TYPE_NAMES.get(game_mode, game_mode.replace("_", " ").title())

    # Calculate match timer
    game_time_min = None
    if time_stamp_str and game_status in ("inGame", "inGame_TFT", "inGame_KIWI"):
        try:
            import time
            start_ts = int(time_stamp_str) / 1000.0
            diff = max(0, int((time.time() - start_ts) // 60))
            game_time_min = diff
        except Exception:
            pass

    # Rank formatting
    tier = lol.get("rankedLeagueTier", "")
    division = lol.get("rankedLeagueDivision", "")
    rank_text = f"{tier.title()} {division}".strip() if tier else "Unranked"

    # Status Label & Description
    status_label = "Online"
    detail = status_msg or "In League Client"

    if game_status == "inGame":
        status_label = "In Game"
        time_part = f" ({game_time_min}m)" if game_time_min is not None else ""
        champ_part = f" as {champ_name}" if champ_name else ""
        detail = f"Playing {mode_name or 'Game'}{champ_part}{time_part}"
    elif game_status in ("championSelect", "champion_select"):
        status_label = "In Champ Select"
        detail = f"Selecting Champion ({mode_name})"
    elif game_status == "inQueue":
        status_label = "In Queue"
        detail = f"Searching Match ({mode_name})"
    elif game_status.startswith("hosting_"):
        status_label = "In Lobby"
        detail = f"In Lobby ({mode_name})"
    elif availability == "away":
        status_label = "Away"
        detail = status_msg or "Away from keyboard"
    elif availability == "dnd":
        status_label = "Do Not Disturb"
        detail = status_msg or "Busy"

    # Party details if available
    party = None
    if lol.get("pty"):
        try:
            pty_data = json.loads(lol["pty"]) if isinstance(lol["pty"], str) else lol["pty"]
            party = {
                "isOpen": pty_data.get("isPartyOpen", False),
                "max": pty_data.get("maxPlayers", 5),
                "count": len(pty_data.get("summoners", [])) or len(pty_data.get("summonerPuuids", []))
            }
        except Exception:
            pass

    return {
        "statusType": availability,
        "statusLabel": status_label,
        "detail": detail,
        "gameStatus": game_status,
        "gameMode": mode_name,
        "championName": champ_name,
        "championId": champ_id,
        "gameTimeMinutes": game_time_min,
        "tier": tier,
        "division": division,
        "rankText": rank_text,
        "party": party
    }


_social_cache = {
    "last_req_ts": 0,
    "incoming": [],
    "outgoing": [],
    "last_blocked_ts": 0,
    "blocked": []
}

def get_social_overview():
    """
    Aggregates all friends, groups, pending requests, blocked players,
    and user's own status for the Friend Manager application.
    """
    import time
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        # 1. Fetch friend groups
        groups_res = session.get(f"{base_url}/lol-chat/v1/friend-groups", timeout=3)
        groups = groups_res.json() if groups_res.status_code == 200 else []
        
        # Ensure Default group exists in structure
        has_default = any(g.get("id") == 0 for g in groups)
        if not has_default:
            groups.append({
                "id": 0,
                "name": "General",
                "priority": 0,
                "collapsed": False,
                "isDefault": True
            })

        # Format group dictionary mapping
        group_map = {}
        for g in groups:
            gid = g.get("id")
            gname = g.get("name", "General")
            if gname == "**Default":
                gname = "General"
            group_map[gid] = {
                "id": gid,
                "name": gname,
                "priority": g.get("priority", 0),
                "collapsed": g.get("collapsed", False),
                "isDefault": (gid == 0 or g.get("name") == "**Default"),
                "friends": []
            }

        # 2. Fetch friends list
        friends_res = session.get(f"{base_url}/lol-chat/v1/friends", timeout=4)
        friends_raw = friends_res.json() if friends_res.status_code == 200 else []

        formatted_friends = []
        counts = {
            "total": len(friends_raw),
            "online": 0,
            "inGame": 0,
            "away": 0,
            "offline": 0,
            "mobile": 0
        }

        default_icon_url = "/lcu-img/lol-game-data/assets/v1/profile-icons/29.jpg"

        for f in friends_raw:
            fid = f.get("id")
            game_name = f.get("gameName") or f.get("name") or "Friend"
            game_tag = f.get("gameTag") or ""
            riot_id = f"{game_name}#{game_tag}" if game_tag else game_name
            icon_id = f.get("icon", 29)
            group_id = f.get("groupId", 0)
            note = f.get("note") or ""
            puuid = f.get("puuid") or ""
            summoner_id = f.get("summonerId", 0)

            presence = format_presence_details(f)
            status_type = presence["statusType"]

            # Statistics count
            if status_type == "offline":
                counts["offline"] += 1
            elif status_type == "mobile":
                counts["mobile"] += 1
            else:
                counts["online"] += 1
                if status_type == "away":
                    counts["away"] += 1
                if presence.get("gameStatus") in ("inGame", "inGame_TFT", "inGame_KIWI", "championSelect"):
                    counts["inGame"] += 1

            # Ensure group exists in group_map
            if group_id not in group_map:
                group_map[group_id] = {
                    "id": group_id,
                    "name": f.get("groupName") or "General",
                    "priority": 99,
                    "collapsed": False,
                    "isDefault": (group_id == 0),
                    "friends": []
                }

            friend_obj = {
                "id": fid,
                "puuid": puuid,
                "summonerId": summoner_id,
                "gameName": game_name,
                "gameTag": game_tag,
                "riotId": riot_id,
                "iconId": icon_id,
                "iconUrl": f"/lcu-img/lol-game-data/assets/v1/profile-icons/{icon_id}.jpg" if icon_id and icon_id > 0 else default_icon_url,
                "groupId": group_id,
                "groupName": group_map[group_id]["name"],
                "note": note,
                "presence": presence
            }

            formatted_friends.append(friend_obj)
            group_map[group_id]["friends"].append(friend_obj)

        # 3. Fetch friend requests (cached for 20s to reduce LCU API overhead)
        now = time.time()
        if now - _social_cache["last_req_ts"] > 20 or not _social_cache["incoming"]:
            req_res = session.get(f"{base_url}/lol-chat/v2/friend-requests", timeout=3)
            raw_requests = req_res.json() if req_res.status_code == 200 else []
            incoming_requests = []
            outgoing_requests = []

            for r in raw_requests:
                r_obj = {
                    "puuid": r.get("puuid"),
                    "gameName": r.get("gameName") or r.get("name") or "Summoner",
                    "tagLine": r.get("tagLine") or "",
                    "riotId": f"{r.get('gameName', '')}#{r.get('tagLine', '')}".strip('#'),
                    "iconId": r.get("icon", 29),
                    "iconUrl": f"/lcu-img/lol-game-data/assets/v1/profile-icons/{r.get('icon', 29)}.jpg" if r.get('icon', -1) > 0 else default_icon_url,
                    "direction": r.get("direction", "in")
                }
                if r.get("direction") == "in":
                    incoming_requests.append(r_obj)
                else:
                    outgoing_requests.append(r_obj)
            _social_cache["incoming"] = incoming_requests
            _social_cache["outgoing"] = outgoing_requests
            _social_cache["last_req_ts"] = now
        else:
            incoming_requests = _social_cache["incoming"]
            outgoing_requests = _social_cache["outgoing"]

        # 4. Fetch blocked players (cached for 20s)
        if now - _social_cache["last_blocked_ts"] > 20 or not _social_cache["blocked"]:
            blocked_res = session.get(f"{base_url}/lol-chat/v1/blocked-players", timeout=3)
            raw_blocked = blocked_res.json() if blocked_res.status_code == 200 else []
            blocked_players = []
            for b in raw_blocked:
                b_name = b.get("gameName") or b.get("name") or "Blocked Player"
                b_tag = b.get("gameTag") or ""
                blocked_players.append({
                    "id": b.get("id"),
                    "puuid": b.get("puuid"),
                    "summonerId": b.get("summonerId"),
                    "gameName": b_name,
                    "gameTag": b_tag,
                    "riotId": f"{b_name}#{b_tag}" if b_tag else b_name,
                    "iconId": b.get("icon", 29),
                    "iconUrl": f"/lcu-img/lol-game-data/assets/v1/profile-icons/{b.get('icon', 29)}.jpg" if b.get("icon", -1) > 0 else default_icon_url
                })
            _social_cache["blocked"] = blocked_players
            _social_cache["last_blocked_ts"] = now
        else:
            blocked_players = _social_cache["blocked"]

        # 5. Fetch user's own status
        me_res = session.get(f"{base_url}/lol-chat/v1/me", timeout=3)
        me_data = me_res.json() if me_res.status_code == 200 else {}
        my_status = {
            "availability": me_data.get("availability", "online"),
            "statusMessage": me_data.get("statusMessage", ""),
            "gameName": me_data.get("gameName", ""),
            "gameTag": me_data.get("gameTag", ""),
            "iconId": me_data.get("icon", 29),
            "iconUrl": f"/lcu-img/lol-game-data/assets/v1/profile-icons/{me_data.get('icon', 29)}.jpg" if me_data.get("icon") else ""
        }

        # Convert groups to sorted list
        groups_list = list(group_map.values())
        groups_list.sort(key=lambda g: (0 if g["isDefault"] else 1, g.get("priority", 0), g["name"].lower()))

        return {
            "success": True,
            "counts": counts,
            "friends": formatted_friends,
            "groups": groups_list,
            "requests": {
                "incoming": incoming_requests,
                "outgoing": outgoing_requests,
                "total": len(incoming_requests) + len(outgoing_requests)
            },
            "blocked": blocked_players,
            "me": my_status
        }
    except Exception as e:
        logger.error(f"Error in get_social_overview: {e}")
        return {"success": False, "error": str(e)}


def create_friend_group(name):
    """Creates a new friend group/folder in LCU."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    if not name or not name.strip():
        return {"success": False, "error": "Group name cannot be empty"}

    try:
        res = session.post(f"{base_url}/lol-chat/v1/friend-groups", json={"name": name.strip()})
        if res.status_code in (200, 201, 204):
            return {"success": True, "data": res.json() if res.content else {}}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error creating friend group: {e}")
        return {"success": False, "error": str(e)}


def update_friend_group(group_id, name=None, collapsed=None):
    """Renames or toggles collapsed state of a friend group."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        payload = {}
        if name is not None:
            payload["name"] = name.strip()
        if collapsed is not None:
            payload["collapsed"] = bool(collapsed)

        res = session.put(f"{base_url}/lol-chat/v1/friend-groups/{group_id}", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error updating friend group {group_id}: {e}")
        return {"success": False, "error": str(e)}


def delete_friend_group(group_id):
    """Deletes a custom friend group."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    if int(group_id) == 0:
        return {"success": False, "error": "Cannot delete the default group"}

    try:
        res = session.delete(f"{base_url}/lol-chat/v1/friend-groups/{group_id}")
        if res.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error deleting friend group {group_id}: {e}")
        return {"success": False, "error": str(e)}


def update_friend(friend_id, group_id=None, note=None):
    """Updates a friend's assigned folder (groupId) or custom note/nickname."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        payload = {}
        if group_id is not None:
            payload["groupId"] = int(group_id)
        if note is not None:
            payload["note"] = str(note)

        res = session.put(f"{base_url}/lol-chat/v1/friends/{friend_id}", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error updating friend {friend_id}: {e}")
        return {"success": False, "error": str(e)}


def batch_move_friends(friend_ids, group_id):
    """Moves multiple friends to a specific folder simultaneously."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    target_group_id = int(group_id)
    success_count = 0
    errors = []

    for fid in friend_ids:
        try:
            res = session.put(f"{base_url}/lol-chat/v1/friends/{fid}", json={"groupId": target_group_id})
            if res.status_code in (200, 201, 204):
                success_count += 1
            else:
                errors.append(f"Failed for {fid}: {res.status_code}")
        except Exception as e:
            errors.append(f"Error for {fid}: {str(e)}")

    return {
        "success": (success_count > 0 or len(friend_ids) == 0),
        "moved": success_count,
        "total": len(friend_ids),
        "errors": errors
    }


def remove_friend(friend_id):
    """Unfriends / removes a friend from the friend list."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        res = session.delete(f"{base_url}/lol-chat/v1/friends/{friend_id}")
        if res.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error removing friend {friend_id}: {e}")
        return {"success": False, "error": str(e)}


def batch_remove_friends(friend_ids):
    """Removes multiple friends from the friend list simultaneously."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    success_count = 0
    errors = []

    for fid in friend_ids:
        try:
            res = session.delete(f"{base_url}/lol-chat/v1/friends/{fid}")
            if res.status_code in (200, 204):
                success_count += 1
            else:
                errors.append(f"Failed for {fid}: {res.status_code}")
        except Exception as e:
            errors.append(f"Error for {fid}: {str(e)}")

    return {
        "success": (success_count > 0 or len(friend_ids) == 0),
        "removed": success_count,
        "total": len(friend_ids),
        "errors": errors
    }


def send_friend_request(game_name, tag_line):
    """Sends an outgoing friend request using Riot ID (Name + Tag)."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    if not game_name or not tag_line:
        return {"success": False, "error": "Game Name and Tag Line are required (e.g. Player#EUW)"}

    try:
        payload = {
            "gameName": game_name.strip(),
            "tagLine": tag_line.strip().lstrip('#')
        }
        res = session.post(f"{base_url}/lol-chat/v2/friend-requests", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True, "message": f"Friend request sent to {payload['gameName']}#{payload['tagLine']}"}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error sending friend request: {e}")
        return {"success": False, "error": str(e)}


def respond_friend_request(puuid, accept=True):
    """Accepts (PUT) or declines/cancels (DELETE) a friend request by player puuid."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        if accept:
            res = session.put(f"{base_url}/lol-chat/v2/friend-requests/{puuid}", json={})
        else:
            res = session.delete(f"{base_url}/lol-chat/v2/friend-requests/{puuid}")

        if res.status_code in (200, 201, 204):
            return {"success": True, "action": "accepted" if accept else "declined"}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error responding to friend request {puuid}: {e}")
        return {"success": False, "error": str(e)}


def get_blocked_players():
    """Retrieves all currently blocked players."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        res = session.get(f"{base_url}/lol-chat/v1/blocked-players")
        if res.status_code == 200:
            return {"success": True, "blocked": res.json()}
        return {"success": False, "error": res.text}
    except Exception as e:
        logger.error(f"Error fetching blocked players: {e}")
        return {"success": False, "error": str(e)}


def unblock_player(player_id):
    """Unblocks a player by their ID."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        res = session.delete(f"{base_url}/lol-chat/v1/blocked-players/{player_id}")
        if res.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error unblocking player {player_id}: {e}")
        return {"success": False, "error": str(e)}


def block_player(name_or_puuid):
    """Blocks a player by name or puuid."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        payload = {"name": name_or_puuid}
        res = session.post(f"{base_url}/lol-chat/v1/blocked-players", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error blocking player {name_or_puuid}: {e}")
        return {"success": False, "error": str(e)}


def get_friend_hovercard(puuid):
    """
    Fetches full hovercard profile info (Rank, Mastery, Summoner Level, Challenge data)
    for a specific friend.
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        res = session.get(f"{base_url}/lol-hovercard/v1/friend-info/{puuid}")
        if res.status_code == 200:
            return {"success": True, "hovercard": res.json()}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error fetching hovercard for {puuid}: {e}")
        return {"success": False, "error": str(e)}


def update_my_status(availability=None, status_message=None):
    """Updates the user's personal chat availability and status message."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        payload = {}
        if availability is not None:
            payload["availability"] = availability
        if status_message is not None:
            payload["statusMessage"] = status_message

        res = session.put(f"{base_url}/lol-chat/v1/me", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True, "availability": availability, "statusMessage": status_message}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error updating user presence: {e}")
        return {"success": False, "error": str(e)}


def invite_to_lobby(summoner_id=None, puuid=None):
    """Invites a friend to the currently active lobby."""
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        payload = []
        if summoner_id and int(summoner_id) > 0:
            payload.append({"toSummonerId": int(summoner_id)})
        elif puuid:
            payload.append({"toUserPuuid": str(puuid)})
        else:
            return {"success": False, "error": "Either summonerId or puuid is required"}

        res = session.post(f"{base_url}/lol-lobby/v2/lobby/invitations", json=payload)
        if res.status_code in (200, 201, 204):
            return {"success": True, "message": "Invitation sent successfully"}
        return {"success": False, "status_code": res.status_code, "error": "No active lobby or failed to invite"}
    except Exception as e:
        logger.error(f"Error sending lobby invite: {e}")
        return {"success": False, "error": str(e)}


# =========================================================================
# Gameflow & Smart Loading Delay Services
# =========================================================================

def get_gameflow_phase():
    """
    Returns the current gameflow phase:
    'None', 'Lobby', 'Matchmaking', 'ReadyCheck', 'ChampSelect', 'InProgress',
    'WaitingForStats', 'PreEndOfGame', 'EndOfGame'
    """
    session, base_url = get_lcu_session()
    if not session:
        return "None"

    try:
        res = session.get(f"{base_url}/lol-gameflow/v1/gameflow-phase", timeout=2)
        if res.status_code == 200:
            return res.json()
        return "None"
    except Exception:
        return "None"


def trigger_reconnect():
    """
    Sends the official LCU reconnect request (same as clicking the yellow
    Reconnect button in the League Client).
    """
    session, base_url = get_lcu_session()
    if not session:
        return {"success": False, "error": "LCU not connected"}

    try:
        res = session.post(f"{base_url}/lol-gameflow/v1/reconnect", timeout=4)
        if res.status_code in (200, 201, 204):
            logger.info("[Loading Delay] Reconnect triggered successfully via LCU API.")
            return {"success": True, "message": "Reconnecting to game..."}
        return {"success": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        logger.error(f"Error triggering reconnect: {e}")
        return {"success": False, "error": str(e)}


def is_game_process_running():
    """Checks if the actual game client binary (League of Legends.exe) is running."""
    import subprocess
    try:
        res = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq League of Legends.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False
        )
        return "League of Legends.exe" in (res.stdout or "")
    except Exception:
        return False


def terminate_game_process():
    """
    Gracefully terminates the League of Legends.exe match process so the client
    stays in the Reconnect state while the server waits in loading screen.
    """
    import subprocess
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "League of Legends.exe"],
            capture_output=True,
            text=True,
            check=False
        )
        logger.info("[Loading Delay] Game process terminated for delayed loading.")
        return True
    except Exception as e:
        logger.error(f"Error terminating game process: {e}")
        return False


