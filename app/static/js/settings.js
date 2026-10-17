/* =====================================================
   SETTINGS PAGE JAVASCRIPT
===================================================== */

document.addEventListener("DOMContentLoaded", function () {
    const navItems = document.querySelectorAll(".settings-nav-item");
    const sections = document.querySelectorAll(".settings-section");

    navItems.forEach(function (item) {
        item.addEventListener("click", function () {
            const target = this.getAttribute("data-section");
            navItems.forEach(nav => nav.classList.remove("active"));
            this.classList.add("active");

            sections.forEach(section => section.classList.remove("active"));
            const targetSection = document.getElementById(target);
            if (targetSection) {
                targetSection.classList.add("active");
            }
        });
    });

    console.log("Settings page initialized.");
});
