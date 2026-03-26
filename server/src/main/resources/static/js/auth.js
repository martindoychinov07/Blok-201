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
        m.className  = 'msg';
        m.textContent = '';
    });
}

function showMsg(id, text, type) {
    const el      = document.getElementById(id);
    el.textContent = text;
    el.className   = 'msg ' + type + ' show';
}

function onRoleChange() {
    const role = document.getElementById('sRole').value;
    document.getElementById('stageWrap').classList.toggle('visible',  role === 'USER');
    document.getElementById('patientWrap').classList.toggle('visible', role === 'CARETAKER');
}

function selectStage(n) {
    selectedStage = n;
    document.getElementById('sc1').className = 'stage-card' + (n === 1 ? ' sel1' : '');
    document.getElementById('sc2').className = 'stage-card' + (n === 2 ? ' sel2' : '');
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

        const data = await res.json();

        if (!res.ok) {
            showMsg('lMsg', data.error || 'Login failed. Please try again.', 'err');
            return;
        }

        enterDashboard(data);
    } catch (err) {
        console.error('Login request failed:', err);

        if (!navigator.onLine) {
            showMsg('lMsg', 'You appear to be offline. Please check your connection and try again.', 'err');
        } else {
            showMsg('lMsg', 'Could not reach the server. Please try again in a moment.', 'err');
        }
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

    if (role === 'CARETAKER' && !patientId) {
        showMsg('sMsg', 'Patient UUID is required for caretaker accounts.', 'err');
        return;
    }

    const body = {
        username,
        password,
        role,
        fullName: fullName || null
    };

    if (role === 'USER') {
        body.dementiaStage = selectedStage;
    }

    if (role === 'CARETAKER') {
        body.patientId = patientId;
    }

    btn.disabled    = true;
    btn.textContent = 'Creating account…';

    try {
        const res = await fetch(API + '/api/auth/signup', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await res.json();

        if (!res.ok) {
            showMsg('sMsg', data.error || 'Registration failed. Please try again.', 'err');
            return;
        }

        showMsg('sMsg', 'Account created. Signing you in…', 'ok');
        setTimeout(function () {
            enterDashboard(data);
        }, 800);
    } catch (err) {
        console.error('Signup request failed:', err);

        if (!navigator.onLine) {
            showMsg('sMsg', 'You appear to be offline. Please check your connection and try again.', 'err');
        } else {
            showMsg('sMsg', 'Could not reach the server. Please try again in a moment.', 'err');
        }
    } finally {
        btn.disabled    = false;
        btn.textContent = 'Create Account';
    }
}

async function doLogout() {
    stopReminderLoop();

    try {
        await fetch(API + '/api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });
    } catch (err) {
        console.warn('Logout request failed, clearing session locally anyway:', err);
    }

    currentUser = null;

    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('authPage').style.display  = 'flex';

    ['lUser', 'lPass', 'sName', 'sUser', 'sPass', 'sPatientId'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) {
            el.value = '';
        }
    });

    document.getElementById('sRole').value = '';
    selectedStage = null;
    onRoleChange();
    selectStage(0);
    clearMsgs();
    switchTab('login');
}