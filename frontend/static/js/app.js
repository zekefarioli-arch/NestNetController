// Configuration
const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8003' 
    : `http://${window.location.hostname}:8003`;

// Wording and numbers live in summary.js (pure, tested in node)
const { displayName, summarize, headline, relativeTime, activitySentence, escapeHtml, SCENES, sceneLabel, plural } = window.NN;

let authToken = localStorage.getItem('authToken');

// DOM Elements
const loginModal = document.getElementById('loginModal');
const mainApp = document.getElementById('mainApp');
const loginForm = document.getElementById('loginForm');
const loginError = document.getElementById('loginError');
const dryRunBadge = document.getElementById('dryRunBadge');

const icon = (name, extra = '') => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

// Theme: the head script applied the saved or system theme; the button only flips and saves it
function syncThemeButton() {
    const dark = document.documentElement.classList.contains('dark');
    document.querySelector('.theme-to-dark').classList.toggle('hidden', dark);
    document.querySelector('.theme-to-light').classList.toggle('hidden', !dark);
    document.getElementById('themeToggle').setAttribute('aria-label', dark ? 'Switch to the light theme' : 'Switch to the dark theme');
}
document.getElementById('themeToggle').addEventListener('click', () => {
    const dark = document.documentElement.classList.toggle('dark');
    try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch (e) { /* private mode: the choice just is not remembered */ }
    syncThemeButton();
});
syncThemeButton();

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    renderScenes();
    renderSkeletons();
    if (authToken) {
        checkAuth();
    }
});

// Authentication
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    await withBusy(loginForm.querySelector('button[type="submit"]'), 'Signing in…', () => signIn(username, password));
});

async function signIn(username, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            loginError.classList.add('hidden');
            await updateDryRunBadge();
            showMainApp();
        } else {
            showLoginError('Wrong username or password. Check them and try again.');
        }
    } catch (error) {
        showLoginError("Can't reach the router. Check that you are on the home network or on WireGuard.");
    }
}

function showLoginError(message) {
    loginError.textContent = message;
    loginError.classList.remove('hidden');
}

function showMainApp() {
    loginModal.classList.add('hidden');
    mainApp.classList.remove('hidden');
    loadDashboard();
}

function logout() {
    authToken = null;
    localStorage.removeItem('authToken');
    dryRunBadge.classList.add('hidden');
    loginModal.classList.remove('hidden');
    mainApp.classList.add('hidden');
}

async function updateDryRunBadge() {
    try {
        const response = await apiRequest('/');
        if (response.ok) {
            const data = await response.json();
            dryRunBadge.classList.toggle('hidden', !data.dry_run);
        }
    } catch (error) {
        // Non-fatal: badge just won't show if this fails
        console.error('Error checking dry-run status:', error);
    }
}

async function checkAuth() {
    try {
        const response = await apiRequest('/');
        if (response.ok) {
            const data = await response.json();
            dryRunBadge.classList.toggle('hidden', !data.dry_run);
            showMainApp();
        } else {
            logout();
        }
    } catch (error) {
        logout();
    }
}

// API Helper
async function apiRequest(endpoint, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
        }
    };
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    });

    // Token vencido o inválido: limpiar sesión y volver al login
    // en vez de dejar que cada caller maneje el 401 por separado
    if (response.status === 401) {
        logout();
        throw new Error('Session expired, please log in again');
    }

    return response;
}

// Feedback: toasts, busy buttons, haptics
// The panel is used mostly from a phone, so every action has to say
// clearly that it was received, that it is running, and how it ended.
const TOAST_ICONS = { success: 'check', error: 'x', warning: 'triangle-alert', info: 'info' };

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast toast-${type} pointer-events-auto flex w-full max-w-sm items-center gap-3 px-4 py-3 text-sm opacity-0 translate-y-2`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.innerHTML = `<span class="toast-icon">${icon(TOAST_ICONS[type] || 'info')}</span><span class="flex-1">${escapeHtml(message)}</span>`;

    // Tap to dismiss early
    const dismiss = () => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 250);
    };
    toast.addEventListener('click', dismiss);

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.remove('opacity-0', 'translate-y-2'));

    // Errors stay longer: they are the ones the user must not miss
    setTimeout(dismiss, type === 'error' ? duration * 2 : duration);

    vibrate(type === 'error' ? [60, 60, 60] : 30);
}

function vibrate(pattern) {
    // Not supported on iOS Safari; harmless no-op there
    if (navigator.vibrate) navigator.vibrate(pattern);
}

// Disables the control while fn runs, so a slow iptables call doesn't look like a
// missed tap (and can't be double-fired). A lever pulses; a button swaps its label
// (.js-label) and shows a spinner.
async function withBusy(button, busyLabel, fn) {
    if (!button) return fn();
    if (button.disabled) return;

    const label = button.querySelector('.js-label');
    const original = label ? label.textContent : null;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.classList.add('is-busy');
    if (label) {
        label.textContent = busyLabel;
        button.classList.add('btn-busy');
    }
    try {
        return await fn();
    } finally {
        // The control may have been replaced by a re-render; restoring a
        // detached node is harmless
        button.disabled = false;
        button.removeAttribute('aria-busy');
        button.classList.remove('is-busy', 'btn-busy');
        if (label) label.textContent = original;
    }
}

async function errorDetail(response, fallback) {
    try {
        const data = await response.json();
        return data.detail || fallback;
    } catch {
        return fallback;
    }
}

// Dashboard
async function loadDashboard() {
    await Promise.all([
        loadGroups(),
        loadLogs()
    ]);
}

// Loading, empty and error states
function renderSkeletons() {
    const rows = (n, h) => Array.from({ length: n }, () => `<div class="py-5"><div class="skeleton ${h}"></div></div>`).join('');
    document.getElementById('groupsContainer').innerHTML = rows(3, 'h-16');
    document.getElementById('logsContainer').innerHTML = rows(3, 'h-8');
}

function renderError(container, what) {
    container.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-3 py-5">
            <p class="flex items-center gap-2 text-sm">${icon('triangle-alert', 'icon-sm text-danger')}<span>${escapeHtml(what)}</span></p>
            <button type="button" class="btn" onclick="loadDashboard()"><span class="js-label">Try again</span></button>
        </div>`;
}

// Scenes: presets that change several groups at once. Drawn as buttons, with an
// "Apply" that looks pressable, so nobody has to guess that the card is the control.
function renderScenes() {
    document.getElementById('scenes').innerHTML = SCENES.map(scene => `
        <button type="button" onclick="quickAction('${scene.action}', this)"
                class="scene flex min-h-[44px] w-full items-center justify-between gap-4 p-4 text-left disabled:cursor-progress">
            <span class="min-w-0">
                <span class="block font-semibold">${escapeHtml(scene.label)}</span>
                <span class="block text-sm text-muted">${escapeHtml(scene.hint)}</span>
            </span>
            <span class="scene-apply">${icon('play', 'icon-sm')}<span class="js-label">Apply</span></span>
        </button>`).join('');
}

async function loadGroups() {
    try {
        const response = await apiRequest('/devices/groups');
        if (!response.ok) throw new Error('Failed to load groups');
        
        const groups = await response.json();
        renderStatement(groups);
        renderGroups(groups);
    } catch (error) {
        console.error('Error loading groups:', error);
        renderError(document.getElementById('groupsContainer'), "Couldn't load the groups.");
    }
}

function renderStatement(groups) {
    const { title, body } = headline(summarize(groups));
    document.getElementById('statement').innerHTML = `
        <h1 id="headline" class="font-display text-5xl leading-[0.95] tracking-tight sm:text-6xl">${escapeHtml(title)}</h1>
        <p class="mt-5 max-w-md text-lg">${escapeHtml(body)}</p>`;
}

function renderGroups(groups) {
    const real = groups.filter(group => !group.auto_detect); // auto-detect groups are not built yet
    // A group with no lever: protected equipment or an always-on group (cameras, essential)
    const isLocked = group => group.protected || group.always_on;
    const switchable = real.filter(group => !isLocked(group));
    const locked = real.filter(isLocked);

    const container = document.getElementById('groupsContainer');
    container.innerHTML = switchable.length
        ? switchable.map(createBreakerRow).join('')
        : `<p class="py-5 text-sm text-muted">No groups can be switched yet. Add one to devices.yaml, then reload the devices.</p>`;

    const lockedContainer = document.getElementById('lockedContainer');
    for (const id of ['locked-title', 'locked-note']) document.getElementById(id).classList.toggle('hidden', !locked.length);
    lockedContainer.classList.toggle('hidden', !locked.length);
    lockedContainer.innerHTML = locked.map(createLockedRow).join('');
}

function deviceList(group) {
    if (!group.devices.length) return `<p class="mt-2 text-sm text-muted">No devices yet.</p>`;
    return `
        <details class="mt-2">
            <summary class="inline-flex min-h-[44px] items-center gap-1 text-sm text-muted hover:text-ink sm:min-h-0">
                ${plural(group.devices.length, 'device', 'devices')}
                ${icon('chevron-down', 'icon-sm chev')}
            </summary>
            <ul class="mt-1 space-y-0.5 text-sm">
                ${group.devices.map(device => `<li>${escapeHtml(displayName(device.name))}</li>`).join('')}
            </ul>
        </details>`;
}

// One breaker: the plate, what is behind it, and the lever.
// The lever is drawn from the server's answer, never optimistically.
function createBreakerRow(group) {
    const name = displayName(group.name);
    return `
        <div class="flex items-start justify-between gap-4 py-5">
            <div class="min-w-0">
                <h3 class="font-display text-2xl leading-tight">${escapeHtml(name)}</h3>
                ${group.description ? `<p class="text-sm text-muted">${escapeHtml(group.description)}</p>` : ''}
                ${deviceList(group)}
            </div>
            <div class="flex shrink-0 flex-col items-end gap-1">
                <span class="lever-hit">
                    <button type="button" role="switch" aria-checked="${group.enabled}" aria-label="Internet for ${escapeHtml(name)}"
                            class="lever" onclick="toggleGroup('${escapeHtml(group.name)}', this)">
                        <span class="lever-slug"></span>
                    </button>
                </span>
                <span class="${group.enabled ? 'state-on' : 'state-off'} text-sm">${group.enabled ? 'Internet on' : 'Internet off'}</span>
            </div>
        </div>`;
}

function createLockedRow(group) {
    return `
        <div class="flex items-start justify-between gap-4 py-5">
            <div class="min-w-0">
                <h3 class="font-display text-2xl leading-tight">${escapeHtml(displayName(group.name))}</h3>
                ${group.description ? `<p class="text-sm text-muted">${escapeHtml(group.description)}</p>` : ''}
                ${deviceList(group)}
            </div>
            <span class="flex shrink-0 items-center gap-1.5 pt-1 text-sm text-muted">${icon('lock', 'icon-sm')}Always on</span>
        </div>`;
}

async function toggleGroup(groupName, button) {
    const label = displayName(groupName);
    await withBusy(button, 'Applying…', async () => {
        try {
            const response = await apiRequest(`/devices/groups/${groupName}/toggle`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                showToast(`${label}: ${await errorDetail(response, 'request failed')}`, 'error');
                return;
            }
            
            const data = await response.json();
            const verb = data.action === 'block' ? 'turned off' : 'turned on';
            // 200 with success=false means some firewall rules failed to apply
            if (data.success) {
                showToast(`${label} ${verb}`, 'success');
            } else {
                showToast(`${label} ${verb} only partly. Some devices failed; check the activity.`, 'warning');
            }
            await loadDashboard();
        } catch (error) {
            console.error('Error toggling group:', error);
            showToast(`Couldn't change ${label}: ${error.message}`, 'error');
        }
    });
}

async function quickAction(action, button) {
    const label = sceneLabel(action);
    await withBusy(button, 'Applying…', async () => {
        try {
            const response = await apiRequest('/devices/quick-action', {
                method: 'POST',
                body: JSON.stringify({ action })
            });
            
            if (!response.ok) {
                showToast(`${label}: ${await errorDetail(response, 'request failed')}`, 'error');
                return;
            }
            
            const data = await response.json();
            if (data.success) {
                showToast(`Scene applied: ${label}`, 'success');
            } else {
                showToast(`Scene applied only partly: ${label}. Check the activity.`, 'warning');
            }
            await loadDashboard();
        } catch (error) {
            console.error('Error executing quick action:', error);
            showToast(`Couldn't apply ${label}: ${error.message}`, 'error');
        }
    });
}

async function reloadConfig(button) {
    await withBusy(button, 'Reloading…', async () => {
        try {
            const response = await apiRequest('/devices/reload', {
                method: 'POST'
            });
            
            if (!response.ok) {
                showToast(`Reload failed: ${await errorDetail(response, 'request failed')}`, 'error');
                return;
            }
            
            await loadDashboard();
            showToast('Devices reloaded', 'success');
        } catch (error) {
            console.error('Error reloading config:', error);
            showToast(`Couldn't reload the devices: ${error.message}`, 'error');
        }
    });
}

async function loadLogs() {
    try {
        const response = await apiRequest('/logs/recent?limit=20');
        if (!response.ok) throw new Error('Failed to load logs');
        
        const logs = await response.json();
        renderLogs(logs);
    } catch (error) {
        console.error('Error loading logs:', error);
        renderError(document.getElementById('logsContainer'), "Couldn't load the activity.");
    }
}

// Activity is a timeline, so the time is the left edge of every row
function renderLogs(logs) {
    const container = document.getElementById('logsContainer');
    
    if (logs.length === 0) {
        container.innerHTML = '<p class="py-5 text-sm text-muted">Nothing yet. Switching a group on or off will show up here.</p>';
        return;
    }
    
    container.innerHTML = logs.map(log => {
        const when = window.NN.parseTimestamp(log.timestamp);
        return `
            <div class="grid grid-cols-[5.5rem_1fr] gap-x-3 py-3 text-sm">
                <time datetime="${when.toISOString()}" title="${escapeHtml(when.toLocaleString())}" class="nums text-muted">${escapeHtml(relativeTime(log.timestamp))}</time>
                <div class="min-w-0">
                    <p class="flex items-center gap-1.5">
                        ${log.success ? '' : icon('x', 'icon-sm text-danger')}
                        <span class="${log.success ? '' : 'font-semibold'}">${escapeHtml(activitySentence(log))}</span>
                    </p>
                    <p class="text-muted">${log.success ? '' : 'Not applied. '}By ${escapeHtml(log.user)}${log.details ? `. ${escapeHtml(log.details)}` : ''}</p>
                </div>
            </div>`;
    }).join('');
}

// Auto-refresh every 30 seconds
setInterval(() => {
    if (!loginModal.classList.contains('hidden')) return;
    loadDashboard();
}, 30000);
