const assert = require('node:assert/strict');
const test = require('node:test');
const { saveDiscount } = require('../../static/js/advertiser-discount.js');

function discountForm(value = '12.50') {
    const input = { value, disabled: false, validity: { valid: true } };
    const button = { disabled: false };
    const status = { textContent: '', dataset: {} };
    const attributes = {};
    return {
        dataset: { discountUrl: '/admin/tenant/t1/principal/p1/discount' },
        input, button, status, attributes,
        querySelector(selector) {
            return { '[name="discount_percentage"]': input, 'button': button, '[role="status"]': status }[selector];
        },
        setAttribute(name, value) { attributes[name] = value; },
        reportValidity() { return input.validity.valid; },
    };
}

test('saves a discount with CSRF and prefix, exposing pending and canonical success', async () => {
    const form = discountForm();
    let finish;
    const saving = saveDiscount(form, async (url, options) => {
        assert.equal(url, form.dataset.discountUrl);
        assert.equal(options.method, 'POST');
        assert.equal(options.credentials, 'same-origin');
        assert.equal(options.headers['X-CSRFToken'], 'csrf-value');
        assert.deepEqual(JSON.parse(options.body), { discount_percentage: '12.50' });
        return new Promise(resolve => { finish = resolve; });
    }, 'csrf-value');
    assert.equal(form.input.disabled, true);
    assert.equal(form.button.disabled, true);
    assert.equal(form.attributes['aria-busy'], 'true');
    assert.equal(form.status.textContent, 'Saving...');
    finish({ ok: true, json: async () => ({ success: true, discount_percentage: '12.5' }) });
    await saving;
    assert.equal(form.input.value, '12.5');
    assert.equal(form.input.disabled, false);
    assert.equal(form.button.disabled, false);
    assert.equal(form.attributes['aria-busy'], 'false');
    assert.equal(form.status.textContent, 'Saved');
    assert.equal(form.status.dataset.state, 'success');
});

for (const [label, fetcher, message] of [
    ['server refusal', async () => ({ ok: false, json: async () => ({ error: 'Principal not found' }) }), 'Principal not found'],
    ['network failure', async () => { throw new Error('Network unavailable'); }, 'Network unavailable'],
    ['non-JSON response', async () => ({ ok: false, json: async () => { throw new SyntaxError('HTML response'); } }), 'Unable to save discount.'],
]) {
    test(`${label} restores controls and preserves the entered discount`, async () => {
        const form = discountForm('8.25');
        await saveDiscount(form, fetcher);
        assert.equal(form.input.value, '8.25');
        assert.equal(form.input.disabled, false);
        assert.equal(form.button.disabled, false);
        assert.equal(form.attributes['aria-busy'], 'false');
        assert.equal(form.status.dataset.state, 'error');
        assert.equal(form.status.textContent, message);
    });
}

test('invalid input and duplicate submissions do not send a request', async () => {
    const form = discountForm();
    const unexpectedFetch = () => { assert.fail('Unexpected request'); };
    form.input.validity.valid = false;
    await saveDiscount(form, unexpectedFetch);
    assert.equal(form.status.textContent, '');
    form.input.validity.valid = true;
    form.button.disabled = true;
    await saveDiscount(form, unexpectedFetch);
    assert.equal(form.status.textContent, '');
});

test('another advertiser can save while the first row is pending', async () => {
    const first = discountForm();
    const second = discountForm('0');
    let finish;
    const pending = saveDiscount(first, () => new Promise(resolve => { finish = resolve; }));
    await saveDiscount(second, async () => ({ ok: true, json: async () => ({ success: true, discount_percentage: '0.00' }) }));
    assert.equal(first.status.dataset.state, 'pending');
    assert.equal(second.status.dataset.state, 'success');
    assert.equal(second.input.value, '0.00');
    finish({ ok: true, json: async () => ({ success: true, discount_percentage: '12.50' }) });
    await pending;
});