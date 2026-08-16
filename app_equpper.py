import base64
import os
import requests
import urllib3
import json
import threading
import time
import winsound  # NEU: Für den Windows-Benachrichtigungs-Sound
from flask import Flask, render_template_string, jsonify, Response, request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCKFILE_PATH = r"C:\Riot Games\League of Legends\lockfile"
LOADOUT_FILE = "loadout.json"
app = Flask(__name__)

def get_lcu_session():
    if not os.path.exists(LOCKFILE_PATH):
        raise FileNotFoundError("Lockfile nicht gefunden. League geöffnet?")
    with open(LOCKFILE_PATH, "r") as f:
        data = f.read().split(":")
        port, password = data[2], data[3]

    session = requests.Session()
    token = base64.b64encode(f"riot:{password}".encode("ascii")).decode("ascii")
    session.headers.update({"Authorization": f"Basic {token}"})
    session.verify = False 
    return session, f"https://127.0.0.1:{port}"

def load_loadout():
    if os.path.exists(LOADOUT_FILE):
        with open(LOADOUT_FILE, "r") as f:
            return json.load(f)
    return {}

def save_loadout(data):
    with open(LOADOUT_FILE, "w") as f:
        json.dump(data, f)
        
def auto_equip_listener():
    last_champ_id = None
    
    while True:
        time.sleep(0.5)
        try:
            session, base_url = get_lcu_session()
            res = session.get(f"{base_url}/lol-champ-select/v1/session")
            
            if res.status_code == 200:
                cs_data = res.json()
                local_cell_id = cs_data.get("localPlayerCellId")
                
                my_selection = next((m for m in cs_data.get("myTeam", []) if m.get("cellId") == local_cell_id), None)
                
                if my_selection:
                    champ_id_raw = my_selection.get("championId")
                    
                    # FIX: Ignorieren, wenn der Champion noch nicht feststeht (z.B. ID -3, -1 oder 0)
                    if not champ_id_raw or int(champ_id_raw) <= 0:
                        continue
                        
                    champ_id = str(champ_id_raw)
                    current_skin = my_selection.get("selectedSkinId")
                    
                    if champ_id != last_champ_id:
                        last_champ_id = champ_id
                        
                        champ_name = f"Champion (ID: {champ_id})"
                        champ_res = session.get(f"{base_url}/lol-game-data/assets/v1/champions/{champ_id}.json")
                        if champ_res.status_code == 200:
                            champ_name = champ_res.json().get("name", champ_name)
                            
                        print(f"\n==================================================")
                        print(f" 🎲 BRAVERY PICK ERKANNT: Du spielst {champ_name}! ")
                        print(f"==================================================")
                        
                        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                        
                        loadout = load_loadout()
                        if champ_id in loadout:
                            target_skin = loadout[champ_id]
                            if current_skin != target_skin:
                                patch_url = f"{base_url}/lol-champ-select/v1/session/my-selection"
                                session.patch(patch_url, json={"selectedSkinId": target_skin})
                                print(f"[Auto-Equip] ➔ Dein Wunsch-Skin wurde erfolgreich geladen!")
                        else:
                            print(f"[Auto-Equip] ➔ Kein Favorit gespeichert. Nutze Standard.")
                            
            else:
                last_champ_id = None 
        except Exception:
            last_champ_id = None


@app.route('/lcu-img/<path:img_path>')
def proxy_image(img_path):
    session, base_url = get_lcu_session()
    if not img_path.startswith('/'):
        img_path = '/' + img_path
    res = session.get(f"{base_url}{img_path}")
    return Response(res.content, mimetype='image/jpeg')

@app.route('/')
def index():
    session, base_url = get_lcu_session()
    summoner_id = session.get(f"{base_url}/lol-summoner/v1/current-summoner").json().get("summonerId")
    champions = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions").json()
    
    loadout = load_loadout()
    unconfigured = []
    configured = []
    
    loadout_changed = False

    for champ in champions:
        if champ.get("id") == -1 or not champ.get("ownership", {}).get("owned", False):
            continue
            
        champ_id = str(champ.get("id"))
        
        owned_skins = [
            {"id": skin.get("id"), "name": skin.get("name"), "img": skin.get("splashPath")}
            for skin in champ.get("skins", []) 
            if skin.get("ownership", {}).get("owned", False) and not skin.get("isBase", False)
        ]
        
        if not owned_skins:
            continue
            
        if len(owned_skins) == 1 and champ_id not in loadout:
            loadout[champ_id] = owned_skins[0]["id"]
            loadout_changed = True
            
        champ_data = {
            "id": champ_id,
            "name": champ.get("name"),
            "img": champ.get("squarePortraitPath") or champ.get("portraitPath"),
            "skins": owned_skins,
            "selected_skin_id": loadout.get(champ_id)
        }
        
        if champ_id in loadout:
            configured.append(champ_data)
        else:
            unconfigured.append(champ_data)
            
    if loadout_changed:
        save_loadout(loadout)

    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>Skin Loadout Manager</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 20px; }
            h1 { text-align: center; color: #f39c12; margin-bottom: 5px; }
            h2 { color: #aaa; border-bottom: 1px solid #333; padding-bottom: 10px; margin-top: 40px; }
            
            .card { background: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 20px; display: flex; gap: 20px; align-items: center; transition: all 0.3s ease; }
            .champ-info { width: 120px; text-align: center; border-right: 1px solid #333; padding-right: 15px; }
            .champ-info img { width: 80px; height: 80px; border-radius: 50%; border: 2px solid #555; }
            .champ-info h3 { margin: 10px 0 0 0; font-size: 16px; color: #ddd; }
            
            .skins-container { display: flex; flex-wrap: wrap; gap: 15px; }
            .skin-item { text-align: center; cursor: pointer; width: 140px; }
            .skin-item img { width: 100%; border-radius: 6px; border: 3px solid #333; transition: 0.2s; }
            .skin-item img:hover { transform: scale(1.05); }
            .skin-item p { margin: 5px 0 0 0; font-size: 13px; color: #bbb; }
            
            .selected-skin { border-color: #f39c12 !important; box-shadow: 0 0 10px rgba(243, 156, 18, 0.5); }
        </style>
    </head>
    <body>
        <h1>Auto-Equipper Loadouts</h1>
        <p style="text-align:center; color:#888;">Wähle deinen Favoriten. Das Tool rüstet den Skin ab sofort automatisch im Champ Select für dich aus.</p>

        <h2>Noch nicht festgelegt (Bitte Skin wählen)</h2>
        <div id="unconfigured-section">
            {% if not unconfigured %}
                <p style="color: #666; font-style: italic;">Alles konfiguriert! Alle Champions mit Skins haben einen Favoriten.</p>
            {% endif %}
            
            {% for champ in unconfigured %}
            <div class="card" id="card-{{ champ.id }}">
                <div class="champ-info">
                    <img src="/lcu-img/{{ champ.img }}" alt="{{ champ.name }}">
                    <h3>{{ champ.name }}</h3>
                </div>
                <div class="skins-container">
                    {% for skin in champ.skins %}
                    <div class="skin-item" onclick="equipSkin('{{ champ.id }}', {{ skin.id }})">
                        <img id="img-{{ skin.id }}" src="/lcu-img/{{ skin.img }}" alt="{{ skin.name }}" class="skin-img">
                        <p>{{ skin.name }}</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>

        <h2>Ausgerüstet & Gespeichert</h2>
        <div id="configured-section">
            {% for champ in configured %}
            <div class="card" id="card-{{ champ.id }}">
                <div class="champ-info">
                    <img src="/lcu-img/{{ champ.img }}" alt="{{ champ.name }}">
                    <h3>{{ champ.name }}</h3>
                </div>
                <div class="skins-container">
                    {% for skin in champ.skins %}
                    <div class="skin-item" onclick="equipSkin('{{ champ.id }}', {{ skin.id }})">
                        <img id="img-{{ skin.id }}" src="/lcu-img/{{ skin.img }}" alt="{{ skin.name }}" class="skin-img {% if champ.selected_skin_id == skin.id %}selected-skin{% endif %}">
                        <p>{{ skin.name }}</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>

        <script>
            async function equipSkin(champId, skinId) {
                const cardId = 'card-' + champId;
                const card = document.getElementById(cardId);
                const unconfiguredSection = document.getElementById('unconfigured-section');
                const configuredSection = document.getElementById('configured-section');

                if (card.parentElement === unconfiguredSection) {
                    configuredSection.prepend(card);
                }

                const allSkinsInCard = card.querySelectorAll('.skin-img');
                allSkinsInCard.forEach(img => img.classList.remove('selected-skin'));
                document.getElementById('img-' + skinId).classList.add('selected-skin');

                fetch('/api/equip', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ champ_id: champId, skin_id: skinId })
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html, unconfigured=unconfigured, configured=configured)

@app.route('/api/equip', methods=['POST'])
def api_equip():
    data = request.json
    champ_id = str(data.get("champ_id"))
    skin_id = data.get("skin_id")
    
    loadout = load_loadout()
    loadout[champ_id] = skin_id
    save_loadout(loadout)
    
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("\n[+] Skin Equipper gestartet! Lass das Terminal im Hintergrund offen.")
    print("[+] Sobald du in Arena auf Random klickst, gibt dir das Tool hier Bescheid!\n")
    app.run(debug=True, port=5000, use_reloader=False)