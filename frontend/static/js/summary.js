// Pure helpers of the panel: wording and numbers built from the API's data.
// No DOM here, so they run in the browser (window.NN) and in Node (tests/test_summary.js).
(function (root) {
    function displayName(name) {
        const text = String(name).replace(/_/g, ' ');
        return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function joinNames(names) {
        if (names.length <= 1) return names.join('');
        return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
    }

    function plural(n, one, many) {
        return `${n} ${n === 1 ? one : many}`;
    }

    // Counts, from the groups the API returns (enabled = the group's devices reach the internet)
    function summarize(groups) {
        const real = groups.filter(g => !g.auto_detect);
        const on = real.filter(g => g.enabled);
        const off = real.filter(g => !g.enabled);
        const count = list => list.reduce((n, g) => n + g.devices.length, 0);
        return {
            groups: real.length,
            onGroups: on.map(g => g.name),
            offGroups: off.map(g => g.name),
            onDevices: count(on),
            offDevices: count(off),
        };
    }

    // The sentence the page opens with
    function headline(s) {
        if (s.groups === 0) {
            return { title: 'No groups yet.', body: 'Add devices to devices.yaml, then reload the devices.' };
        }
        const tail = 'Anything that is not listed is always offline.';
        const reach = s.offDevices === 0
            ? `${plural(s.onDevices, 'device', 'devices')} can reach the internet.`
            : `${plural(s.offDevices, 'device', 'devices')} cannot reach the internet, ${s.onDevices} can.`;
        if (s.offGroups.length === 0) {
            return { title: 'Every group is on.', body: `${reach} ${tail}` };
        }
        const names = s.offGroups.map(displayName);
        const title = names.length <= 3
            ? `${joinNames(names)} ${names.length === 1 ? 'is' : 'are'} off.`
            : `${names.length} groups are off.`;
        return { title, body: `${reach} ${tail}` };
    }

    // The backend writes UTC without a zone suffix; without this the browser reads it as local time
    function parseTimestamp(iso) {
        const text = String(iso);
        return new Date(/(Z|[+-]\d\d:?\d\d)$/.test(text) ? text : `${text}Z`);
    }

    function relativeTime(iso, now = new Date()) {
        const seconds = Math.round((now - parseTimestamp(iso)) / 1000);
        if (seconds < 45) return 'just now';
        if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
        if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
        return parseTimestamp(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
    }

    // One name per action through the whole flow: the button, the toast and the activity line
    const SCENES = [
        { action: 'only_essential_security', label: 'Essential and cameras', hint: 'Turns every other group off.' },
        { action: 'only_essential', label: 'Essential only', hint: 'Turns the cameras off too.' },
        { action: 'enable_all', label: 'Everything on', hint: 'Turns every group on.' },
    ];

    function sceneLabel(action) {
        const scene = SCENES.find(s => s.action === action);
        return scene ? scene.label : displayName(action);
    }

    function activitySentence(log) {
        const target = displayName(String(log.target).split('/')[0]);
        switch (log.action) {
            case 'enable_group':
            case 'unblock_group': return `${target} turned on`;
            case 'disable_group':
            case 'block_group': return `${target} turned off`;
            case 'enable_all': return 'Everything turned on';
            case 'only_essential':
            case 'only_essential_security': return `Scene: ${sceneLabel(log.action)}`;
            case 'reload_config': return 'Devices reloaded';
            case 'add_device': return `Device added to ${target}`;
            case 'delete_device': return `Device removed from ${target}`;
            case 'create_group': return `Group ${target} created`;
            case 'delete_group': return `Group ${target} deleted`;
            case 'restore_backup': return 'Device list restored from a backup';
            default: return displayName(log.action);
        }
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    const api = { displayName, joinNames, plural, summarize, headline, parseTimestamp, relativeTime, SCENES, sceneLabel, activitySentence, escapeHtml };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.NN = api;
})(typeof window !== 'undefined' ? window : globalThis);
