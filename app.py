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


# State
app_state = {
    "sound_enabled": True,
    "last_champ_id": None,
    "running": True
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

# Start auto equip thread
equip_thread = threading.Thread(target=auto_equip_background_thread, daemon=True)
equip_thread.start()

@app.route('/lcu-img/<path:img_path>')
def proxy_image(img_path):
    """
    Proxies images from the local LCU client to circumvent SSL / CORS restrictions.
    """
    session, base_url = lcu_client.get_lcu_session()
    if not session:
        return Response(b"", status=404, mimetype='image/jpeg')
    
    if not img_path.startswith('/'):
        img_path = '/' + img_path
    
    try:
        res = session.get(f"{base_url}{img_path}", timeout=4)
        if res.status_code == 200:
            content_type = res.headers.get("Content-Type", "image/jpeg")
            resp = Response(res.content, mimetype=content_type)
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp
        return Response(b"", status=res.status_code)
    except Exception as e:
        logger.debug(f"Image proxy error: {e}")
        return Response(b"", status=500)

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
        return jsonify({"success": False, "error": "Sync laeuft bereits."}), 400

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

def open_browser(port):
    time.sleep(1.2)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception as e:
        logger.debug(f"Could not open browser automatically: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f" [HexSkin] Studio Server running on: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    
    # Auto-open browser in background for convenient 1-click start
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    
    app.run(debug=False, host="127.0.0.1", port=port, use_reloader=False)


