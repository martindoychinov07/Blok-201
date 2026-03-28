function switchTab(tab) {
    const isLogin = tab === 'login';

    document.querySelectorAll('.tab').forEach(function (t, i) {
        t.classList.toggle('active', isLogin ? i === 0 : i === 1);
    });

    document.getElementById('loginSection').classList.toggle('active', isLogin);
    document.getElementById('signupSection').classList.toggle('active', !isLogin);

    clearMsgs();
}

function clearMsgs() {
    document.querySelectorAll('.msg').forEach(function (m) {
        m.className   = 'msg';
        m.textContent = '';
        m.style.display = 'none';
    });
}

function showMsg(id, text, type) {
    const el      = document.getElementById(id);
    if (!el) {
        alert(text);
        return;
    }
    el.textContent = text;
    el.className   = 'msg ' + type + ' show';
    el.style.display = 'block';
    el.style.marginTop = '10px';
    el.style.fontSize = '.84rem';
    el.style.lineHeight = '1.4';
    if (type === 'err') {
        el.style.color = '#b33939';
    } else if (type === 'ok') {
        el.style.color = '#1f7a4a';
    } else {
        el.style.color = '#5f697f';
    }
}

function onRoleChange() {
    const role = document.getElementById('sRole').value;
    document.getElementById('stageWrap').classList.toggle('visible',   role === 'USER');
    document.getElementById('patientWrap').classList.toggle('visible',  role === 'CAREGIVER');
}

function selectStage(n) {
    selectedStage = n;
    document.getElementById('sc1').className = 'stage-card' + (n === 1 ? ' sel1' : '');
    document.getElementById('sc2').className = 'stage-card' + (n === 2 ? ' sel2' : '');
}

async function parseApiBody(res) {
    const text = await res.text();
    if (!text) {
        return {};
    }
    try {
        return JSON.parse(text);
    } catch (_err) {
        return { error: text };
    }
}

function looksLikeUuid(value) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function doLogin(btn) {
    const username = document.getElementById('lUser').value.trim();
    const password = document.getElementById('lPass').value;

    if (!username || !password) {
        showMsg('lMsg', 'Please fill in all fields.', 'err');
        return;
    }

    btn.disabled    = true;
    btn.textContent = 'Signing in…';

    try {
        const res = await fetch(API + '/api/auth/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await parseApiBody(res);

        if (!res.ok) {
            const message = data.error || data.message || ('Login failed (' + res.status + ').');
            console.warn('Login failed response:', res.status, data);
            showMsg('lMsg', message, 'err');
            return;
        }

        enterDashboard(data);
    } catch (err) {
        console.error('Login request failed:', err);
        showMsg('lMsg',
            navigator.onLine
                ? 'Could not reach the server. Please try again in a moment.'
                : 'You appear to be offline. Please check your connection.',
            'err');
    } finally {
        btn.disabled    = false;
        btn.textContent = 'Sign In';
    }
}

async function doSignup(btn) {
    const fullName  = document.getElementById('sName').value.trim();
    const username  = document.getElementById('sUser').value.trim();
    const password  = document.getElementById('sPass').value;
    const role      = document.getElementById('sRole').value;
    const patientId = document.getElementById('sPatientId').value.trim();

    if (!username || !password || !role) {
        showMsg('sMsg', 'Please fill in all required fields.', 'err');
        return;
    }

    if (role === 'USER' && !selectedStage) {
        showMsg('sMsg', 'Please select your dementia stage.', 'err');
        return;
    }

    if (role === 'CAREGIVER' && !patientId) {
        showMsg('sMsg', 'Patient UUID is required for custodian accounts.', 'err');
        return;
    }

    if (role === 'CAREGIVER' && patientId && !looksLikeUuid(patientId)) {
        showMsg('sMsg', 'Patient UUID format is invalid.', 'err');
        return;
    }

    const body = { username, password, role, fullName: fullName || null };

    if (role === 'USER')      { body.dementiaStage = selectedStage; }
    if (role === 'CAREGIVER') { body.patientId     = patientId; }

    btn.disabled    = true;
    btn.textContent = 'Creating account…';

    try {
        const res = await fetch(API + '/api/auth/signup', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await parseApiBody(res);

        if (!res.ok) {
            const message = data.error || data.message || ('Registration failed (' + res.status + ').');
            console.warn('Signup failed response:', res.status, data);
            showMsg('sMsg', message, 'err');
            return;
        }

        showMsg('sMsg', 'Account created! Entering dashboard…', 'ok');
        setTimeout(function () { enterDashboard(data); }, 600);
    } catch (err) {
        console.error('Signup request failed:', err);
        showMsg('sMsg',
            navigator.onLine
                ? 'Could not reach the server. Please try again in a moment.'
                : 'You appear to be offline. Please check your connection.',
            'err');
    } finally {
        btn.disabled    = false;
        btn.textContent = 'Create Account';
    }
}

async function doLogout() {
    stopReminderLoop();
    disconnectWebSocket();
    if (typeof cleanupAiAssistant === 'function') {
        cleanupAiAssistant();
    }

    try {
        await fetch(API + '/api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });
    } catch (err) {
        console.warn('Logout request failed; clearing session locally:', err);
    }

    currentUser = null;

    ['credentialsCard', 'userIdCard', 'sensorPanel'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) { el.remove(); }
    });

    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('authPage').style.display  = 'flex';

    ['lUser','lPass','sName','sUser','sPass','sPatientId'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) { el.value = ''; }
    });

    document.getElementById('sRole').value = '';
    selectedStage = null;
    onRoleChange();
    selectStage(0);
    clearMsgs();
    switchTab('login');
}
