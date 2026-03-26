function enterDashboard(user) {
    currentUser = user;

    document.getElementById('authPage').style.display  = 'none';
    document.getElementById('dashboard').style.display = 'block';

    const isCaretaker = user.role === 'CARETAKER';
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

    document.getElementById('dName').textContent = user.fullName || user.username;

    const first = user.fullName ? user.fullName.split(' ')[0] : user.username;

    document.getElementById('dGreeting').textContent = isCaretaker
        ? 'Welcome, ' + first
        : 'Good to see you, ' + first;

    if (isCaretaker) {
        document.getElementById('dSub').textContent = 'You are in the caretaker portal.';
    } else if (isStage2) {
        document.getElementById('dSub').textContent = 'Your caretaker manages some features on your behalf.';
    } else {
        document.getElementById('dSub').textContent = 'You have full access to all DementiaAid features.';
    }

    document.getElementById('dashHint').textContent =
        'Use the calendar below to write and schedule your own tasks and reminders. ' +
        'Add a time to a task and DementiaAid will notify you when that moment arrives.';

    checkNotifPermission();

    const today = new Date();
    firedToday  = new Set();
    calYear     = today.getFullYear();
    calMonth    = today.getMonth();
    calSelected = new Date(today);

    renderCalendar();
    startReminderLoop();
}