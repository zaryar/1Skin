/**
 * HexSkin Studio - Frontend Application Script (English)
 */

const state = {
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
    hiddenDisenchantLootIds: new Set()
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initControls();
    initSearch();
    initBraverySync();
    
    // Initial fetch
    refreshAllData();

    // Regular polling for status (every 3 seconds)
    setInterval(pollStatus, 3000);
});

// --- Tab Navigation ---
function initTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });
}

function switchTab(tabName) {
    state.activeTab = tabName;
    
    // Update Tab Buttons
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('data-tab') === tabName);
    });

    // Update Tab Content Sections
    document.querySelectorAll('.tab-content').forEach(s => {
        s.classList.toggle('active', s.id === `tab-${tabName}`);
    });
}

// --- Controls & Buttons ---
function initControls() {
    // Sound Toggle Button
    const soundBtn = document.getElementById('btn-sound-toggle');
    if (soundBtn) {
        soundBtn.addEventListener('click', toggleSoundSetting);
    }

    // Refresh Button
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshAllData();
            showToast('Syncing...', 'Refreshing data from League Client.', 'info');
        });
    }

    // Modal Retry Button
    const modalRetry = document.getElementById('btn-modal-retry');
    if (modalRetry) {
        modalRetry.addEventListener('click', refreshAllData);
    }

    // Loadout Filter Pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            state.loadoutsFilter = pill.getAttribute('data-filter');
            renderLoadouts();
        });
    });
}

// --- Search Inputs ---
function initSearch() {
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
}

// --- API Calls & Data Fetching ---
async function refreshAllData() {
    await pollStatus();
    if (state.status && state.status.connected) {
        fetchCrafterData();
        fetchDisenchanterData();
        fetchLoadoutsData();
    }
}

async function pollStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        state.status = data;
        updateHeaderStatus(data);
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
            
            // Also update banner OE
            const bannerOE = document.getElementById('crafter-avail-oe');
            if (bannerOE) bannerOE.innerText = `${Number(status.currencies.oe || 0).toLocaleString()} OE`;
        }

        // Sound icon
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

// --- Tab 1: Crafter (Missing Skins) ---
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

    let totalShardsCount = 0;
    state.crafterData.champions.forEach(c => totalShardsCount += c.shards.length);
    badge.innerText = totalShardsCount;
    if (totalSkinsStat) totalSkinsStat.innerText = `${totalShardsCount} Skins`;

    if (filteredChamps.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.innerHTML = filteredChamps.map(item => {
        const champ = item.champ;
        const shardsHtml = item.shards.map(shard => {
            const hasEnoughOE = currentOE >= shard.cost;
            const costText = shard.cost > 0 ? `${Number(shard.cost).toLocaleString()} OE` : 'Free';
            const btnText = hasEnoughOE ? `Unlock (${costText})` : `Need OE (${costText})`;
            const imgUrl = shard.splashPath ? `/lcu-img/${shard.splashPath}` : `/lcu-img/${champ.img}`;

            return `
                <div class="shard-row-item" id="shard-row-${shard.lootId}">
                    <img class="shard-thumb" src="${imgUrl}" alt="${shard.skinName}" loading="lazy" onerror="this.src='/lcu-img/${champ.img}'">
                    <div class="shard-info">
                        <div class="shard-name" title="${shard.skinName}">${shard.skinName}</div>
                        <div class="shard-cost-badge">
                            <span>💎</span> ${shard.cost > 0 ? Number(shard.cost).toLocaleString() + ' Orange Essence' : 'Free Upgrade'}
                        </div>
                    </div>
                    <button class="btn-craft" 
                            id="btn-craft-${shard.lootId}" 
                            ${!hasEnoughOE ? 'disabled' : ''} 
                            onclick="craftSkin('${shard.lootId}', '${shard.skinName.replace(/'/g, "\\'")}', ${shard.cost}, ${champ.id})">
                        ${btnText}
                    </button>
                </div>
            `;
        }).join('');

        return `
            <div class="champ-craft-card" id="crafter-card-champ-${champ.id}">
                <div class="champ-portrait-col">
                    <img src="/lcu-img/${champ.img}" alt="${champ.name}">
                    <h3>${champ.name}</h3>
                </div>
                <div class="shards-col">
                    ${shardsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function craftSkin(lootId, skinName, cost, champId) {
    const btn = document.getElementById(`btn-craft-${lootId}`);
    if (btn) {
        btn.disabled = true;
        btn.innerText = 'Crafting...';
    }

    try {
        const res = await fetch('/api/crafter/upgrade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ loot_id: lootId })
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast('Skin Unlocked! ✨', `${skinName} was permanently added to your collection!`, 'success');
            
            // Remove shard row or refresh
            const shardRow = document.getElementById(`shard-row-${lootId}`);
            if (shardRow) shardRow.remove();

            // Refresh data
            refreshAllData();
        } else {
            showToast('Unlock Failed', data.error || 'Could not complete the craft recipe.', 'error');
            if (btn) {
                btn.disabled = false;
                const costText = cost > 0 ? `${Number(cost).toLocaleString()} OE` : 'Free';
                btn.innerText = `Unlock (${costText})`;
            }
        }
    } catch (e) {
        showToast('Network Error', 'Request to the server failed.', 'error');
        if (btn) {
            btn.disabled = false;
            const costText = cost > 0 ? `${Number(cost).toLocaleString()} OE` : 'Free';
            btn.innerText = `Unlock (${costText})`;
        }
    }
}

// --- Tab 2: Disenchanter (Extra Shards) ---
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
    const totalOEGainStat = document.getElementById('disenchant-total-oe-gain');

    if (!state.disenchantData || !state.disenchantData.shards) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        badge.innerText = '0';
        return;
    }

    const query = state.searchQueries.disenchanter;
    const visibleShards = state.disenchantData.shards.filter(s => {
        if (state.hiddenDisenchantLootIds.has(s.lootId)) return false;
        if (!query) return true;
        return s.champName.toLowerCase().includes(query) || s.skinName.toLowerCase().includes(query);
    });

    const allVisible = state.disenchantData.shards.filter(s => !state.hiddenDisenchantLootIds.has(s.lootId));
    let potentialOE = 0;
    allVisible.forEach(s => potentialOE += (s.disenchantValue || 0) * (s.count || 1));

    badge.innerText = allVisible.length;
    if (totalCountStat) totalCountStat.innerText = `${allVisible.length} Shards`;
    if (totalOEGainStat) totalOEGainStat.innerText = `+${Number(potentialOE).toLocaleString()} OE`;

    if (visibleShards.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.innerHTML = visibleShards.map(shard => {
        const ownedSkinsHtml = shard.ownedSkins.map(os => `
            <div class="owned-skin-mini" title="${os.name}">
                <img src="/lcu-img/${os.img}" alt="${os.name}" loading="lazy" onerror="this.src='/lcu-img/${shard.champPortrait}'">
                <span>${os.name}</span>
            </div>
        `).join('');

        const splashUrl = shard.splashPath ? `/lcu-img/${shard.splashPath}` : `/lcu-img/${shard.champPortrait}`;
        const countBadge = shard.count > 1 ? `<span class="shard-badge-count">${shard.count}x</span>` : '';

        return `
            <div class="disenchant-card" id="disenchant-card-${shard.lootId}">
                <div class="owned-preview-col">
                    <div class="owned-header">
                        <img src="/lcu-img/${shard.champPortrait}" alt="${shard.champName}">
                        <h4>Already Owned (${shard.champName})</h4>
                    </div>
                    <div class="owned-skins-thumbs">
                        ${ownedSkinsHtml}
                    </div>
                </div>

                <div class="shard-action-col">
                    <div>
                        <div class="shard-splash-hero">
                            <img src="${splashUrl}" alt="${shard.skinName}" loading="lazy" onerror="this.src='/lcu-img/${shard.champPortrait}'">
                            ${countBadge}
                        </div>
                        <div class="shard-target-title">${shard.skinName}</div>
                        <div class="shard-disenchant-val">
                            Value: <strong>+${Number(shard.disenchantValue).toLocaleString()} OE</strong>
                        </div>
                    </div>

                    <div class="action-btn-group">
                        <button class="btn-disenchant" onclick="disenchantSkin('${shard.lootId}', '${shard.skinName.replace(/'/g, "\\'")}', ${shard.disenchantValue})">
                            Disenchant (+${shard.disenchantValue} OE)
                        </button>
                        <button class="btn-ghost" onclick="hideDisenchantCard('${shard.lootId}')">
                            Keep
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function disenchantSkin(lootId, skinName, value) {
    const card = document.getElementById(`disenchant-card-${lootId}`);
    if (card) {
        card.style.opacity = '0.5';
        card.style.pointerEvents = 'none';
    }

    try {
        const res = await fetch('/api/disenchanter/disenchant', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ loot_id: lootId })
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast('Disenchanted! 💎', `Received +${value} Orange Essence for ${skinName}.`, 'success');
            if (card) card.remove();
            refreshAllData();
        } else {
            showToast('Disenchant Failed', data.error || 'Could not disenchant shard.', 'error');
            if (card) {
                card.style.opacity = '1';
                card.style.pointerEvents = 'auto';
            }
        }
    } catch (e) {
        showToast('Network Error', 'Request to the server failed.', 'error');
        if (card) {
            card.style.opacity = '1';
            card.style.pointerEvents = 'auto';
        }
    }
}

function hideDisenchantCard(lootId) {
    state.hiddenDisenchantLootIds.add(lootId);
    const card = document.getElementById(`disenchant-card-${lootId}`);
    if (card) {
        card.style.transition = 'all 0.3s ease';
        card.style.transform = 'scale(0.95)';
        card.style.opacity = '0';
        setTimeout(() => {
            renderDisenchanter();
        }, 300);
    }
}

// --- Tab 3: Loadouts & Auto-Equipper ---
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
    const countAll = document.getElementById('loadouts-count-all');
    const countConfigured = document.getElementById('loadouts-count-configured');
    const countUnconfigured = document.getElementById('loadouts-count-unconfigured');

    if (!state.loadoutsData) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        badge.innerText = '0';
        return;
    }

    const configured = state.loadoutsData.configured || [];
    const unconfigured = state.loadoutsData.unconfigured || [];
    const all = [...unconfigured, ...configured];

    badge.innerText = all.length;
    if (countAll) countAll.innerText = all.length;
    if (countConfigured) countConfigured.innerText = configured.length;
    if (countUnconfigured) countUnconfigured.innerText = unconfigured.length;

    let targetList = all;
    if (state.loadoutsFilter === 'configured') {
        targetList = configured;
    } else if (state.loadoutsFilter === 'unconfigured') {
        targetList = unconfigured;
    }

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
            const badgeHtml = isSelected ? '<div class="skin-tile-badge">Equipped</div>' : '';

            return `
                <div class="skin-tile ${isSelected ? 'selected' : ''}" 
                     id="skin-tile-${skin.id}" 
                     onclick="equipSkin('${champ.id}', ${skin.id}, '${skin.name.replace(/'/g, "\\'")}', '${champ.name.replace(/'/g, "\\'")}')">
                    <div class="skin-tile-img-wrap">
                        <img src="/lcu-img/${skin.img}" alt="${skin.name}" loading="lazy" onerror="this.src='/lcu-img/${champ.img}'">
                        ${badgeHtml}
                    </div>
                    <div class="skin-tile-name" title="${skin.name}">${skin.name}</div>
                </div>
            `;
        }).join('');

        return `
            <div class="loadout-card" id="loadout-card-${champ.id}">
                <div class="loadout-champ-col">
                    <img src="/lcu-img/${champ.img}" alt="${champ.name}">
                    <h3>${champ.name}</h3>
                </div>
                <div class="loadout-skins-gallery">
                    ${skinsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function equipSkin(champId, skinId, skinName, champName) {
    // 1. Optimistic UI update in the card
    const card = document.getElementById(`loadout-card-${champId}`);
    if (card) {
        const allTiles = card.querySelectorAll('.skin-tile');
        allTiles.forEach(t => {
            t.classList.remove('selected');
            const badge = t.querySelector('.skin-tile-badge');
            if (badge) badge.remove();
        });

        const targetTile = document.getElementById(`skin-tile-${skinId}`);
        if (targetTile) {
            targetTile.classList.add('selected');
            const imgWrap = targetTile.querySelector('.skin-tile-img-wrap');
            if (imgWrap && !imgWrap.querySelector('.skin-tile-badge')) {
                const badge = document.createElement('div');
                badge.className = 'skin-tile-badge';
                badge.innerText = 'Equipped';
                imgWrap.appendChild(badge);
            }
        }
    }

    // 2. Send API request
    try {
        const res = await fetch('/api/loadouts/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ champ_id: champId, skin_id: skinId })
        });

        if (res.ok) {
            showToast('Skin Equipped! 🎨', `${skinName} will be auto-equipped for ${champName}.`, 'success');
            // Update local state
            if (state.loadoutsData) {
                if (!state.loadoutsData.loadouts) state.loadoutsData.loadouts = {};
                state.loadoutsData.loadouts[champId] = skinId;
                
                // Update champ in configured / unconfigured arrays
                const allChamps = [...(state.loadoutsData.configured || []), ...(state.loadoutsData.unconfigured || [])];
                const targetChamp = allChamps.find(c => c.id === champId);
                if (targetChamp) {
                    targetChamp.selectedSkinId = skinId;
                    targetChamp.isConfigured = true;
                }
            }
        } else {
            showToast('Save Failed', 'Could not save the preferred skin.', 'error');
        }
    } catch (e) {
        showToast('Network Error', 'Failed to connect to server.', 'error');
    }
}

// --- Bravery Sync Modal & Progress ---
let syncPollInterval = null;

function initBraverySync() {
    const btnOpen = document.getElementById('btn-open-bravery-modal');
    const btnClose = document.getElementById('btn-close-bravery-modal');
    const btnStart = document.getElementById('btn-start-bravery-sync');
    const btnStop = document.getElementById('btn-stop-bravery-sync');
    const modal = document.getElementById('bravery-sync-modal');

    if (btnOpen && modal) {
        btnOpen.addEventListener('click', () => {
            modal.classList.remove('hidden');
            checkBraverySyncStatus();
        });
    }

    if (btnClose && modal) {
        btnClose.addEventListener('click', () => {
            modal.classList.add('hidden');
        });
    }

    if (btnStart) {
        btnStart.addEventListener('click', startBraverySync);
    }

    if (btnStop) {
        btnStop.addEventListener('click', stopBraverySync);
    }
}

async function startBraverySync() {
    const btnStart = document.getElementById('btn-start-bravery-sync');
    const btnStop = document.getElementById('btn-stop-bravery-sync');
    const progressArea = document.getElementById('sync-progress-area');

    try {
        const res = await fetch('/api/sync/bravery/start', { method: 'POST' });
        const data = await res.json();

        if (res.ok && data.success) {
            btnStart.classList.add('hidden');
            btnStop.classList.remove('hidden');
            progressArea.classList.remove('hidden');

            if (syncPollInterval) clearInterval(syncPollInterval);
            syncPollInterval = setInterval(checkBraverySyncStatus, 400);
            showToast('Sync Started ⚡', 'Synchronizing your preferred skins in custom lobby...', 'info');
        } else {
            showToast('Error', data.error || 'Could not start sync. Is a Custom Game lobby open?', 'error');
        }
    } catch (e) {
        showToast('Network Error', 'Request to the server failed.', 'error');
    }
}

async function stopBraverySync() {
    try {
        await fetch('/api/sync/bravery/stop', { method: 'POST' });
        if (syncPollInterval) clearInterval(syncPollInterval);
        document.getElementById('btn-start-bravery-sync').classList.remove('hidden');
        document.getElementById('btn-stop-bravery-sync').classList.add('hidden');
        document.getElementById('sync-status-msg').innerText = 'Synchronization stopped.';
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
            btnStart.classList.add('hidden');
            btnStop.classList.remove('hidden');
            progressArea.classList.remove('hidden');

            const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
            fill.style.width = `${percent}%`;
            msg.innerText = data.message || 'Synchronizing...';
            countText.innerText = `${data.current} / ${data.total} Champions`;
            percentText.innerText = `${percent}%`;
        } else {
            btnStart.classList.remove('hidden');
            btnStop.classList.add('hidden');
            if (data.status === 'done') {
                fill.style.width = '100%';
                msg.innerText = '✨ Synchronization completed successfully!';
                percentText.innerText = '100%';
                if (syncPollInterval) clearInterval(syncPollInterval);
            } else if (data.status === 'error') {
                msg.innerText = data.message || 'Error during synchronization.';
                if (syncPollInterval) clearInterval(syncPollInterval);
            }
        }
    } catch (e) {
        console.error('Error polling sync status', e);
    }
}

// --- Toast Notifications System ---
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
