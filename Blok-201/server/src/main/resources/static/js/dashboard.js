let locationMap = null;
let locationMarker = null;

function enterDashboard(user) {
    currentUser = user;

    document.getElementById('authPage').style.display  = 'none';
    document.getElementById('dashboard').style.display = 'block';

    const isCaretaker = user.role === 'CAREGIVER';
    const isStage1    = user.role === 'USER' && user.dementiaStage === 1;
    const isStage2    = user.role === 'USER' && user.dementiaStage === 2;

    const badge = document.getElementById('dBadge');
    if (isCaretaker) {
        badge.textContent = 'Custodian';
        badge.className   = 'badge ct';
    } else if (isStage1) {
        badge.textContent = 'Stage 1';
        badge.className   = 'badge s1';
    } else {
        badge.textContent = 'Stage 2';
        badge.className   = 'badge s2';
    }

    const hint = document.getElementById('dashHint');
    if (isStage2) {
        hint.textContent = 'View your schedule below. Your custodian manages these tasks for you.';
    } else {
        hint.textContent = 'Use the calendar below to write and schedule your own tasks and reminders.';
    }
    document.getElementById('dName').textContent = user.fullName || user.username;

    const first = user.fullName ? user.fullName.split(' ')[0] : user.username;
    document.getElementById('dGreeting').textContent = isCaretaker
        ? 'Welcome, ' + first
        : 'Good to see you, ' + first;

    if (isCaretaker) {
        document.getElementById('dSub').textContent =
            'You are in the custodian portal.'
            + (user.patientUsername ? ' Managing: ' + user.patientUsername + '.' : '');
    } else if (isStage2) {
        document.getElementById('dSub').textContent =
            'Your custodian manages some features on your behalf.';
    } else {
        document.getElementById('dSub').textContent =
            'You have full access to all DementiaAid features.';
    }

    document.getElementById('dashHint').textContent =
        'Use the calendar below to write and schedule your own tasks and reminders. ' +
        'Add a time to a task and DementiaAid will notify you when that moment arrives.';

    renderIdCard(user, isCaretaker);

    renderSensorPanel(isCaretaker || isStage1);

    if (typeof initAiAssistant === 'function') {
        initAiAssistant(user);
    }

    checkNotifPermission();

    const today = new Date();
    firedToday  = new Set();
    calYear     = today.getFullYear();
    calMonth    = today.getMonth();
    calSelected = new Date(today);

    renderCalendar();
    startReminderLoop();

    connectWebSocket();
}

function renderIdCard(user, isCaretaker) {
    const existing = document.getElementById('userIdCard');
    if (existing) { existing.remove(); }
    if (isCaretaker) { return; }

    const card = document.createElement('div');
    card.id        = 'userIdCard';
    card.className = 'info-card id-card';
    card.innerHTML =
        '<div class="info-card-title">&#128100; Your Patient ID</div>' +
        '<div class="info-card-body">' +
            '<div class="info-row">' +
                '<span class="info-value mono uuid-text" id="uuidDisplay">' + escHtml(user.id) + '</span>' +
                '<button class="copy-btn" onclick="copyUserId()" title="Copy to clipboard">Copy</button>' +
            '</div>' +
        '</div>' +
        '<div class="info-card-note">Share this ID with your custodian so they can link their account to yours.</div>';

    insertBeforeCalendar(card);
}

function copyUserId() {
    const id = currentUser && currentUser.id;
    if (!id) { return; }
    navigator.clipboard.writeText(id).then(function () {
        const btn = document.querySelector('.copy-btn');
        if (btn) {
            btn.textContent = 'Copied!';
            setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
        }
    }).catch(function () {
        const ta = document.createElement('textarea');
        ta.value = id;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
    });
}

function renderSensorPanel(visible) {
    const existing = document.getElementById('sensorPanel');
    if (existing) { existing.remove(); }
    if (locationMap) {
        try { locationMap.remove(); } catch (e) {}
        locationMap = null;
        locationMarker = null;
    }
    if (!visible) { return; }

    const panel = document.createElement('div');
    panel.id        = 'sensorPanel';
    panel.className = 'sensor-panel';
    panel.innerHTML =
        '<div class="sensor-header">' +
            '<span class="sensor-title">&#128506; Live GPS Location</span>' +
            '<span class="ws-dot disconnected" id="wsDot" title="WebSocket disconnected"></span>' +
        '</div>' +
        '<div class="sensor-map" id="sensorMap">' +
            '<div class="sensor-empty">Waiting for GPS coordinates...</div>' +
        '</div>' +
        '<div class="location-meta">' +
            '<div class="location-item"><div class="location-label">Latitude</div><div class="location-value" id="locLat">—</div></div>' +
            '<div class="location-item"><div class="location-label">Longitude</div><div class="location-value" id="locLng">—</div></div>' +
            '<div class="location-item"><div class="location-label">Speed</div><div class="location-value" id="locSpeed">—</div></div>' +
            '<div class="location-item"><div class="location-label">Source</div><div class="location-value" id="locSource">GPS module</div></div>' +
        '</div>' +
        '<div class="sensor-ts" id="sensorTs">Waiting for data…</div>';

    const dashBody = document.querySelector('.dash-body');
    const calSection = dashBody.querySelector('.cal-section');
    dashBody.insertBefore(panel, calSection);

    initLocationMap();
}

function updateSensorUI(data) {
    if (!data) {
        return;
    }

    const latitude = pickNumber(data.latitude, data.lat);
    const longitude = pickNumber(data.longitude, data.lon, data.lng);
    const speed = pickNumber(data.speedKmh, data.speed_kmh, data.speed);

    const latEl = document.getElementById('locLat');
    const lngEl = document.getElementById('locLng');
    const speedEl = document.getElementById('locSpeed');
    const sourceEl = document.getElementById('locSource');
    const tsEl = document.getElementById('sensorTs');

    if (latEl) { latEl.textContent = Number.isFinite(latitude) ? latitude.toFixed(6) : '—'; }
    if (lngEl) { lngEl.textContent = Number.isFinite(longitude) ? longitude.toFixed(6) : '—'; }
    if (speedEl) { speedEl.textContent = Number.isFinite(speed) ? speed.toFixed(1) + ' km/h' : '—'; }
    if (sourceEl) { sourceEl.textContent = data.deviceId || data.source || 'GPS module'; }

    if (tsEl && data.timestamp) {
        const d = new Date(data.timestamp);
        tsEl.textContent = 'Last GPS update: ' + d.toLocaleTimeString();
    }

    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
        updateLocationMap(latitude, longitude);
    }
}

function initLocationMap() {
    const mapEl = document.getElementById('sensorMap');
    if (!mapEl || typeof L === 'undefined') {
        return;
    }

    locationMap = L.map(mapEl, { zoomControl: true }).setView([42.6977, 23.3219], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(locationMap);
}

function updateLocationMap(lat, lng) {
    if (!locationMap || typeof L === 'undefined') {
        return;
    }

    if (!locationMarker) {
        locationMarker = L.marker([lat, lng]).addTo(locationMap).bindPopup('Live GPS position');
    } else {
        locationMarker.setLatLng([lat, lng]);
    }

    locationMap.setView([lat, lng], Math.max(locationMap.getZoom(), 15));
}

function pickNumber(...values) {
    for (const value of values) {
        const num = Number(value);
        if (Number.isFinite(num)) {
            return num;
        }
    }
    return null;
}

async function fetchLatestGpsSnapshot() {
    try {
        const res = await fetch(API + '/api/sensor/latest', { credentials: 'include' });
        if (!res.ok) {
            return;
        }
        const body = await res.json();
        if (body && body.status === 'ok' && body.item) {
            updateSensorUI(body.item);
        }
    } catch (e) {
        // silent fallback
    }
}

function connectWebSocket() {
    disconnectWebSocket();

    if (typeof SockJS === 'undefined' || typeof Stomp === 'undefined') {
        console.warn('SockJS or Stomp not loaded — WebSocket skipped.');
        return;
    }

    const socket = new SockJS(API + '/ws');
    stompClient  = Stomp.over(socket);
    stompClient.debug = null;

    stompClient.connect({}, function onConnected() {
        setWsDot(true);
        fetchLatestGpsSnapshot();

        sensorSub = stompClient.subscribe('/topic/sensor', function (frame) {
            try {
                const data = JSON.parse(frame.body);
                updateSensorUI(data);
            } catch (e) {
                console.error('Bad sensor frame:', frame.body, e);
            }
        });

    }, function onError(err) {
        console.warn('STOMP error:', err);
        setWsDot(false);
        fetchLatestGpsSnapshot();
        setTimeout(function () {
            if (currentUser) { connectWebSocket(); }
        }, 5000);
    });
}

function disconnectWebSocket() {
    if (sensorSub)   { try { sensorSub.unsubscribe(); } catch(e){} sensorSub = null; }
    if (stompClient) { try { stompClient.disconnect(); } catch(e){} stompClient = null; }
    setWsDot(false);
}

function setWsDot(connected) {
    const dot = document.getElementById('wsDot');
    if (!dot) { return; }
    dot.className = 'ws-dot ' + (connected ? 'connected' : 'disconnected');
    dot.title     = connected ? 'WebSocket connected' : 'WebSocket disconnected';
}

function insertBeforeCalendar(el) {
    const dashBody   = document.querySelector('.dash-body');
    const calSection = dashBody.querySelector('.cal-section');
    const sensorPanel = document.getElementById('sensorPanel');
    const ref = sensorPanel || calSection;
    dashBody.insertBefore(el, ref);
}

function escHtml(str) {
    if (str == null) { return ''; }
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
