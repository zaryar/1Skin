/**
 * Hextech Hub - Unified Application Script
 * HexSkin Studio & HexSocial Friend Manager
 */

const state = {
    // Top-level Application Switcher
    activeApp: 'skin', // 'skin' or 'social'

    // HexSkin State
    activeTab: 'crafter',
    status: null,
    crafterData: null,
    disenchantData: null,
    loadoutsData: null,
    loadoutsFilter: 'all',
    searchQueries: {
        crafter: '',
        disenchanter: '',
        loadouts: ''
    },
    hiddenDisenchantLootIds: new Set(),

    // HexSocial State
    socialData: null,
    socialView: 'all', // 'all', 'online', 'ingame', 'away', 'offline', or 'folder_<id>'
    socialFilter: 'all', // 'all', 'online', 'ingame', 'offline'
    socialSort: 'status', // 'status', 'name', 'folder', 'rank'
    socialLayout: 'grid', // 'grid' or 'list'
    socialSearch: '',
    selectedFriends: new Set(),
    inspectedFriendPuuid: null,
    activeRequestTab: 'incoming', // 'incoming' or 'outgoing'
    confirmCallback: null,

    // Smart Break Delay (WC-Pause) State
    breakDelay: {
        enabled: false,
        delaySeconds: 75,
        active: false,
        remainingSeconds: 0
    },
    lastSocialFingerprint: '',
    breakDelayTimer: null
};

// --- Security & Utility Helpers ---
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initAppSwitcher();
    initSkinStudio();
    initSocialHub();
    initBreakDelay();
    
    // Check initial route
    if (window.location.pathname === '/friends') {
        switchApp('social');
    }

    // Initial fetch
    refreshAllData();

    // Balanced polling for status and presence (every 4.5 seconds)
    setInterval(pollStatus, 4500);
});

// =========================================================================
// Top-Level App Switcher
// =========================================================================
function initAppSwitcher() {
    const btnSkin = document.getElementById('btn-switch-skin');
    const btnSocial = document.getElementById('btn-switch-social');

    if (btnSkin) {
        btnSkin.addEventListener('click', () => switchApp('skin'));
    }
    if (btnSocial) {
        btnSocial.addEventListener('click', () => switchApp('social'));
    }
}

function switchApp(appName) {
    state.activeApp = appName;

    // Update Switcher Buttons
    const btnSkin = document.getElementById('btn-switch-skin');
    const btnSocial = document.getElementById('btn-switch-social');
    const brandTitle = document.getElementById('brand-title');
    const brandSubtitle = document.getElementById('brand-subtitle');

    if (btnSkin) btnSkin.classList.toggle('active', appName === 'skin');
    if (btnSocial) btnSocial.classList.toggle('active', appName === 'social');

    // Update Subviews
    const viewSkin = document.getElementById('view-skin-studio');
    const viewSocial = document.getElementById('view-social-hub');

    if (viewSkin) viewSkin.classList.toggle('active', appName === 'skin');
    if (viewSocial) viewSocial.classList.toggle('active', appName === 'social');

    if (appName === 'skin') {
        if (brandTitle) brandTitle.innerText = 'HEXSKIN';
        if (brandSubtitle) brandSubtitle.innerText = 'LOOT & LOADOUT STUDIO';
        document.title = 'HexSkin Studio | LoL Skin Crafter & Auto-Equipper';
        history.replaceState(null, '', '/');
    } else {
        if (brandTitle) brandTitle.innerText = 'HEXSOCIAL';
        if (brandSubtitle) brandSubtitle.innerText = 'FRIEND & SOCIAL HUB';
        document.title = 'HexSocial | League Friend Manager & Hub';
        history.replaceState(null, '', '/friends');
        fetchSocialData();
    }
}

// =========================================================================
// Common Header & LCU Polling
// =========================================================================
async function refreshAllData() {
    await pollStatus();
    if (state.status && state.status.connected) {
        fetchCrafterData();
        fetchDisenchanterData();
        fetchLoadoutsData();
        fetchSocialData();
    }
}

async function pollStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        state.status = data;
        updateHeaderStatus(data);

        // Also background refresh social if active
        if (state.activeApp === 'social' && data.connected) {
            fetchSocialData(true);
        }

        // Check break delay status
        fetchBreakDelayStatus();
    } catch (e) {
        updateHeaderStatus({ connected: false });
    }
}

function updateHeaderStatus(status) {
    const pill = document.getElementById('lcu-status-pill');
    const text = document.getElementById('lcu-status-text');
    const modal = document.getElementById('offline-modal');
    const csPill = document.getElementById('champ-select-pill');

    if (status.connected) {
        pill.className = 'status-pill online';
        text.innerText = 'LCU Connected';
        if (modal) modal.classList.add('hidden');

        // Champ select indicator
        if (csPill) {
            csPill.classList.toggle('hidden', !status.inChampSelect);
        }

        // Profile details
        if (status.summoner) {
            document.getElementById('header-summoner-name').innerText = status.summoner.name || 'Summoner';
            document.getElementById('header-summoner-tag').innerText = status.summoner.tag ? `#${status.summoner.tag}` : '';
            document.getElementById('header-level').innerText = status.summoner.level || '1';
            
            const avatar = document.getElementById('header-avatar');
            if (avatar && status.summoner.iconUrl) {
                avatar.src = status.summoner.iconUrl;
            }
        }

        // Currencies
        if (status.currencies) {
            document.getElementById('header-oe-val').innerText = Number(status.currencies.oe || 0).toLocaleString();
            document.getElementById('header-be-val').innerText = Number(status.currencies.be || 0).toLocaleString();
            document.getElementById('header-me-val').innerText = Number(status.currencies.me || 0).toLocaleString();
            document.getElementById('header-rp-val').innerText = Number(status.currencies.rp || 0).toLocaleString();
            
            const bannerOE = document.getElementById('crafter-avail-oe');
            if (bannerOE) bannerOE.innerText = `${Number(status.currencies.oe || 0).toLocaleString()} OE`;
        }

        updateSoundIcon(status.soundEnabled);
    } else {
        pill.className = 'status-pill offline';
        text.innerText = 'LCU Offline';
        if (modal) modal.classList.remove('hidden');
        if (csPill) csPill.classList.add('hidden');
    }
}

async function toggleSoundSetting() {
    try {
        const res = await fetch('/api/settings/sound', { method: 'POST' });
        const data = await res.json();
        updateSoundIcon(data.soundEnabled);
        showToast(
            'Sound Setting', 
            data.soundEnabled ? 'Auto-Equip sound enabled' : 'Auto-Equip sound muted', 
            'info'
        );
    } catch (e) {
        console.error('Failed to toggle sound', e);
    }
}

function updateSoundIcon(enabled) {
    const onIcon = document.getElementById('icon-sound-on');
    const offIcon = document.getElementById('icon-sound-off');
    if (onIcon && offIcon) {
        onIcon.classList.toggle('hidden', !enabled);
        offIcon.classList.toggle('hidden', !!enabled);
    }
}

// =========================================================================
// SECTION 1: HEXSKIN STUDIO LOGIC
// =========================================================================
function initSkinStudio() {
    // Tab switching
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.getAttribute('data-tab');
            switchSkinTab(targetTab);
        });
    });

    // Sound button
    const soundBtn = document.getElementById('btn-sound-toggle');
    if (soundBtn) soundBtn.addEventListener('click', toggleSoundSetting);

    // Refresh button
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshAllData();
            showToast('Syncing...', 'Refreshing data from League Client.', 'info');
        });
    }

    // Modal Retry Button
    const modalRetry = document.getElementById('btn-modal-retry');
    if (modalRetry) modalRetry.addEventListener('click', refreshAllData);

    // Loadout Filter Pills
    document.querySelectorAll('.filter-pill[data-filter]').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill[data-filter]').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            state.loadoutsFilter = pill.getAttribute('data-filter');
            renderLoadouts();
        });
    });

    // Search inputs
    const crafterSearch = document.getElementById('crafter-search');
    if (crafterSearch) {
        crafterSearch.addEventListener('input', (e) => {
            state.searchQueries.crafter = e.target.value.toLowerCase().trim();
            renderCrafter();
        });
    }

    const disenchantSearch = document.getElementById('disenchant-search');
    if (disenchantSearch) {
        disenchantSearch.addEventListener('input', (e) => {
            state.searchQueries.disenchanter = e.target.value.toLowerCase().trim();
            renderDisenchanter();
        });
    }

    const loadoutsSearch = document.getElementById('loadouts-search');
    if (loadoutsSearch) {
        loadoutsSearch.addEventListener('input', (e) => {
            state.searchQueries.loadouts = e.target.value.toLowerCase().trim();
            renderLoadouts();
        });
    }

    initBraverySync();
}

function switchSkinTab(tabName) {
    state.activeTab = tabName;
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(s => {
        s.classList.toggle('active', s.id === `tab-${tabName}`);
    });
}

// --- Tab 1: Crafter ---
async function fetchCrafterData() {
    try {
        const res = await fetch('/api/crafter');
        const data = await res.json();
        if (data.success) {
            state.crafterData = data;
            renderCrafter();
        }
    } catch (e) {
        console.error('Error fetching crafter data:', e);
    }
}

function renderCrafter() {
    const container = document.getElementById('crafter-cards-container');
    const emptyState = document.getElementById('crafter-empty-state');
    const badge = document.getElementById('badge-crafter-count');
    const totalSkinsStat = document.getElementById('crafter-total-skins');

    if (!state.crafterData || !state.crafterData.champions) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        badge.innerText = '0';
        return;
    }

    const currentOE = (state.status && state.status.currencies) ? state.status.currencies.oe : (state.crafterData.oe || 0);
    const query = state.searchQueries.crafter;

    const filteredChamps = state.crafterData.champions.filter(item => {
        if (!query) return true;
        const champMatch = item.champ.name.toLowerCase().includes(query);
        const skinMatch = item.shards.some(s => s.skinName.toLowerCase().includes(query));
        return champMatch || skinMatch;
    });

    let totalAvailableShards = 0;
    filteredChamps.forEach(c => totalAvailableShards += c.shards.length);

    badge.innerText = totalAvailableShards;
    if (totalSkinsStat) totalSkinsStat.innerText = `${totalAvailableShards} Skins`;

    if (filteredChamps.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.innerHTML = filteredChamps.map(item => {
        const champ = item.champ;
        const shardsHtml = item.shards.map(shard => {
            const canAfford = currentOE >= shard.cost;
            const btnText = canAfford ? `Unlock (${shard.cost.toLocaleString()} OE)` : `Need ${shard.cost.toLocaleString()} OE`;
            const btnClass = canAfford ? 'btn-craft' : 'btn-craft btn-disabled';

            return `
                <div class="shard-row-item" id="shard-item-${shard.lootId}">
                    <img src="/lcu-img/${shard.splashPath}" alt="${shard.skinName}" class="shard-thumb" loading="lazy">
                    <div class="shard-info">
                        <h4 class="shard-name" title="${shard.skinName}">${shard.skinName}</h4>
                        <div class="shard-cost-badge">
                            <span>💎</span>
                            <span class="${canAfford ? 'text-gold' : 'text-danger'}">${shard.cost.toLocaleString()} OE</span>
                            ${shard.count > 1 ? `<span class="shard-count-tag">x${shard.count}</span>` : ''}
                        </div>
                    </div>
                    <button 
                        class="${btnClass}" 
                        data-loot-id="${shard.lootId}" 
                        data-cost="${shard.cost}"
                        data-skin-name="${shard.skinName}"
                        ${!canAfford ? 'disabled' : ''}
                        onclick="upgradeSkin('${shard.lootId}', ${shard.cost}, '${shard.skinName}', '${champ.id}')">
                        ${btnText}
                    </button>
                </div>
            `;
        }).join('');

        return `
            <div class="champ-craft-card" id="crafter-champ-${champ.id}">
                <div class="champ-portrait-col">
                    <img src="/lcu-img/${champ.img}" alt="${champ.name}" loading="lazy">
                    <h3>${champ.name}</h3>
                    <span class="badge-tag missing-tag">0 Skins</span>
                </div>
                <div class="shards-col">
                    ${shardsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function upgradeSkin(lootId, cost, skinName, champId) {
    const shardCard = document.getElementById(`shard-item-${lootId}`);
    if (shardCard) shardCard.classList.add('loading-shimmer');

    try {
        const res = await fetch('/api/crafter/upgrade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ loot_id: lootId })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Skin Unlocked! ✨', `Successfully unlocked ${skinName}!`, 'success');
            refreshAllData();
        } else {
            showToast('Unlock Failed', data.error || 'Failed to craft skin.', 'error');
            if (shardCard) shardCard.classList.remove('loading-shimmer');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
        if (shardCard) shardCard.classList.remove('loading-shimmer');
    }
}

// --- Tab 2: Disenchanter ---
async function fetchDisenchanterData() {
    try {
        const res = await fetch('/api/disenchanter');
        const data = await res.json();
        if (data.success) {
            state.disenchantData = data;
            renderDisenchanter();
        }
    } catch (e) {
        console.error('Error fetching disenchanter data:', e);
    }
}

function renderDisenchanter() {
    const container = document.getElementById('disenchant-cards-container');
    const emptyState = document.getElementById('disenchant-empty-state');
    const badge = document.getElementById('badge-disenchant-count');
    const totalCountStat = document.getElementById('disenchant-total-count');
    const totalOeStat = document.getElementById('disenchant-total-oe-gain');

    if (!state.disenchantData || !state.disenchantData.shards) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        badge.innerText = '0';
        return;
    }

    const query = state.searchQueries.disenchanter;
    const filteredShards = state.disenchantData.shards.filter(item => {
        if (state.hiddenDisenchantLootIds.has(item.lootId)) return false;
        if (!query) return true;
        return item.champName.toLowerCase().includes(query) || item.skinName.toLowerCase().includes(query);
    });

    let totalOeGain = 0;
    filteredShards.forEach(s => totalOeGain += (s.disenchantValue * s.count));

    badge.innerText = filteredShards.length;
    if (totalCountStat) totalCountStat.innerText = `${filteredShards.length} Shards`;
    if (totalOeStat) totalOeStat.innerText = `+${totalOeGain.toLocaleString()} OE`;

    if (filteredShards.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.innerHTML = filteredShards.map(shard => {
        const totalShardOE = shard.disenchantValue * shard.count;
        const ownedSkinsHtml = (shard.ownedSkins || []).map(os => `
            <div class="owned-skin-mini" title="Owned: ${os.name}">
                <img src="/lcu-img/${os.img}" alt="${os.name}" loading="lazy">
                <span>${os.name}</span>
            </div>
        `).join('');

        return `
            <div class="disenchant-card" id="disenchant-card-${shard.lootId}">
                <div class="owned-preview-col">
                    <div class="owned-header">
                        <img src="/lcu-img/${shard.champPortrait}" alt="${shard.champName}" loading="lazy">
                        <h4 title="${shard.champName}">${shard.champName}</h4>
                    </div>
                    <div class="owned-skins-thumbs">
                        ${ownedSkinsHtml}
                    </div>
                </div>

                <div class="shard-action-col">
                    <div class="shard-splash-hero">
                        <img src="/lcu-img/${shard.splashPath}" alt="${shard.skinName}" loading="lazy">
                        ${shard.count > 1 ? `<span class="shard-badge-count">x${shard.count}</span>` : ''}
                    </div>
                    <div>
                        <h4 class="shard-target-title" title="${shard.skinName}">${shard.skinName}</h4>
                        <div class="shard-disenchant-val">+${totalShardOE.toLocaleString()} OE Gain</div>
                    </div>
                    <div class="action-btn-group">
                        <button 
                            class="btn-disenchant"
                            onclick="disenchantSkin('${shard.lootId}', ${shard.count}, '${shard.skinName}', ${totalShardOE})">
                            <span>💎</span> Disenchant
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function disenchantSkin(lootId, count, skinName, totalOE) {
    const card = document.getElementById(`disenchant-card-${lootId}`);
    if (card) card.classList.add('loading-shimmer');

    try {
        const res = await fetch('/api/disenchanter/disenchant', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ loot_id: lootId, repeat: count })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Disenchanted! 💎', `+${totalOE} OE gained from ${skinName}`, 'success');
            state.hiddenDisenchantLootIds.add(lootId);
            if (card) card.remove();
            refreshAllData();
        } else {
            showToast('Disenchant Failed', data.error || 'Failed to disenchant.', 'error');
            if (card) card.classList.remove('loading-shimmer');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
        if (card) card.classList.remove('loading-shimmer');
    }
}

// --- Tab 3: Auto-Equipper Loadouts ---
async function fetchLoadoutsData() {
    try {
        const res = await fetch('/api/loadouts');
        const data = await res.json();
        if (data.success) {
            state.loadoutsData = data;
            renderLoadouts();
        }
    } catch (e) {
        console.error('Error fetching loadouts data:', e);
    }
}

function renderLoadouts() {
    const container = document.getElementById('loadouts-container');
    const emptyState = document.getElementById('loadouts-empty-state');
    const badge = document.getElementById('badge-loadouts-count');
    
    if (!state.loadoutsData) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        badge.innerText = '0';
        return;
    }

    const countAll = state.loadoutsData.totalChampionsWithSkins || 0;
    const countConfig = state.loadoutsData.configured ? state.loadoutsData.configured.length : 0;
    const countUnconfig = state.loadoutsData.unconfigured ? state.loadoutsData.unconfigured.length : 0;

    badge.innerText = countConfig;
    document.getElementById('loadouts-count-all').innerText = countAll;
    document.getElementById('loadouts-count-configured').innerText = countConfig;
    document.getElementById('loadouts-count-unconfigured').innerText = countUnconfig;

    let targetList = [];
    if (state.loadoutsFilter === 'configured') targetList = state.loadoutsData.configured || [];
    else if (state.loadoutsFilter === 'unconfigured') targetList = state.loadoutsData.unconfigured || [];
    else targetList = [...(state.loadoutsData.configured || []), ...(state.loadoutsData.unconfigured || [])];

    const query = state.searchQueries.loadouts;
    const filteredList = targetList.filter(item => {
        if (!query) return true;
        const champMatch = item.name.toLowerCase().includes(query);
        const skinMatch = item.skins.some(s => s.name.toLowerCase().includes(query));
        return champMatch || skinMatch;
    });

    if (filteredList.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.innerHTML = filteredList.map(champ => {
        const skinsHtml = champ.skins.map(skin => {
            const isSelected = (champ.selectedSkinId === skin.id);
            return `
                <div class="skin-tile ${isSelected ? 'selected' : ''}" 
                     onclick="saveLoadoutFavorite('${champ.id}', ${skin.id}, '${skin.name}')"
                     title="${skin.name}">
                    <div class="skin-tile-img-wrap">
                        <img src="/lcu-img/${skin.img}" alt="${skin.name}" loading="lazy">
                        ${isSelected ? '<span class="skin-tile-badge">★ ACTIVE</span>' : ''}
                    </div>
                    <div class="skin-tile-name">${skin.name}</div>
                </div>
            `;
        }).join('');

        return `
            <div class="loadout-card" id="loadout-champ-${champ.id}">
                <div class="loadout-champ-col">
                    <img src="/lcu-img/${champ.img}" alt="${champ.name}" loading="lazy">
                    <h3>${champ.name}</h3>
                    <span class="badge-tag">${champ.skins.length} Skins</span>
                </div>
                <div class="loadout-skins-gallery">
                    ${skinsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function saveLoadoutFavorite(champId, skinId, skinName) {
    try {
        const res = await fetch('/api/loadouts/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ champ_id: champId, skin_id: skinId })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Preference Saved', `Favorite set: ${skinName}`, 'info');
            fetchLoadoutsData();
        }
    } catch (e) {
        console.error('Failed to save skin preference:', e);
    }
}

// --- Arena Bravery Sync ---
let syncPollInterval = null;

function initBraverySync() {
    const btnOpen = document.getElementById('btn-open-bravery-modal');
    const btnClose = document.getElementById('btn-close-bravery-modal');
    const modal = document.getElementById('bravery-sync-modal');
    const btnStart = document.getElementById('btn-start-bravery-sync');
    const btnStop = document.getElementById('btn-stop-bravery-sync');

    if (btnOpen && modal) btnOpen.addEventListener('click', () => modal.classList.remove('hidden'));
    if (btnClose && modal) btnClose.addEventListener('click', () => modal.classList.add('hidden'));

    if (btnStart) btnStart.addEventListener('click', startBraverySync);
    if (btnStop) btnStop.addEventListener('click', stopBraverySync);
}

async function startBraverySync() {
    try {
        const res = await fetch('/api/sync/bravery/start', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            showToast('Sync Started', 'Bravery Custom Lobby sync is running...', 'info');
            if (syncPollInterval) clearInterval(syncPollInterval);
            syncPollInterval = setInterval(checkBraverySyncStatus, 500);
        } else {
            showToast('Sync Failed', data.error || 'Could not start sync.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

async function stopBraverySync() {
    try {
        await fetch('/api/sync/bravery/stop', { method: 'POST' });
        if (syncPollInterval) clearInterval(syncPollInterval);
        checkBraverySyncStatus();
        showToast('Sync Stopped', 'Skin synchronization was canceled.', 'info');
    } catch (e) {
        console.error('Failed to stop sync', e);
    }
}

async function checkBraverySyncStatus() {
    try {
        const res = await fetch('/api/sync/bravery/status');
        const data = await res.json();

        const btnStart = document.getElementById('btn-start-bravery-sync');
        const btnStop = document.getElementById('btn-stop-bravery-sync');
        const progressArea = document.getElementById('sync-progress-area');
        const fill = document.getElementById('sync-progress-fill');
        const msg = document.getElementById('sync-status-msg');
        const countText = document.getElementById('sync-progress-text');
        const percentText = document.getElementById('sync-progress-percent');

        if (data.running) {
            if (btnStart) btnStart.classList.add('hidden');
            if (btnStop) btnStop.classList.remove('hidden');
            if (progressArea) progressArea.classList.remove('hidden');

            const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
            if (fill) fill.style.width = `${percent}%`;
            if (msg) msg.innerText = data.message || 'Synchronizing...';
            if (countText) countText.innerText = `${data.current} / ${data.total} Champions`;
            if (percentText) percentText.innerText = `${percent}%`;
        } else {
            if (btnStart) btnStart.classList.remove('hidden');
            if (btnStop) btnStop.classList.add('hidden');
            if (data.status === 'done') {
                if (fill) fill.style.width = '100%';
                if (msg) msg.innerText = '✨ Synchronization completed successfully!';
                if (percentText) percentText.innerText = '100%';
                if (syncPollInterval) clearInterval(syncPollInterval);
            } else if (data.status === 'error') {
                if (msg) msg.innerText = data.message || 'Error during synchronization.';
                if (syncPollInterval) clearInterval(syncPollInterval);
            }
        }
    } catch (e) {
        console.error('Error polling sync status', e);
    }
}

// =========================================================================
// SECTION 2: HEXSOCIAL FRIEND MANAGER CONTROLLER
// =========================================================================
function initSocialHub() {
    // 1. Sidebar Nav Views
    document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(i => i.classList.remove('active'));
            document.querySelectorAll('.group-nav-item').forEach(g => g.classList.remove('active'));
            item.classList.add('active');
            state.socialView = item.getAttribute('data-view');
            renderSocialHub();
        });
    });

    // 2. Personal Presence Status Updates
    const selectAvailability = document.getElementById('select-my-availability');
    if (selectAvailability) {
        selectAvailability.addEventListener('change', async (e) => {
            const avail = e.target.value;
            await updateMyPresence(avail, null);
        });
    }

    const btnSaveStatus = document.getElementById('btn-save-my-status');
    const inputStatusMsg = document.getElementById('input-my-status-msg');
    if (btnSaveStatus && inputStatusMsg) {
        const handleStatusSave = async () => {
            const msg = inputStatusMsg.value.trim();
            await updateMyPresence(null, msg);
        };
        btnSaveStatus.addEventListener('click', handleStatusSave);
        inputStatusMsg.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleStatusSave();
        });
    }

    // 3. Social Search Input
    const socialSearch = document.getElementById('social-search');
    if (socialSearch) {
        socialSearch.addEventListener('input', (e) => {
            state.socialSearch = e.target.value.toLowerCase().trim();
            renderSocialHub();
        });
    }

    // 4. Social Filter Pills
    document.querySelectorAll('.filter-pill[data-social-filter]').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill[data-social-filter]').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            state.socialFilter = pill.getAttribute('data-social-filter');
            renderSocialHub();
        });
    });

    // 5. Social Sorting
    const selectSort = document.getElementById('select-social-sort');
    if (selectSort) {
        selectSort.addEventListener('change', (e) => {
            state.socialSort = e.target.value;
            renderSocialHub();
        });
    }

    // 6. Layout View Toggle
    const btnGrid = document.getElementById('btn-view-grid');
    const btnList = document.getElementById('btn-view-list');
    if (btnGrid && btnList) {
        btnGrid.addEventListener('click', () => {
            btnGrid.classList.add('active');
            btnList.classList.remove('active');
            state.socialLayout = 'grid';
            renderSocialHub();
        });
        btnList.addEventListener('click', () => {
            btnList.classList.add('active');
            btnGrid.classList.remove('active');
            state.socialLayout = 'list';
            renderSocialHub();
        });
    }

    // 7. Batch Operations
    const btnBatchSelectAll = document.getElementById('btn-batch-select-all');
    const btnBatchClear = document.getElementById('btn-batch-clear');
    const btnExecuteBatchMove = document.getElementById('btn-execute-batch-move');
    const btnExecuteBatchRemove = document.getElementById('btn-execute-batch-remove');

    if (btnBatchSelectAll) btnBatchSelectAll.addEventListener('click', selectAllFriendsInView);
    if (btnBatchClear) btnBatchClear.addEventListener('click', clearSelectedFriends);
    if (btnExecuteBatchMove) btnExecuteBatchMove.addEventListener('click', executeBatchMove);
    if (btnExecuteBatchRemove) btnExecuteBatchRemove.addEventListener('click', promptBatchRemoveFriends);

    // 8. Modals Triggers
    const btnOpenAddFriend = document.getElementById('btn-open-add-friend');
    const btnCloseAddModal = document.getElementById('btn-close-add-modal');
    const btnSubmitAddFriend = document.getElementById('btn-submit-add-friend');
    const modalAddFriend = document.getElementById('modal-add-friend');

    if (btnOpenAddFriend && modalAddFriend) {
        btnOpenAddFriend.addEventListener('click', () => modalAddFriend.classList.remove('hidden'));
    }
    if (btnCloseAddModal && modalAddFriend) {
        btnCloseAddModal.addEventListener('click', () => modalAddFriend.classList.add('hidden'));
    }
    if (btnSubmitAddFriend) {
        btnSubmitAddFriend.addEventListener('click', submitAddFriend);
    }

    // Quick Add Folder & Folder Manager
    const btnAddFolderQuick = document.getElementById('btn-add-folder-quick');
    const btnOpenFolderManager = document.getElementById('btn-open-folder-manager');
    const btnCloseFolderModal = document.getElementById('btn-close-folder-modal');
    const btnSubmitCreateFolder = document.getElementById('btn-submit-create-folder');
    const modalManageFolders = document.getElementById('modal-manage-folders');

    if (btnAddFolderQuick && modalManageFolders) {
        btnAddFolderQuick.addEventListener('click', () => {
            modalManageFolders.classList.remove('hidden');
            renderFolderManagerModal();
        });
    }
    if (btnOpenFolderManager && modalManageFolders) {
        btnOpenFolderManager.addEventListener('click', () => {
            modalManageFolders.classList.remove('hidden');
            renderFolderManagerModal();
        });
    }
    if (btnCloseFolderModal && modalManageFolders) {
        btnCloseFolderModal.addEventListener('click', () => modalManageFolders.classList.add('hidden'));
    }
    if (btnSubmitCreateFolder) {
        btnSubmitCreateFolder.addEventListener('click', submitCreateFolder);
    }

    // Requests Modal
    const btnOpenRequests = document.getElementById('btn-open-requests-modal');
    const btnCloseRequests = document.getElementById('btn-close-requests-modal');
    const modalRequests = document.getElementById('modal-friend-requests');

    if (btnOpenRequests && modalRequests) {
        btnOpenRequests.addEventListener('click', () => {
            modalRequests.classList.remove('hidden');
            renderRequestsModal();
        });
    }
    if (btnCloseRequests && modalRequests) {
        btnCloseRequests.addEventListener('click', () => modalRequests.classList.add('hidden'));
    }

    const btnReqTabIn = document.getElementById('btn-req-tab-incoming');
    const btnReqTabOut = document.getElementById('btn-req-tab-outgoing');
    if (btnReqTabIn && btnReqTabOut) {
        btnReqTabIn.addEventListener('click', () => {
            btnReqTabIn.classList.add('active');
            btnReqTabOut.classList.remove('active');
            state.activeRequestTab = 'incoming';
            renderRequestsModal();
        });
        btnReqTabOut.addEventListener('click', () => {
            btnReqTabOut.classList.add('active');
            btnReqTabIn.classList.remove('active');
            state.activeRequestTab = 'outgoing';
            renderRequestsModal();
        });
    }

    // Blocked Modal
    const btnOpenBlocked = document.getElementById('btn-open-blocked-modal');
    const btnCloseBlocked = document.getElementById('btn-close-blocked-modal');
    const modalBlocked = document.getElementById('modal-blocked-players');

    if (btnOpenBlocked && modalBlocked) {
        btnOpenBlocked.addEventListener('click', () => {
            modalBlocked.classList.remove('hidden');
            renderBlockedModal();
        });
    }
    if (btnCloseBlocked && modalBlocked) {
        btnCloseBlocked.addEventListener('click', () => modalBlocked.classList.add('hidden'));
    }

    // Friend Profile Drawer Controls
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    if (btnCloseDrawer) {
        btnCloseDrawer.addEventListener('click', closeProfileDrawer);
    }

    const btnDrawerSaveNote = document.getElementById('btn-drawer-save-note');
    if (btnDrawerSaveNote) {
        btnDrawerSaveNote.addEventListener('click', saveDrawerNote);
    }

    const drawerSelectFolder = document.getElementById('drawer-select-folder');
    if (drawerSelectFolder) {
        drawerSelectFolder.addEventListener('change', changeDrawerFolder);
    }

    const btnDrawerInvite = document.getElementById('btn-drawer-invite');
    if (btnDrawerInvite) {
        btnDrawerInvite.addEventListener('click', () => {
            if (state.inspectedFriend) {
                inviteFriendToLobby(state.inspectedFriend.summonerId, state.inspectedFriend.puuid, state.inspectedFriend.riotId);
            }
        });
    }

    const btnDrawerRemove = document.getElementById('btn-drawer-remove');
    if (btnDrawerRemove) {
        btnDrawerRemove.addEventListener('click', () => {
            if (state.inspectedFriend) {
                confirmAction(
                    'Remove Friend',
                    `Are you sure you want to unfriend <strong>${state.inspectedFriend.riotId}</strong>?`,
                    () => removeFriend(state.inspectedFriend.id, state.inspectedFriend.riotId)
                );
            }
        });
    }

    const btnDrawerBlock = document.getElementById('btn-drawer-block');
    if (btnDrawerBlock) {
        btnDrawerBlock.addEventListener('click', () => {
            if (state.inspectedFriend) {
                confirmAction(
                    'Block Player',
                    `Are you sure you want to block <strong>${state.inspectedFriend.riotId}</strong>?`,
                    () => blockPlayer(state.inspectedFriend.puuid, state.inspectedFriend.riotId)
                );
            }
        });
    }

    // Confirmation Modal
    const btnConfirmYes = document.getElementById('btn-confirm-yes');
    const btnConfirmNo = document.getElementById('btn-confirm-no');
    const modalConfirm = document.getElementById('modal-social-confirm');

    if (btnConfirmYes) {
        btnConfirmYes.addEventListener('click', () => {
            if (modalConfirm) modalConfirm.classList.add('hidden');
            if (state.confirmCallback) {
                state.confirmCallback();
                state.confirmCallback = null;
            }
        });
    }
    if (btnConfirmNo && modalConfirm) {
        btnConfirmNo.addEventListener('click', () => {
            modalConfirm.classList.add('hidden');
            state.confirmCallback = null;
        });
    }

    // Reset filter empty button
    const btnEmptyReset = document.getElementById('btn-empty-reset');
    if (btnEmptyReset) {
        btnEmptyReset.addEventListener('click', () => {
            state.socialFilter = 'all';
            state.socialView = 'all';
            state.socialSearch = '';
            const searchInput = document.getElementById('social-search');
            if (searchInput) searchInput.value = '';
            document.querySelectorAll('.filter-pill[data-social-filter]').forEach(p => {
                p.classList.toggle('active', p.getAttribute('data-social-filter') === 'all');
            });
            document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(i => {
                i.classList.toggle('active', i.getAttribute('data-view') === 'all');
            });
            renderSocialHub();
        });
    }
}

// --- Fetch Social Data ---
async function fetchSocialData(isSilent = false) {
    try {
        const res = await fetch('/api/social/overview');
        const data = await res.json();
        if (data.success) {
            state.socialData = data;
            renderSocialHub();
        }
    } catch (e) {
        if (!isSilent) console.error('Error fetching social data:', e);
    }
}

// --- Main Render Engine for HexSocial ---
function renderSocialHub() {
    if (!state.socialData) return;

    const data = state.socialData;
    const counts = data.counts || { total: 0, online: 0, inGame: 0, away: 0, offline: 0 };
    const reqTotal = (data.requests && data.requests.total) ? data.requests.total : 0;

    // 1. Header & Badge Updates
    const headerSocialBadge = document.getElementById('header-social-badge');
    if (headerSocialBadge) {
        headerSocialBadge.innerText = reqTotal;
        headerSocialBadge.classList.toggle('hidden', reqTotal === 0);
    }

    const badgeReq = document.getElementById('badge-requests-count');
    if (badgeReq) {
        badgeReq.innerText = reqTotal;
        badgeReq.classList.toggle('hidden', reqTotal === 0);
    }

    const badgeBlocked = document.getElementById('badge-blocked-count');
    if (badgeBlocked) {
        badgeBlocked.innerText = data.blocked ? data.blocked.length : 0;
    }

    // 2. Personal Presence in Sidebar
    if (data.me) {
        const myAvatar = document.getElementById('social-my-avatar');
        const myDot = document.getElementById('social-my-status-dot');
        const myName = document.getElementById('social-my-name');
        const myTag = document.getElementById('social-my-tag');
        const selectAvail = document.getElementById('select-my-availability');
        const inputStatus = document.getElementById('input-my-status-msg');

        if (myAvatar && data.me.iconUrl) myAvatar.src = data.me.iconUrl;
        if (myName) myName.innerText = data.me.gameName || 'Summoner';
        if (myTag) myTag.innerText = data.me.gameTag ? `#${data.me.gameTag}` : '';
        if (selectAvail && !selectAvail.matches(':focus')) selectAvail.value = data.me.availability || 'online';
        if (inputStatus && !inputStatus.matches(':focus')) inputStatus.value = data.me.statusMessage || '';

        if (myDot) {
            myDot.className = `presence-dot status-${data.me.availability || 'online'}`;
        }
    }

    // 3. Update Sidebar View Counts
    document.getElementById('badge-view-all').innerText = counts.total;
    document.getElementById('badge-view-online').innerText = counts.online;
    document.getElementById('badge-view-ingame').innerText = counts.inGame;
    document.getElementById('badge-view-away').innerText = counts.away;
    document.getElementById('badge-view-offline').innerText = counts.offline;

    // Smart Fingerprint Diffing to prevent DOM thrashing and UI stutter
    const friendsRaw = data.friends || [];
    const currentFingerprint = `${state.socialView}_${state.socialFilter}_${state.socialSort}_${state.socialSearch}_${state.socialLayout}_${state.selectedFriends.size}_${(data.groups || []).map(g => `${g.id}:${g.name}:${g.friends ? g.friends.length : 0}`).join(',')}_${friendsRaw.map(f => `${f.id}:${f.presence.statusType}:${f.presence.gameStatus}:${f.presence.gameTimeMinutes}:${f.groupId}:${f.note}`).join(';')}`;

    if (state.lastSocialFingerprint === currentFingerprint) {
        return; // Exact same UI state: skip heavy DOM rebuild!
    }
    state.lastSocialFingerprint = currentFingerprint;

    // 4. Render Sidebar Folders / Groups List
    const groupsListContainer = document.getElementById('social-groups-list');
    if (groupsListContainer && data.groups) {
        groupsListContainer.innerHTML = data.groups.map(group => {
            const isSelectedGroup = (state.socialView === `folder_${group.id}`);
            const friendCount = group.friends ? group.friends.length : 0;
            const isDefault = group.isDefault || (group.id === 0);

            return `
                <div class="group-nav-item ${isSelectedGroup ? 'active' : ''}" data-group-id="${group.id}" onclick="selectFolderView(${group.id})">
                    <div class="group-info" title="${group.name}">
                        <span>${isDefault ? '📁' : '📂'}</span>
                        <span class="group-name-label">${group.name}</span>
                    </div>
                    <div class="group-actions">
                        <span class="nav-badge">${friendCount}</span>
                        ${!isDefault ? `
                            <button class="btn-group-action" title="Rename Folder" onclick="event.stopPropagation(); promptRenameFolder(${group.id}, '${group.name}')">✏️</button>
                            <button class="btn-group-action" title="Delete Folder" onclick="event.stopPropagation(); promptDeleteFolder(${group.id}, '${group.name}')">🗑️</button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    // 5. Filter & Sort Friends List
    let friends = [...(data.friends || [])];

    // Filter by View
    let viewTitle = 'All Friends';
    if (state.socialView === 'online') {
        friends = friends.filter(f => f.presence.statusType !== 'offline');
        viewTitle = 'Online & Active Friends';
    } else if (state.socialView === 'ingame') {
        friends = friends.filter(f => ['inGame', 'championSelect', 'inGame_TFT', 'inGame_KIWI'].includes(f.presence.gameStatus));
        viewTitle = 'In Game & Champ Select';
    } else if (state.socialView === 'away') {
        friends = friends.filter(f => f.presence.statusType === 'away');
        viewTitle = 'Away Friends';
    } else if (state.socialView === 'offline') {
        friends = friends.filter(f => f.presence.statusType === 'offline' || f.presence.statusType === 'mobile');
        viewTitle = 'Offline Friends';
    } else if (state.socialView.startsWith('folder_')) {
        const folderId = parseInt(state.socialView.replace('folder_', ''), 10);
        const folderObj = (data.groups || []).find(g => g.id === folderId);
        viewTitle = folderObj ? `Folder: ${folderObj.name}` : 'Folder';
        friends = friends.filter(f => f.groupId === folderId);
    }

    // Secondary Filter Pills
    if (state.socialFilter === 'online') {
        friends = friends.filter(f => f.presence.statusType !== 'offline');
    } else if (state.socialFilter === 'ingame') {
        friends = friends.filter(f => ['inGame', 'championSelect'].includes(f.presence.gameStatus));
    } else if (state.socialFilter === 'offline') {
        friends = friends.filter(f => f.presence.statusType === 'offline');
    }

    // Search Query
    if (state.socialSearch) {
        const q = state.socialSearch;
        friends = friends.filter(f => {
            const nameMatch = f.gameName.toLowerCase().includes(q) || f.riotId.toLowerCase().includes(q);
            const noteMatch = f.note && f.note.toLowerCase().includes(q);
            const groupMatch = f.groupName && f.groupName.toLowerCase().includes(q);
            const presenceMatch = f.presence.detail && f.presence.detail.toLowerCase().includes(q);
            return nameMatch || noteMatch || groupMatch || presenceMatch;
        });
    }

    // Sorting
    friends.sort((a, b) => {
        if (state.socialSort === 'name') {
            return a.gameName.localeCompare(b.gameName);
        } else if (state.socialSort === 'folder') {
            return a.groupName.localeCompare(b.groupName);
        } else if (state.socialSort === 'rank') {
            return (b.presence.tier || '').localeCompare(a.presence.tier || '');
        } else {
            // Default: Presence (In-Game -> Online -> Away -> Offline)
            const getPriority = (f) => {
                if (f.presence.gameStatus === 'inGame') return 4;
                if (f.presence.statusType === 'online') return 3;
                if (f.presence.statusType === 'away') return 2;
                if (f.presence.statusType === 'dnd') return 2;
                return 1;
            };
            const pDiff = getPriority(b) - getPriority(a);
            if (pDiff !== 0) return pDiff;
            return a.gameName.localeCompare(b.gameName);
        }
    });

    // Update Toolbar View Header
    const currentViewTitle = document.getElementById('social-current-view-title');
    const filteredCountBadge = document.getElementById('social-filtered-count-badge');
    if (currentViewTitle) currentViewTitle.innerText = viewTitle;
    if (filteredCountBadge) filteredCountBadge.innerText = `${friends.length} Friends`;

    // 6. Render Friends Grid / List
    const friendsContainer = document.getElementById('social-friends-container');
    const emptyState = document.getElementById('social-empty-state');

    if (friendsContainer) {
        friendsContainer.className = `social-friends-grid ${state.socialLayout === 'list' ? 'list-layout' : ''}`;
    }

    if (friends.length === 0) {
        if (friendsContainer) friendsContainer.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
    } else {
        if (emptyState) emptyState.classList.add('hidden');
        if (friendsContainer) {
            friendsContainer.innerHTML = friends.map(f => renderFriendCardHTML(f, data.groups || [])).join('');
        }
    }

    // 7. Update Batch Bar
    updateBatchBar(friends);
}

// --- Friend Card HTML Builder ---
function renderFriendCardHTML(friend, allGroups) {
    const isSelected = state.selectedFriends.has(friend.id);
    const presence = friend.presence || {};
    const statusType = presence.statusType || 'offline';
    const isIngame = ['inGame', 'championSelect', 'inGame_TFT', 'inGame_KIWI'].includes(presence.gameStatus);

    let statusDotClass = `status-${statusType}`;
    if (isIngame) statusDotClass = 'status-ingame';

    const safeFriendId = escapeHTML(friend.id);
    const safePuuid = escapeHTML(friend.puuid);
    const safeGameName = escapeHTML(friend.gameName);
    const safeGameTag = escapeHTML(friend.gameTag);
    const safeRiotId = escapeHTML(friend.riotId);
    const safeIconUrl = escapeHTML(friend.iconUrl);
    const safeNote = escapeHTML(friend.note);
    const safeStatusLabel = escapeHTML(presence.statusLabel || 'Online');
    const safeDetail = escapeHTML(presence.detail || 'In League Client');
    const safeRank = escapeHTML(presence.rankText || '');

    // Folder Options for inline quick switcher
    const folderOptions = allGroups.map(g => `
        <option value="${escapeHTML(g.id)}" ${friend.groupId === g.id ? 'selected' : ''}>${escapeHTML(g.name)}</option>
    `).join('');

    return `
        <div class="friend-card ${isSelected ? 'card-selected' : ''}" id="friend-card-${safeFriendId}" data-friend-id="${safeFriendId}">
            <div class="friend-card-header">
                <input type="checkbox" class="friend-card-checkbox" ${isSelected ? 'checked' : ''} onclick="toggleSelectFriend('${safeFriendId}')">
                
                <div class="friend-avatar-wrap" onclick="openProfileDrawer('${safePuuid}')" title="Inspect Profile">
                    <img src="${safeIconUrl}" alt="${safeGameName}" class="friend-avatar-img" loading="lazy">
                    <span class="presence-dot ${statusDotClass}"></span>
                </div>

                <div class="friend-identity">
                    <div class="friend-name-row">
                        <span class="friend-game-name" onclick="openProfileDrawer('${safePuuid}')" title="${safeRiotId}">${safeGameName}</span>
                        <span class="friend-game-tag">#${safeGameTag}</span>
                    </div>
                    <div class="friend-meta-row">
                        ${presence.tier ? `<span class="friend-rank-pill">🏆 ${safeRank}</span>` : ''}
                    </div>
                </div>
            </div>

            <!-- Live Game / Activity Presence -->
            <div class="friend-presence-box ${isIngame ? 'status-ingame' : ''}">
                <span class="presence-indicator-icon">${isIngame ? '⚔️' : (statusType === 'online' ? '🟢' : (statusType === 'away' ? '🟡' : '⚪'))}</span>
                <div class="presence-text-wrap">
                    <div class="presence-primary-text">${safeStatusLabel}</div>
                    <div class="presence-secondary-text">${safeDetail}</div>
                </div>
            </div>

            <!-- Note Preview (if set) -->
            ${friend.note ? `<div class="friend-note-preview" title="${safeNote}">📝 ${safeNote}</div>` : ''}

            <!-- Card Footer: Folder Assign & Actions -->
            <div class="friend-card-footer">
                <select class="friend-group-select-pill" title="Assigned Folder" onchange="changeFriendFolder('${safeFriendId}', this.value)">
                    ${folderOptions}
                </select>

                <div class="friend-card-actions">
                    <button class="btn-card-action btn-action-invite" title="Invite to Lobby" onclick="inviteFriendToLobby(${parseInt(friend.summonerId, 10) || 0}, '${safePuuid}', '${safeRiotId}')">
                        🎮 Invite
                    </button>
                    <button class="btn-card-action" title="View Profile" onclick="openProfileDrawer('${safePuuid}')">
                        👤
                    </button>
                    <button class="btn-card-action" title="Unfriend" onclick="promptRemoveFriend('${safeFriendId}', '${safeRiotId}')">
                        🗑️
                    </button>
                </div>
            </div>
        </div>
    `;
}

// --- Folder & View Selection ---
function selectFolderView(groupId) {
    document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(i => i.classList.remove('active'));
    document.querySelectorAll('.group-nav-item').forEach(g => {
        g.classList.toggle('active', parseInt(g.getAttribute('data-group-id'), 10) === groupId);
    });
    state.socialView = `folder_${groupId}`;
    renderSocialHub();
}

// --- Batch Selection Operations ---
function toggleSelectFriend(friendId) {
    if (state.selectedFriends.has(friendId)) {
        state.selectedFriends.delete(friendId);
    } else {
        state.selectedFriends.add(friendId);
    }
    renderSocialHub();
}

function selectAllFriendsInView() {
    const friendCards = document.querySelectorAll('.friend-card[data-friend-id]');
    friendCards.forEach(card => {
        state.selectedFriends.add(card.getAttribute('data-friend-id'));
    });
    renderSocialHub();
}

function clearSelectedFriends() {
    state.selectedFriends.clear();
    renderSocialHub();
}

function updateBatchBar(visibleFriends) {
    const batchBar = document.getElementById('social-batch-bar');
    const selectedText = document.getElementById('batch-selected-text');
    const batchFolderSelect = document.getElementById('select-batch-folder');

    if (!batchBar) return;

    if (state.selectedFriends.size > 0) {
        batchBar.classList.remove('hidden');
        if (selectedText) {
            selectedText.innerHTML = `<strong>${state.selectedFriends.size}</strong> friends selected`;
        }

        if (batchFolderSelect && state.socialData && state.socialData.groups) {
            batchFolderSelect.innerHTML = state.socialData.groups.map(g => `
                <option value="${g.id}">${g.name}</option>
            `).join('');
        }
    } else {
        batchBar.classList.add('hidden');
    }
}

async function executeBatchMove() {
    const select = document.getElementById('select-batch-folder');
    if (!select) return;

    const targetGroupId = parseInt(select.value, 10);
    const friendIds = Array.from(state.selectedFriends);

    if (friendIds.length === 0) return;

    try {
        const res = await fetch('/api/social/friends/batch-move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ friendIds: friendIds, groupId: targetGroupId })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Friends Moved! 📁', `Successfully moved ${data.moved} friends to folder.`, 'success');
            state.selectedFriends.clear();
            state.lastSocialFingerprint = '';
            fetchSocialData();
        } else {
            showToast('Batch Move Failed', data.error || 'Could not move friends.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

function promptBatchRemoveFriends() {
    const count = state.selectedFriends.size;
    if (count === 0) return;

    confirmAction(
        'Remove Multiple Friends',
        `Are you sure you want to remove <strong>${count}</strong> friends from your friend list?`,
        () => executeBatchRemove()
    );
}

async function executeBatchRemove() {
    const friendIds = Array.from(state.selectedFriends);
    if (friendIds.length === 0) return;

    try {
        const res = await fetch('/api/social/friends/batch-remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ friendIds: friendIds })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Friends Removed 🗑️', `Successfully removed ${data.removed} friends.`, 'info');
            state.selectedFriends.clear();
            state.lastSocialFingerprint = '';
            fetchSocialData();
        } else {
            showToast('Batch Remove Failed', data.error || 'Could not remove friends.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// --- Friend API Actions ---
async function changeFriendFolder(friendId, targetGroupId) {
    try {
        const res = await fetch(`/api/social/friends/${encodeURIComponent(friendId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ groupId: parseInt(targetGroupId, 10) })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Folder Updated', 'Friend moved to new folder.', 'info');
            fetchSocialData();
        } else {
            showToast('Error', data.error || 'Failed to update folder.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

async function updateMyPresence(availability, statusMessage) {
    try {
        const payload = {};
        if (availability) payload.availability = availability;
        if (statusMessage !== null && statusMessage !== undefined) payload.statusMessage = statusMessage;

        const res = await fetch('/api/social/me/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            showToast('Status Updated', 'Presence updated in League Client.', 'success');
            fetchSocialData();
        }
    } catch (e) {
        console.error('Failed to update presence:', e);
    }
}

async function inviteFriendToLobby(summonerId, puuid, riotId) {
    try {
        const res = await fetch('/api/social/invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ summonerId: summonerId, puuid: puuid })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Invitation Sent! 🎮', `Invited ${riotId} to your lobby.`, 'success');
        } else {
            showToast('Invitation Failed', data.error || 'Make sure you are currently in an active lobby.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

function promptRemoveFriend(friendId, riotId) {
    confirmAction(
        'Remove Friend',
        `Are you sure you want to remove <strong>${riotId}</strong> from your friends list?`,
        () => removeFriend(friendId, riotId)
    );
}

async function removeFriend(friendId, riotId) {
    try {
        const res = await fetch(`/api/social/friends/${encodeURIComponent(friendId)}`, {
            method: 'DELETE'
        });
        const data = await res.json();

        if (data.success) {
            showToast('Friend Removed', `Removed ${riotId} from your friend list.`, 'info');
            closeProfileDrawer();
            fetchSocialData();
        } else {
            showToast('Error', data.error || 'Failed to remove friend.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// =========================================================================
// SECTION 3: FRIEND PROFILE DRAWER (HOVERCARD INSPECTOR)
// =========================================================================
async function openProfileDrawer(puuid) {
    const drawer = document.getElementById('social-profile-drawer');
    if (!drawer) return;

    // Find friend in existing social data
    const friend = (state.socialData && state.socialData.friends) 
        ? state.socialData.friends.find(f => f.puuid === puuid) 
        : null;

    if (!friend) return;
    state.inspectedFriend = friend;

    // Populate Hero
    document.getElementById('drawer-avatar').src = friend.iconUrl;
    document.getElementById('drawer-riot-name').innerText = friend.gameName;
    document.getElementById('drawer-riot-tag').innerText = friend.gameTag ? `#${friend.gameTag}` : '';
    document.getElementById('drawer-note-text').value = friend.note || '';

    // Presence Pill
    const presenceBadge = document.getElementById('drawer-presence-badge');
    const isIngame = ['inGame', 'championSelect'].includes(friend.presence.gameStatus);
    const statusType = friend.presence.statusType || 'offline';
    presenceBadge.className = `drawer-presence-pill status-${isIngame ? 'ingame' : statusType}`;
    presenceBadge.innerText = isIngame ? 'IN GAME' : statusType.toUpperCase();

    // Activity Card
    document.getElementById('drawer-activity-title').innerText = friend.presence.statusLabel || 'Online';
    document.getElementById('drawer-activity-detail').innerText = friend.presence.detail || 'In League Client';
    document.getElementById('drawer-activity-icon').innerText = isIngame ? '⚔️' : (statusType === 'online' ? '🟢' : '⚪');

    // Rank Card
    document.getElementById('drawer-rank-tier').innerText = friend.presence.rankText || 'Unranked';
    document.getElementById('drawer-rank-stats').innerText = friend.presence.gameMode || 'No Active Match';

    // Folder Selector
    const drawerSelectFolder = document.getElementById('drawer-select-folder');
    if (drawerSelectFolder && state.socialData && state.socialData.groups) {
        drawerSelectFolder.innerHTML = state.socialData.groups.map(g => `
            <option value="${g.id}" ${friend.groupId === g.id ? 'selected' : ''}>${g.name}</option>
        `).join('');
    }

    drawer.classList.remove('hidden');

    // Fetch Full Detailed Hovercard from LCU
    try {
        const res = await fetch(`/api/social/hovercard/${encodeURIComponent(puuid)}`);
        const hcData = await res.json();
        if (hcData.success && hcData.hovercard) {
            const hc = hcData.hovercard;
            if (hc.summonerLevel) {
                document.getElementById('drawer-level').innerText = hc.summonerLevel;
            }
            if (hc.lol && hc.lol.rankedLeagueTier) {
                const tier = hc.lol.rankedLeagueTier;
                const div = hc.lol.rankedLeagueDivision || '';
                const wins = hc.lol.rankedWins || 0;
                const losses = hc.lol.rankedLosses || 0;
                document.getElementById('drawer-rank-tier').innerText = `${tier.toUpperCase()} ${div}`;
                document.getElementById('drawer-rank-stats').innerText = `${wins} Wins • ${losses} Losses`;
            }
        }
    } catch (e) {
        console.debug('Hovercard fetch error:', e);
    }
}

function closeProfileDrawer() {
    const drawer = document.getElementById('social-profile-drawer');
    if (drawer) drawer.classList.add('hidden');
    state.inspectedFriend = null;
}

async function saveDrawerNote() {
    if (!state.inspectedFriend) return;
    const noteText = document.getElementById('drawer-note-text').value.trim();

    try {
        const res = await fetch(`/api/social/friends/${encodeURIComponent(state.inspectedFriend.id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: noteText })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Note Saved! 📝', 'Friend note updated successfully.', 'success');
            fetchSocialData();
        } else {
            showToast('Error', data.error || 'Failed to save note.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

async function changeDrawerFolder(e) {
    if (!state.inspectedFriend) return;
    const targetGroupId = parseInt(e.target.value, 10);
    await changeFriendFolder(state.inspectedFriend.id, targetGroupId);
}

// =========================================================================
// SECTION 4: MODALS (ADD FRIEND, FOLDERS, REQUESTS, BLOCKED)
// =========================================================================

// --- 1. Add Friend Modal ---
async function submitAddFriend() {
    const input = document.getElementById('input-add-riot-id');
    if (!input) return;

    const riotId = input.value.trim();
    if (!riotId || !riotId.includes('#')) {
        showToast('Invalid Riot ID', 'Please enter in Name#Tag format (e.g. Faker#KR1)', 'error');
        return;
    }

    const [gameName, tagLine] = riotId.split('#');

    try {
        const res = await fetch('/api/social/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gameName: gameName, tagLine: tagLine })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Request Sent! 📬', `Friend request sent to ${riotId}`, 'success');
            document.getElementById('modal-add-friend').classList.add('hidden');
            input.value = '';
            fetchSocialData();
        } else {
            showToast('Request Failed', data.error || 'Player not found or request failed.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// --- 2. Folder Manager Modal ---
function renderFolderManagerModal() {
    const list = document.getElementById('folders-manage-list');
    if (!list || !state.socialData) return;

    const groups = state.socialData.groups || [];
    list.innerHTML = groups.map(g => {
        const isDefault = g.isDefault || (g.id === 0);
        const count = g.friends ? g.friends.length : 0;

        return `
            <div class="folder-manage-row">
                <div class="folder-meta">
                    <span>${isDefault ? '📁' : '📂'}</span>
                    <strong style="color: ${isDefault ? 'var(--gold-primary)' : 'var(--text-main)'}">${g.name}</strong>
                    ${isDefault ? '<span class="count-pill">Default</span>' : ''}
                </div>
                <div>${count} friends</div>
                <div class="folder-actions">
                    ${!isDefault ? `
                        <button class="btn-ghost btn-sm" onclick="promptRenameFolder(${g.id}, '${g.name}')">Rename</button>
                        <button class="btn-danger-outline btn-sm" onclick="promptDeleteFolder(${g.id}, '${g.name}')">Delete</button>
                    ` : '<span style="color:var(--text-muted); font-size:11px;">Fixed</span>'}
                </div>
            </div>
        `;
    }).join('');
}

async function submitCreateFolder() {
    const input = document.getElementById('input-new-folder-name');
    if (!input) return;

    const name = input.value.trim();
    if (!name) {
        showToast('Folder Name Required', 'Please enter a name for the folder.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/social/groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Folder Created! 📂', `Created folder "${name}"`, 'success');
            input.value = '';
            await fetchSocialData();
            renderFolderManagerModal();
        } else {
            showToast('Error', data.error || 'Failed to create folder.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

function promptRenameFolder(groupId, oldName) {
    const newName = prompt('Enter new folder name:', oldName);
    if (newName && newName.trim() && newName.trim() !== oldName) {
        renameFolder(groupId, newName.trim());
    }
}

async function renameFolder(groupId, newName) {
    try {
        const res = await fetch(`/api/social/groups/${groupId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Folder Renamed', `Renamed to "${newName}"`, 'success');
            await fetchSocialData();
            renderFolderManagerModal();
        } else {
            showToast('Error', data.error || 'Failed to rename folder.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

function promptDeleteFolder(groupId, folderName) {
    confirmAction(
        'Delete Folder',
        `Are you sure you want to delete the folder <strong>"${folderName}"</strong>?<br><br>Friends in this folder will automatically move to the General folder.`,
        () => deleteFolder(groupId)
    );
}

async function deleteFolder(groupId) {
    try {
        const res = await fetch(`/api/social/groups/${groupId}`, {
            method: 'DELETE'
        });
        const data = await res.json();

        if (data.success) {
            showToast('Folder Deleted', 'Folder deleted successfully.', 'info');
            if (state.socialView === `folder_${groupId}`) {
                state.socialView = 'all';
            }
            await fetchSocialData();
            renderFolderManagerModal();
        } else {
            showToast('Error', data.error || 'Failed to delete folder.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// --- 3. Requests Modal ---
function renderRequestsModal() {
    const container = document.getElementById('requests-list-container');
    if (!container || !state.socialData || !state.socialData.requests) return;

    const requests = state.socialData.requests;
    const isIncoming = (state.activeRequestTab === 'incoming');
    const list = isIncoming ? requests.incoming : requests.outgoing;

    document.getElementById('req-count-incoming').innerText = requests.incoming.length;
    document.getElementById('req-count-outgoing').innerText = requests.outgoing.length;

    if (!list || list.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding: 30px; color: var(--text-muted);">
                <div style="font-size: 28px; margin-bottom: 8px;">📬</div>
                No ${isIncoming ? 'incoming' : 'outgoing'} friend requests.
            </div>
        `;
        return;
    }

    container.innerHTML = list.map(req => `
        <div class="request-item">
            <div class="request-meta">
                <img src="${req.iconUrl || '/static/img/default-avatar.png'}" alt="${req.riotId}" class="champ-mini-icon">
                <span class="request-name">${req.riotId}</span>
            </div>
            <div class="request-actions">
                ${isIncoming ? `
                    <button class="btn-primary btn-sm" onclick="respondRequest('${req.puuid}', true)">Accept</button>
                    <button class="btn-danger-outline btn-sm" onclick="respondRequest('${req.puuid}', false)">Decline</button>
                ` : `
                    <button class="btn-danger-outline btn-sm" onclick="respondRequest('${req.puuid}', false)">Cancel</button>
                `}
            </div>
        </div>
    `).join('');
}

async function respondRequest(puuid, accept) {
    try {
        const res = await fetch('/api/social/requests/respond', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ puuid: puuid, accept: accept })
        });
        const data = await res.json();

        if (data.success) {
            showToast(accept ? 'Request Accepted! 🎉' : 'Request Removed', accept ? 'Added to your friend list.' : 'Request declined/canceled.', 'info');
            await fetchSocialData();
            renderRequestsModal();
        } else {
            showToast('Error', data.error || 'Failed to process request.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// --- 4. Blocked Players Modal ---
function renderBlockedModal() {
    const container = document.getElementById('blocked-list-container');
    if (!container || !state.socialData) return;

    const blocked = state.socialData.blocked || [];
    if (blocked.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding: 30px; color: var(--text-muted);">
                <div style="font-size: 28px; margin-bottom: 8px;">✨</div>
                You have no blocked players.
            </div>
        `;
        return;
    }

    container.innerHTML = blocked.map(b => `
        <div class="blocked-item">
            <div class="blocked-meta">
                <span style="font-size: 16px;">🚫</span>
                <span class="blocked-name">${b.riotId}</span>
            </div>
            <div class="blocked-actions">
                <button class="btn-ghost btn-sm" onclick="unblockPlayer('${b.id || b.puuid}', '${b.riotId}')">Unblock</button>
            </div>
        </div>
    `).join('');
}

async function unblockPlayer(playerId, riotId) {
    try {
        const res = await fetch(`/api/social/blocked/${encodeURIComponent(playerId)}`, {
            method: 'DELETE'
        });
        const data = await res.json();

        if (data.success) {
            showToast('Player Unblocked', `Unblocked ${riotId}.`, 'info');
            await fetchSocialData();
            renderBlockedModal();
        } else {
            showToast('Error', data.error || 'Failed to unblock player.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

async function blockPlayer(nameOrPuuid, riotId) {
    try {
        const res = await fetch('/api/social/blocked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: nameOrPuuid })
        });
        const data = await res.json();

        if (data.success) {
            showToast('Player Blocked', `Blocked ${riotId}.`, 'info');
            closeProfileDrawer();
            fetchSocialData();
        } else {
            showToast('Error', data.error || 'Failed to block player.', 'error');
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

// --- 5. Confirmation Modal Helper ---
function confirmAction(title, message, onConfirm) {
    const modal = document.getElementById('modal-social-confirm');
    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-msg');

    if (titleEl) titleEl.innerText = title;
    if (msgEl) msgEl.innerHTML = message;

    state.confirmCallback = onConfirm;
    if (modal) modal.classList.remove('hidden');
}

// =========================================================================
// SECTION 5: TOAST SYSTEM
// =========================================================================
function showToast(title, msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${msg}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = 'all 0.3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(30px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// =========================================================================
// SECTION 6: SMART BREAK DELAY (WC-PAUSE) CONTROLLER
// =========================================================================
function initBreakDelay() {
    const btnToggle = document.getElementById('btn-break-delay-toggle');
    const modalSettings = document.getElementById('modal-break-delay-settings');
    const btnCloseModal = document.getElementById('btn-close-delay-modal');
    const btnSaveSettings = document.getElementById('btn-save-delay-settings');
    const rangeSlider = document.getElementById('range-delay-seconds');
    const labelSeconds = document.getElementById('label-delay-seconds');
    const switchEnable = document.getElementById('switch-delay-enable');
    const btnReconnectBanner = document.getElementById('btn-reconnect-now-banner');

    if (btnToggle && modalSettings) {
        btnToggle.addEventListener('click', () => {
            modalSettings.classList.remove('hidden');
            if (switchEnable) switchEnable.checked = state.breakDelay.enabled;
            if (rangeSlider) rangeSlider.value = state.breakDelay.delaySeconds || 75;
            if (labelSeconds) labelSeconds.innerText = `${state.breakDelay.delaySeconds || 75} Sekunden`;
        });
    }

    if (btnCloseModal && modalSettings) {
        btnCloseModal.addEventListener('click', () => modalSettings.classList.add('hidden'));
    }

    if (rangeSlider && labelSeconds) {
        rangeSlider.addEventListener('input', (e) => {
            labelSeconds.innerText = `${e.target.value} Sekunden`;
        });
    }

    if (btnSaveSettings) {
        btnSaveSettings.addEventListener('click', saveDelaySettings);
    }

    if (btnReconnectBanner) {
        btnReconnectBanner.addEventListener('click', reconnectNow);
    }
}

function updateBreakDelayDisplay() {
    const activeBanner = document.getElementById('break-delay-active-banner');
    const countdownDisplay = document.getElementById('delay-countdown-display');
    const progressFill = document.getElementById('delay-progress-fill');

    if (!activeBanner) return;

    if (state.breakDelay.active) {
        activeBanner.classList.remove('hidden');

        const rem = Math.max(0, state.breakDelay.remaining_seconds || 0);
        const mins = Math.floor(rem / 60);
        const secs = rem % 60;
        const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        if (countdownDisplay) countdownDisplay.innerText = timeStr;

        if (progressFill) {
            const total = state.breakDelay.delay_seconds || 75;
            const percent = total > 0 ? Math.max(0, Math.min(100, (rem / total) * 100)) : 0;
            progressFill.style.width = `${percent}%`;
        }
    } else {
        activeBanner.classList.add('hidden');
    }
}

async function fetchBreakDelayStatus() {
    try {
        const res = await fetch('/api/delay-reconnect/status');
        const data = await res.json();
        state.breakDelay = data;

        // 1. Update Header Button Status
        const btnToggle = document.getElementById('btn-break-delay-toggle');
        const textDelay = document.getElementById('header-delay-text');

        if (btnToggle && textDelay) {
            btnToggle.classList.toggle('active', !!data.enabled);
            if (data.enabled) {
                textDelay.innerText = `Break Delay: ON (${data.delay_seconds || 75}s)`;
            } else {
                textDelay.innerText = 'Break Delay: OFF';
            }
        }

        // 2. Active Delay Local Countdown Controller
        updateBreakDelayDisplay();

        if (data.active) {
            if (!state.breakDelayTimer) {
                state.breakDelayTimer = setInterval(() => {
                    if (state.breakDelay.remaining_seconds > 0) {
                        state.breakDelay.remaining_seconds--;
                        updateBreakDelayDisplay();
                    } else {
                        clearInterval(state.breakDelayTimer);
                        state.breakDelayTimer = null;
                    }
                }, 1000);
            }
        } else {
            if (state.breakDelayTimer) {
                clearInterval(state.breakDelayTimer);
                state.breakDelayTimer = null;
            }
        }
    } catch (e) {
        // Silent error
    }
}

async function saveDelaySettings() {
    const switchEnable = document.getElementById('switch-delay-enable');
    const rangeSlider = document.getElementById('range-delay-seconds');
    const modalSettings = document.getElementById('modal-break-delay-settings');

    const enabled = switchEnable ? switchEnable.checked : false;
    const delaySec = rangeSlider ? parseInt(rangeSlider.value, 10) : 75;

    try {
        const res = await fetch('/api/delay-reconnect/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled, delay_seconds: delaySec })
        });
        const data = await res.json();

        if (data.success) {
            state.breakDelay.enabled = data.enabled;
            state.breakDelay.delaySeconds = data.delay_seconds;
            if (modalSettings) modalSettings.classList.add('hidden');

            showToast(
                'Break Delay Mode',
                data.enabled ? `Enabled (${data.delay_seconds}s delay after Champ Select)` : 'Disabled',
                data.enabled ? 'success' : 'info'
            );
            fetchBreakDelayStatus();
        }
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

async function reconnectNow() {
    const activeBanner = document.getElementById('break-delay-active-banner');
    if (activeBanner) activeBanner.classList.add('hidden');

    try {
        showToast('Connecting...', 'Launching game reconnect immediately 🚀', 'info');
        const res = await fetch('/api/delay-reconnect/reconnect-now', {
            method: 'POST'
        });
        const data = await res.json();
        if (data.success) {
            showToast('Connected! 🎮', 'Reconnecting to loading screen!', 'success');
        }
        fetchBreakDelayStatus();
    } catch (e) {
        showToast('Error', e.message, 'error');
    }
}

