// Telegram Web App API
const tg = window.Telegram?.WebApp;

// Application State
const appState = {
    service: null,
    master: null,
    date: null,
    time: null,
    services: {
        "Женская стрижка": 500,
        "Мужская стрижка": 400,
        "Окрашивание": 1500,
        "Бритье": 300,
        "Укладка": 600
    },
    masters: {
        "Дмитрий": { specialization: ["стрижка", "бритье", "окрашивание"] },
        "Александр": { specialization: ["стрижка", "укладка"] }
    },
    bookedSlots: {
        "2025-11-18": ["09:00", "10:00", "14:00"],
        "2025-11-19": ["11:00", "15:00"]
    }
};

// Initialize Telegram Web App
function initTelegram() {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.MainButton.color = "#A855F7";
    }
}

// DOM Elements
const elements = {
    servicesList: document.getElementById('services-list'),
    mastersList: document.getElementById('masters-list'),
    calendar: document.getElementById('calendar'),
    timeSlots: document.getElementById('time-slots'),
    confirmationDetails: document.getElementById('confirmation-details'),
    successText: document.getElementById('success-text'),
    backBtn: document.getElementById('back-btn'),
    resetBtn: document.getElementById('reset-btn'),
    confirmBtn: document.getElementById('confirm-btn'),
    cancelBtn: document.getElementById('cancel-btn'),
    newBookingBtn: document.getElementById('new-booking-btn')
};

// Initialize App
function init() {
    initTelegram();
    loadServices();
    setupEventListeners();
}

// Setup Event Listeners
function setupEventListeners() {
    elements.backBtn.addEventListener('click', goBack);
    elements.resetBtn.addEventListener('click', resetBooking);
    elements.confirmBtn.addEventListener('click', confirmBooking);
    elements.cancelBtn.addEventListener('click', goBack);
    elements.newBookingBtn.addEventListener('click', resetBooking);
}

// Load Services
function loadServices() {
    elements.servicesList.innerHTML = '';
    Object.entries(appState.services).forEach(([name, price]) => {
        const div = document.createElement('div');
        div.className = 'service-item';
        if (appState.service === name) div.classList.add('selected');
        div.innerHTML = `
            <span class="service-name">✂️ ${name}</span>
            <span class="service-price">${price}₽</span>
        `;
        div.addEventListener('click', () => selectService(name));
        elements.servicesList.appendChild(div);
    });
}

// Select Service
function selectService(service) {
    appState.service = service;
    loadServices();
    showStep('step-masters');
    loadMasters();
}

// Load Masters
function loadMasters() {
    elements.mastersList.innerHTML = '';
    Object.entries(appState.masters).forEach(([name, info]) => {
        const div = document.createElement('div');
        div.className = 'master-item';
        if (appState.master === name) div.classList.add('selected');
        const specs = info.specialization.join(', ');
        div.innerHTML = `
            <span class="master-name">👨‍💼 ${name}</span>
            <span class="master-spec">${specs}</span>
        `;
        div.addEventListener('click', () => selectMaster(name));
        elements.mastersList.appendChild(div);
    });
}

// Select Master
function selectMaster(master) {
    appState.master = master;
    loadMasters();
    showStep('step-calendar');
    loadCalendar();
}

// Load Calendar
function loadCalendar() {
    elements.calendar.innerHTML = '';
    
    // Get next 14 days
    for (let i = 0; i < 14; i++) {
        const date = new Date();
        date.setDate(date.getDate() + i);
        
        // Skip weekends
        if (date.getDay() === 0 || date.getDay() === 6) continue;
        
        const dateStr = date.toISOString().split('T')[0];
        const dayName = date.toLocaleDateString('ru-RU', { weekday: 'short' });
        const dayNum = date.getDate();
        
        const div = document.createElement('div');
        div.className = 'calendar-day';
        if (appState.date === dateStr) div.classList.add('selected');
        
        div.innerHTML = `
            <span class="day-name">${dayName}</span>
            <span class="day-date">${dayNum}</span>
        `;
        
        div.addEventListener('click', () => selectDate(dateStr));
        elements.calendar.appendChild(div);
    }
}

// Select Date
function selectDate(date) {
    appState.date = date;
    loadCalendar();
    showStep('step-time');
    loadTimeSlots();
}

// Load Time Slots
function loadTimeSlots() {
    elements.timeSlots.innerHTML = '';
    
    const workStart = 8;
    const workEnd = 18;
    const lunchStart = 13;
    const lunchEnd = 14;
    
    // Get booked slots for this date
    const booked = appState.bookedSlots[appState.date] || [];
    
    for (let hour = workStart; hour < workEnd; hour++) {
        for (let min of [0, 30]) {
            const timeStr = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
            
            // Skip lunch
            if (hour >= lunchStart && hour < lunchEnd) continue;
            
            // Skip booked
            if (booked.includes(timeStr)) continue;
            
            const div = document.createElement('div');
            div.className = 'time-item';
            if (appState.time === timeStr) div.classList.add('selected');
            div.textContent = `🕐 ${timeStr}`;
            div.addEventListener('click', () => selectTime(timeStr));
            elements.timeSlots.appendChild(div);
        }
    }
}

// Select Time
function selectTime(time) {
    appState.time = time;
    loadTimeSlots();
    showStep('step-confirmation');
    loadConfirmation();
}

// Load Confirmation
function loadConfirmation() {
    const price = appState.services[appState.service];
    
    elements.confirmationDetails.innerHTML = `
        <div class="confirmation-item">
            <span class="confirmation-label">✂️ Услуга:</span>
            <span class="confirmation-value">${appState.service}</span>
        </div>
        <div class="confirmation-item">
            <span class="confirmation-label">👨‍💼 Мастер:</span>
            <span class="confirmation-value">${appState.master}</span>
        </div>
        <div class="confirmation-item">
            <span class="confirmation-label">📅 Дата:</span>
            <span class="confirmation-value">${appState.date}</span>
        </div>
        <div class="confirmation-item">
            <span class="confirmation-label">🕐 Время:</span>
            <span class="confirmation-value">${appState.time}</span>
        </div>
        <div class="confirmation-item">
            <span class="confirmation-label">💰 Цена:</span>
            <span class="confirmation-value">${price}₽</span>
        </div>
    `;
}

// Confirm Booking
function confirmBooking() {
    const bookingData = {
        service: appState.service,
        master: appState.master,
        date: appState.date,
        time: appState.time,
        price: appState.services[appState.service]
    };
    
    // Send data back to Telegram Bot
    if (tg && tg.sendData) {
        tg.sendData(JSON.stringify(bookingData));
    }
    
    // Show success
    showStep('step-success');
    elements.successText.innerHTML = `
        <strong>Запись успешно создана!</strong><br>
        ${appState.service} с ${appState.master}<br>
        ${appState.date} в ${appState.time}
    `;
}

// Go Back
function goBack() {
    if (document.getElementById('step-services').style.display !== 'none' &&
        !document.getElementById('step-services').classList.contains('hidden')) {
        return;
    }
    
    if (isStepVisible('step-success')) {
        resetBooking();
    } else if (isStepVisible('step-confirmation')) {
        showStep('step-time');
    } else if (isStepVisible('step-time')) {
        showStep('step-calendar');
    } else if (isStepVisible('step-calendar')) {
        showStep('step-masters');
    } else if (isStepVisible('step-masters')) {
        showStep('step-services');
    }
}

// Reset Booking
function resetBooking() {
    appState.service = null;
    appState.master = null;
    appState.date = null;
    appState.time = null;
    
    showStep('step-services');
    loadServices();
}

// Show Step
function showStep(stepId) {
    document.querySelectorAll('.step').forEach(step => {
        step.classList.add('hidden');
    });
    
    const step = document.getElementById(stepId);
    step.classList.remove('hidden');
}

// Check if step is visible
function isStepVisible(stepId) {
    return !document.getElementById(stepId).classList.contains('hidden');
}

// Start App
document.addEventListener('DOMContentLoaded', init);
