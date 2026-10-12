// Tests of the pure helpers in static/js/summary.js (plain node, no framework).
const assert = require('assert');
const NN = require('../static/js/summary.js');

const g = (name, enabled, n, extra = {}) => ({ name, enabled, devices: Array.from({ length: n }, (_, i) => ({ name: `d${i}` })), ...extra });

// numbers
const s = NN.summarize([g('media', false, 4), g('essential', false, 1), g('security', true, 6), g('infrastructure', true, 5, { protected: true }), g('kids', false, 0, { auto_detect: true })]);
assert.deepStrictEqual([s.groups, s.onDevices, s.offDevices], [4, 11, 5]);
assert.deepStrictEqual(s.offGroups, ['media', 'essential']);

// headline
assert.strictEqual(NN.headline(s).title, 'Media and Essential are off.');
assert.strictEqual(NN.headline(s).body, '5 devices cannot reach the internet, 11 can. Anything that is not listed is always offline.');
assert.strictEqual(NN.headline(NN.summarize([g('a', true, 2)])).title, 'Every group is on.');
assert.strictEqual(NN.headline(NN.summarize([g('zeke_phone', false, 1)])).title, 'Zeke phone is off.');
assert.strictEqual(NN.headline(NN.summarize([g('a', false, 1), g('b', false, 1), g('c', false, 1), g('d', false, 1)])).title, '4 groups are off.');
assert.strictEqual(NN.headline(NN.summarize([])).title, 'No groups yet.');
assert.strictEqual(NN.headline(NN.summarize([g('a', true, 1), g('empty', false, 0)])).body.startsWith('1 device can'), true);

// names
assert.strictEqual(NN.displayName('zeke_phone'), 'Zeke phone');
assert.strictEqual(NN.joinNames(['A', 'B', 'C']), 'A, B and C');

// time: the backend sends UTC with no zone suffix
const now = new Date('2026-10-12T14:00:00Z');
assert.strictEqual(NN.relativeTime('2026-10-12T13:57:00', now), '3 min ago');
assert.strictEqual(NN.relativeTime('2026-10-12T13:59:50', now), 'just now');
assert.strictEqual(NN.relativeTime('2026-10-12T11:00:00+00:00', now), '3 h ago');

// activity sentences share the names of the buttons
assert.strictEqual(NN.activitySentence({ action: 'disable_group', target: 'media' }), 'Media turned off');
assert.strictEqual(NN.activitySentence({ action: 'unblock_group', target: 'zeke_phone' }), 'Zeke phone turned on');
assert.strictEqual(NN.sceneLabel('only_essential'), 'Essential only');
assert.strictEqual(NN.activitySentence({ action: 'only_essential_security', target: 'quick_action' }), 'Scene: Essential and cameras');
assert.strictEqual(NN.activitySentence({ action: 'add_device', target: 'media/AA:BB' }), 'Device added to Media');
assert.strictEqual(NN.activitySentence({ action: 'something_new', target: 'x' }), 'Something new');

// untrusted text never becomes markup
assert.strictEqual(NN.escapeHtml('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');

console.log('summary: all checks passed');
