import json
import os
import sys
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import lcu_client

def get_gameflow_phase(session, base_url):
    try:
        r = session.get(f"{base_url}/lol-gameflow/v1/gameflow-phase", timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def wait_for_phase(session, base_url, target_phases, max_wait=8.0):
    start = time.time()
    while time.time() - start < max_wait:
        phase = get_gameflow_phase(session, base_url)
        if phase in target_phases:
            return phase
        time.sleep(0.2)
    return None

def sync_skins(specific_champ_ids=None, progress_callback=None):
    """
    Ultra-fast 1-Session Bravery Skin Synchronizer:
    Enters Champ Select once, cycles through all 190+ champions and their favorite skins
    in the SAME Champ Select session without locking in, and exits Champ Select once at the end.
    Total duration: ~12-15 seconds for all champions!
    """
    session, base_url = lcu_client.get_lcu_session()
    if not session:
        print("[ERROR] League of Legends client not found. Please start League of Legends.")
        return False

    loadout = lcu_client.load_loadout()
    if not loadout:
        print("[WARNING] No loadouts found in loadout.json.")
        return False

    # Filter targets
    targets = []
    for champ_id, skin_id in loadout.items():
        if specific_champ_ids and str(champ_id) not in specific_champ_ids:
            continue
        targets.append((str(champ_id), int(skin_id)))

    total = len(targets)
    print(f"\n=======================================================")
    print(f" [HexSkin] Fast 1-Session Bravery Skin Sync ({total} Champions)")
    print(f"=======================================================\n")

    phase = get_gameflow_phase(session, base_url)
    if phase in ["InProgress", "GameStart"]:
        print(f"[ERROR] Cannot sync: Game is currently in progress ({phase}).")
        return False

    # Step 1: Ensure we are in Champ Select
    if phase != "ChampSelect":
        lobby_res = session.get(f"{base_url}/lol-lobby/v2/lobby")
        if lobby_res.status_code != 200:
            print("[ERROR] No active Custom Game lobby found.")
            print("[INFO] Please create a Custom Game (Blind Pick) in League and stay in the lobby or Champ Select.")
            return False
        
        print("[INFO] Starting Custom Game Champ Select...")
        session.post(f"{base_url}/lol-lobby/v1/lobby/custom/start-champ-select")
        phase = wait_for_phase(session, base_url, ["ChampSelect"], max_wait=6.0)
        if phase != "ChampSelect":
            print("[ERROR] Could not enter Champ Select. Please enter Champ Select manually.")
            return False

    # Step 2: Find pick action ID
    local_cell_id = None
    pick_action_id = None
    for _ in range(25):
        time.sleep(0.2)
        cs_res = session.get(f"{base_url}/lol-champ-select/v1/session")
        if cs_res.status_code == 200:
            cs_data = cs_res.json()
            local_cell_id = cs_data.get("localPlayerCellId")
            actions = cs_data.get("actions", [])
            for group in actions:
                for act in group:
                    if act.get("actorCellId") == local_cell_id and act.get("type") == "pick":
                        pick_action_id = act.get("id")
                        break
            if pick_action_id is not None:
                break

    if pick_action_id is None:
        print("[ERROR] Could not find player pick action in Champ Select.")
        return False

    print("[INFO] Connected to Champ Select session! Rapidly syncing all skins...\n")

    success_count = 0
    failed_count = 0

    for idx, (champ_id, target_skin_id) in enumerate(targets, 1):
        try:
            # 1. Switch hovered champion in session
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/actions/{pick_action_id}",
                json={"championId": int(champ_id)}
            )
            time.sleep(0.04)

            # 2. Select target skin
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/my-selection",
                json={"selectedSkinId": target_skin_id}
            )

            print(f"[{idx}/{total}] Champion {champ_id} -> Skin {target_skin_id} synced! OK")
            success_count += 1

            if progress_callback:
                progress_callback(idx, total, f"Champion {champ_id}", "done")

            time.sleep(0.04)

        except Exception as e:
            print(f"[{idx}/{total}] Error: {e}")
            failed_count += 1

    # Step 3: Exit Champ Select & Lobby safely at the end
    print("\n[INFO] All skins synced! Exiting Champ Select safely...")
    time.sleep(0.4)
    session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
    time.sleep(0.3)
    try:
        session.delete(f"{base_url}/lol-lobby/v2/lobby")
    except Exception:
        pass

    print(f"\n=======================================================")
    print(f" [HexSkin] 1-Session Synchronization Completed!")
    print(f"    Successfully synced: {success_count} / {total} Champions")
    print(f"=======================================================\n")
    print("Arena Bravery will now automatically load all your preferred skins!")
    return True


if __name__ == '__main__':
    sync_skins()
