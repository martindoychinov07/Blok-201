function checkNotifPermission() {
    if (!('Notification' in window)) {
        return;
    }

    const bar = document.getElementById('notifBar');
    bar.classList.toggle('visible', Notification.permission === 'default');
}

function requestNotifPermission() {
    if (!('Notification' in window)) {
        console.warn('This browser does not support desktop notifications.');
        return;
    }

    Notification.requestPermission()
        .then(function (permission) {
            document.getElementById('notifBar').classList.remove('visible');

            if (permission === 'denied') {
                console.warn('Notification permission denied by the user. Reminders will show as in-app toasts only.');
            }
        })
        .catch(function (err) {
            console.error('Failed to request notification permission:', err);
        });
}

function startReminderLoop() {
    stopReminderLoop();
    notifInterval = setInterval(checkReminders, 30000);
    checkReminders();
}

function stopReminderLoop() {
    if (notifInterval) {
        clearInterval(notifInterval);
        notifInterval = null;
    }
}

function checkReminders() {
    try {
        const now      = new Date();
        const key      = dateKey(now);
        const events   = loadEvents();
        const todayEvs = events[key] || [];
        const hh       = String(now.getHours()).padStart(2, '0');
        const mm       = String(now.getMinutes()).padStart(2, '0');
        const nowStr   = hh + ':' + mm;

        todayEvs.forEach(function (ev, idx) {
            if (!ev.time) {
                return;
            }

            const fireId = key + '_' + idx + '_' + ev.time;

            if (firedToday.has(fireId)) {
                return;
            }

            if (ev.time === nowStr) {
                firedToday.add(fireId);
                fireReminder(ev.text, ev.time);
            }
        });
    } catch (err) {
        console.error('Error while checking reminders:', err);
    }
}

function fireReminder(text, time) {
    if ('Notification' in window && Notification.permission === 'granted') {
        try {
            new Notification('DementiaAid reminder', {
                body: text,
                icon: ''
            });
        } catch (err) {
            console.error('Failed to show browser notification:', err);
        }
    }

    showToast(text, time);
}

function showToast(text, time) {
    try {
        const container = document.getElementById('toastContainer');
        const toast     = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML =
            '<div class="toast-title">Reminder</div>' +
            '<div>' + text + (time ? ' &mdash; ' + formatTime(time) : '') + '</div>';

        container.appendChild(toast);

        setTimeout(function () {
            toast.classList.add('fade-out');
            setTimeout(function () {
                toast.remove();
            }, 400);
        }, 7000);
    } catch (err) {
        console.error('Failed to display toast notification:', err);
    }
}