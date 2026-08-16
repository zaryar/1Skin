import base64
import json
import logging
import os
import requests
import sys

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

            # Auto-assign single skin if not already set
            if len(owned_skins) == 1 and champ_id_str not in loadout:
                loadout[champ_id_str] = owned_skins[0]["id"]
                loadout_changed = True

            selected_skin_id = loadout.get(champ_id_str)
            
            champ_entry = {
                "id": champ_id_str,
                "name": champ.get("name"),
                "img": champ.get("squarePortraitPath") or champ.get("portraitPath") or f"/lol-game-data/assets/v1/champion-icons/{champ_id}.png",
                "skins": owned_skins,
                "selectedSkinId": selected_skin_id,
                "isConfigured": (champ_id_str in loadout and selected_skin_id is not None)
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
            if champ_id in loadout:
                target_skin = loadout[champ_id]
                if current_skin != target_skin:
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
