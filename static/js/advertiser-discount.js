async function saveDiscount(form, fetchImpl = globalThis.fetch, csrfToken = '') {
    const input = form.querySelector('[name="discount_percentage"]');
    const button = form.querySelector('button');
    const status = form.querySelector('[role="status"]');
    if (button.disabled || !form.reportValidity()) return;

    input.disabled = true;
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.dataset.state = 'pending';
    status.textContent = 'Saving...';
    try {
        const response = await fetchImpl(form.dataset.discountUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ discount_percentage: input.value }),
        });
        const result = await response.json();
        if (!response.ok || result.success !== true || typeof result.discount_percentage !== 'string') {
            throw new Error(result.error || 'Unable to save discount.');
        }
        input.value = result.discount_percentage;
        status.dataset.state = 'success';
        status.textContent = 'Saved';
    } catch (error) {
        status.dataset.state = 'error';
        status.textContent = error instanceof SyntaxError ? 'Unable to save discount.' : error.message;
    } finally {
        input.disabled = false;
        button.disabled = false;
        form.setAttribute('aria-busy', 'false');
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { saveDiscount };
}

if (typeof document !== 'undefined') {
    document.querySelectorAll('[data-discount-url]').forEach(form => {
        form.addEventListener('submit', event => {
            event.preventDefault();
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            void saveDiscount(form, globalThis.fetch, csrfToken);
        });
    });
}