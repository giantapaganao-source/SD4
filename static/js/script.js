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
