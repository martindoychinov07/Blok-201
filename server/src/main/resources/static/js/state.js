const API = '';

const MONTHS = [
    'January', 'February', 'March', 'April',
    'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December'
];

let currentUser   = null;
let selectedStage = null;
let calYear       = null;
let calMonth      = null;
let calSelected   = null;
let notifInterval = null;
let firedToday    = new Set();

let stompClient   = null;
let sensorSub     = null;

function lsKey() {
    if (!currentUser) {
        return 'daid_cal_anon';
    }

    if (currentUser.role === 'CAREGIVER' && currentUser.patientId) {
        return 'daid_cal_' + currentUser.patientId;
    }

    return 'daid_cal_' + (currentUser.id || 'anon');
}

function loadEvents() {
    try {
        const raw = localStorage.getItem(lsKey());
        return JSON.parse(raw) || {};
    } catch (err) {
        console.error('Failed to load events from localStorage:', err);
        return {};
    }
}

function saveEvents(events) {
    try {
        localStorage.setItem(lsKey(), JSON.stringify(events));
    } catch (err) {
        console.error('Failed to save events to localStorage:', err);
    }
}

function dateKey(d) {
    const year  = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day   = String(d.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
}

function sameDay(a, b) {
    return a.getFullYear() === b.getFullYear()
        && a.getMonth()    === b.getMonth()
        && a.getDate()     === b.getDate();
}

function formatTime(t) {
    if (!t) { return ''; }
    const parts = t.split(':').map(Number);
    const h     = parts[0];
    const m     = parts[1];
    const ampm  = h >= 12 ? 'PM' : 'AM';
    const h12   = h % 12 || 12;
    return h12 + ':' + String(m).padStart(2, '0') + ' ' + ampm;
}