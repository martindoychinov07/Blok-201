function calMove(dir) {
    calMonth += dir;

    if (calMonth > 11) {
        calMonth = 0;
        calYear++;
    }

    if (calMonth < 0) {
        calMonth = 11;
        calYear--;
    }

    renderCalendar();
}

function renderCalendar() {
    const today    = new Date();
    const first    = new Date(calYear, calMonth, 1);
    const last     = new Date(calYear, calMonth + 1, 0);
    const startDow = first.getDay();
    const events   = loadEvents();

    document.getElementById('calMonthName').textContent  = MONTHS[calMonth];
    document.getElementById('calYear').textContent       = calYear;
    document.getElementById('calTodayLabel').textContent =
        'Today is ' + MONTHS[today.getMonth()] + ' ' + today.getDate() + ', ' + today.getFullYear();

    const grid = document.getElementById('calGrid');
    grid.innerHTML = '';

    for (let i = 0; i < startDow; i++) {
        const empty = document.createElement('div');
        empty.className = 'cal-day empty';
        grid.appendChild(empty);
    }

    for (let d = 1; d <= last.getDate(); d++) {
        const date = new Date(calYear, calMonth, d);
        const key  = dateKey(date);
        const cell = document.createElement('div');

        const isToday    = sameDay(date, today);
        const isPast     = !isToday && date < today;
        const isSelected = calSelected && sameDay(date, calSelected);
        const hasEvent   = events[key] && events[key].length > 0;

        let cls = 'cal-day';

        if (isToday) {
            cls += ' today';
        } else if (isPast) {
            cls += ' past';
        } else if (isSelected) {
            cls += ' selected';
        }

        if (hasEvent) {
            cls += ' has-event';
        }

        cell.className   = cls;
        cell.textContent = d;

        if (!isPast) {
            cell.onclick = function () {
                selectDate(date);
            };
        }

        grid.appendChild(cell);
    }

    renderEvents();
}

function selectDate(date) {
    calSelected = date;
    renderCalendar();
}

function renderEvents() {
    if (!calSelected) {
        return;
    }

    const key    = dateKey(calSelected);
    const events = loadEvents();
    const list   = events[key] || [];
    const label  = MONTHS[calSelected.getMonth()] + ' ' + calSelected.getDate() + ', ' + calSelected.getFullYear();

    document.getElementById('calEventsDate').textContent = label;

    const el = document.getElementById('calEventsList');
    el.innerHTML = '';

    const today  = new Date();
    const isPast = !sameDay(calSelected, today) && calSelected < today;

    document.getElementById('calAdd').classList.toggle('hidden', isPast);
    document.getElementById('calPastNotice').style.display = isPast ? 'block' : 'none';

    if (list.length === 0) {
        const empty = document.createElement('div');
        empty.className   = 'no-events';
        empty.textContent = 'No tasks for this day.';
        el.appendChild(empty);
        return;
    }

    list.forEach(function (ev, idx) {
        const timeHtml = ev.time
            ? '<br/><span class="event-time">' + formatTime(ev.time) + '</span>'
            : '';

        const row = document.createElement('div');
        row.className = 'event-item';
        row.innerHTML =
            '<div class="event-left">'                                               +
                '<div class="event-dot"></div>'                                      +
                '<div class="event-text">' + ev.text + timeHtml + '</div>'           +
            '</div>'                                                                  +
            '<button class="event-del" title="Remove"'                               +
                ' onclick="removeEvent(\'' + key + '\', ' + idx + ')">&#215;</button>';

        el.appendChild(row);
    });
}

function addEvent() {
    const textInput = document.getElementById('calInput');
    const timeInput = document.getElementById('calTime');
    const text      = textInput.value.trim();

    if (!text || !calSelected) {
        return;
    }

    const today  = new Date();
    const isPast = !sameDay(calSelected, today) && calSelected < today;

    if (isPast) {
        return;
    }

    const key    = dateKey(calSelected);
    const events = loadEvents();

    if (!events[key]) {
        events[key] = [];
    }

    events[key].push({
        text: text,
        time: timeInput.value || ''
    });

    saveEvents(events);

    textInput.value = '';
    timeInput.value = '';

    renderCalendar();
}

function removeEvent(key, idx) {
    const events = loadEvents();

    if (!events[key]) {
        return;
    }

    events[key].splice(idx, 1);

    if (events[key].length === 0) {
        delete events[key];
    }

    saveEvents(events);
    renderCalendar();
}