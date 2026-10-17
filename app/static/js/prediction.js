const predictionForm = document.getElementById("predictionForm");
const predictBtn = document.getElementById("predictBtn");

if (predictionForm) {
    predictionForm.addEventListener("submit", function (event) {
        event.preventDefault();

        const attendance = Number(document.getElementById("attendance")?.value) || 80;
        const studyHours = Number(document.getElementById("studyHours")?.value) || 15;
        const previousMarks = Number(document.getElementById("previousMarks")?.value) || 75;
        const sleepDuration = Number(document.getElementById("sleepDuration")?.value) || 7;
        const socialMedia = Number(document.getElementById("socialMedia")?.value) || 2;
        const participation = document.getElementById("participation") ? document.getElementById("participation").value : "medium";

        // Button Loading State
        predictBtn.disabled = true;
        predictBtn.innerHTML = `
            <i class="bi bi-arrow-repeat spin"></i>
            Analyzing with AI Model...
        `;

        // Send AJAX request to Flask ML prediction endpoint
        fetch("/api/predict", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                attendance: attendance,
                studyHours: studyHours,
                previousMarks: previousMarks,
                sleep_duration: sleepDuration,
                social_media: socialMedia,
                participation: participation,
                motivation_level: participation
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error("Prediction request failed");
            }
            return response.json();
        })
        .then(data => {
            const predictedScore = data.predicted_score;
            const status = data.performance_category || data.status;
            const risk = data.risk_level;
            const description = data.description;
            const recommendation = data.recommendation;

            // Update DOM Elements
            const scoreEl = document.getElementById("predictionScore");
            if (scoreEl) scoreEl.textContent = predictedScore;

            const statusEl = document.getElementById("predictionStatus");
            if (statusEl) statusEl.textContent = status;

            const descEl = document.getElementById("predictionDescription");
            if (descEl) descEl.textContent = description;

            const riskEl = document.getElementById("riskLevel");
            if (riskEl) riskEl.textContent = risk;

            const recEl = document.getElementById("recommendationText");
            if (recEl) recEl.textContent = recommendation;

            // Update Factors
            const attFactor = document.getElementById("attendanceFactor");
            if (attFactor) attFactor.textContent = attendance + "%";

            const studyFactor = document.getElementById("studyFactor");
            if (studyFactor) studyFactor.textContent = studyHours + " hrs";

            const marksFactor = document.getElementById("marksFactor");
            if (marksFactor) marksFactor.textContent = previousMarks + "%";

            const sleepFactor = document.getElementById("sleepFactor");
            if (sleepFactor) sleepFactor.textContent = sleepDuration + " hrs";

            const socialFactor = document.getElementById("socialFactor");
            if (socialFactor) socialFactor.textContent = socialMedia + " hrs";

            // Update Progress Bars
            const attBar = document.getElementById("attendanceBar");
            if (attBar) attBar.style.width = attendance + "%";

            const studyBar = document.getElementById("studyBar");
            if (studyBar) studyBar.style.width = Math.min(studyHours * 5, 100) + "%";

            const marksBar = document.getElementById("marksBar");
            if (marksBar) marksBar.style.width = previousMarks + "%";

            const sleepBar = document.getElementById("sleepBar");
            if (sleepBar) sleepBar.style.width = Math.min((sleepDuration / 12) * 100, 100) + "%";

            const socialBar = document.getElementById("socialBar");
            if (socialBar) socialBar.style.width = Math.min((socialMedia / 10) * 100, 100) + "%";

            // Update Score Circle Gauge
            const scoreCircle = document.querySelector(".score-circle");
            if (scoreCircle) {
                const degree = predictedScore * 3.6;
                scoreCircle.style.background = `
                    radial-gradient(
                        circle,
                        white 58%,
                        transparent 59%
                    ),
                    conic-gradient(
                        #684ff5 ${degree}deg,
                        #eceaff ${degree}deg
                    )
                `;
            }

            // Reset Button
            predictBtn.disabled = false;
            predictBtn.innerHTML = `
                <i class="bi bi-stars"></i>
                Predict Again
            `;
        })
        .catch(err => {
            console.error("Prediction error:", err);
            alert("Error generating prediction. Please try again.");
            predictBtn.disabled = false;
            predictBtn.innerHTML = `
                <i class="bi bi-stars"></i>
                Predict Performance
            `;
        });
    });
}