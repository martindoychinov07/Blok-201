const aiState = {
    alerts: [],
    reminders: [],
    interval: null,
    loading: false,
    patientId: null,
};

function initAiAssistant(user) {
    aiState.patientId = aiResolvePatientId(user);
    aiBindUi();
    aiApplyRoleMode(user);
    aiLoadAll();
    aiStartLoop();
}

function cleanupAiAssistant() {
    if (aiState.interval) {
        clearInterval(aiState.interval);
        aiState.interval = null;
    }
    aiState.alerts = [];
    aiState.reminders = [];
    aiState.patientId = null;
    aiRenderAll();
}

function aiBindUi() {
    const refresh = document.getElementById('aiRefreshBtn');
    const sendText = document.getElementById('aiSendTextBtn');
    const sendAudio = document.getElementById('aiSendAudioBtn');

    if (refresh && !refresh.dataset.bound) {
        refresh.dataset.bound = '1';
        refresh.addEventListener('click', aiLoadAll);
    }

    if (sendText && !sendText.dataset.bound) {
        sendText.dataset.bound = '1';
        sendText.addEventListener('click', aiSubmitText);
    }

    if (sendAudio && !sendAudio.dataset.bound) {
        sendAudio.dataset.bound = '1';
        sendAudio.addEventListener('click', aiSubmitAudio);
    }
}

function aiApplyRoleMode(user) {
    const isStage2Patient = user && user.role === 'USER' && Number(user.dementiaStage) === 2;
    const textInput = document.getElementById('aiTextInput');
    const textBtn = document.getElementById('aiSendTextBtn');
    const audioInput = document.getElementById('aiAudioInput');
    const audioBtn = document.getElementById('aiSendAudioBtn');

    [textInput, textBtn, audioInput, audioBtn].forEach((el) => {
        if (el) {
            el.disabled = !!isStage2Patient;
        }
    });

    if (isStage2Patient) {
        aiSetStatus('View-only AI mode for Stage 2. Your custodian can send new items.');
    }
}

function aiStartLoop() {
    if (aiState.interval) {
        clearInterval(aiState.interval);
    }
    aiState.interval = setInterval(aiLoadAll, 5000);
}

async function aiLoadAll() {
    if (aiState.loading || !currentUser) {
        return;
    }
    aiState.loading = true;
    aiSetStatus('Loading AI data...');

    try {
        const patientQuery = aiState.patientId ? '&patient_id=' + encodeURIComponent(aiState.patientId) : '';
        const [alertsResp, remindersResp] = await Promise.all([
            fetch(API + '/api/ai/alerts?status=all&limit=100' + patientQuery, { credentials: 'include' }),
            fetch(API + '/api/ai/reminders?status=all&limit=120' + patientQuery, { credentials: 'include' })
        ]);

        const alertsBody = await alertsResp.json();
        const remindersBody = await remindersResp.json();

        if (!alertsResp.ok) throw new Error(alertsBody.error || 'Failed to load AI alerts');
        if (!remindersResp.ok) throw new Error(remindersBody.error || 'Failed to load AI reminders');

        aiState.alerts = Array.isArray(alertsBody.items) ? alertsBody.items : [];
        aiState.reminders = Array.isArray(remindersBody.items) ? remindersBody.items : [];

        aiSyncAppointmentsToCalendar();
        aiSetStatus('AI synced · ' + new Date().toLocaleTimeString());
        aiRenderAll();
    } catch (err) {
        aiSetStatus('AI error: ' + (err.message || err));
    } finally {
        aiState.loading = false;
    }
}

function aiRenderAll() {
    aiRenderAlerts();
    aiRenderReminders();
}

function aiRenderAlerts() {
    const el = document.getElementById('aiAlertsList');
    if (!el) return;

    if (!aiState.alerts.length) {
        el.innerHTML = '<div class="ai-empty">No alerts.</div>';
        return;
    }

    el.innerHTML = aiState.alerts.map((a) => {
        return (
            '<div class="ai-item">' +
                '<div class="ai-item-row"><strong>' + aiEsc(a.title || 'Alert') + '</strong>' +
                '<span class="ai-pill warning">' + aiEsc(a.level || 'info') + '</span></div>' +
                '<div>' + aiEsc(a.message || '-') + '</div>' +
                '<div class="ai-item-row"><span class="mono">' + aiEsc(a.status || 'active') + '</span>' +
                '<span class="mono">' + aiEsc(aiFmtDate(a.createdAt)) + '</span></div>' +
                '<div class="ai-item-row">' +
                    '<button data-ai-alert="' + aiEsc(a.alertId) + '" data-ai-alert-status="acknowledged">Ack</button>' +
                    '<button data-ai-alert="' + aiEsc(a.alertId) + '" data-ai-alert-status="dismissed">Dismiss</button>' +
                '</div>' +
            '</div>'
        );
    }).join('');

    el.querySelectorAll('[data-ai-alert]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const alertId = btn.getAttribute('data-ai-alert');
            const status = btn.getAttribute('data-ai-alert-status');
            await aiPatch('/api/ai/alerts/' + encodeURIComponent(alertId), status);
        });
    });
}

function aiRenderReminders() {
    const el = document.getElementById('aiRemindersList');
    if (!el) return;

    if (!aiState.reminders.length) {
        el.innerHTML = '<div class="ai-empty">No reminders.</div>';
        return;
    }

    el.innerHTML = aiState.reminders.map((r) => {
        return (
            '<div class="ai-item">' +
                '<div class="ai-item-row"><strong>' + aiEsc(r.type || 'task') + '</strong>' +
                '<span class="ai-pill">' + aiEsc(r.status || 'active') + '</span></div>' +
                '<div>' + aiEsc(r.text || '-') + '</div>' +
                '<div class="mono">' + aiEsc(r.timeText || 'no-time') + '</div>' +
                '<div class="ai-item-row">' +
                    '<button data-ai-rem="' + aiEsc(r.reminderId) + '" data-ai-rem-status="done">Done</button>' +
                    '<button data-ai-rem="' + aiEsc(r.reminderId) + '" data-ai-rem-status="cancelled">Cancel</button>' +
                '</div>' +
            '</div>'
        );
    }).join('');

    el.querySelectorAll('[data-ai-rem]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const reminderId = btn.getAttribute('data-ai-rem');
            const status = btn.getAttribute('data-ai-rem-status');
            await aiPatch('/api/ai/reminders/' + encodeURIComponent(reminderId), status);
        });
    });
}

function aiSyncAppointmentsToCalendar() {
    if (!currentUser) {
        return;
    }

    const events = loadEvents();
    Object.keys(events).forEach((key) => {
        const dayItems = Array.isArray(events[key]) ? events[key] : [];
        const kept = dayItems.filter((item) => !item || item.aiSync !== true);
        if (kept.length > 0) {
            events[key] = kept;
        } else {
            delete events[key];
        }
    });

    const activeAppointmentReminders = aiState.reminders.filter((item) => {
        if (!item) return false;
        const status = String(item.status || 'active').toLowerCase();
        if (status === 'cancelled' || status === 'stale') return false;
        return aiIsAppointmentReminder(item);
    });

    const dedup = new Set();
    activeAppointmentReminders.forEach((item) => {
        const parsed = aiParseCalendarSchedule(aiScheduleSource(item));
        if (!parsed || !parsed.date) {
            return;
        }

        const dayKey = dateKey(parsed.date);
        const text = String(item.text || 'Appointment').trim() || 'Appointment';
        const time = parsed.time || '';
        const uniqueKey = dayKey + '|' + time + '|' + text.toLowerCase();
        if (dedup.has(uniqueKey)) {
            return;
        }
        dedup.add(uniqueKey);

        if (!events[dayKey]) {
            events[dayKey] = [];
        }
        events[dayKey].push({
            text,
            time,
            aiSync: true,
            aiReminderId: item.reminderId || null
        });
    });

    saveEvents(events);
    if (typeof renderCalendar === 'function') {
        renderCalendar();
    }
}

function aiIsAppointmentReminder(item) {
    const type = String((item && item.type) || '').toLowerCase();
    if (type === 'appointment' || type === 'visit') {
        return true;
    }

    const text = String((item && item.text) || '').toLowerCase();
    return text.includes('appointment')
        || text.includes('doctor')
        || text.includes('visit')
        || text.includes('преглед')
        || text.includes('доктор')
        || text.includes('лекар');
}

function aiScheduleSource(item) {
    const timeText = String((item && (item.timeText || item.time_text)) || '').trim();
    const text = String((item && item.text) || '').trim();
    return [timeText, text].filter(Boolean).join(' ');
}

function aiParseCalendarSchedule(rawTimeText) {
    const raw = String(rawTimeText || '').trim();
    if (!raw) {
        return null;
    }

    const lower = raw
        .toLowerCase()
        .replace(/,/g, ' ')
        .replace(/\b(\d{1,2})(st|nd|rd|th)\b/g, '$1')
        .replace(/\b(\d{1,2})-?(ти|ри|ви|ми)\b/g, '$1')
        .replace(/\s+/g, ' ')
        .trim();
    let date = null;

    const explicitDate = lower.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
    if (explicitDate) {
        date = new Date(Number(explicitDate[1]), Number(explicitDate[2]) - 1, Number(explicitDate[3]));
    }

    if (!date) {
        const dotOrSlash = lower.match(/\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b/);
        if (dotOrSlash) {
            const day = Number(dotOrSlash[1]);
            const month = Number(dotOrSlash[2]);
            const yearRaw = dotOrSlash[3] ? Number(dotOrSlash[3]) : null;
            const year = yearRaw == null ? null : (yearRaw < 100 ? 2000 + yearRaw : yearRaw);
            date = aiBuildFutureAwareDate(day, month - 1, year);
        }
    }

    if (!date) {
        const monthWords = {
            january: 0, jan: 0, януари: 0,
            february: 1, feb: 1, февруари: 1,
            march: 2, mar: 2, март: 2,
            april: 3, apr: 3, април: 3,
            may: 4, май: 4,
            june: 5, jun: 5, юни: 5,
            july: 6, jul: 6, юли: 6,
            august: 7, aug: 7, август: 7,
            september: 8, sept: 8, sep: 8, септември: 8,
            october: 9, oct: 9, октомври: 9,
            november: 10, nov: 10, ноември: 10,
            december: 11, dec: 11, декември: 11
        };

        const wordsMatch = lower.match(/\b(\d{1,2})\s+([a-zа-я]+)(?:\s+(\d{4}))?\b/i);
        if (wordsMatch) {
            const day = Number(wordsMatch[1]);
            const monthName = wordsMatch[2].toLowerCase();
            const monthIndex = monthWords[monthName];
            if (monthIndex != null) {
                const year = wordsMatch[3] ? Number(wordsMatch[3]) : null;
                date = aiBuildFutureAwareDate(day, monthIndex, year);
            }
        }
    }

    if (!date) {
        const dayOnly = lower.match(/\b(\d{1,2})\b/);
        if (dayOnly) {
            const day = Number(dayOnly[1]);
            date = aiBuildNearestDayOnlyDate(day);
        }
    }

    if (!date) {
        const monthWords = {
            january: 0, jan: 0, януари: 0,
            february: 1, feb: 1, февруари: 1,
            march: 2, mar: 2, март: 2,
            april: 3, apr: 3, април: 3,
            may: 4, май: 4,
            june: 5, jun: 5, юни: 5,
            july: 6, jul: 6, юли: 6,
            august: 7, aug: 7, август: 7,
            september: 8, sept: 8, sep: 8, септември: 8,
            october: 9, oct: 9, октомври: 9,
            november: 10, nov: 10, ноември: 10,
            december: 11, dec: 11, декември: 11
        };

        const monthFirst = lower.match(/\b([a-zа-я]+)\s+(\d{1,2})(?:\s+(\d{4}))?\b/i);
        if (monthFirst) {
            const monthName = monthFirst[1].toLowerCase();
            const monthIndex = monthWords[monthName];
            if (monthIndex != null) {
                const day = Number(monthFirst[2]);
                const year = monthFirst[3] ? Number(monthFirst[3]) : null;
                date = aiBuildFutureAwareDate(day, monthIndex, year);
            }
        }
    }

    if (!date) {
        const now = new Date();
        if (lower.includes('tomorrow') || lower.includes('утре')) {
            date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        } else if (lower.includes('day after tomorrow') || lower.includes('вдругиден') || lower.includes('ден след утре')) {
            date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 2);
        } else if (lower.includes('today') || lower.includes('днес')) {
            date = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        }
    }

    if (!date) {
        const weekMap = {
            sunday: 0,
            monday: 1,
            tuesday: 2,
            wednesday: 3,
            thursday: 4,
            friday: 5,
            saturday: 6,
            неделя: 0,
            понеделник: 1,
            вторник: 2,
            сряда: 3,
            четвъртък: 4,
            петък: 5,
            събота: 6
        };
        for (const [name, index] of Object.entries(weekMap)) {
            if (lower.includes(name)) {
                date = aiNextWeekday(index);
                break;
            }
        }
    }

    if (!date) {
        return null;
    }

    const time = aiExtractTime(lower);

    return { date, time };
}

function aiExtractTime(lower) {
    const explicitBg = lower.match(/\bот\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|ч|ч\.|часа)?\b/);
    if (explicitBg) {
        const maybe = aiNormalizeTime(explicitBg[1], explicitBg[2], explicitBg[3]);
        if (maybe) {
            return maybe;
        }
    }

    const all = [...lower.matchAll(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b/g)];
    for (const m of all) {
        const maybe = aiNormalizeTime(m[1], m[2], m[3]);
        if (maybe) {
            return maybe;
        }
    }
    return '';
}

function aiNormalizeTime(hourRaw, minuteRaw, suffixRaw) {
    let hour = Number(hourRaw);
    const minute = Number(minuteRaw || '0');
    const suffix = String(suffixRaw || '').toLowerCase();

    if (suffix === 'pm' && hour < 12) hour += 12;
    if (suffix === 'am' && hour === 12) hour = 0;

    if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
        return '';
    }
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
        return '';
    }

    return String(hour).padStart(2, '0') + ':' + String(minute).padStart(2, '0');
}

function aiNextWeekday(targetDay) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const delta = (targetDay - start.getDay() + 7) % 7;
    return new Date(start.getFullYear(), start.getMonth(), start.getDate() + delta);
}

function aiBuildFutureAwareDate(day, monthIndex, yearOrNull) {
    if (!Number.isInteger(day) || !Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11 || day < 1 || day > 31) {
        return null;
    }

    const today = new Date();
    const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    let year = yearOrNull != null ? yearOrNull : today.getFullYear();
    let candidate = new Date(year, monthIndex, day);

    if (candidate.getMonth() !== monthIndex || candidate.getDate() !== day) {
        return null;
    }

    if (yearOrNull == null && candidate < startToday) {
        candidate = new Date(year + 1, monthIndex, day);
        if (candidate.getMonth() !== monthIndex || candidate.getDate() !== day) {
            return null;
        }
    }

    return candidate;
}

function aiBuildNearestDayOnlyDate(day) {
    if (!Number.isInteger(day) || day < 1 || day > 31) {
        return null;
    }

    const now = new Date();
    const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    let candidate = new Date(startToday.getFullYear(), startToday.getMonth(), day);
    if (candidate.getDate() !== day) {
        return null;
    }

    if (candidate < startToday) {
        candidate = new Date(startToday.getFullYear(), startToday.getMonth() + 1, day);
        if (candidate.getDate() !== day) {
            return null;
        }
    }

    return candidate;
}

async function aiPatch(url, status) {
    try {
        const res = await fetch(API + url, {
            method: 'PATCH',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });

        const body = await res.json();
        if (!res.ok) {
            throw new Error(body.error || 'Request failed');
        }
        await aiLoadAll();
    } catch (err) {
        aiSetStatus('Update failed: ' + (err.message || err));
    }
}

async function aiSubmitText() {
    const input = document.getElementById('aiTextInput');
    const msg = document.getElementById('aiTextMsg');
    if (!input || !msg) return;

    const text = input.value.trim();
    if (!text) {
        msg.textContent = 'Enter text first.';
        return;
    }

    msg.textContent = 'Sending...';
    try {
        const res = await fetch(API + '/api/embedded/text', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: aiState.patientId, text })
        });
        const body = await res.json();
        if (!res.ok) {
            const details = body.details ? (' · ' + body.details) : '';
            throw new Error((body.error || 'Analyze text failed') + details);
        }

        input.value = '';
        msg.textContent = 'Accepted ✓';
        await aiLoadAll();
    } catch (err) {
        msg.textContent = 'Error: ' + (err.message || err);
    }
}

async function aiSubmitAudio() {
    const input = document.getElementById('aiAudioInput');
    const msg = document.getElementById('aiAudioMsg');
    if (!input || !msg) return;

    const file = input.files && input.files[0];
    if (!file) {
        msg.textContent = 'Select WAV file.';
        return;
    }

    msg.textContent = 'Uploading...';
    try {
        const formData = new FormData();
        formData.append('patient_id', aiState.patientId || 'p_001');
        formData.append('audio', file);

        const res = await fetch(API + '/api/embedded/audio', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        const body = await res.json();
        if (!res.ok) {
            const details = body.details ? (' · ' + body.details) : '';
            throw new Error((body.error || 'Transcribe failed') + details);
        }

        msg.textContent = 'Accepted ✓';
        input.value = '';
        await aiLoadAll();
    } catch (err) {
        msg.textContent = 'Error: ' + (err.message || err);
    }
}

function aiResolvePatientId(user) {
    if (!user) return 'p_001';
    if (user.role === 'CAREGIVER' && user.patientId) {
        return String(user.patientId);
    }
    if (user.id) {
        return String(user.id);
    }
    return 'p_001';
}

function aiSetStatus(text) {
    const el = document.getElementById('aiStatus');
    if (el) {
        el.textContent = text;
    }
}

function aiFmtDate(value) {
    if (!value) return '-';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}

function aiEsc(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
