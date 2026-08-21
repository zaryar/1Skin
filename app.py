import logging
import os
import sys
import threading
import time
import webbrowser
from flask import Flask, jsonify, render_template, request, Response
import lcu_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("hexskin_app")

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

app = Flask(
    __name__,
    template_folder=get_resource_path("templates"),
    static_folder=get_resource_path("static")
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True


# State
app_state = {
    "sound_enabled": True,
    "last_champ_id": None,
    "running": True
}

loading_delay_state = {
    "enabled": False,
    "delay_seconds": 75,
    "active": False,
    "remaining_seconds": 0,
    "last_phase": "None",
    "reconnected": False,
    "reconnect_requested": False
}

def auto_equip_background_thread():
    """
    Background worker that continuously monitors Champ Select and auto-equips
    the selected favorite skin from loadout.json.
    """
    logger.info("[Auto-Equipper] Background thread started.")
    while app_state["running"]:
        time.sleep(0.5)
        try:
            new_champ = lcu_client.auto_equip_monitor_step(
                app_state["last_champ_id"],
                sound_enabled=app_state["sound_enabled"]
            )
            app_state["last_champ_id"] = new_champ
        except Exception as e:
            logger.debug(f"[Auto-Equipper] Step error: {e}")
            app_state["last_champ_id"] = None

def loading_delay_background_thread():
    """
    Background worker that monitors when a match starts (phase -> 'InProgress').
    If loading delay is enabled, it gracefully kills the game window and runs
    the safe auto-reconnect countdown timer until user clicks Reconnect or timer expires.
    """
    logger.info("[Loading Delay] Background monitor thread started.")
    while app_state["running"]:
        time.sleep(1.0)
        try:
            phase = lcu_client.get_gameflow_phase()
            last_phase = loading_delay_state["last_phase"]

            # When game transitions into InProgress from ChampSelect
            if loading_delay_state["enabled"]:
                if phase == "InProgress" and last_phase == "ChampSelect" and not loading_delay_state["reconnected"] and not loading_delay_state["active"]:
                    logger.info("[Loading Delay] Match start detected! Pausing loading process...")
                    loading_delay_state["active"] = True
                    loading_delay_state["remaining_seconds"] = int(loading_delay_state["delay_seconds"])
                    loading_delay_state["reconnect_requested"] = False

                    # Wait 2 seconds for process to launch, then terminate
                    time.sleep(2.0)
                    lcu_client.terminate_game_process()

                    # Run countdown loop
                    while loading_delay_state["active"] and loading_delay_state["remaining_seconds"] > 0:
                        if loading_delay_state["reconnect_requested"]:
                            break
                        time.sleep(1.0)
                        loading_delay_state["remaining_seconds"] -= 1

                    # Reconnect when timer finishes or when requested
                    logger.info("[Loading Delay] Countdown finished or reconnect requested. Connecting to game...")
                    lcu_client.trigger_reconnect()
                    loading_delay_state["active"] = False
                    loading_delay_state["reconnected"] = True
                    loading_delay_state["reconnect_requested"] = False

            if phase in ("None", "Lobby", "Matchmaking", "EndOfGame", "WaitingForStats"):
                loading_delay_state["reconnected"] = False
                loading_delay_state["active"] = False
                loading_delay_state["reconnect_requested"] = False

            loading_delay_state["last_phase"] = phase
        except Exception as e:
            logger.debug(f"[Loading Delay] Monitor error: {e}")

# Start background threads
equip_thread = threading.Thread(target=auto_equip_background_thread, daemon=True)
equip_thread.start()

delay_thread = threading.Thread(target=loading_delay_background_thread, daemon=True)
delay_thread.start()

SAFE_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.svg', '.ico', '.gif')
SAFE_IMAGE_PREFIXES = (
    '/lol-game-data/assets/',
    '/fe-lol-',
    '/lol-champ-select/',
    '/lol-loot/assets/',
    '/assets/'
)

@app.route('/lcu-img/<path:img_path>')
def proxy_image(img_path):
    """
    Proxies images from the local LCU client to circumvent SSL / CORS restrictions.
    Secured against path traversal and non-image LCU endpoint exposure.
    """
    if '..' in img_path or '\\' in img_path:
        return Response(b"Invalid image path", status=400)

    if not img_path.startswith('/'):
        img_path = '/' + img_path

    lower_path = img_path.lower()
    is_safe_ext = any(lower_path.endswith(ext) for ext in SAFE_IMAGE_EXTENSIONS)
    is_safe_prefix = any(lower_path.startswith(prefix) for prefix in SAFE_IMAGE_PREFIXES)

    if not (is_safe_ext or is_safe_prefix):
        return Response(b"Forbidden asset path", status=403)

    session, base_url = lcu_client.get_lcu_session()
    if not session:
        return Response(b"", status=404, mimetype='image/jpeg')

    try:
        res = session.get(f"{base_url}{img_path}", timeout=4)
        if res.status_code == 200:
            content_type = res.headers.get("Content-Type", "image/jpeg")
            resp = Response(res.content, mimetype=content_type)
            resp.headers["Cache-Control"] = "public, max-age=86400"
            resp.headers["X-Content-Type-Options"] = "nosniff"
            return resp
        return Response(b"", status=res.status_code)
    except Exception as e:
        logger.debug(f"Image proxy error: {e}")
        return Response(b"", status=500)

@app.route('/static/img/default-avatar.png')
def default_avatar():
    """Serves standard League Poro avatar as fallback."""
    return proxy_image('lol-game-data/assets/v1/profile-icons/29.jpg')

@app.route('/')
def index():
    """Serves the main single page dashboard application."""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Returns summoner status, currencies, champ select state, and settings."""
    status = lcu_client.get_player_status()
    status["soundEnabled"] = app_state["sound_enabled"]
    return jsonify(status)

@app.route('/api/settings/sound', methods=['POST'])
def api_toggle_sound():
    """Toggles or sets the auto-equip audio notification setting."""
    data = request.json or {}
    if "enabled" in data:
        app_state["sound_enabled"] = bool(data["enabled"])
    else:
        app_state["sound_enabled"] = not app_state["sound_enabled"]
    return jsonify({"success": True, "soundEnabled": app_state["sound_enabled"]})

@app.route('/api/crafter')
def api_crafter():
    """Returns champions without skins that have matching shards in loot."""
    data = lcu_client.get_crafter_data()
    return jsonify(data)

@app.route('/api/crafter/upgrade', methods=['POST'])
def api_upgrade_skin():
    """
    Upgrades a skin shard into a permanent skin using dynamic recipe slot inspection.
    """
    data = request.json or {}
    loot_id = data.get("loot_id")
    if not loot_id:
        return jsonify({"success": False, "error": "loot_id is required"}), 400

    result = lcu_client.execute_loot_recipe(loot_id, recipe_type="UPGRADE")
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/disenchanter')
def api_disenchanter():
    """Returns skin shards for champions where the player already owns skins."""
    data = lcu_client.get_disenchanter_data()
    return jsonify(data)

@app.route('/api/disenchanter/disenchant', methods=['POST'])
def api_disenchant_skin():
    """
    Disenchants a skin shard into Orange Essence using dynamic recipe slot inspection.
    """
    data = request.json or {}
    loot_id = data.get("loot_id")
    repeat = int(data.get("repeat", 1))
    if not loot_id:
        return jsonify({"success": False, "error": "loot_id is required"}), 400

    result = lcu_client.execute_loot_recipe(loot_id, recipe_type="DISENCHANT", repeat=repeat)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/loadouts')
def api_loadouts():
    """Returns all owned champions with owned skins and saved favorite selections."""
    data = lcu_client.get_loadouts_data()
    return jsonify(data)

@app.route('/api/loadouts/save', methods=['POST'])
def api_save_loadout():
    """Saves favorite skin for a champion."""
    data = request.json or {}
    champ_id = str(data.get("champ_id", ""))
    skin_id = data.get("skin_id")
    
    if not champ_id or skin_id is None:
        return jsonify({"success": False, "error": "champ_id and skin_id are required"}), 400

    loadout = lcu_client.load_loadout()
    loadout[champ_id] = int(skin_id)
    saved = lcu_client.save_loadout(loadout)
    
    if saved:
        return jsonify({"success": True, "champ_id": champ_id, "skin_id": skin_id})
    return jsonify({"success": False, "error": "Failed to save loadout"}), 500

# =========================================================================
# Arena Bravery Sync Endpoints
# =========================================================================
sync_state = {
    "running": False,
    "current": 0,
    "total": 0,
    "currentChamp": "",
    "status": "idle",
    "message": ""
}

@app.route('/api/sync/bravery/status')
def api_sync_status():
    return jsonify(sync_state)

@app.route('/api/sync/bravery/start', methods=['POST'])
def api_sync_start():
    if sync_state["running"]:
        return jsonify({"success": False, "error": "Skin synchronization is already running."}), 400

    import sync_bravery_skins

    def run_sync_thread():
        sync_state["running"] = True
        sync_state["status"] = "syncing"
        sync_state["current"] = 0
        sync_state["message"] = "Starting synchronization..."

        def cb(current, total, champ_name, step_status):
            sync_state["current"] = current
            sync_state["total"] = total
            sync_state["currentChamp"] = champ_name
            sync_state["message"] = f"Syncing {champ_name} ({current}/{total})..."

        try:
            success = sync_bravery_skins.sync_skins(progress_callback=cb)
            sync_state["status"] = "done" if success else "error"
            sync_state["message"] = "Synchronization completed successfully!" if success else "Synchronization failed."
        except Exception as e:
            sync_state["status"] = "error"
            sync_state["message"] = f"Error: {str(e)}"
        finally:
            sync_state["running"] = False

    t = threading.Thread(target=run_sync_thread, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Sync started."})

@app.route('/api/sync/bravery/stop', methods=['POST'])
def api_sync_stop():
    sync_state["running"] = False
    sync_state["status"] = "idle"
    sync_state["message"] = "Synchronization stopped."
    return jsonify({"success": True})

# =========================================================================
# Social & Friend Manager Endpoints
# =========================================================================

@app.route('/friends')
def friends_view():
    """Serves the dashboard with the Friend Manager mode pre-selected."""
    return render_template('index.html')

@app.route('/api/social/overview')
def api_social_overview():
    """Returns complete friends list, groups, requests, blocked players, and user presence."""
    data = lcu_client.get_social_overview()
    status_code = 200 if data.get("success") else 500
    return jsonify(data), status_code

@app.route('/api/social/groups', methods=['POST'])
def api_create_group():
    """Creates a new friend group/folder."""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Folder name is required"}), 400
    
    result = lcu_client.create_friend_group(name)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/groups/<int:group_id>', methods=['PUT'])
def api_update_group(group_id):
    """Renames or updates a friend group."""
    data = request.json or {}
    name = data.get("name")
    collapsed = data.get("collapsed")
    result = lcu_client.update_friend_group(group_id, name=name, collapsed=collapsed)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/groups/<int:group_id>', methods=['DELETE'])
def api_delete_group(group_id):
    """Deletes a custom friend group."""
    result = lcu_client.delete_friend_group(group_id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/friends/<path:friend_id>', methods=['PUT'])
def api_update_friend(friend_id):
    """Updates a friend's assigned folder (groupId) or custom note/nickname."""
    data = request.json or {}
    group_id = data.get("groupId")
    note = data.get("note")
    result = lcu_client.update_friend(friend_id, group_id=group_id, note=note)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/friends/batch-move', methods=['POST'])
def api_batch_move_friends():
    """Moves multiple friends to a specific folder at once."""
    data = request.json or {}
    friend_ids = data.get("friendIds", [])
    group_id = data.get("groupId")
    
    if group_id is None or not isinstance(friend_ids, list):
        return jsonify({"success": False, "error": "friendIds list and groupId are required"}), 400

    result = lcu_client.batch_move_friends(friend_ids, group_id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/friends/batch-remove', methods=['POST'])
def api_batch_remove_friends():
    """Removes multiple friends from the friend list at once."""
    data = request.json or {}
    friend_ids = data.get("friendIds", [])
    
    if not isinstance(friend_ids, list) or not friend_ids:
        return jsonify({"success": False, "error": "A non-empty friendIds list is required"}), 400

    result = lcu_client.batch_remove_friends(friend_ids)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/friends/<path:friend_id>', methods=['DELETE'])
def api_remove_friend(friend_id):
    """Unfriends / removes a friend."""
    result = lcu_client.remove_friend(friend_id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/requests', methods=['POST'])
def api_send_friend_request():
    """Sends an outgoing friend request using Riot ID (Name + Tag)."""
    data = request.json or {}
    game_name = data.get("gameName", "").strip()
    tag_line = data.get("tagLine", "").strip()
    
    # Handle single input string like "Player#EUW"
    riot_id = data.get("riotId", "").strip()
    if riot_id and '#' in riot_id:
        parts = riot_id.split('#', 1)
        game_name = parts[0].strip()
        tag_line = parts[1].strip()

    if not game_name or not tag_line:
        return jsonify({"success": False, "error": "Valid Riot ID (GameName#Tag) is required."}), 400

    result = lcu_client.send_friend_request(game_name, tag_line)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/requests/respond', methods=['POST'])
def api_respond_friend_request():
    """Accepts or declines a friend request."""
    data = request.json or {}
    puuid = data.get("puuid")
    accept = bool(data.get("accept", True))
    
    if not puuid:
        return jsonify({"success": False, "error": "puuid is required"}), 400

    result = lcu_client.respond_friend_request(puuid, accept=accept)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/blocked', methods=['GET'])
def api_get_blocked():
    """Returns list of blocked players."""
    result = lcu_client.get_blocked_players()
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/blocked', methods=['POST'])
def api_block_player():
    """Blocks a player."""
    data = request.json or {}
    name = data.get("name") or data.get("puuid")
    if not name:
        return jsonify({"success": False, "error": "Player name or puuid is required"}), 400
    
    result = lcu_client.block_player(name)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/blocked/<path:player_id>', methods=['DELETE'])
def api_unblock_player(player_id):
    """Unblocks a player."""
    result = lcu_client.unblock_player(player_id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/hovercard/<path:puuid>')
def api_friend_hovercard(puuid):
    """Fetches full hovercard profile details for a friend."""
    result = lcu_client.get_friend_hovercard(puuid)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/me/status', methods=['POST'])
def api_update_me_status():
    """Updates user's own availability ('online', 'away', 'dnd', 'offline') and status message."""
    data = request.json or {}
    availability = data.get("availability")
    status_message = data.get("statusMessage")
    result = lcu_client.update_my_status(availability=availability, status_message=status_message)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

@app.route('/api/social/invite', methods=['POST'])
def api_invite_friend():
    """Invites a friend to the current active lobby."""
    data = request.json or {}
    summoner_id = data.get("summonerId")
    puuid = data.get("puuid")
    result = lcu_client.invite_to_lobby(summoner_id=summoner_id, puuid=puuid)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

# =========================================================================
# Smart Loading Delay & Break Controller Endpoints
# =========================================================================

@app.route('/api/delay-reconnect/status')
def api_delay_status():
    """Returns current status of the Smart Loading Delay controller."""
    phase = lcu_client.get_gameflow_phase()
    loading_delay_state["phase"] = phase
    return jsonify(loading_delay_state)

@app.route('/api/delay-reconnect/settings', methods=['POST'])
def api_delay_settings():
    """Updates enabled state and delay duration (e.g. 75s)."""
    data = request.json or {}
    if "enabled" in data:
        loading_delay_state["enabled"] = bool(data["enabled"])
    if "delay_seconds" in data:
        sec = max(20, min(120, int(data["delay_seconds"])))
        loading_delay_state["delay_seconds"] = sec
    
    return jsonify({
        "success": True,
        "enabled": loading_delay_state["enabled"],
        "delay_seconds": loading_delay_state["delay_seconds"]
    })

@app.route('/api/delay-reconnect/reconnect-now', methods=['POST'])
def api_delay_reconnect_now():
    """Instantly triggers reconnect, interrupting any ongoing delay countdown."""
    loading_delay_state["reconnect_requested"] = True
    result = lcu_client.trigger_reconnect()
    loading_delay_state["active"] = False
    loading_delay_state["reconnected"] = True
    return jsonify(result)

@app.route('/api/delay-reconnect/cancel', methods=['POST'])
def api_delay_cancel():
    """Cancels delay and reconnects immediately."""
    loading_delay_state["active"] = False
    loading_delay_state["reconnect_requested"] = True
    result = lcu_client.trigger_reconnect()
    return jsonify(result)

def open_browser(port):
    time.sleep(1.2)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception as e:
        logger.debug(f"Could not open browser automatically: {e}")

if __name__ == '__main__':
    try:
        port = int(os.environ.get("PORT", 5000))
        print(f"\n=======================================================")
        print(f" [HexSkin] Studio Server running on: http://127.0.0.1:{port}")
        print(f" [HexSkin] Opening web browser automatically...")
        print(f"=======================================================\n")
        print("Keep this window open while using HexSkin Studio.")
        print("Press Ctrl+C to close.\n")
        
        # Auto-open browser in background for convenient 1-click start
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        
        app.run(debug=False, host="127.0.0.1", port=port, use_reloader=False)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        input("\nPress Enter to exit...")



