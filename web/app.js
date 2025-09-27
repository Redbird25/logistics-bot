const form = document.getElementById('search-form');
const resultsContainer = document.getElementById('results');
const emptyState = document.getElementById('empty-state');
const template = document.getElementById('result-template');

const API_BASE = '/search';

function qs(selector, parent) {
    return (parent || document).querySelector(selector);
}

function formatAmount(amount, currency) {
    if (amount === null || amount === undefined) {
        return 'Не указано';
    }
    const value = Number(amount);
    if (!Number.isFinite(value)) {
        return String(amount);
    }
    let text;
    if (value >= 1_000_000) {
        text = `${(value / 1_000_000).toFixed(1).replace(/\.0$/, '')} млн`;
    } else if (value >= 1_000) {
        text = `${(value / 1_000).toFixed(1).replace(/\.0$/, '')} тыс`;
    } else {
        text = value.toLocaleString('ru-RU');
    }
    const currencyMap = { UZS: 'сум', USD: 'USD', EUR: 'EUR', RUB: '₽' };
    const suffix = currencyMap[(currency || '').toUpperCase()] || (currency || '').toUpperCase();
    return `${text} ${suffix}`.trim();
}

function humanizeTime(value) {
    if (!value) return '';
    const posted = new Date(value);
    if (Number.isNaN(posted.getTime())) return '';
    const diff = Math.max(0, Date.now() - posted.getTime());
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'меньше минуты назад';
    if (minutes < 60) return `${minutes} мин назад`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ч назад`;
    const days = Math.floor(hours / 24);
    return `${days} дн назад`;
}

function formatDistance(metadata) {
    if (!metadata) return '';
    const parts = [];
    if (Number.isFinite(metadata.distance_km)) {
        parts.push(`${metadata.distance_km.toFixed(0)} км`);
    }
    if (Number.isFinite(metadata.duration_hours)) {
        parts.push(`${metadata.duration_hours.toFixed(1)} ч`);
    }
    return parts.join(' • ');
}

function buildLink(item) {
    const chatId = item.chat_id;
    const messageId = item.message_id;
    if (!chatId || messageId === null || messageId === undefined) return '#';
    const numeric = Number(chatId);
    if (!Number.isFinite(numeric)) return '#';
    if (numeric < 0) {
        return `https://t.me/c/${String(Math.abs(numeric)).slice(3)}/${messageId}`;
    }
    return '#';
}

function renderResults(items) {
    resultsContainer.innerHTML = '';
    if (!items.length) {
        emptyState.classList.remove('hidden');
        return;
    }
    emptyState.classList.add('hidden');
    items.forEach((item, index) => {
        const clone = template.content.cloneNode(true);
        const route = `${(item.route_from || 'Не указано').trim()} → ${(item.route_to || 'Не указано').trim()}`;
        qs('.route', clone).textContent = `${index + 1}. ${route}`;
        qs('.posted', clone).textContent = humanizeTime(item.posted_at) || '';

        const metadata = item.metadata || {};
        const vehicleParts = [];
        if (item.vehicle_type) vehicleParts.push(item.vehicle_type);
        if (Array.isArray(item.tags)) {
            item.tags.forEach(tag => {
                const clean = String(tag || '').trim();
                if (clean && !vehicleParts.includes(clean)) {
                    vehicleParts.push(clean);
                }
            });
        }
        const vehicleText = vehicleParts.join(', ');
        qs('.vehicle', clone).textContent = vehicleText ? vehicleText : 'Не указано';

        const cargoRaw = metadata.cargo || metadata.notes || '';
        const cargoText = String(cargoRaw || '').trim();
        qs('.cargo', clone).textContent = cargoText && cargoText.toLowerCase() !== 'n/a' ? cargoText : 'Не указано';

        qs('.price', clone).textContent = formatAmount(item.price_amount, item.price_currency);

        const contactRaw = (item.contact || '').trim();
        qs('.contact', clone).textContent = contactRaw && contactRaw.toLowerCase() !== 'n/a' ? contactRaw : 'Не указано';

        const distance = formatDistance(metadata);
        const distanceRow = qs('.meta', clone);
        if (distance) {
            distanceRow.classList.remove('hidden');
            qs('.distance', clone).textContent = distance;
        } else {
            distanceRow.classList.add('hidden');
        }

        const link = buildLink(item);
        qs('.link', clone).href = link;
        if (link === '#') {
            qs('.link', clone).classList.add('disabled');
        }

        resultsContainer.appendChild(clone);
    });
}

async function fetchResults(params = {}) {
    const url = new URL(API_BASE, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
        if (value) url.searchParams.set(key, value);
    });
    const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!response.ok) {
        throw new Error('Failed to load data');
    }
    return response.json();
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const payload = {
        origin: data.get('origin')?.trim(),
        destination: data.get('destination')?.trim(),
        vehicle_type: data.get('vehicle')?.trim(),
    };
    try {
        form.classList.add('loading');
        const items = await fetchResults(payload);
        renderResults(items || []);
    } catch (error) {
        console.error(error);
        emptyState.classList.remove('hidden');
        emptyState.querySelector('p').textContent = 'Не удалось загрузить данные. Попробуйте позже.';
    } finally {
        form.classList.remove('loading');
    }
});

fetchResults().then(renderResults).catch(() => {
    emptyState.classList.remove('hidden');
});
