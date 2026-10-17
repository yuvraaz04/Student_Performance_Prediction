/* =====================================================
   REPORTS PAGE JAVASCRIPT
===================================================== */

const generateReportBtn = document.getElementById("generateReportBtn");
const reportModal = document.getElementById("reportModal");
const closeModal = document.getElementById("closeModal");
const modalOverlay = document.querySelector(".modal-overlay");
const reportFilter = document.getElementById("reportFilter");
const reportsTableBody = document.getElementById("reportsTableBody");

// Open Modal
if (generateReportBtn && reportModal) {
    generateReportBtn.addEventListener("click", function () {
        reportModal.classList.add("show");
    });
}

// Close Modal
function closeReportModal() {
    if (reportModal) {
        reportModal.classList.remove("show");
    }
}

if (closeModal) {
    closeModal.addEventListener("click", closeReportModal);
}

if (modalOverlay) {
    modalOverlay.addEventListener("click", closeReportModal);
}

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeReportModal();
    }
});

// Unified Report Filter & Search
const reportsSearchInput = document.getElementById("studentReportsSearch");

function applyReportsFiltering() {
    if (!reportsTableBody) return;
    const selectedType = reportFilter ? reportFilter.value.toLowerCase() : "all";
    const searchQuery = reportsSearchInput ? reportsSearchInput.value.trim().toLowerCase() : "";
    const rows = reportsTableBody.querySelectorAll("tr");

    rows.forEach(function (row) {
        const text = row.innerText.toLowerCase();
        const badge = row.querySelector(".type-badge");
        const type = badge ? badge.textContent.trim().toLowerCase() : "";

        let matchesType = false;
        if (selectedType === "all") {
            matchesType = true;
        } else if (selectedType === "performance" && type.includes("perf")) {
            matchesType = true;
        } else if (selectedType === "risk" && type.includes("risk")) {
            matchesType = true;
        } else if (selectedType === "prediction" && type.includes("pred")) {
            matchesType = true;
        }

        const matchesSearch = !searchQuery || text.includes(searchQuery);

        if (matchesType && matchesSearch) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

if (reportFilter) {
    reportFilter.addEventListener("change", applyReportsFiltering);
}

if (reportsSearchInput) {
    reportsSearchInput.addEventListener("input", applyReportsFiltering);
}

console.log("StudentIQ Reports system initialized.");
