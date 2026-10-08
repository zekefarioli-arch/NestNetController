// Configuration
const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8003' 
    : `http://${window.location.hostname}:8003`;

let authToken = localStorage.getItem('authToken');

// DOM Elements
const loginModal = document.getElementById('loginModal');
const mainApp = document.getElementById('mainApp');
const loginForm = document.getElementById('loginForm');
const loginError = document.getElementById('loginError');
const dryRunBadge = document.getElementById('dryRunBadge');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (authToken) {
        checkAuth();
    }
});

// Authentication
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
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
            showLoginError('Invalid username or password');
        }
    } catch (error) {
        showLoginError('Connection error. Is the backend running?');
    }
});

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
const TOAST_STYLES = {
    success: { classes: 'bg-green-600', icon: '✓' },
    error:   { classes: 'bg-red-600',   icon: '✗' },
    warning: { classes: 'bg-yellow-500', icon: '⚠' },
    info:    { classes: 'bg-gray-800',  icon: 'ℹ' },
};

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    const style = TOAST_STYLES[type] || TOAST_STYLES.info;

    const toast = document.createElement('div');
    toast.className = `${style.classes} text-white pointer-events-auto w-full max-w-sm rounded-lg shadow-lg px-4 py-3 flex items-center gap-3 text-sm transition duration-300 opacity-0 translate-y-2`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const icon = document.createElement('span');
    icon.className = 'font-bold text-base';
    icon.textContent = style.icon;
    const text = document.createElement('span');
    text.className = 'flex-1';
    text.textContent = message;
    toast.append(icon, text);

    // Tap to dismiss early
    const dismiss = () => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
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

// Disables the button and shows a spinner while fn runs, so a slow
// iptables call doesn't look like a missed tap (and can't be double-fired)
async function withBusy(button, busyLabel, fn) {
    if (!button) return fn();
    if (button.disabled) return;

    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `
        <span class="inline-flex items-center justify-center gap-2">
            <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle>
                <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="4" stroke-linecap="round"></path>
            </svg>
            ${busyLabel}
        </span>`;
    try {
        return await fn();
    } finally {
        // The button may have been replaced by a re-render; restoring a
        // detached node is harmless
        button.disabled = false;
        button.innerHTML = original;
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

function formatGroupName(name) {
    return name.charAt(0).toUpperCase() + name.slice(1);
}

const QUICK_ACTION_LABELS = {
    only_essential_security: 'Only Essential + Security',
    only_essential: 'Only Essential',
    enable_all: 'All groups enabled',
};

// Dashboard
async function loadDashboard() {
    await Promise.all([
        loadGroups(),
        loadLogs()
    ]);
}

async function loadGroups() {
    try {
        const response = await apiRequest('/devices/groups');
        if (!response.ok) throw new Error('Failed to load groups');
        
        const groups = await response.json();
        renderGroups(groups);
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

function renderGroups(groups) {
    const container = document.getElementById('groupsContainer');
    container.innerHTML = '';
    
    groups.forEach(group => {
        if (group.auto_detect) return; // Skip auto-detect groups for now
        
        const card = createGroupCard(group);
        container.appendChild(card);
    });
}

function createGroupCard(group) {
    const div = document.createElement('div');
    div.className = 'bg-white rounded-lg shadow p-6';
    
    const isProtected = group.protected;
    const statusColor = group.enabled ? 'text-green-600' : 'text-red-600';
    const statusIcon = group.enabled ? '✅' : '❌';
    const statusText = group.enabled ? 'Active' : 'Blocked';
    
    div.innerHTML = `
        <div class="flex justify-between items-start mb-4">
            <div>
                <h3 class="text-lg font-semibold text-gray-900 capitalize">${group.name}</h3>
                <p class="text-sm text-gray-500 mt-1">${group.description || ''}</p>
            </div>
            <span class="${statusColor} text-2xl">${statusIcon}</span>
        </div>
        
        <div class="mb-4">
            <div class="text-sm text-gray-600">
                ${group.devices.length} device${group.devices.length !== 1 ? 's' : ''}
            </div>
            <div class="mt-2 space-y-1">
                ${group.devices.slice(0, 3).map(device => `
                    <div class="text-xs text-gray-500">
                        • ${device.name}
                    </div>
                `).join('')}
                ${group.devices.length > 3 ? `<div class="text-xs text-gray-400">+ ${group.devices.length - 3} more</div>` : ''}
            </div>
        </div>
        
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium ${statusColor}">${statusText}</span>
            ${!isProtected ? `
                <button 
                    onclick="toggleGroup('${group.name}', this)" 
                    class="${group.enabled ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'} text-white px-4 py-2 rounded-lg text-sm transition active:scale-95 disabled:opacity-60"
                >
                    ${group.enabled ? 'Block' : 'Enable'}
                </button>
            ` : `
                <span class="text-xs text-gray-400 px-4 py-2">🔒 Protected</span>
            `}
        </div>
    `;
    
    return div;
}

async function toggleGroup(groupName, button) {
    const label = formatGroupName(groupName);
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
            const verb = data.action === 'block' ? 'blocked' : 'enabled';
            // 200 with success=false means some firewall rules failed to apply
            if (data.success) {
                showToast(`${label} ${verb}`, 'success');
            } else {
                showToast(`${label} ${verb} only partially — some devices failed, check the activity log`, 'warning');
            }
            await loadDashboard();
        } catch (error) {
            console.error('Error toggling group:', error);
            showToast(`Couldn't change ${label}: ${error.message}`, 'error');
        }
    });
}

async function quickAction(action, button) {
    const label = QUICK_ACTION_LABELS[action] || formatAction(action);
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
                showToast(`${label} applied`, 'success');
            } else {
                showToast(`${label} applied only partially — check the activity log`, 'warning');
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
            showToast('Configuration reloaded', 'success');
        } catch (error) {
            console.error('Error reloading config:', error);
            showToast(`Couldn't reload configuration: ${error.message}`, 'error');
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
    }
}

function renderLogs(logs) {
    const container = document.getElementById('logsContainer');
    
    if (logs.length === 0) {
        container.innerHTML = '<div class="p-4 text-gray-500 text-center">No activity yet</div>';
        return;
    }
    
    container.innerHTML = logs.map(log => {
        const timestamp = new Date(log.timestamp).toLocaleString();
        const statusColor = log.success ? 'text-green-600' : 'text-red-600';
        const statusIcon = log.success ? '✓' : '✗';
        
        return `
            <div class="p-4 hover:bg-gray-50 transition-colors">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <span class="${statusColor} font-bold">${statusIcon}</span>
                        <div>
                            <div class="text-sm font-medium text-gray-900">
                                ${formatAction(log.action)} - ${log.target}
                            </div>
                            <div class="text-xs text-gray-500">
                                by ${log.user} at ${timestamp}
                            </div>
                        </div>
                    </div>
                </div>
                ${log.details ? `<div class="ml-8 mt-1 text-xs text-gray-500">${log.details}</div>` : ''}
            </div>
        `;
    }).join('');
}

function formatAction(action) {
    return action
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Auto-refresh every 30 seconds
setInterval(() => {
    if (!loginModal.classList.contains('hidden')) return;
    loadDashboard();
}, 30000);
