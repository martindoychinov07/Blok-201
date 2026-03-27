function enterDashboard(user) {
    currentUser = user;

    document.getElementById('authPage').style.display  = 'none';
    document.getElementById('dashboard').style.display = 'block';

    const isCaretaker = user.role === 'CAREGIVER';
    const isStage1    = user.role === 'USER' && user.dementiaStage === 1;
    const isStage2    = user.role === 'USER' && user.dementiaStage === 2;

    const badge = document.getElementById('dBadge');
    if (isCaretaker) {
        badge.textContent = 'Caretaker';
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
        hint.textContent = 'View your schedule below. Your caretaker manages these tasks for you.';
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
            'You are in the caretaker portal.'
            + (user.patientUsername ? ' Managing: ' + user.patientUsername + '.' : '');
    } else if (isStage2) {
        document.getElementById('dSub').textContent =
            'Your caretaker manages some features on your behalf.';
    } else {
        document.getElementById('dSub').textContent =
            'You have full access to all DementiaAid features.';
    }

    document.getElementById('dashHint').textContent =
        'Use the calendar below to write and schedule your own tasks and reminders. ' +
        'Add a time to a task and DementiaAid will notify you when that moment arrives.';

    renderCredentialsCard(user, isCaretaker);

    renderIdCard(user, isCaretaker);

    renderSensorPanel(isCaretaker || isStage1);

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

function renderCredentialsCard(user, isCaretaker) {
    const existing = document.getElementById('credentialsCard');
    if (existing) { existing.remove(); }

    if (!user.password) { return; }

    const card = document.createElement('div');
    card.id        = 'credentialsCard';
    card.className = 'info-card credentials-card';
    card.innerHTML =
        '<div class="info-card-title">&#128274; Your account credentials</div>' +
        '<div class="info-card-body">' +
            '<div class="info-row"><span class="info-label">Username</span>' +
                '<span class="info-value mono">' + escHtml(user.username) + '</span></div>' +
            '<div class="info-row"><span class="info-label">Password</span>' +
                '<span class="info-value mono">' + escHtml(user.password) + '</span></div>' +
            '<div class="info-row"><span class="info-label">Role</span>' +
                '<span class="info-value">' + escHtml(user.role) + '</span></div>' +
        '</div>' +
        '<div class="info-card-note">Save these details — the password will not be shown again.</div>';

    insertBeforeCalendar(card);
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
        '<div class="info-card-note">Share this ID with your caretaker so they can link their account to yours.</div>';

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
    if (!visible) { return; }

    const panel = document.createElement('div');
    panel.id        = 'sensorPanel';
    panel.className = 'sensor-panel';
    panel.innerHTML =
        '<div class="sensor-header">' +
            '<span class="sensor-title">&#127782; Live Sensor Data</span>' +
            '<span class="ws-dot disconnected" id="wsDot" title="WebSocket disconnected"></span>' +
        '</div>' +
        '<div class="sensor-grid" id="sensorGrid">' +
            '<div class="sensor-tile" id="stTemp">' +
                '<div class="sensor-icon">&#127777;</div>' +
                '<div class="sensor-val" id="svTemp">—</div>' +
                '<div class="sensor-lbl">Temperature</div>' +
            '</div>' +
            '<div class="sensor-tile" id="stHum">' +
                '<div class="sensor-icon">&#128167;</div>' +
                '<div class="sensor-val" id="svHum">—</div>' +
                '<div class="sensor-lbl">Humidity</div>' +
            '</div>' +
            '<div class="sensor-tile" id="stPres">' +
                '<div class="sensor-icon">&#127774;</div>' +
                '<div class="sensor-val" id="svPres">—</div>' +
                '<div class="sensor-lbl">Pressure</div>' +
            '</div>' +
            '<div class="sensor-tile" id="stDev">' +
                '<div class="sensor-icon">&#128225;</div>' +
                '<div class="sensor-val" id="svDev">—</div>' +
                '<div class="sensor-lbl">Device</div>' +
            '</div>' +
        '</div>' +
        '<div class="sensor-ts" id="sensorTs">Waiting for data…</div>';

    const dashBody = document.querySelector('.dash-body');
    const calSection = dashBody.querySelector('.cal-section');
    dashBody.insertBefore(panel, calSection);
}

function updateSensorUI(data) {
    const svTemp = document.getElementById('svTemp');
    const svHum  = document.getElementById('svHum');
    const svPres = document.getElementById('svPres');
    const svDev  = document.getElementById('svDev');
    const sTs    = document.getElementById('sensorTs');

    if (svTemp) { svTemp.textContent = data.temperature != null ? data.temperature.toFixed(1) + ' °C' : '—'; }
    if (svHum)  { svHum.textContent  = data.humidity    != null ? data.humidity.toFixed(1)    + ' %'  : '—'; }
    if (svPres) { svPres.textContent = data.pressure    != null ? data.pressure.toFixed(1)    + ' hPa': '—'; }
    if (svDev)  { svDev.textContent  = data.deviceId    || '—'; }

    if (sTs && data.timestamp) {
        const d = new Date(data.timestamp);
        sTs.textContent = 'Last update: ' + d.toLocaleTimeString();
    }

    ['svTemp','svHum','svPres','svDev'].forEach(function(id) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('sensor-flash');
            void el.offsetWidth;
            el.classList.add('sensor-flash');
        }
    });
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