class SelectableTargetingEditor {
    constructor(container, field) {
        this.container = container;
        this.field = field;
        this.options = Object.create(null);
        this.keys = [];
        this.busy = false;
        this.catalog = TargetingCatalog.shared(container.dataset.tenantId, container.dataset.scriptRoot);
        try {
            const saved = JSON.parse(field.value || '{}');
            if (!saved || typeof saved !== 'object' || Array.isArray(saved)) throw new Error('Invalid saved options.');
            Object.assign(this.options, saved);
        } catch (error) {
            container.textContent = 'Saved targeting options could not be read. The original value is preserved.';
            return;
        }
        field.form?.addEventListener('submit', event => {
            if (this.busy) {
                event.preventDefault();
                event.stopImmediatePropagation();
                this.status('Wait for GAM values to finish loading before saving.', true);
            }
        }, true);
        this.render();
        this.loadKeys();
    }

    element(tag, text, className) {
        const element = document.createElement(tag);
        if (text) element.textContent = text;
        if (className) element.className = className;
        return element;
    }

    action(title, icon, handler) {
        const button = this.element('button');
        button.type = 'button';
        button.title = title;
        button.setAttribute('aria-label', title);
        const symbol = this.element('i');
        symbol.className = `fas fa-${icon}`;
        symbol.setAttribute('aria-hidden', 'true');
        button.append(symbol);
        button.disabled = this.busy;
        button.addEventListener('click', handler);
        return button;
    }

    status(message, error = false) {
        this.message.textContent = message;
        this.message.setAttribute('role', error ? 'alert' : 'status');
    }

    save() {
        this.field.value = JSON.stringify(this.options);
    }

    async loadKeys(refresh = false) {
        this.status('Loading GAM keys...');
        try {
            this.keys = (await this.catalog.keys(refresh)).filter(key => key.status === 'ACTIVE');
            this.updateKeys();
            this.status(this.keys.length ? '' : 'No active GAM keys. Sync inventory to populate the catalog.');
        } catch (error) {
            this.status(error.message, true);
        }
    }

    updateKeys() {
        const selected = this.select.value;
        const query = this.search.value.toLowerCase();
        this.select.replaceChildren(this.element('option', 'Select a GAM key'));
        this.select.firstChild.value = '';
        for (const key of this.keys) {
            if (Object.hasOwn(this.options, key.name)) continue;
            if (!`${key.name} ${key.display_name || ''}`.toLowerCase().includes(query)) continue;
            const option = this.element('option', key.display_name && key.display_name !== key.name
                ? `${key.display_name} (${key.name})` : key.name);
            option.value = key.id;
            this.select.append(option);
        }
        this.select.value = selected;
        this.add.disabled = this.busy || !this.select.value;
    }

    async expose(key, refresh = false) {
        if (this.busy || !key) return;
        this.busy = true;
        this.render();
        this.status(`Loading all values for ${key.name}...`);
        try {
            const option = selectableOption(key, await this.catalog.values(key.id, refresh));
            if (Object.hasOwn(this.options, key.name)) {
                const previous = this.options[key.name];
                if (!confirm(`Replace the allowed values for ${key.name} with ${option.values.length} active GAM values?`)) return;
                if (previous && !Array.isArray(previous) && previous.display_name) option.display_name = previous.display_name;
            }
            this.options[key.name] = option;
            this.save();
            this.pendingMessage = `${key.name}: ${option.values.length} values included.`;
        } catch (error) {
            this.pendingMessage = error.message;
            this.pendingError = true;
        } finally {
            this.busy = false;
            this.render();
            this.status(this.pendingMessage || '', this.pendingError || false);
            this.pendingMessage = '';
            this.pendingError = false;
        }
    }

    render() {
        this.container.replaceChildren();
        const toolbar = this.element('div', '', 'selectable-targeting-toolbar');
        const searchLabel = this.element('label', 'Find key');
        this.search = this.element('input');
        this.search.type = 'search';
        this.search.disabled = this.busy;
        searchLabel.append(this.search);
        const keyLabel = this.element('label', 'GAM key');
        this.select = this.element('select');
        this.select.disabled = this.busy;
        keyLabel.append(this.select);
        this.add = this.action('Expose selected key', 'plus', () => {
            this.expose(this.keys.find(key => String(key.id) === this.select.value));
        });
        const retry = this.action('Reload GAM keys', 'sync-alt', () => this.loadKeys(true));
        toolbar.append(searchLabel, keyLabel, this.add, retry);
        this.message = this.element('div', '', 'selectable-targeting-status');
        this.message.setAttribute('aria-live', 'polite');
        this.container.append(toolbar, this.message);
        this.search.addEventListener('input', () => this.updateKeys());
        this.select.addEventListener('change', () => this.updateKeys());
        this.updateKeys();
        for (const [name, saved] of Object.entries(this.options)) this.renderRow(name, saved);
        if (!Object.keys(this.options).length) {
            this.container.append(this.element('p', 'No buyer-selectable keys.'));
        }
    }

    renderRow(name, saved) {
        const row = this.element('div', '', 'selectable-targeting-row');
        row.dataset.key = name;
        const heading = this.element('div', '', 'selectable-targeting-heading');
        const refresh = this.action(`Refresh values for ${name}`, 'sync-alt', () => {
            const key = this.keys.find(item => item.name === name);
            if (key) this.expose(key, true);
            else this.status('This key is absent from the active GAM catalog. Saved values are preserved.', true);
        });
        const remove = this.action(`Remove ${name}`, 'trash-alt', () => {
            delete this.options[name];
            this.save();
            this.render();
        });
        heading.append(this.element('strong', name), refresh, remove);
        row.append(heading);
        const values = Array.isArray(saved) ? saved : saved?.values;
        if (!Array.isArray(values)) {
            row.append(this.element('p', 'Saved configuration preserved. Refresh to replace its values.'));
            this.container.append(row);
            return;
        }
        const label = this.element('label', 'Buyer label', 'selectable-targeting-label');
        const input = this.element('input');
        input.type = 'text';
        input.value = saved.display_name || name;
        input.disabled = this.busy;
        input.addEventListener('input', () => {
            this.options[name] = { ...(Array.isArray(saved) ? { values } : saved), display_name: input.value };
            this.save();
        });
        label.append(input);
        const details = this.element('details');
        details.append(this.element('summary', `${values.length} allowed values`));
        const list = this.element('div', '', 'selectable-targeting-values');
        list.textContent = values.map(value => typeof value === 'string' ? value : JSON.stringify(value)).join(', ');
        details.append(list);
        row.append(label, details);
        this.container.append(row);
    }
}
