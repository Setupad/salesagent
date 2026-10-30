const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');

const template = readFileSync(resolve(__dirname, '../../templates/add_product_gam.html'), 'utf8');
const source = template.slice(template.indexOf('function prepareFormSubmission(event)'),
    template.indexOf('// Filter formats based on search input'));

test('GAM editor requests a versioned picker asset', () => {
    assert.match(template, /format-template-picker\.js\?v=[^"\s]+/);
});

function submit(formats, pickerActive) {
    const formatsField = { value: JSON.stringify(formats) };
    let prevented = false;
    let message;
    const context = {
        window: { formatPicker: pickerActive ? {} : undefined },
        document: {
            getElementById: id => id === 'formats-data' ? formatsField : { value: '', elements: [] },
            querySelectorAll: () => [{ dataset: { agentUrl: 'legacy-agent', formatId: 'stale-format' } }]
        },
        console: { log() {}, error() {}, warn() {} },
        alert: value => { message = value; }
    };
    runInNewContext(`${source}\nthis.submit = prepareFormSubmission;`, context);
    context.submit({ preventDefault() { prevented = true; } });
    return { formats: JSON.parse(formatsField.value), prevented, message };
}

test('empty picker blocks saving without restoring legacy formats', () => {
    const result = submit([], true);
    assert.equal(result.prevented, true);
    assert.deepEqual(result.formats, []);
    assert.match(result.message, /format/i);
});

test('selected picker formats reach submission unchanged', () => {
    const formats = [{ agent_url: 'agent', id: 'native_standard' }];
    assert.deepEqual(submit(formats, true), { formats, prevented: false, message: undefined });
});

test('legacy checkboxes remain supported when no picker is active', () => {
    assert.deepEqual(submit([], false).formats,
        [{ agent_url: 'legacy-agent', format_id: 'stale-format' }]);
});
