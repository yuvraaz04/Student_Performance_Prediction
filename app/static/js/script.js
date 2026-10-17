// ================================
// KPI COUNTER ANIMATION
// ================================

const counters = document.querySelectorAll(".counter");

counters.forEach(counter => {

    const updateCounter = () => {

        const target = +counter.getAttribute("data-target");
        const count = +counter.innerText;

        const increment = target / 120;

        if (count < target) {

            counter.innerText = Math.ceil(count + increment);

            setTimeout(updateCounter, 20);

        } else {

            counter.innerText = target;

        }

    };

    updateCounter();

});

// ================================
// PERFORMANCE LINE CHART
// ================================

const perfElem = document.getElementById("performanceChart");
const performanceChart = perfElem ? new Chart(
    perfElem,
    {
        type: "line",

        data: {

            labels: [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun"
            ],

            datasets: [

                {

                    label: "Average Score",

                    data: [62, 68, 73, 71, 78, 84],

                    borderColor: "#6C63FF",

                    backgroundColor: "rgba(108,99,255,.15)",

                    fill: true,

                    borderWidth: 3,

                    tension: .4,

                    pointRadius: 4,

                    pointBackgroundColor: "#6C63FF"

                }

            ]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            animation: {

                duration: 2000

            },

            plugins: {

                legend: {

                    display: false

                }

            }

        }

    }

) : null;
// ================================
// GENDER DISTRIBUTION DOUGHNUT
// ================================

const genderElem = document.getElementById("genderChart");
const genderChart = genderElem ? new Chart(
    genderElem,
    {

        type:"doughnut",

        data:{

            labels:[
                "Male",
                "Female"
            ],

            datasets:[

                {

                    data:[
                        52,
                        48
                    ],

                    backgroundColor:[

                        "#6C63FF",
                        "#FF7EB3"

                    ],

                    borderWidth:0

                }

            ]

        },

        options:{

            responsive:true,

            maintainAspectRatio:false,

            animation:{

                animateRotate:true,

                duration:2000

            },

            plugins:{

                legend:{

                    position:"bottom"

                }

            }

        }

    }

) : null;


// ================================
// SUBJECT ANALYSIS BAR CHART
// ================================

const subjectElem = document.getElementById("subjectChart");
const subjectChart = subjectElem ? new Chart(

    subjectElem,

    {

        type:"bar",

        data:{

            labels:[

                "Math",
                "Science",
                "English",
                "Computer",
                "History"

            ],

            datasets:[

                {

                    label:"Average Marks",

                    data:[

                        82,
                        76,
                        79,
                        88,
                        72

                    ],

                    backgroundColor:[

                        "#6C63FF",
                        "#8B5CF6",
                        "#A78BFA",
                        "#C4B5FD",
                        "#DDD6FE"

                    ],

                    borderRadius:10

                }

            ]

        },

        options:{

            responsive:true,

            maintainAspectRatio:false,

            animation:{

                duration:2000

            },

            scales:{

                y:{

                    beginAtZero:true,

                    max:100

                }

            },

            plugins:{

                legend:{

                    display:false

                }

            }

        }

    }

) : null;


// ================================
// ATTENDANCE TREND AREA CHART
// ================================

const attendanceElem = document.getElementById("attendanceChart");
const attendanceChart = attendanceElem ? new Chart(

    attendanceElem,

    {

        type:"line",

        data:{

            labels:[

                "Week 1",
                "Week 2",
                "Week 3",
                "Week 4",
                "Week 5",
                "Week 6"

            ],

            datasets:[

                {

                    label:"Attendance %",

                    data:[

                        78,
                        82,
                        80,
                        86,
                        90,
                        88

                    ],

                    borderColor:"#10B981",

                    backgroundColor:"rgba(16,185,129,.15)",

                    fill:true,

                    tension:.4,

                    borderWidth:3,

                    pointRadius:4

                }

            ]

        },

        options:{

            responsive:true,

            maintainAspectRatio:false,

            animation:{

                duration:2000

            },

            plugins:{

                legend:{

                    display:false

                }

            },

            scales:{

                y:{

                    min:50,

                    max:100

                }

            }

        }

    }

) : null;
// ================================
// SIDEBAR ACTIVE MENU
// ================================

const menuItems = document.querySelectorAll(".menu li");

menuItems.forEach(item => {

    item.addEventListener("click",()=>{

        menuItems.forEach(menu=>{
            menu.classList.remove("active");
        });

        item.classList.add("active");

    });

});


// ================================
// SEARCH STUDENT INTERACTION
// ================================

const searchInput = document.querySelector(".search input");

if(searchInput){

    searchInput.addEventListener("keyup",()=>{

        let value = searchInput.value.toLowerCase();

        const rows = document.querySelectorAll("tbody tr");


        rows.forEach(row=>{

            let text = row.innerText.toLowerCase();


            if(text.includes(value)){

                row.style.display="table-row";

            }

            else{

                row.style.display="none";

            }

        });

    });

}


// ================================
// EXPORT BUTTON DEMO
// ================================

const exportBtn = document.querySelector(".export");


if(exportBtn){

    exportBtn.addEventListener("click",()=>{


        alert(
            "Student performance report exported successfully!"
        );


    });

}


// ================================
// PREDICTION BUTTON
// ================================

const predictionBtn = document.querySelector(".predict-btn");


if(predictionBtn){

    predictionBtn.addEventListener("click",()=>{


        predictionBtn.innerHTML =
        "Analyzing... 🤖";


        predictionBtn.disabled=true;


        setTimeout(()=>{


            predictionBtn.innerHTML =
            "Prediction Complete ✓";


        },2000);


    });

}


// ================================
// CARD FLOATING EFFECT
// ================================

const cards = document.querySelectorAll(
    ".kpi-card,.chart-card,.table-card"
);


cards.forEach(card=>{


    card.addEventListener("mousemove",(e)=>{


        const rect = card.getBoundingClientRect();


        const x =
        e.clientX - rect.left;


        const y =
        e.clientY - rect.top;



        card.style.transform =
        `
        perspective(700px)
        rotateX(${-(y-rect.height/2)/25}deg)
        rotateY(${(x-rect.width/2)/25}deg)
        translateY(-5px)
        `;


    });



    card.addEventListener("mouseleave",()=>{


        card.style.transform="";


    });


});


// ================================
// AUTO UPDATE DEMO DATA
// ================================

setInterval(()=>{


    const insightItems =
    document.querySelectorAll(".insight-item");


    if(insightItems.length){


        insightItems.forEach(item=>{


            item.style.opacity="0.7";


            setTimeout(()=>{

                item.style.opacity="1";

            },300);


        });


    }


},5000);