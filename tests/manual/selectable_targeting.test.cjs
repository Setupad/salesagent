const { test } = require('node:test');
const assert = require('node:assert/strict');
const { TargetingCatalog, selectableOption } = require('../../static/js/targeting_catalog.js');

test('loads every values page and shares requests across widgets', async () => {
    const calls = [];
    const fetcher = async url => {
        calls.push(url);
        const offset = new URL(url, 'https://example.test').searchParams.get('offset');
        return { ok: true, json: async () => offset === '0'
            ? { values: [{ name: 'amp', status: 'ACTIVE' }], has_more: true, next_offset: 250 }
            : { values: [{ name: 'web', status: 'ACTIVE' }], has_more: false, next_offset: null } };
    };
    const catalog = new TargetingCatalog('tenant/a', '/admin', fetcher);
    const [first, second] = await Promise.all([catalog.values('12'), catalog.values('12')]);
    assert.deepEqual(first.map(value => value.name), ['amp', 'web']);
    assert.deepEqual(second, first);
    assert.equal(calls.length, 2);
    assert.match(calls[0], /^\/admin\/api\/tenant\/tenant%2Fa\/targeting\/values\/12\?/);
});

test('failed requests can be retried without losing saved options', async () => {
    let attempts = 0;
    const catalog = new TargetingCatalog('tenant', '', async () => {
        attempts += 1;
        return { ok: attempts > 1, status: 503, json: async () => ({ customKeys: [{ name: 'sport' }] }) };
    });
    await assert.rejects(catalog.keys(), /503/);
    assert.deepEqual(await catalog.keys(), [{ name: 'sport' }]);
    assert.equal(attempts, 2);
});

test('rejects incomplete or non-progressing pages instead of publishing a partial allowlist', async () => {
    const catalog = new TargetingCatalog('tenant', '', async () => ({
        ok: true, json: async () => ({ values: [{ name: 'web' }], has_more: true, next_offset: 0 })
    }));
    await assert.rejects(catalog.values('12'), /incomplete/i);
});

test('exposes all distinct active value names, not GAM IDs or labels', () => {
    assert.deepEqual(selectableOption({ name: 'hb_env', display_name: 'Environment' }, [
        { id: '1', name: 'amp', display_name: 'AMP', status: 'ACTIVE' },
        { id: '2', name: 'web', status: 'ACTIVE' },
        { id: '3', name: 'retired', status: 'INACTIVE' },
        { id: '4', name: 'amp', status: 'ACTIVE' }
    ]), { display_name: 'Environment', values: ['amp', 'web'] });
});

test('refuses keys with no active values', () => {
    assert.throws(() => selectableOption({ name: 'sport' }, []), /active values/i);
});
