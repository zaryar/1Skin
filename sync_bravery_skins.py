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

def wait_for_phase(session, base_url, target_phases, max_wait=6.0):
    start = time.time()
    while time.time() - start < max_wait:
        phase = get_gameflow_phase(session, base_url)
        if phase in target_phases:
            return phase
        time.sleep(0.2)
    return None

def sync_skins(specific_champ_ids=None, delay_between=0.4, progress_callback=None):
    """
    Automates the 'Last Used Skin' sync for Arena Bravery by cycling through
    champions in a Custom Game Lobby, picking them without locking in (to avoid
    ever triggering the game countdown), selecting the target skin, and immediately
    canceling champ select to return to the custom lobby.
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
    print(f" [HexSkin] Safe Arena Bravery Skin Sync ({total} Champions)")
    print(f"=======================================================\n")

    # 1. Verify custom lobby exists & we are in Lobby phase
    phase = get_gameflow_phase(session, base_url)
    if phase in ["InProgress", "GameStart", "WaitingForStats"]:
        print(f"[ERROR] Cannot start sync: League is currently in game ({phase}).")
        return False

    lobby_res = session.get(f"{base_url}/lol-lobby/v2/lobby")
    if lobby_res.status_code != 200:
        print("[ERROR] No active Custom Game lobby found in client.")
        print("[INFO] Please create a Custom Game (Blind Pick) in the League Client and try again.")
        return False

    success_count = 0
    failed_count = 0

    for idx, (champ_id, target_skin_id) in enumerate(targets, 1):
        try:
            # A. Ensure we are in Lobby phase before starting
            current_phase = get_gameflow_phase(session, base_url)
            if current_phase == "ChampSelect":
                # If still in ChampSelect from previous step, cancel it
                session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
                wait_for_phase(session, base_url, ["Lobby", "None"], max_wait=3.0)
            elif current_phase in ["InProgress", "GameStart"]:
                print(f"\n[ABORT] Game is loading or in progress ({current_phase}). Stopping sync.")
                return False

            # B. Fetch champion name
            champ_res = session.get(f"{base_url}/lol-game-data/assets/v1/champions/{champ_id}.json", timeout=2)
            champ_name = champ_res.json().get("name", f"Champion {champ_id}") if champ_res.status_code == 200 else f"Champion {champ_id}"

            print(f"[{idx}/{total}] Syncing {champ_name} (Skin ID: {target_skin_id})...", end="", flush=True)
            if progress_callback:
                progress_callback(idx, total, champ_name, "syncing")

            # C. Start Champ Select
            start_res = session.post(f"{base_url}/lol-lobby/v1/lobby/custom/start-champ-select")
            if start_res.status_code not in (200, 204):
                # Retry once if client was momentarily busy
                time.sleep(0.3)
                start_res = session.post(f"{base_url}/lol-lobby/v1/lobby/custom/start-champ-select")
                if start_res.status_code not in (200, 204):
                    print(f" -> Error starting Champ Select ({start_res.status_code})")
                    failed_count += 1
                    continue

            # D. Wait for Champ Select session
            session_ready = False
            local_cell_id = None
            pick_action_id = None

            for _ in range(15):
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
                                session_ready = True
                                break
                    if session_ready:
                        break

            if not session_ready or pick_action_id is None:
                print(" -> Timeout waiting for Champ Select session")
                session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
                wait_for_phase(session, base_url, ["Lobby", "None"], max_wait=2.0)
                failed_count += 1
                continue

            # E. Select Champion (DO NOT call complete/lock-in to prevent game start countdown!)
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/actions/{pick_action_id}",
                json={"championId": int(champ_id)}
            )
            time.sleep(0.15)

            # F. Select Target Skin
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/my-selection",
                json={"selectedSkinId": target_skin_id}
            )
            time.sleep(0.15)

            # G. Cancel Champ Select immediately (Returns back to Custom Lobby safely)
            session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
            
            # H. Wait for client to return to Lobby state
            returned_phase = wait_for_phase(session, base_url, ["Lobby", "None"], max_wait=3.0)
            if not returned_phase:
                # Extra safety: try cancel again
                session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
                wait_for_phase(session, base_url, ["Lobby", "None"], max_wait=2.0)

            print(" -> OK!")
            success_count += 1

            if progress_callback:
                progress_callback(idx, total, champ_name, "done")

            time.sleep(delay_between)

        except Exception as e:
            print(f" -> Error: {e}")
            failed_count += 1
            try:
                session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
                wait_for_phase(session, base_url, ["Lobby", "None"], max_wait=2.0)
            except Exception:
                pass
            time.sleep(0.5)

    print(f"\n=======================================================")
    print(f" [HexSkin] Synchronization Completed!")
    print(f"    Successful: {success_count} / {total}")
    if failed_count > 0:
        print(f"    Failed: {failed_count}")
    print(f"=======================================================\n")
    print("Arena Bravery will now automatically load your preferred skins!")
    return True

if __name__ == '__main__':
    sync_skins()
