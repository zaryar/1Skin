import json
import os
import sys
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import lcu_client

def sync_skins(specific_champ_ids=None, delay_between=0.6, progress_callback=None):
    """
    Automates the 'Last Used Skin' sync for Arena Bravery by cycling through
    champions in a Custom Game Lobby, locking them, selecting the favorite skin,
    and immediately aborting champ select.
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
    print(f" [HexSkin] Arena Bravery Skin Sync Started ({total} Champions)")
    print(f"=======================================================\n")
    print("[NOTICE] Please create a Custom Game lobby (Blind Pick) in the League Client")
    print("         and stay in the lobby. The script will handle the rest!\n")

    # 1. Verify custom lobby exists
    lobby_res = session.get(f"{base_url}/lol-lobby/v2/lobby")
    if lobby_res.status_code != 200:
        print("[ERROR] No active Custom Game lobby found in client.")
        print("[INFO] Please create a Custom Game (Blind Pick) and restart the sync.")
        return False

    success_count = 0
    failed_count = 0

    for idx, (champ_id, target_skin_id) in enumerate(targets, 1):
        try:
            # Fetch champion name
            champ_res = session.get(f"{base_url}/lol-game-data/assets/v1/champions/{champ_id}.json", timeout=2)
            champ_name = champ_res.json().get("name", f"Champion {champ_id}") if champ_res.status_code == 200 else f"Champion {champ_id}"

            print(f"[{idx}/{total}] Syncing {champ_name} (Skin ID: {target_skin_id})...", end="", flush=True)
            if progress_callback:
                progress_callback(idx, total, champ_name, "syncing")

            # A. Start Champ Select
            start_res = session.post(f"{base_url}/lol-lobby/v1/lobby/custom/start-champ-select")
            if start_res.status_code not in (200, 204):
                print(f" -> Error starting Champ Select ({start_res.status_code})")
                failed_count += 1
                continue

            # B. Wait for Champ Select session
            session_ready = False
            local_cell_id = None
            pick_action_id = None

            for _ in range(12):
                time.sleep(0.25)
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
                print(" -> Timeout waiting for Champ Select")
                session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
                failed_count += 1
                continue

            # C. Pick Champion
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/actions/{pick_action_id}",
                json={"championId": int(champ_id)}
            )
            session.post(f"{base_url}/lol-champ-select/v1/session/actions/{pick_action_id}/complete")
            time.sleep(0.2)

            # D. Select Target Skin
            session.patch(
                f"{base_url}/lol-champ-select/v1/session/my-selection",
                json={"selectedSkinId": target_skin_id}
            )
            time.sleep(0.2)

            # E. Cancel Champ Select (Drops back into Custom Lobby)
            session.post(f"{base_url}/lol-lobby/v1/lobby/custom/cancel-champ-select")
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
            except Exception:
                pass
            time.sleep(1)

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
