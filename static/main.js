/* ============================================================ */
/* ==== JS for dropdowns, modals, and Flatpickr datepicker ==== */
/* ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
    /* ===== Sidebar dropdowns ===== */
    const toggles = document.querySelectorAll('.navbar-group-toggle');

    toggles.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const group = btn.closest('.navbar-group');
            if (group) group.classList.toggle('open');
        });
    });

    /* ===== calendar/date picker (Flatpickr) ===== */

    if (typeof flatpickr !== "undefined") {
        const startDateInput = document.querySelector("input[name='start_date']");
        if (startDateInput) {
            flatpickr(startDateInput, {
                dateFormat: "Y-m-d",
                altInput: true,
                altFormat: "F j, Y",
                defaultDate: "today"
            });
        }

        const expenseDate = document.querySelector("#expense_date");
        if (expenseDate) {
            flatpickr(expenseDate, {
                dateFormat: "Y-m-d",
                altInput: true,
                altFormat: "F j, Y",
                defaultDate: "today",
            });
          }

        const ledgerDateInput = document.querySelector("input[name='date']");
        if (ledgerDateInput) {
            flatpickr(ledgerDateInput, {
                dateFormat: "Y-m-d",
                altInput: true,
                altFormat: "F j, Y",
                defaultDate: "today"
            });
        }
    }

    /* ===== Ledger modal ===== */
    (function () {
        const ledgerModal = document.getElementById('ledger-modal');
        if (!ledgerModal) return;

        function openLedgerModal() {
            ledgerModal.classList.add('open');
        }

        function closeLedgerModal() {
            ledgerModal.classList.remove('open');
        }

        document.addEventListener('click', function (e) {
            const openBtn = e.target.closest('[data-open-ledger-modal]');
            const closeBtn = e.target.closest('[data-close-ledger-modal]');

            if (openBtn) {
                e.preventDefault();
                openLedgerModal();
            } else if (closeBtn) {
                e.preventDefault();
                closeLedgerModal();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && ledgerModal.classList.contains('open')) {
                closeLedgerModal();
            }
        });
    })();

    /* ===== Add Resident modal ===== */
    (function () {
        const residentModal = document.getElementById('resident-modal');
        if (!residentModal) return;

        function openResidentModal() {
            residentModal.classList.add('open');
        }

        function closeResidentModal() {
            residentModal.classList.remove('open');
        }

        document.addEventListener('click', function (e) {
            const openBtn = e.target.closest('[data-open-resident-modal]');
            const closeBtn = e.target.closest('[data-close-resident-modal]');

            if (openBtn) {
                e.preventDefault();
                openResidentModal();
            } else if (closeBtn) {
                e.preventDefault();
                closeResidentModal();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && residentModal.classList.contains('open')) {
                closeResidentModal();
            }
        });
    })();

    // Receipt modal (view PDF)
    const receiptModal = document.getElementById("receipt-modal");
    const receiptFrame = document.getElementById("receipt-frame");

    document.querySelectorAll("[data-open-receipt-modal]").forEach(btn => {
        btn.addEventListener("click", () => {
            const url = btn.getAttribute("data-receipt-url");
            if (!url) return;

            receiptFrame.src = url;
            receiptModal.classList.add("open");
        });
    });

    document.querySelectorAll("[data-close-receipt-modal]").forEach(btn => {
        btn.addEventListener("click", () => {
            receiptModal.classList.remove("open");
            receiptFrame.src = ""; // stop the PDF from staying loaded
        });
    });
});
