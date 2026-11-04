// script.js - popups (modals) and auto-hiding messages

// Any button with data-modal opens that popup. The button's data-* values fill the form.
document.querySelectorAll("[data-modal]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var modal = document.getElementById(btn.dataset.modal);
    var form = modal.querySelector("form");
    form.reset();
    form.action = btn.dataset.action;
    Object.keys(btn.dataset).forEach(function (key) {
      if (form.elements[key]) form.elements[key].value = btn.dataset[key];
    });
    modal.querySelector("h2").textContent = btn.dataset.heading;
    modal.classList.add("open");
  });
});

// Close popups with Cancel or by clicking the dark background
document.querySelectorAll(".modal").forEach(function (modal) {
  modal.addEventListener("click", function (e) {
    if (e.target === modal || e.target.hasAttribute("data-close")) modal.classList.remove("open");
  });
});

// Fade out messages after 4 seconds
document.querySelectorAll(".alert").forEach(function (a) {
  setTimeout(function () { a.classList.add("hide"); }, 4000);
});

var dashboardClock = document.getElementById("dashboardClock");
if (dashboardClock) {
  var dashboardClockDate = document.getElementById("dashboardClockDate");
  function updateDashboardClock() {
    var now = new Date();
    dashboardClock.textContent = now.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
    dashboardClockDate.textContent = now.toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    });
    dashboardClock.dateTime = now.toISOString();
  }
  updateDashboardClock();
  window.setInterval(updateDashboardClock, 1000);
}

var reminderPanel = document.getElementById("reminderPanel");
if (reminderPanel) {
  var reminderList = document.getElementById("reminderList");
  var enableNotificationsButton = document.getElementById("enableNotifications");
  var notificationStatus = document.getElementById("notificationStatus");
  var shownReminderIds = new Set();
  var storageAvailable = true;

  function showReminderStatus(message) {
    notificationStatus.textContent = message;
  }

  function sendBrowserReminder(reminder) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    var storageKey = "studybuddy-notification-" + reminder.id;
    try {
      if (storageAvailable && window.localStorage.getItem(storageKey)) return;
      new Notification(reminder.title, {
        body: reminder.message,
        tag: storageKey,
        renotify: false
      });
      shownReminderIds.add(reminder.id);
      if (storageAvailable) window.localStorage.setItem(storageKey, "sent");
    } catch (error) {
      console.error("Could not display or save the browser reminder.", error);
      storageAvailable = false;
      showReminderStatus("A browser reminder could not be saved or displayed. In-app reminders are still available.");
    }
  }

  function pollReminders() {
    fetch(reminderPanel.dataset.url, { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("Reminder request failed with status " + response.status);
        return response.json();
      })
      .then(function (data) {
        reminderList.replaceChildren();
        data.reminders.forEach(function (reminder) {
          var item = document.createElement("li");
          item.textContent = reminder.message;
          reminderList.appendChild(item);
          if (!shownReminderIds.has(reminder.id)) sendBrowserReminder(reminder);
        });
        reminderPanel.hidden = data.reminders.length === 0;
        if (!("Notification" in window)) {
          showReminderStatus("Browser notifications are not supported in this browser.");
          enableNotificationsButton.hidden = true;
        } else if (Notification.permission === "denied") {
          showReminderStatus("Browser notifications are blocked. Allow them in your browser's site settings.");
          enableNotificationsButton.hidden = true;
        } else if (Notification.permission === "granted") {
          enableNotificationsButton.hidden = true;
          if (storageAvailable) showReminderStatus("");
        } else {
          enableNotificationsButton.hidden = false;
          enableNotificationsButton.textContent = "Enable notifications";
          showReminderStatus("Enable browser notifications to receive alerts while this site is open.");
        }
      })
      .catch(function (error) {
        console.error("Could not check StudyBuddy reminders.", error);
        showReminderStatus("Could not check reminders. Check your connection or refresh the page.");
      });
  }

  enableNotificationsButton.addEventListener("click", function () {
    if (!("Notification" in window)) return;
    Notification.requestPermission().then(function () {
      pollReminders();
    }).catch(function (error) {
      console.error("Could not request browser notification permission.", error);
      showReminderStatus("Could not enable browser notifications. Check your browser settings.");
    });
  });

  pollReminders();
  window.setInterval(pollReminders, 60000);
}
