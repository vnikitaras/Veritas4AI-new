let currentStep = 1;

// --- ADVANCED DRAG & DROP AND FILE VALIDATION ---
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('fileInput');
    const fileListText = document.getElementById('fileListText');
    const fileHelpText = document.getElementById('fileHelpText');
    const dropZone = document.getElementById('dropZone');

    if (!dropZone || !fileInput) return;

    // Επιτρεπόμενοι τύποι (προστέθηκε το .zip με βάση το HTML σου) και όριο 10MB
    const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.zip'];
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

    // Κλικ στο Drop Zone ανοίγει τον File Explorer
    dropZone.addEventListener('click', () => fileInput.click());

    // --- DRAG & DROP EVENTS ---
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault(); 
        dropZone.style.borderColor = 'var(--primary-500)';
        dropZone.style.backgroundColor = 'var(--primary-100)';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = ''; 
        dropZone.style.backgroundColor = '';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '';
        dropZone.style.backgroundColor = '';
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            validateAndProcessFiles(fileInput.files);
        }
    });

    // Χειρισμός μέσω κλικ (File Explorer)
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            validateAndProcessFiles(fileInput.files);
        }
    });

    // --- ΛΟΓΙΚΗ ΕΠΙΚΥΡΩΣΗΣ ---
    function validateAndProcessFiles(files) {
        let validFiles = [];
        let errors = [];

        Array.from(files).forEach(file => {
            const fileName = file.name.toLowerCase();
            
            const isValidExtension = ALLOWED_EXTENSIONS.some(ext => fileName.endsWith(ext));
            const isValidSize = file.size <= MAX_FILE_SIZE;

            if (!isValidExtension) {
                errors.push(`"${file.name}" is an unsupported format.`);
            } else if (!isValidSize) {
                errors.push(`"${file.name}" exceeds the 10MB limit.`);
            } else {
                validFiles.push(file);
            }
        });

        updateUI(validFiles, errors);
    }

    // --- ΕΝΗΜΕΡΩΣΗ UI ---
    function updateUI(validFiles, errors) {
        if (errors.length > 0) {
            // Σφάλμα: Κόκκινα χρώματα και καθαρισμός αρχείων
            fileListText.innerHTML = `<span style="color: var(--danger);"><i class="fas fa-exclamation-triangle"></i> Validation Error</span>`;
            fileHelpText.innerHTML = `<span style="color: var(--danger); font-weight: 500;">${errors[0]}</span>`;
            dropZone.style.borderColor = 'var(--danger)';
            dropZone.style.backgroundColor = 'rgba(217, 45, 32, 0.05)';
            fileInput.value = ''; 
        } else if (validFiles.length > 0) {
            // Επιτυχία: Πράσινα χρώματα
            const count = validFiles.length;
            fileListText.innerHTML = `<span style="color: var(--accent-green);"><i class="fas fa-check-circle"></i> ${count} File(s) Ready</span>`;
            
            let names = validFiles.map(f => f.name).join(', ');
            if (names.length > 40) names = names.substring(0, 37) + '...';
            
            fileHelpText.innerHTML = `<span style="color: var(--accent-green); font-weight: 500;">${names}</span>`;
            dropZone.style.borderColor = 'var(--accent-green)';
            dropZone.style.backgroundColor = 'rgba(25, 193, 144, 0.05)';
        }
    }
});

function showStep(step) {
    document.querySelectorAll('.form-step').forEach(s => s.classList.remove('active'));
    const targetStep = document.getElementById('step' + step);
    if (targetStep) targetStep.classList.add('active');
    
    document.querySelectorAll('.step').forEach(d => {
        const ds = parseInt(d.dataset.step);
        d.classList.remove('active', 'completed');
        if (ds === step) d.classList.add('active');
        if (ds < step) d.classList.add('completed');
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function nextStep(targetStep) {
    const currentStepEl = document.querySelector('.form-step.active');
    
    // Validation Logic
    const inputs = currentStepEl.querySelectorAll('input, select, textarea');
    
    for (const input of inputs) {
        // Check only if visible and required
        if (input.offsetParent !== null && input.hasAttribute('required') && !input.checkValidity()) {
            input.reportValidity(); 
            return; 
        }
    }

    if (targetStep === 3) {
        try {
            populateReview();
        } catch (error) {
            console.error("Error populating review:", error);
        }
    }
    
    currentStep = targetStep;
    showStep(targetStep);
}

function prevStep(step) {
    currentStep = step;
    showStep(step);
}

function toggleMode(mode) {
    const app = document.getElementById('mode-application');
    const files = document.getElementById('mode-files');
    const appInputs = app.querySelectorAll('input, select, textarea');
    
    if (mode === 'application') {
        app.style.display = 'block';
        files.style.display = 'none';
        appInputs.forEach(i => i.setAttribute('required', ''));
    } else {
        app.style.display = 'none';
        files.style.display = 'block';
        appInputs.forEach(i => i.removeAttribute('required'));
    }
}

function populateReview() {
    const mode = document.querySelector('input[name="input_mode"]:checked');
    const modeValue = mode ? mode.value : 'application';
    
    // Default Risk Badge (Since we removed user input)
    const riskBadgeHtml = `<span class="summary-badge" style="background:#e0e7ff; color:#3730a3;">AI ESTIMATE</span>`;

    if (modeValue === 'application') {
        const name = document.getElementById('appName').value || "N/A";
        const role = document.getElementById('organizationRole').value || "N/A";
        const domain = document.getElementById('applicationArea').value || "N/A";

        document.getElementById('rev-name').innerText = name;
        document.getElementById('rev-role').innerText = role;
        document.getElementById('rev-domain').innerText = domain;
        document.getElementById('rev-risk-badge').innerHTML = riskBadgeHtml;
        
    } else {
        // Files mode review
        const fileInput = document.getElementById('fileInput');
        const fileNameField = document.getElementById('applicationNameFiles');
        
        let displayText = "From Documents";
        if (fileNameField && fileNameField.value) {
            displayText = fileNameField.value;
        } else if (fileInput && fileInput.files.length > 0) {
            displayText = fileInput.files[0].name + (fileInput.files.length > 1 ? ` +${fileInput.files.length-1} more` : "");
        }
        
        document.getElementById('rev-name').innerText = displayText;
        document.getElementById('rev-role').innerText = "Defined in docs";
        document.getElementById('rev-domain').innerText = "Defined in docs";
        document.getElementById('rev-risk-badge').innerHTML = riskBadgeHtml;
    }
}

// --- Νέα Ασύγχρονη Λογική Υποβολής με SSE (Server-Sent Events) και Μοντέρνο UI ---
const form = document.getElementById('reportForm');
if (form) {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const checkedRadio = document.querySelector('input[name="details"]:checked');
        if (!checkedRadio) {
            alert("Please select a Report Package.");
            return;
        }

        // Στόχευση του νέου Μοντέρνου UI
        const overlay = document.getElementById('modernLoadingOverlay');
        const progressBar = document.getElementById('modernProgressBar');
        const progressText = document.getElementById('modernProgressText');
        const progressTitle = document.getElementById('modernProgressTitle');
        const submitBtn = document.getElementById('submitBtn') || this.querySelector('button[type="submit"]');
        
        if (submitBtn) submitBtn.disabled = true;
        
        // Εμφάνιση του όμορφου Overlay
        if (overlay) {
            overlay.style.display = 'flex';
            if (progressBar) progressBar.style.width = '0%';
            if (progressText) progressText.innerText = 'Προετοιμασία εγγράφων...';
            if (progressTitle) progressTitle.innerText = 'Το Veritas4AI αναλύει τα δεδομένα...';
        }

        try {
            const formData = new FormData(this);
            const response = await fetch('/generate-report', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            const jobId = data.job_id;
            const eventSource = new EventSource(`/stream-progress/${jobId}`);

            eventSource.onmessage = function(event) {
                const jobData = JSON.parse(event.data);

                if (jobData.error) {
                    eventSource.close();
                    alert("Σφάλμα: " + jobData.error);
                    resetModernUI(submitBtn, overlay);
                    return;
                }

                // Smooth ενημέρωση του UI
                if (progressBar && progressText) {
                    progressBar.style.width = jobData.progress + '%';
                    progressText.innerText = jobData.status;
                }

                // Ολοκλήρωση
                if (jobData.result_file) {
                    eventSource.close();
                    if (progressTitle) progressTitle.innerText = "Η ανάλυση ολοκληρώθηκε!";
                    if (progressText) progressText.innerText = "Το έγγραφό σας είναι έτοιμο. Έναρξη λήψης...";
                    if (progressBar) progressBar.style.width = '100%';

                    // 1 δευτερόλεπτο delay για να δει ο χρήστης το 100%
                    setTimeout(() => {
                        window.location.href = `/download-report/${jobId}`;
                    }, 1000);

                    // Κλείσιμο του overlay μετά το κατέβασμα
                    setTimeout(() => {
                        resetModernUI(submitBtn, overlay);
                    }, 6000);
                }
            };

            eventSource.onerror = function() {
                eventSource.close();
                alert("Η σύνδεση διακόπηκε. Η παραγωγή ίσως συνεχίζεται στο παρασκήνιο.");
                resetModernUI(submitBtn, overlay);
            };

        } catch (error) {
            console.error("Error:", error);
            alert("Σφάλμα συστήματος: " + error.message);
            resetModernUI(submitBtn, overlay);
        }
    });
}

function resetModernUI(submitBtn, overlay) {
    if (submitBtn) submitBtn.disabled = false;
    if (overlay) overlay.style.display = 'none';
}
// --- EU AI ACT HIGH-RISK DOMAIN CHECKER ---
document.addEventListener('DOMContentLoaded', () => {
    const applicationAreaSelect = document.getElementById('applicationArea');
    const indicator = document.getElementById('riskIndicatorBox');
    const icon = document.getElementById('riskIcon');
    const title = document.getElementById('riskTitle');
    const text = document.getElementById('riskText');

    if (!applicationAreaSelect) return;

    // Κατηγορίες που συνήθως εμπίπτουν στο Annex III (High-Risk)
    const highRiskDomains = [
        "Health & Care",
        "Education & Research",
        "Finance, Banking & Insurance",
        "Public Safety, Defense & Security",
        "Governance & Public Administration",
        "Core Digital Infrastructure & Platforms",
        "Energy, Utilities & Built Environment",
        "Transport, Mobility & Logistics"
    ];

    applicationAreaSelect.addEventListener('change', function() {
        const selected = this.value;

        if (!selected || selected === "Other") {
            indicator.style.display = 'none';
            return;
        }

        indicator.style.display = 'flex';

        if (highRiskDomains.includes(selected)) {
            // High Risk - Απαλό κόκκινο/πορτοκαλί warning
            indicator.style.backgroundColor = '#FEF2F2'; 
            indicator.style.border = '1px solid #FCA5A5';
            indicator.style.color = '#991B1B'; 
            
            icon.className = 'fas fa-exclamation-triangle';
            icon.style.color = '#DC2626';
            
            title.innerText = 'ℹ️ Sector with possible Annex III use cases';
            text.innerText = 'Some uses in this sector can fall under Annex III, but the risk class depends on the intended purpose of your system, not on the sector. It will be determined from your description or documents.';
        } else {
            // Low/Minimal Risk - Απαλό πράσινο success
            indicator.style.backgroundColor = '#F0FDF4'; 
            indicator.style.border = '1px solid #86EFAC';
            indicator.style.color = '#166534'; 
            
            icon.className = 'fas fa-shield-check';
            icon.style.color = '#16A34A';
            
            title.innerText = 'ℹ️ Classification depends on intended purpose';
            text.innerText = 'The sector alone does not determine the risk class. Transparency rules (Art. 50) or other obligations may still apply depending on the specific use case.';
        }
    });
});
