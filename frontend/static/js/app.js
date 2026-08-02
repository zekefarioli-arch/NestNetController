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
    
    return fetch(`${API_BASE_URL}${endpoint}`, {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    });
}

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
                    onclick="toggleGroup('${group.name}')" 
                    class="${group.enabled ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'} text-white px-4 py-2 rounded-lg text-sm transition-colors"
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

async function toggleGroup(groupName) {
    try {
        const response = await apiRequest(`/devices/groups/${groupName}/toggle`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
            return;
        }
        
        await loadDashboard();
    } catch (error) {
        console.error('Error toggling group:', error);
        alert('Failed to toggle group');
    }
}

async function quickAction(action) {
    try {
        const response = await apiRequest('/devices/quick-action', {
            method: 'POST',
            body: JSON.stringify({ action })
        });
        
        if (!response.ok) throw new Error('Quick action failed');
        
        await loadDashboard();
    } catch (error) {
        console.error('Error executing quick action:', error);
        alert('Failed to execute quick action');
    }
}

async function reloadConfig() {
    try {
        const response = await apiRequest('/devices/reload', {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Reload failed');
        
        await loadDashboard();
        alert('Configuration reloaded successfully');
    } catch (error) {
        console.error('Error reloading config:', error);
        alert('Failed to reload configuration');
    }
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
