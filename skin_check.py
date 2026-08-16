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
    
    # 1. Champions abrufen (Nur besessene & ohne Skin filtern)
    champions = session.get(f"{base_url}/lol-champions/v1/inventories/{summoner_id}/champions").json()
    champs_without_skins = {}
    
    for champ in champions:
        if champ.get("id") == -1: continue
        
        # Wichtig: Champion MUSS besessen sein
        if not champ.get("ownership", {}).get("owned", False):
            continue
        
        has_skin = any(
            skin.get("ownership", {}).get("owned") 
            for skin in champ.get("skins", []) 
            if not skin.get("isBase")
        )
        
        if not has_skin:
            champs_without_skins[champ.get("id")] = {
                "name": champ.get("name"),
                "img": champ.get("squarePortraitPath") or champ.get("portraitPath")
            }

    # 2. Loot abrufen und filtern (Orangene Essenz + Splitter)
    loot = session.get(f"{base_url}/lol-loot/v1/player-loot").json()
    
    oe_count = 0
    shards_by_champ = {}
    
    for item in loot:
        if item.get("lootName") == "CURRENCY_cosmetic":
            oe_count = item.get("count", 0)
            continue
            
        item_type = item.get("type")
        if item_type in ["SKIN_RENTAL", "CHAMPION_SKIN_RENTAL"]:
            champ_id = item.get("parentStoreItemId")
            
            if champ_id in champs_without_skins:
                if champ_id not in shards_by_champ:
                    shards_by_champ[champ_id] = {
                        "champ_info": champs_without_skins[champ_id],
                        "shards": []
                    }
                
                shards_by_champ[champ_id]["shards"].append({
                    "id": item.get("lootId"),
                    "skin_name": item.get("itemDesc"),
                    "shard_img": item.get("splashPath"),
                    "cost": item.get("upgradeEssenceValue", 0)
                })

    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>LoL Skin Crafter</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { color: #f39c12; margin-bottom: 5px; }
            .oe-display { font-size: 24px; font-weight: bold; color: #e67e22; background: #2a2a2a; padding: 10px 20px; border-radius: 8px; display: inline-block; border: 1px solid #444; }
            
            .card { background: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 20px; margin-bottom: 30px; display: flex; gap: 30px; }
            
            .champ-section { width: 180px; border-right: 1px solid #333; padding-right: 20px; text-align: center; display: flex; flex-direction: column; justify-content: center; }
            .champ-section img { width: 100%; border-radius: 50%; border: 3px solid #555; margin-bottom: 15px; }
            .champ-section h2 { margin: 0; color: #ddd; }
            
            .shards-section { flex: 1; display: flex; flex-wrap: wrap; gap: 20px; }
            
            .shard-card { background: #2a2a2a; border-radius: 8px; padding: 15px; text-align: center; width: calc(33.333% - 15px); min-width: 200px; box-sizing: border-box; border: 1px solid #444; display: flex; flex-direction: column; justify-content: space-between; }
            .shard-card img { width: 100%; border-radius: 4px; border: 2px solid #f39c12; margin-bottom: 10px; }
            .shard-card h4 { margin: 5px 0 15px 0; font-size: 16px; }
            
            .btn-upgrade { background-color: #f39c12; color: #000; border: none; padding: 12px; cursor: pointer; border-radius: 4px; font-weight: bold; width: 100%; transition: 0.2s; font-size: 14px; }
            .btn-upgrade:hover { background-color: #d68910; }
            .btn-upgrade:disabled { background-color: #555; color: #888; cursor: not-allowed; border: 1px solid #444; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Skin Crafter: Missing Skins</h1>
            <div class="oe-display" id="oe-counter">Orangene Essenz: <span id="oe-value">{{ oe }}</span> OE</div>
        </div>

        <div id="container">
            {% if not data %}
                <h3 style="text-align:center; color: #888;">Du hast alle möglichen Skins gecraftet oder keine Splitter für besessene Champions ohne Skin.</h3>
            {% endif %}
            
            {% for champ_id, group in data.items() %}
            <div class="card" id="champ-card-{{ champ_id }}">
                <div class="champ-section">
                    <img src="/lcu-img/{{ group.champ_info.img }}" alt="{{ group.champ_info.name }}">
                    <h2>{{ group.champ_info.name }}</h2>
                </div>
                
                <div class="shards-section">
                    {% for shard in group.shards %}
                    <div class="shard-card">
                        <div>
                            <img src="/lcu-img/{{ shard.shard_img }}" alt="{{ shard.skin_name }}">
                            <h4>{{ shard.skin_name }}</h4>
                        </div>
                        <button class="btn-upgrade oe-btn" 
                                data-cost="{{ shard.cost }}" 
                                onclick="upgradeSkin('{{ shard.id }}', {{ shard.cost }}, 'champ-card-{{ champ_id }}')">
                            Unlock to permanent skin ({{ shard.cost }} OE)
                        </button>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>

        <script>
            let currentOE = {{ oe }};

            function updateButtons() {
                document.getElementById('oe-value').innerText = currentOE;
                const buttons = document.querySelectorAll('.oe-btn');
                buttons.forEach(btn => {
                    const cost = parseInt(btn.getAttribute('data-cost'));
                    if (currentOE < cost) {
                        btn.disabled = true;
                        btn.innerText = `Zu wenig OE (${cost})`;
                    } else {
                        btn.disabled = false;
                        btn.innerText = `Unlock to permanent skin (${cost} OE)`;
                    }
                });
            }

            updateButtons();

            async function upgradeSkin(lootId, cost, cardId) {
                if (currentOE < cost) {
                    alert("Nicht genug Orangene Essenz!");
                    return;
                }

                // 1. Optimistic UI Update: Sofort ausblenden & OE abziehen
                const card = document.getElementById(cardId);
                card.style.display = 'none';
                currentOE -= cost;
                updateButtons();

                try {
                    // 2. Request im Hintergrund senden
                    const res = await fetch('/api/upgrade', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ loot_id: lootId })
                    });
                    
                    if (!res.ok) {
                        const data = await res.json();
                        throw new Error(data.message || "Skin konnte nicht gecraftet werden.");
                    }

                } catch (error) {
                    // 3. Fallback: Bei einem Fehler rückgängig machen
                    alert("Fehler im Hintergrund: " + error.message + "\\nAktion wird rückgängig gemacht.");
                    card.style.display = 'flex';
                    currentOE += cost; 
                    updateButtons(); 
                }
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html, data=shards_by_champ, oe=oe_count)

@app.route('/api/upgrade', methods=['POST'])
def upgrade():
    loot_id = request.json.get("loot_id")
    session, base_url = get_lcu_session()
    
    # 1. Rezept dynamisch abfragen
    recipes_url = f"{base_url}/lol-loot/v1/recipes/initial-item/{loot_id}"
    recipes_res = session.get(recipes_url)
    
    recipe_name = "SKIN_upgrade" 
    
    if recipes_res.status_code == 200:
        for recipe in recipes_res.json():
            if recipe.get("type") == "UPGRADE":
                recipe_name = recipe.get("recipeName")
                break
                
    # 2. Fix: Beide benötigten Slots (Splitter + OE) im Body übergeben
    payload = [
        loot_id, 
        "CURRENCY_cosmetic"
    ]
    
    recipe_url = f"{base_url}/lol-loot/v1/recipes/{recipe_name}/craft?repeat=1"
    res = session.post(recipe_url, json=payload)
    
    if res.status_code in (200, 204):
        return jsonify({"status": "success"})
        
    print(f"\n[FEHLER] Code: {res.status_code} | Rezept: {recipe_name}")
    print(f"Gesendete Payload: {payload}")
    print(f"Riot API sagt: {res.text}\n")
    
    return jsonify({"status": "error", "message": res.text}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)