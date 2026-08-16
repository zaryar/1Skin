import base64
import os
import requests
import urllib3
from flask import Flask, render_template_string, jsonify, Response, request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCKFILE_PATH = r"C:\Riot Games\League of Legends\lockfile"
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

# Proxy-Route für die Bilder, da der Browser LCU-Bilder (SSL-Fehler) blockieren würde
@app.route('/lcu-img/<path:img_path>')
def proxy_image(img_path):
    session, base_url = get_lcu_session()
    # Flask schneidet den führenden Slash ab, den fügen wir wieder an
    if not img_path.startswith('/'):
        img_path = '/' + img_path
    
    res = session.get(f"{base_url}{img_path}")
    return Response(res.content, mimetype='image/jpeg')

@app.route('/')
def index():
    session, base_url = get_lcu_session()
    summoner_id = session.get(f"{base_url}/lol-summoner/v1/current-summoner").json().get("summonerId")
    
    # 1. Besessene Skins abrufen
    champions = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions").json()
    champs_with_skins = {}
    
    for champ in champions:
        if champ.get("id") == -1: continue
        champ_id = champ.get("id")
        
        owned_skins = []
        for skin in champ.get("skins", []):
            if skin.get("ownership", {}).get("owned") and not skin.get("isBase"):
                owned_skins.append({
                    "name": skin.get("name"),
                    "img": skin.get("splashPath")
                })
        
        if owned_skins:
            champs_with_skins[champ_id] = {
                "name": champ.get("name"),
                "skins": owned_skins
            }

    # 2. Loot abrufen und filtern
    loot = session.get(f"{base_url}/lol-loot/v1/player-loot").json()
    shards_to_process = []
    
    for item in loot:
        if item.get("type") in ["SKIN_RENTAL", "CHAMPION_SKIN_RENTAL"]:
            champ_id = item.get("parentStoreItemId")
            if champ_id in champs_with_skins:
                shards_to_process.append({
                    "id": item.get("lootId"),
                    "champ_name": champs_with_skins[champ_id]["name"],
                    "skin_name": item.get("itemDesc"),
                    "shard_img": item.get("splashPath"),
                    "value": item.get("disenchantValue"),
                    "count": item.get("count"),
                    "owned_skins": champs_with_skins[champ_id]["skins"]
                })

    # Einfaches HTML/CSS Template direkt im Python-Skript (Dark Mode)
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>LoL Skin Manager</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 20px; }
            h1 { text-align: center; color: #c8aa6e; }
            .card { background: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 20px; margin-bottom: 30px; display: flex; gap: 30px; }
            .owned-section { flex: 1; border-right: 1px solid #333; padding-right: 20px; }
            .shard-section { flex: 1; text-align: center; }
            .skin-list { display: flex; flex-wrap: wrap; gap: 10px; }
            .skin-item { text-align: center; font-size: 12px; color: #aaa; width: 150px; }
            .skin-item img { width: 100%; border-radius: 4px; border: 2px solid #555; }
            .shard-img { width: 100%; max-width: 400px; border-radius: 6px; border: 2px solid #c8aa6e; margin-bottom: 15px; }
            .btn-group { display: flex; justify-content: center; gap: 15px; margin-top: 20px; }
            button { padding: 10px 20px; font-size: 16px; font-weight: bold; cursor: pointer; border: none; border-radius: 4px; color: white; transition: 0.2s;}
            .btn-disenchant { background-color: #d9534f; }
            .btn-disenchant:hover { background-color: #c9302c; }
            .btn-keep { background-color: #5bc0de; }
            .btn-keep:hover { background-color: #31b0d5; }
            .count-badge { background: #c8aa6e; color: #000; padding: 2px 8px; border-radius: 12px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Loot Manager: Splitter für Champions mit Skin</h1>
        <div id="container">
            {% if not shards %}
                <h3 style="text-align:center;">Du hast keine passenden Splitter mehr!</h3>
            {% endif %}
            
            {% for shard in shards %}
            <div class="card" id="card-{{ loop.index }}">
                <div class="owned-section">
                    <h3>Bereits im Besitz ({{ shard.champ_name }}):</h3>
                    <div class="skin-list">
                        {% for skin in shard.owned_skins %}
                        <div class="skin-item">
                            <img src="/lcu-img/{{ skin.img }}" alt="{{ skin.name }}">
                            <p>{{ skin.name }}</p>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                <div class="shard-section">
                    <h3>Gefundener Splitter: <span style="color:#c8aa6e;">{{ shard.skin_name }}</span></h3>
                    {% if shard.count > 1 %}<p><span class="count-badge">{{ shard.count }}x vorhanden</span></p>{% endif %}
                    <img class="shard-img" src="/lcu-img/{{ shard.shard_img }}" alt="Shard">
                    
                    <div class="btn-group">
                        <button class="btn-disenchant" onclick="action('{{ shard.id }}', 'disenchant', 'card-{{ loop.index }}')">
                            Entzaubern (+{{ shard.value }} OE)
                        </button>
                        <button class="btn-keep" onclick="action('{{ shard.id }}', 'keep', 'card-{{ loop.index }}')">
                            Behalten (Ausblenden)
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

        <script>
            async function action(lootId, type, cardId) {
                if(type === 'disenchant') {
                    const res = await fetch('/api/disenchant', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ loot_id: lootId })
                    });
                    
                    if(!res.ok) {
                        alert("Fehler beim Entzaubern!");
                        return;
                    }
                }
                
                // Karte ausblenden nach Klick
                const card = document.getElementById(cardId);
                card.style.display = 'none';
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html, shards=shards_to_process)

@app.route('/api/disenchant', methods=['POST'])
def disenchant():
    loot_id = request.json.get("loot_id")
    session, base_url = get_lcu_session()
    
    # Entzaubert genau EINEN Splitter (repeat=1)
    recipe_url = f"{base_url}/lol-loot/v1/recipes/SKIN_RENTAL_disenchant/craft?repeat=1"
    res = session.post(recipe_url, json=[loot_id])
    
    if res.status_code in (200, 204):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    # Startet den Server nur lokal
    app.run(debug=True, port=5000)