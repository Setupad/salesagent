class TargetingCatalog {
    static catalogs = new Map();

    static shared(tenantId, scriptRoot = '') {
        const key = JSON.stringify([tenantId, scriptRoot]);
        if (!this.catalogs.has(key)) {
            this.catalogs.set(key, new TargetingCatalog(tenantId, scriptRoot));
        }
        return this.catalogs.get(key);
    }

    constructor(tenantId, scriptRoot = '', fetcher = (...args) => fetch(...args)) {
        this.base = `${scriptRoot}/api/tenant/${encodeURIComponent(tenantId)}/targeting`;
        this.fetcher = fetcher;
        this.requests = new Map();
    }

    async request(path) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await this.fetcher(this.base + path, {
                credentials: 'same-origin', signal: controller.signal
            });
            if (response.redirected) throw new Error('Session expired. Reload the page to sign in.');
            if (!response.ok) throw new Error(`Targeting request failed (HTTP ${response.status}).`);
            return await response.json();
        } finally {
            clearTimeout(timeout);
        }
    }

    cached(key, loader, refresh = false) {
        if (refresh) this.requests.delete(key);
        if (!this.requests.has(key)) {
            const pending = loader().catch(error => {
                if (this.requests.get(key) === pending) this.requests.delete(key);
                throw error;
            });
            this.requests.set(key, pending);
        }
        return this.requests.get(key);
    }

    data(refresh = false) {
        return this.cached('catalog', () => this.request('/all'), refresh);
    }

    async keys(refresh = false) {
        const data = await this.data(refresh);
        return data.customKeys || data.custom_targeting_keys || [];
    }

    values(keyId, refresh = false) {
        return this.cached(`values:${keyId}`, async () => {
            const values = [];
            let offset = 0;
            while (true) {
                const page = await this.request(`/values/${encodeURIComponent(keyId)}?offset=${offset}&limit=250`);
                if (!Array.isArray(page.values) || typeof page.has_more !== 'boolean') {
                    throw new Error('The targeting values response is incomplete.');
                }
                values.push(...page.values);
                if (!page.has_more) return values;
                if (!Number.isInteger(page.next_offset) || page.next_offset <= offset || !page.values.length) {
                    throw new Error('The targeting values response is incomplete.');
                }
                offset = page.next_offset;
            }
        }, refresh);
    }
}

function selectableOption(key, values) {
    const names = [...new Set(values
        .filter(value => value.status === 'ACTIVE' && typeof value.name === 'string' && value.name.length)
        .map(value => value.name))];
    if (!names.length) throw new Error('This key has no active values to expose.');
    const option = { display_name: key.display_name || key.name, values: names };
    const labels = targetingValueLabels(names, values);
    if (Object.keys(labels).length) option.value_labels = labels;
    return option;
}

function targetingValueLabels(names, values) {
    const allowed = new Set(names);
    return Object.fromEntries(values
        .filter(value => allowed.has(value.name) && typeof value.display_name === 'string'
            && value.display_name.trim() && value.display_name !== value.name)
        .map(value => [value.name, value.display_name]));
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TargetingCatalog, selectableOption, targetingValueLabels };
}
