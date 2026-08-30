// Global configurations and states
let config = {
    apiHost: window.location.origin,
    threshold: 0.50,
    sampleFps: 2,
    audioAlert: true,
    autoRecord: true,
    targetClasses: ['Fighting', 'Weapons', 'Falls', 'Trespass', 'Panic', 'Abandoned', 'Assault', 'Shooting', 'Robbery', 'Burglary', 'Vandalism']
};

let privacyConfig = {
    enable_face_blur: true,
    anonymize_bystanders: false,
    retention_days: 30
};

let state = {
    activeTab: 'live-feed-section',
    selectedCamera: 'CAM-01',
    isAnalyzingWebcam: false,
    cameraMode: 'simulation', // Default to simulation for rich demonstration
    webcamStream: null,
    webcamTimer: null,
    sirenPlaying: false,
    alerts: [],
    // Simulation state
    simScenario: 'Normal', // 'Normal', 'Fighting', 'Weapons', 'Falls', 'Trespass', 'Panic', 'Abandoned'
    simFrameIndex: 0,
    simInterval: null,
    // Chart references
    liveChart: null,
    timelineChart: null,
    analyticsTrendChart: null,
    analyticsDistChart: null,
    // Live chart data arrays
    liveChartData: Array(30).fill(0),
    poseChartData: Array(30).fill(0),
    audioChartData: Array(30).fill(0)
};

// All available categories
const ALL_CATEGORIES = [
    'Normal', 'Abuse', 'Arrest', 'Arson', 'Assault', 
    'Burglary', 'Explosion', 'Fighting', 'RoadAccident', 
    'Robbery', 'Shooting', 'Shoplifting', 'Stealing', 'Vandalism',
    'Weapons', 'Falls', 'Panic', 'Trespass', 'Abandoned'
];

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadPrivacyConfig();
    initNavigation();
    initCharts();
    initWebcam();
    initSimulation();
    initVideoUpload();
    initSettingsForm();
    initViewTabs();
    initScenarioSelect();
    refreshAlerts();
    refreshStats();
    
    // Hook playback modal close button
    document.getElementById('close-clip-modal-btn').addEventListener('click', closeClipModal);
    
    // Auto-update stats every 10s
    setInterval(() => {
        if (state.activeTab === 'live-feed-section' || state.activeTab === 'analytics-section') {
            refreshStats();
            refreshAlertsTableOnly();
        }
    }, 10000);
});

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('guardian_ai_config');
    if (saved) {
        try {
            config = { ...config, ...JSON.parse(saved) };
        } catch (e) {
            console.error("Failed to load saved config:", e);
        }
    }
    document.getElementById('audio-alarm-switch').checked = config.audioAlert;
    document.getElementById('threshold-slider').value = config.threshold;
    document.getElementById('threshold-val').textContent = config.threshold;
    document.getElementById('sample-fps-select').value = config.sampleFps;
    
    const autoRec = document.getElementById('auto-record-chk');
    if (autoRec) {
        autoRec.checked = config.autoRecord;
    }
}

// Fetch privacy configuration from server
function loadPrivacyConfig() {
    fetch(`${config.apiHost}/api/privacy`)
    .then(res => res.json())
    .then(data => {
        privacyConfig = data;
        // Sync checkboxes in settings UI
        document.getElementById('privacy-face-blur').checked = privacyConfig.enable_face_blur;
        document.getElementById('privacy-anonymize').checked = privacyConfig.anonymize_bystanders;
        document.getElementById('privacy-retention').value = privacyConfig.retention_days;
    })
    .catch(err => console.error("Error loading privacy config:", err));
}

// Navigation Tab Switching
function initNavigation() {
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.getAttribute('data-target');
            
            // Toggle active menu item
            menuItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            // Toggle active section
            document.querySelectorAll('.content-section').forEach(sec => {
                sec.classList.remove('active');
            });
            document.getElementById(target).classList.add('active');
            state.activeTab = target;
            
            // Update Page Title
            document.getElementById('page-title').textContent = item.querySelector('span').textContent;
            
            // Re-render charts when visible
            if (target === 'analytics-section') {
                refreshAnalyticsCharts();
            }
        });
    });
    
    // Dismiss alarm button
    document.getElementById('dismiss-alarm-btn').addEventListener('click', () => {
        stopAlarm();
    });
}

// Live Grid vs Facility Map View Tabs
function initViewTabs() {
    const btnFeeds = document.getElementById('tab-btn-feeds');
    const btnMap = document.getElementById('tab-btn-map');
    const gridView = document.getElementById('camera-grid-view');
    const mapView = document.getElementById('facility-map-view');
    
    btnFeeds.addEventListener('click', () => {
        btnMap.classList.remove('active');
        btnFeeds.classList.add('active');
        mapView.style.display = 'none';
        gridView.style.display = 'block';
    });
    
    btnMap.addEventListener('click', () => {
        btnFeeds.classList.remove('active');
        btnMap.classList.add('active');
        gridView.style.display = 'none';
        mapView.style.display = 'block';
    });
}

// Scenario selector inject & bind
function initScenarioSelect() {
    const controls = document.querySelector('.cctv-container .card-header');
    
    // Create scenario select element
    const select = document.createElement('select');
    select.id = 'sim-scenario-select';
    select.className = 'filter-select';
    select.style.marginLeft = '10px';
    select.style.padding = '4px 8px';
    select.style.fontSize = '12px';
    
    const scenarios = [
        { val: 'Normal', label: 'Simulate: Normal Scene' },
        { val: 'Fighting', label: 'Simulate: Fighting (Critical)' },
        { val: 'Weapons', label: 'Simulate: Weapons Visible (Critical)' },
        { val: 'Falls', label: 'Simulate: Sudden Fall (High)' },
        { val: 'Trespass', label: 'Simulate: Trespass (Medium)' },
        { val: 'Panic', label: 'Simulate: Crowd Panic (Medium)' },
        { val: 'Abandoned', label: 'Simulate: Abandoned Object (Low)' }
    ];
    
    scenarios.forEach(sc => {
        const opt = document.createElement('option');
        opt.value = sc.val;
        opt.textContent = sc.label;
        select.appendChild(opt);
    });
    
    // Add next to camera controls
    controls.appendChild(select);
    
    select.addEventListener('change', (e) => {
        state.simScenario = e.target.value;
        console.log("Simulating scenario changed to:", state.simScenario);
    });
    
    // Hide initially if webcam is selected
    if (state.cameraMode === 'webcam') {
        select.style.display = 'none';
    }
}

// Initialize Charts
function initCharts() {
    const ctxLive = document.getElementById('live-anomaly-chart').getContext('2d');
    state.liveChart = new Chart(ctxLive, {
        type: 'line',
        data: {
            labels: Array(30).fill(''),
            datasets: [
                {
                    label: 'Combined Score',
                    data: state.liveChartData,
                    borderColor: '#00d2ff',
                    borderWidth: 2,
                    backgroundColor: 'rgba(0, 210, 255, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                },
                {
                    label: 'Pose Anomaly',
                    data: state.poseChartData,
                    borderColor: '#f59e0b',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0
                },
                {
                    label: 'Audio Anomaly',
                    data: state.audioChartData,
                    borderColor: '#a855f7',
                    borderWidth: 1,
                    borderDash: [2, 2],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { 
                    display: true,
                    position: 'top',
                    labels: { color: '#8c9ba5', boxWidth: 12, font: { size: 10 } }
                } 
            },
            scales: {
                y: {
                    min: 0,
                    max: 1.0,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8c9ba5' }
                },
                x: { display: false }
            }
        }
    });
}

// Webcam Capture and Streaming
function initWebcam() {
    const btnWebcam = document.getElementById('btn-camera-webcam');
    const btnSim = document.getElementById('btn-camera-simulation');
    
    btnWebcam.addEventListener('click', () => {
        btnSim.classList.remove('active');
        btnWebcam.classList.add('active');
        const select = document.getElementById('sim-scenario-select');
        if (select) select.style.display = 'none';
        switchCameraMode('webcam');
    });
    
    // Set to simulation mode by default for demo
    btnSim.addEventListener('click', () => {
        btnWebcam.classList.remove('active');
        btnSim.classList.add('active');
        const select = document.getElementById('sim-scenario-select');
        if (select) select.style.display = 'inline-block';
        switchCameraMode('simulation');
    });
    
    switchCameraMode('simulation'); // Start in simulation
}

function switchCameraMode(mode) {
    state.cameraMode = mode;
    stopLoops();
    
    const canvas = document.getElementById('surveillance-canvas');
    canvas.width = 640;
    canvas.height = 360;
    
    if (mode === 'webcam') {
        document.getElementById('active-feed-label').textContent = `${state.selectedCamera} - WEBCAM LIVE`;
        navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360 } })
            .then(stream => {
                state.webcamStream = stream;
                const video = document.getElementById('webcam-video');
                video.srcObject = stream;
                video.onloadedmetadata = () => {
                    video.play();
                    startWebcamLoop();
                };
            })
            .catch(err => {
                console.warn("Webcam not available, falling back to Simulation mode:", err);
                document.getElementById('btn-camera-webcam').classList.remove('active');
                document.getElementById('btn-camera-simulation').classList.add('active');
                const select = document.getElementById('sim-scenario-select');
                if (select) select.style.display = 'inline-block';
                switchCameraMode('simulation');
            });
    } else {
        document.getElementById('active-feed-label').textContent = `${state.selectedCamera} - MOCK SURVEILLANCE FEED`;
        startSimulationLoop();
    }
}

function stopLoops() {
    if (state.webcamTimer) clearInterval(state.webcamTimer);
    if (state.simInterval) clearInterval(state.simInterval);
    if (state.webcamStream) {
        state.webcamStream.getTracks().forEach(track => track.stop());
        state.webcamStream = null;
    }
}

function startWebcamLoop() {
    const video = document.getElementById('webcam-video');
    const canvas = document.getElementById('surveillance-canvas');
    const ctx = canvas.getContext('2d');
    
    const intervalMs = 1000 / config.sampleFps;
    
    state.webcamTimer = setInterval(() => {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Draw face blur overlay on webcam feed if enabled
        if (privacyConfig.enable_face_blur) {
            // Draw a mock pixelated blur in the center where a face might be
            applyFaceBlur(ctx, 320, 150, 60);
        }
        
        updateWatermark();
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
        analyzeFrame(dataUrl);
    }, intervalMs);
}

// Interactive Camera Node Switching
window.switchActiveCCTV = (camId) => {
    state.selectedCamera = camId;
    
    // Highlight camera box in grid
    document.querySelectorAll('.camera-box').forEach(box => {
        box.classList.remove('active');
    });
    
    let camIdx = parseInt(camId.replace('CAM-0', ''));
    const activeBox = document.getElementById(`cam-box-${camIdx}`);
    if (activeBox) {
        activeBox.classList.add('active');
    }
    
    // If simulation, redraw watermark details
    if (state.cameraMode === 'simulation') {
        document.getElementById('active-feed-label').textContent = `${camId} - MOCK SURVEILLANCE FEED`;
    } else {
        document.getElementById('active-feed-label').textContent = `${camId} - WEBCAM LIVE`;
    }
    
    console.log("Switched active CCTV monitor to:", camId);
};

// Switch view to live cctv feed tab and select camera
window.jumpToCameraFeed = (camId) => {
    // 1. Switch Active tab to Live Monitor
    const liveMonitorMenu = document.querySelector('.menu-item[data-target="live-feed-section"]');
    if (liveMonitorMenu) {
        liveMonitorMenu.click();
    }
    
    // 2. Select live grid tab view instead of map
    document.getElementById('tab-btn-feeds').click();
    
    // 3. Switch camera feed focus
    switchActiveCCTV(camId);
};

// SVG Map camera click
window.selectCameraFromMap = (camId) => {
    // Select camera
    switchActiveCCTV(camId);
    // Jump to feeds tab
    document.getElementById('tab-btn-feeds').click();
};

// Pixelated Face Blur simulation overlay
function applyFaceBlur(ctx, x, y, size) {
    ctx.save();
    // Crop face region
    const blurCanvas = document.createElement('canvas');
    blurCanvas.width = 8;
    blurCanvas.height = 8;
    const blurCtx = blurCanvas.getContext('2d');
    
    // Draw cropped region very small
    blurCtx.drawImage(ctx.canvas, x - size/2, y - size/2, size, size, 0, 0, 8, 8);
    
    // Draw back large, pixelated
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(blurCanvas, 0, 0, 8, 8, x - size/2, y - size/2, size, size);
    
    // Draw fine green reticle indicating blur active
    ctx.strokeStyle = 'rgba(0, 255, 0, 0.4)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x - size/2, y - size/2, size, size);
    ctx.fillStyle = 'rgba(0, 255, 0, 0.6)';
    ctx.font = "9px monospace";
    ctx.fillText("PRIVACY MASK", x - size/2 + 2, y - size/2 - 4);
    ctx.restore();
}

// Mock Simulation Feed Generator
function startSimulationLoop() {
    const canvas = document.getElementById('surveillance-canvas');
    const ctx = canvas.getContext('2d');
    const intervalMs = 1000 / config.sampleFps;
    
    state.simInterval = setInterval(() => {
        state.simFrameIndex++;
        
        // Draw background floor grid details based on selected camera
        ctx.fillStyle = '#080a0f';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.strokeStyle = '#18202d';
        ctx.lineWidth = 1;
        for (let x = 40; x < canvas.width; x += 40) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 40; y < canvas.height; y += 40) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }
        
        // Render room geometry outline depending on active camera to simulate authentic fields
        ctx.strokeStyle = '#22d3ee';
        ctx.lineWidth = 2.5;
        ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);
        
        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.font = "11px Outfit";
        
        // Customize simulated environments
        let actorX = 320;
        let actorY = 200;
        let showFaceMask = false;
        
        if (state.selectedCamera === 'CAM-01') {
            ctx.fillText("AREA: MAIN ENTRANCE ACC-1", 20, 30);
            ctx.strokeRect(150, 80, 100, 200); // Main doors
            ctx.fillStyle = 'rgba(34, 211, 238, 0.1)';
            ctx.fillRect(150, 80, 100, 200);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.fillText("[ACCESS HATCH GATE]", 155, 180);
            
            // Actor positions in Access gate
            actorX = 200 + Math.sin(state.simFrameIndex * 0.1) * 30;
            actorY = 180;
        } 
        else if (state.selectedCamera === 'CAM-02') {
            ctx.fillText("AREA: RECEPTION LOBBY FRONT", 20, 30);
            ctx.fillRect(100, 250, 440, 60); // Desk
            ctx.strokeStyle = '#475569';
            ctx.strokeRect(100, 250, 440, 60);
            ctx.fillText("[LOBBY DESK]", 290, 285);
            
            actorX = 320 + Math.cos(state.simFrameIndex * 0.08) * 80;
            actorY = 160;
        }
        else if (state.selectedCamera === 'CAM-03') {
            ctx.fillText("AREA: BACK LOADING DOCK ALLEY", 20, 30);
            ctx.strokeRect(40, 80, 80, 140); // Warehouse crates
            ctx.strokeRect(40, 230, 80, 100);
            ctx.fillText("[CRATES]", 55, 150);
            
            actorX = 420;
            actorY = 170 + Math.sin(state.simFrameIndex * 0.05) * 50;
        }
        else {
            ctx.fillText("AREA: PARKING LOT ROW C", 20, 30);
            ctx.strokeStyle = '#475569';
            // Draw car lanes
            ctx.strokeRect(50, 50, 120, 120);
            ctx.strokeRect(200, 50, 120, 120);
            ctx.fillText("[LANE 1]", 90, 110);
            ctx.fillText("[LANE 2]", 240, 110);
            
            actorX = 400 + Math.sin(state.simFrameIndex * 0.06) * 120;
            actorY = 260;
        }
        
        ctx.fillStyle = '#64748b';
        ctx.font = "10px monospace";
        ctx.fillText(`FEED FEED-MODE: ${state.cameraMode.toUpperCase()} | TIME-ALIGN: L-SECS`, 20, 340);
        
        // Scenario Graphic Animations
        if (state.simScenario === 'Normal') {
            // Calm single pedestrian walk
            let pedestrianX = (state.simFrameIndex * 3) % (canvas.width + 100) - 50;
            ctx.fillStyle = 'rgba(34, 211, 238, 0.4)';
            ctx.beginPath();
            ctx.arc(pedestrianX, 220, 16, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#22d3ee';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            
            showFaceMask = true;
            actorX = pedestrianX;
            actorY = 220;
        }
        else if (state.simScenario === 'Fighting') {
            // Frantic colliding vectors representing assault
            let drift1 = Math.sin(state.simFrameIndex * 0.9) * 35;
            let drift2 = Math.cos(state.simFrameIndex * 1.3) * 30;
            
            // Actor 1 (red)
            ctx.fillStyle = 'rgba(239, 68, 68, 0.6)';
            ctx.beginPath(); ctx.arc(actorX - 25 + drift1, actorY + drift2, 22, 0, Math.PI*2); ctx.fill();
            ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 3; ctx.stroke();
            
            // Actor 2 (orange)
            ctx.fillStyle = 'rgba(249, 115, 22, 0.6)';
            ctx.beginPath(); ctx.arc(actorX + 25 - drift1, actorY - drift2, 22, 0, Math.PI*2); ctx.fill();
            ctx.strokeStyle = '#f97316'; ctx.lineWidth = 3; ctx.stroke();
            
            // Flash points
            if (state.simFrameIndex % 2 === 0) {
                ctx.fillStyle = 'rgba(253, 224, 71, 0.4)';
                ctx.beginPath(); ctx.arc(actorX + (drift1-drift2)/2, actorY + (drift2-drift1)/2, 40, 0, Math.PI*2); ctx.fill();
            }
            
            ctx.fillStyle = '#ef4444';
            ctx.font = "bold 13px Outfit";
            ctx.fillText("CONFLICT TELEMETRY: HIGH CHAOS", actorX - 100, actorY - 50);
            
            showFaceMask = true; // Blur center of conflict
        }
        else if (state.simScenario === 'Weapons') {
            // Standing actor with highlighted weapon box
            ctx.fillStyle = 'rgba(239, 68, 68, 0.4)';
            ctx.beginPath();
            ctx.arc(actorX, actorY, 20, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2.5;
            ctx.stroke();
            
            // Gun outline highlighted
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            ctx.strokeRect(actorX + 15, actorY, 35, 20);
            ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
            ctx.fillRect(actorX + 15, actorY, 35, 20);
            ctx.fillStyle = '#ef4444';
            ctx.font = "10px monospace";
            ctx.fillText("WEAPON: DETECTED (0.94)", actorX + 15, actorY - 5);
            
            showFaceMask = true;
        }
        else if (state.simScenario === 'Falls') {
            // Fall simulation: actor drops suddenly
            let floorY = 280;
            let fallY = 120 + (state.simFrameIndex * 15) % 180;
            if (fallY > floorY - 10) {
                fallY = floorY; // Static collapsed posture
            }
            
            ctx.fillStyle = 'rgba(249, 115, 22, 0.5)';
            ctx.beginPath();
            if (fallY === floorY) {
                // Collapsed oval posture
                ctx.ellipse(actorX, floorY + 10, 35, 12, 0, 0, Math.PI * 2);
            } else {
                ctx.arc(actorX, fallY, 18, 0, Math.PI * 2);
            }
            ctx.fill();
            ctx.strokeStyle = '#f97316';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            if (fallY === floorY) {
                ctx.fillStyle = '#f97316';
                ctx.font = "bold 11px Outfit";
                ctx.fillText("TELEMETRY: RAPID HEIGHT COLLAPSE", actorX - 100, floorY - 20);
            }
            
            showFaceMask = (fallY !== floorY);
            actorY = fallY;
        }
        else if (state.simScenario === 'Trespass') {
            // Crawling dark circle encroaching Access Hatch
            let thiefX = 60 + (state.simFrameIndex * 2.5) % 160;
            ctx.fillStyle = 'rgba(30, 41, 59, 0.95)';
            ctx.beginPath();
            ctx.ellipse(thiefX, 180, 22, 12, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#eab308';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            ctx.fillStyle = '#eab308';
            ctx.font = "11px Outfit";
            ctx.fillText("HATCH ACCESS BREACH", 60, 140);
            
            // Draw restricted zone outline
            ctx.strokeStyle = 'rgba(234, 179, 8, 0.3)';
            ctx.lineWidth = 1;
            ctx.strokeRect(50, 120, 150, 100);
            
            actorX = thiefX;
            actorY = 180;
            showFaceMask = true;
        }
        else if (state.simScenario === 'Panic') {
            // Frantic multi circles moving at high speed
            ctx.fillStyle = 'rgba(234, 179, 8, 0.5)';
            for (let i = 0; i < 5; i++) {
                let px = 200 + i * 50 + Math.sin(state.simFrameIndex * 0.9 + i) * 35;
                let py = 150 + Math.cos(state.simFrameIndex * 0.8 + i) * 30;
                
                ctx.beginPath();
                ctx.arc(px, py, 12, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = '#eab308';
                ctx.stroke();
                
                if (privacyConfig.enable_face_blur) {
                    applyFaceBlur(ctx, px, py - 4, 18);
                }
            }
            ctx.fillStyle = '#eab308';
            ctx.font = "bold 12px Outfit";
            ctx.fillText("WARNING: CROWD VELOCITY SPIKE", 220, 90);
        }
        else if (state.simScenario === 'Abandoned') {
            // Standing pedestrian walk away, leaving red bounding box on shopping bag
            let walkerX = 280 + (state.simFrameIndex * 2) % 300;
            
            // Walker
            if (walkerX < canvas.width - 20) {
                ctx.fillStyle = 'rgba(34, 211, 238, 0.4)';
                ctx.beginPath(); ctx.arc(walkerX, 220, 15, 0, Math.PI * 2); ctx.fill();
                ctx.stroke();
                if (privacyConfig.enable_face_blur) {
                    applyFaceBlur(ctx, walkerX, 220, 25);
                }
            }
            
            // Stationary abandoned bag
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(260, 220, 16, 16);
            ctx.strokeStyle = '#3b82f6';
            ctx.strokeRect(260, 220, 16, 16);
            
            // Alert highlighting box
            ctx.strokeStyle = 'rgba(59, 130, 246, 0.7)';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(250, 210, 36, 36);
            
            ctx.fillStyle = '#3b82f6';
            ctx.font = "9px monospace";
            ctx.fillText("STATIONARY BAG: 120s", 225, 200);
        }
        
        // Global face blur overlay activation
        if (showFaceMask && privacyConfig.enable_face_blur) {
            applyFaceBlur(ctx, actorX, actorY - 8, 32);
        }
        
        // Global bystander outline masking
        if (privacyConfig.anonymize_bystanders && state.simScenario !== 'Normal') {
            // Draw dummy green skeleton outline for non-targets
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.3)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(120, 240); ctx.lineTo(120, 190);
            ctx.lineTo(110, 210); ctx.moveTo(120, 190); ctx.lineTo(130, 210);
            ctx.moveTo(120, 240); ctx.lineTo(115, 270); ctx.moveTo(120, 240); ctx.lineTo(125, 270);
            ctx.stroke();
            ctx.fillStyle = 'rgba(16, 185, 129, 0.4)';
            ctx.beginPath(); ctx.arc(120, 180, 8, 0, Math.PI * 2); ctx.fill();
        }
        
        updateWatermark();
        
        // Extract canvas image and send to backend API
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
        analyzeFrame(dataUrl);
    }, intervalMs);
}

function updateWatermark() {
    const watermark = document.getElementById('watermark-time');
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    watermark.textContent = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

// POST frame to backend and update diagnostics UI
function analyzeFrame(base64Image) {
    fetch(`${config.apiHost}/api/predict_frame`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: base64Image })
    })
    .then(res => {
        if (!res.ok) throw new Error("HTTP error " + res.status);
        return res.json();
    })
    .then(data => {
        updateDiagnostics(data);
    })
    .catch(err => {
        console.error("Frame prediction error:", err);
    });
}

function updateDiagnostics(data) {
    const scoreVal = document.getElementById('live-score-value');
    const scoreBar = document.getElementById('live-score-bar');
    const poseVal = document.getElementById('pose-score-value');
    const poseBar = document.getElementById('pose-score-bar');
    const audioVal = document.getElementById('audio-score-value');
    const audioBar = document.getElementById('audio-score-bar');
    
    const threatBadge = document.getElementById('live-threat-badge');
    const threatLabel = document.getElementById('live-threat-label');
    const cameraBox = document.querySelector('.camera-box.active');
    
    const score = data.anomaly_score;
    const isAnomaly = data.is_anomaly; // uses inference logic
    const category = data.category;
    const severity = data.severity;
    
    // 1. Update text score telemetry
    scoreVal.textContent = score.toFixed(2);
    scoreBar.style.width = `${score * 100}%`;
    
    const poseAnomaly = data.pose_anomaly || 0.02;
    poseVal.textContent = poseAnomaly.toFixed(2);
    poseBar.style.width = `${poseAnomaly * 100}%`;
    
    const audioAnomaly = data.audio_anomaly || 0.02;
    audioVal.textContent = audioAnomaly.toFixed(2);
    audioBar.style.width = `${audioAnomaly * 100}%`;
    
    // Severity border colors
    if (isAnomaly) {
        scoreVal.className = 'threat';
        scoreBar.className = `progress-bar-fill bg-severity-${severity.toLowerCase()}`;
        threatBadge.className = `detection-badge anomaly animate-flicker border-severity-${severity.toLowerCase()}`;
        threatLabel.textContent = `${category} (${severity})`;
        cameraBox.classList.add('anomaly-detected');
        
        // Check if we should fire alarm (Alerts trigger sound only for Critical/High)
        if (config.targetClasses.includes(category)) {
            triggerAlarm(category, score, severity);
        }
    } else {
        scoreVal.className = '';
        scoreBar.className = 'progress-bar-fill';
        threatBadge.className = "detection-badge";
        threatLabel.textContent = "Normal";
        cameraBox.classList.remove('anomaly-detected');
    }
    
    // 2. Scroll live chart data
    state.liveChartData.push(score);
    state.liveChartData.shift();
    state.poseChartData.push(poseAnomaly);
    state.poseChartData.shift();
    state.audioChartData.push(audioAnomaly);
    state.audioChartData.shift();
    
    state.liveChart.data.datasets[0].data = state.liveChartData;
    state.liveChart.data.datasets[1].data = state.poseChartData;
    state.liveChart.data.datasets[2].data = state.audioChartData;
    
    // Change line color based on alert
    state.liveChart.data.datasets[0].borderColor = isAnomaly ? '#ef4444' : '#00d2ff';
    state.liveChart.data.datasets[0].backgroundColor = isAnomaly ? 'rgba(239, 68, 68, 0.05)' : 'rgba(0, 210, 255, 0.05)';
    state.liveChart.update('none'); // Update without full animation for performance
    
    // 3. Update category probabilities list
    updateProbabilitiesList(data.category_probabilities, category);
}

function updateProbabilitiesList(probs, topClass) {
    const container = document.getElementById('class-probabilities-list');
    container.innerHTML = '';
    
    // Sort classes by probability descending
    const sorted = Object.entries(probs)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5); // top 5
        
    sorted.forEach(([name, val]) => {
        const isTop = name === topClass;
        const isAlertClass = name !== 'Normal';
        
        const row = document.createElement('div');
        row.className = `prob-row ${isTop ? 'active' : ''}`;
        
        let barClass = '';
        if (isTop) {
            barClass = isAlertClass ? 'alert-class' : 'high';
        }
        
        row.innerHTML = `
            <div class="prob-name-container">${name}</div>
            <div class="prob-bar-container">
                <div class="prob-bar-fill ${barClass}" style="width: ${val * 100}%"></div>
            </div>
            <div class="prob-val">${(val * 100).toFixed(0)}%</div>
        `;
        container.appendChild(row);
    });
}

// Alarm controls (Sirens, visual flashing, saving alert to server logs)
function triggerAlarm(category, score, severity) {
    // Show alarm banner only for Critical or High alerts to avoid warning fatigue
    if (severity === 'Critical' || severity === 'High') {
        const banner = document.getElementById('alarm-banner');
        banner.className = `alarm-banner active bg-severity-${severity.toLowerCase()}`;
        banner.style.display = 'flex';
        
        document.getElementById('alarm-title').textContent = `${severity.toUpperCase()} THREAT DETECTED: ${category.toUpperCase()}`;
        document.getElementById('alarm-desc').textContent = `${state.selectedCamera} is reporting classification of ${category} at ${(score * 100).toFixed(0)}% confidence index.`;
        
        // Play siren sound (siren sound only plays for Critical severity alerts)
        const audio = document.getElementById('siren-audio');
        if (config.audioAlert && !state.sirenPlaying && severity === 'Critical') {
            audio.play().then(() => {
                state.sirenPlaying = true;
            }).catch(err => console.log("Audio play blocked by browser:", err));
        }
    }
    
    // Check if we already logged this threat recently to avoid flooding
    const now = new Date();
    const lastAlert = state.alerts[0];
    if (lastAlert) {
        const diffSeconds = (now - new Date(lastAlert.timestamp)) / 1000;
        // Skip logging if same type was logged in the last 15 seconds
        if (lastAlert.type === category && lastAlert.camera_id.includes(state.selectedCamera) && diffSeconds < 15) {
            return;
        }
    }
    
    // Log alert to backend
    const alertData = {
        camera_id: state.selectedCamera,
        type: category,
        severity: severity,
        score: score,
        description: `Autonomous temporal GRU engine triggered a high-probability alert for ${category}.`
    };
    
    fetch(`${config.apiHost}/api/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alertData)
    })
    .then(res => res.json())
    .then(loggedAlert => {
        refreshAlerts();
        refreshStats();
        
        // Auto-record a 10s clip if configured
        if (config.autoRecord && !state.isRecordingClip && severity === 'Critical') {
            startRecording(loggedAlert.id);
        }
    })
    .catch(err => console.error("Failed to log alert to backend:", err));
}

function stopAlarm() {
    const banner = document.getElementById('alarm-banner');
    banner.classList.remove('active');
    banner.style.display = 'none';
    
    const audio = document.getElementById('siren-audio');
    audio.pause();
    audio.currentTime = 0;
    state.sirenPlaying = false;
}

// Operator confirm / dismiss feedback actions
window.handleOperatorAction = (alertId, action) => {
    fetch(`${config.apiHost}/api/alerts/${alertId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    })
    .then(res => res.json())
    .then(result => {
        console.log(`Alert ${alertId} was ${action} by operator:`, result);
        
        // Acknowledge banner and stop sound if this was the triggering alert
        stopAlarm();
        
        // Refresh alert views and statistics
        refreshAlerts();
        refreshStats();
    })
    .catch(err => console.error(`Error processing ${action} action:`, err));
};

// Fetch alerts and update tiered lists + history log
function refreshAlerts() {
    fetch(`${config.apiHost}/api/alerts`)
    .then(res => res.json())
    .then(data => {
        state.alerts = data;
        
        // 1. Separate alerts into queues: active critical vs active review list
        const criticalList = document.getElementById('critical-alert-list');
        const reviewList = document.getElementById('review-alert-list');
        
        criticalList.innerHTML = '';
        reviewList.innerHTML = '';
        
        const activeCriticalAlerts = data.filter(a => a.status === 'Logged' && a.severity === 'Critical');
        const activeReviewAlerts = data.filter(a => a.status === 'Logged' && (a.severity === 'High' || a.severity === 'Medium'));
        
        // Update facility map nodes styling
        updateFacilityMapNodes(data.filter(a => a.status === 'Logged'));
        
        if (activeCriticalAlerts.length === 0) {
            criticalList.innerHTML = `<p class="empty-placeholder">No active critical threats.</p>`;
        } else {
            activeCriticalAlerts.forEach(alert => {
                const card = document.createElement('div');
                card.className = "alert-queue-card critical animate-pulse-glow";
                card.innerHTML = `
                    <div class="card-details">
                        <div class="card-title-row">
                            <span class="threat-badge bg-severity-critical">${alert.type}</span>
                            <span class="conf">Score: ${(alert.score*100).toFixed(0)}%</span>
                        </div>
                        <p class="desc">${alert.description}</p>
                        <p class="meta"><i class="fa-solid fa-clock"></i> ${alert.timestamp} | <strong>${alert.location}</strong></p>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-xs btn-green" onclick="handleOperatorAction('${alert.id}', 'Confirmed')" title="Confirm Threat"><i class="fa-solid fa-check"></i> Confirm</button>
                        <button class="btn btn-xs btn-outline-red" onclick="handleOperatorAction('${alert.id}', 'Dismissed')" title="Dismiss False Alarm"><i class="fa-solid fa-xmark"></i> Dismiss</button>
                        <button class="btn btn-xs btn-primary" onclick="jumpToCameraFeed('${alert.camera_id}')" title="Jump to Feed"><i class="fa-solid fa-arrow-right-to-bracket"></i> Live Feed</button>
                    </div>
                `;
                criticalList.appendChild(card);
            });
        }
        
        if (activeReviewAlerts.length === 0) {
            reviewList.innerHTML = `<p class="empty-placeholder">No review alerts in queue.</p>`;
        } else {
            activeReviewAlerts.forEach(alert => {
                const card = document.createElement('div');
                card.className = `alert-queue-card ${alert.severity.toLowerCase()}`;
                card.innerHTML = `
                    <div class="card-details">
                        <div class="card-title-row">
                            <span class="threat-badge bg-severity-${alert.severity.toLowerCase()}">${alert.type}</span>
                            <span class="conf">Score: ${(alert.score*100).toFixed(0)}%</span>
                        </div>
                        <p class="desc">${alert.description}</p>
                        <p class="meta"><i class="fa-solid fa-clock"></i> ${alert.timestamp} | <strong>${alert.location}</strong></p>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-xs btn-green" onclick="handleOperatorAction('${alert.id}', 'Confirmed')" title="Confirm"><i class="fa-solid fa-check"></i> Confirm</button>
                        <button class="btn btn-xs btn-outline-red" onclick="handleOperatorAction('${alert.id}', 'Dismissed')" title="Dismiss"><i class="fa-solid fa-xmark"></i> Dismiss</button>
                        <button class="btn btn-xs btn-outline" onclick="jumpToCameraFeed('${alert.camera_id}')" title="Live Feed"><i class="fa-solid fa-eye"></i> View</button>
                    </div>
                `;
                reviewList.appendChild(card);
            });
        }
        
        // 2. Render History logs table
        renderHistoryTable();
    })
    .catch(err => console.error("Failed to load alerts:", err));
}

// Periodic lightweight update of alert table only
function refreshAlertsTableOnly() {
    fetch(`${config.apiHost}/api/alerts`)
    .then(res => res.json())
    .then(data => {
        state.alerts = data;
        renderHistoryTable();
    })
    .catch(err => console.error("Failed to update alert table:", err));
}

// Update SVG map node highlighting
function updateFacilityMapNodes(activeAlerts) {
    const cameras = ['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'];
    cameras.forEach(cam => {
        const camIdx = parseInt(cam.replace('CAM-0', ''));
        const node = document.getElementById(`map-node-cam${camIdx}`);
        if (!node) return;
        
        const circle = node.querySelector('.node-circle');
        
        // Find highest severity active alert for this camera
        const camAlerts = activeAlerts.filter(a => a.camera_id.includes(cam));
        if (camAlerts.length === 0) {
            circle.className.baseVal = "node-circle bg-normal";
            circle.style.animation = "none";
        } else {
            // Sort by severity (Critical > High > Medium > Low)
            const severities = ['Low', 'Medium', 'High', 'Critical'];
            camAlerts.sort((a,b) => severities.indexOf(b.severity) - severities.indexOf(a.severity));
            const topSeverity = camAlerts[0].severity.toLowerCase();
            
            circle.className.baseVal = `node-circle bg-severity-${topSeverity}`;
            circle.style.animation = "mapPulse 1.2s infinite ease-in-out";
        }
    });
}

// Render historical logs table with search & filters
function renderHistoryTable() {
    const tbody = document.getElementById('alert-table-body');
    tbody.innerHTML = '';
    
    // Get filter inputs
    const query = document.getElementById('log-search-input').value.toLowerCase();
    const severityFilter = document.getElementById('log-severity-filter').value;
    const statusFilter = document.getElementById('log-status-filter').value;
    
    // Apply filters
    const filtered = state.alerts.filter(alert => {
        const matchesQuery = !query || 
            alert.camera_id.toLowerCase().includes(query) || 
            alert.location.toLowerCase().includes(query) ||
            alert.type.toLowerCase().includes(query) ||
            alert.description.toLowerCase().includes(query);
            
        const matchesSeverity = severityFilter === 'ALL' || alert.severity === severityFilter;
        const matchesStatus = statusFilter === 'ALL' || alert.status === statusFilter;
        
        return matchesQuery && matchesSeverity && matchesStatus;
    });
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding:30px; text-align:center; color:var(--text-muted);">No logs matching search criteria.</td></tr>`;
        return;
    }
    
    filtered.forEach(alert => {
        const isCritical = alert.severity === 'Critical';
        const tr = document.createElement('tr');
        if (isCritical && alert.status === 'Logged') tr.className = "critical-row";
        
        let actionHtml = `
            <button class="btn-action-icon" onclick="viewAlertDetails('${alert.id}')" title="Inspect Details">
                <i class="fa-solid fa-circle-info"></i>
            </button>
        `;
        
        if (alert.clip_url) {
            actionHtml += `
                <button class="btn-action-icon" onclick="playAlertClip('${alert.clip_url}', '${alert.type}', '${alert.timestamp}', '${alert.camera_id}')" title="Play Recorded Clip" style="color:var(--accent-blue); margin-left: 10px;">
                    <i class="fa-solid fa-circle-play"></i>
                </button>
            `;
        }
        
        // Add confirm / dismiss icons direct in table if it's logged
        if (alert.status === 'Logged') {
            actionHtml += `
                <button class="btn-action-icon" onclick="handleOperatorAction('${alert.id}', 'Confirmed')" title="Confirm Threat" style="color:var(--accent-green); margin-left: 10px;">
                    <i class="fa-solid fa-circle-check"></i>
                </button>
                <button class="btn-action-icon" onclick="handleOperatorAction('${alert.id}', 'Dismissed')" title="Dismiss False Alarm" style="color:var(--accent-red); margin-left: 10px;">
                    <i class="fa-solid fa-circle-xmark"></i>
                </button>
            `;
        }
        
        tr.innerHTML = `
            <td>${alert.timestamp}</td>
            <td>${alert.camera_id}</td>
            <td>${alert.location}</td>
            <td><span class="badge-threat border-severity-${alert.severity.toLowerCase()}">${alert.type}</span></td>
            <td><span class="severity-badge-text text-severity-${alert.severity.toLowerCase()}">${alert.severity}</span></td>
            <td><span class="score-text ${isCritical ? 'high' : 'medium'}">${alert.score.toFixed(2)}</span></td>
            <td><span class="status-badge ${alert.status.toLowerCase()}">${alert.status}</span></td>
            <td>${actionHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Clear alert history
document.getElementById('btn-clear-alerts').addEventListener('click', () => {
    if (confirm("Are you sure you want to clear threat logs? Active Logged threats will be deleted.")) {
        state.alerts = [];
        const tbody = document.getElementById('alert-table-body');
        tbody.innerHTML = `<tr><td colspan="8" style="padding:30px; text-align:center; color:var(--text-muted);">No threat logs recorded in database.</td></tr>`;
        stopAlarm();
        refreshAlerts();
    }
});

// Bind search and filter events
document.getElementById('log-search-input').addEventListener('input', renderHistoryTable);
document.getElementById('log-severity-filter').addEventListener('change', renderHistoryTable);
document.getElementById('log-status-filter').addEventListener('change', renderHistoryTable);

window.viewAlertDetails = (id) => {
    const alert = state.alerts.find(a => a.id === id);
    if (alert) {
        // Render alert details in a neat pop-up dialog
        alert(JSON.stringify(alert, null, 2));
    }
};

// Forensic Video Upload & Timeline Analysis
function initVideoUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('video-file-input');
    
    // Drag and drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        }, false);
    });
    
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleVideoUpload(files[0]);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (fileInput.files.length > 0) {
            handleVideoUpload(fileInput.files[0]);
        }
    });
}

function handleVideoUpload(file) {
    if (!file.type.startsWith('video/')) {
        alert("Invalid file format. Please upload a valid video file.");
        return;
    }
    
    const dropZone = document.getElementById('drop-zone');
    const statusDiv = document.getElementById('upload-status');
    const progressBar = document.getElementById('upload-progress-bar');
    
    dropZone.style.display = 'none';
    statusDiv.style.display = 'flex';
    progressBar.style.width = '0%';
    
    const formData = new FormData();
    formData.append('file', file);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${config.apiHost}/api/analyze_video`, true);
    
    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 90;
            progressBar.style.width = `${percent}%`;
        }
    };
    
    xhr.onload = () => {
        progressBar.style.width = '100%';
        if (xhr.status === 200) {
            const result = JSON.parse(xhr.responseText);
            displayForensicResults(result);
        } else {
            alert("Video analysis failed. Please check backend logs.");
            dropZone.style.display = 'flex';
            statusDiv.style.display = 'none';
        }
    };
    
    xhr.onerror = () => {
        alert("Connection lost. Backend server is unreachable.");
        dropZone.style.display = 'flex';
        statusDiv.style.display = 'none';
    };
    
    xhr.send(formData);
}

function displayForensicResults(data) {
    document.getElementById('upload-status').style.display = 'none';
    document.getElementById('timeline-instructions').style.display = 'none';
    
    document.getElementById('video-playback-container').style.display = 'block';
    document.getElementById('analysis-results-container').style.display = 'block';
    
    const player = document.getElementById('analyzed-video-player');
    player.src = `${config.apiHost}${data.video_url}`;
    player.load();
    
    document.getElementById('res-duration').textContent = `${data.duration.toFixed(1)}s`;
    document.getElementById('res-max-score').textContent = data.max_anomaly_score.toFixed(2);
    document.getElementById('res-incidents-count').textContent = data.anomalous_segments.length;
    
    renderTimelineChart(data.timeline, player);
    renderIncidentList(data.anomalous_segments, player);
}

function renderTimelineChart(timeline, player) {
    const ctx = document.getElementById('video-timeline-chart').getContext('2d');
    
    if (state.timelineChart) {
        state.timelineChart.destroy();
    }
    
    const labels = timeline.map(t => t.timestamp.toFixed(1) + 's');
    const scores = timeline.map(t => t.prediction.anomaly_score);
    const classes = timeline.map(t => t.prediction.category);
    
    state.timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Anomaly Index',
                data: scores,
                borderColor: '#00d2ff',
                borderWidth: 2,
                backgroundColor: 'rgba(0, 210, 255, 0.04)',
                fill: true,
                tension: 0.2,
                pointRadius: 2,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const val = context.parsed.y;
                            const cat = classes[context.dataIndex];
                            return `Score: ${val.toFixed(2)} (${cat})`;
                        }
                    }
                }
            },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const timestamp = timeline[idx].timestamp;
                    player.currentTime = timestamp;
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 1.0,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8c9ba5' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8c9ba5', maxTicksLimit: 10 }
                }
            }
        }
    });
    
    const overlayBadge = document.getElementById('video-overlay-badge');
    player.ontimeupdate = () => {
        const time = player.currentTime;
        let closest = timeline[0];
        let minDiff = Infinity;
        
        timeline.forEach(t => {
            let diff = Math.abs(t.timestamp - time);
            if (diff < minDiff) {
                minDiff = diff;
                closest = t;
            }
        });
        
        if (closest && closest.prediction.anomaly_score > config.threshold) {
            overlayBadge.className = `overlay-badge threat border-severity-${closest.prediction.severity.toLowerCase()}`;
            overlayBadge.textContent = `${closest.prediction.category} (${closest.prediction.severity})`;
        } else {
            overlayBadge.className = "overlay-badge normal";
            overlayBadge.textContent = "Normal";
        }
    };
}

function renderIncidentList(segments, player) {
    const list = document.getElementById('incident-list');
    list.innerHTML = '';
    
    if (segments.length === 0) {
        list.innerHTML = `<p class="text-muted" style="text-align:center; padding: 20px 0;">No crime/anomalies detected in this video.</p>`;
        return;
    }
    
    segments.forEach(seg => {
        const item = document.createElement('div');
        item.className = "incident-item";
        item.innerHTML = `
            <div class="incident-details">
                <div class="incident-bullet bg-severity-${seg.severity.toLowerCase()}"></div>
                <div>
                    <span class="incident-class">${seg.type} (${seg.severity})</span>
                    <p class="text-muted" style="font-size:11px;">Surveillance Event Detected</p>
                </div>
            </div>
            <div class="incident-action">
                <span class="incident-time">${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s</span>
                <i class="fa-solid fa-play ml-2"></i>
            </div>
        `;
        
        item.addEventListener('click', () => {
            player.currentTime = seg.start;
            player.play();
        });
        
        list.appendChild(item);
    });
}

// Analytics Trends & Distribution
function refreshStats() {
    fetch(`${config.apiHost}/api/stats`)
    .then(res => res.json())
    .then(data => {
        document.getElementById('stat-total-alerts').textContent = data.total_alerts;
        document.getElementById('stat-feedback-size').textContent = data.feedback_size + " Samples";
        
        // Update stats progress bar
        document.getElementById('fb-metric-handled').textContent = data.total_alerts;
        document.getElementById('fb-metric-confirmed').textContent = data.confirmed_count;
        document.getElementById('fb-metric-dismissed').textContent = data.dismissed_count;
        
        const countProgress = data.feedback_size;
        const progressPercent = Math.min(100, (countProgress / 100) * 100);
        document.getElementById('feedback-progress-txt').textContent = `${countProgress} / 100 Samples`;
        document.getElementById('feedback-progress-bar').style.width = `${progressPercent}%`;
    })
    .catch(err => console.error("Error refreshing stats:", err));
}

function refreshAnalyticsCharts() {
    fetch(`${config.apiHost}/api/stats`)
    .then(res => res.json())
    .then(data => {
        renderTrendChart(data.weekly_history);
        renderDistributionChart(data.anomaly_counts);
    })
    .catch(err => console.error("Error loading analytics:", err));
}

function renderTrendChart(weekly) {
    const ctx = document.getElementById('analytics-trend-chart').getContext('2d');
    if (state.analyticsTrendChart) {
        state.analyticsTrendChart.destroy();
    }
    
    state.analyticsTrendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: weekly.labels,
            datasets: [{
                label: 'Threats Logged',
                data: weekly.counts,
                backgroundColor: 'rgba(0, 210, 255, 0.4)',
                borderColor: '#00d2ff',
                borderWidth: 1.5,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8c9ba5', stepSize: 1 }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8c9ba5' }
                }
            }
        }
    });
}

function renderDistributionChart(counts) {
    const ctx = document.getElementById('analytics-dist-chart').getContext('2d');
    if (state.analyticsDistChart) {
        state.analyticsDistChart.destroy();
    }
    
    const labels = Object.keys(counts);
    const vals = Object.values(counts);
    
    state.analyticsDistChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: vals,
                backgroundColor: [
                    '#ef4444', // Fighting - Red
                    '#f97316', // Falls - Orange
                    '#eab308', // Trespass - Yellow
                    '#3b82f6', // Abandoned - Blue
                    '#a855f7', // Weapons - Purple
                    '#38bdf8', // Burglary
                    '#f43f5e', // Vandalism
                    '#8b5cf6', // RoadAccident
                    '#64748b'  // Other - Grey
                ],
                borderWidth: 1,
                borderColor: '#11141b'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#8c9ba5', font: { family: 'Inter' } }
                }
            }
        }
    });
}

// Settings Forms
function initSettingsForm() {
    const slider = document.getElementById('threshold-slider');
    const val = document.getElementById('threshold-val');
    
    slider.addEventListener('input', () => {
        val.textContent = slider.value;
    });
    
    // Build check grid for target alert classes
    const grid = document.getElementById('class-filter-grid');
    grid.innerHTML = '';
    
    ALL_CATEGORIES.forEach(cat => {
        if (cat === 'Normal') return; // Skip normal
        
        const isChecked = config.targetClasses.includes(cat);
        const item = document.createElement('label');
        item.className = "checkbox-item";
        item.innerHTML = `
            <input type="checkbox" value="${cat}" ${isChecked ? 'checked' : ''} />
            <span>${cat}</span>
        `;
        grid.appendChild(item);
    });
    
    // Save settings button
    document.getElementById('btn-save-settings').addEventListener('click', () => {
        config.threshold = parseFloat(slider.value);
        config.sampleFps = parseInt(document.getElementById('sample-fps-select').value);
        config.audioAlert = document.getElementById('audio-alarm-switch').checked;
        config.autoRecord = document.getElementById('auto-record-chk').checked;
        
        const checkedClasses = [];
        grid.querySelectorAll('input:checked').forEach(input => {
            checkedClasses.push(input.value);
        });
        config.targetClasses = checkedClasses;
        
        localStorage.setItem('guardian_ai_config', JSON.stringify(config));
        
        // Save Privacy config to backend
        const privData = {
            enable_face_blur: document.getElementById('privacy-face-blur').checked,
            anonymize_bystanders: document.getElementById('privacy-anonymize').checked,
            retention_days: parseInt(document.getElementById('privacy-retention').value)
        };
        
        fetch(`${config.apiHost}/api/privacy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(privData)
        })
        .then(res => res.json())
        .then(resData => {
            privacyConfig = resData.privacy_config;
            alert("System configurations and data privacy parameters updated successfully.");
            switchCameraMode(state.cameraMode);
        })
        .catch(err => console.error("Error saving privacy configurations:", err));
    });
    
    document.getElementById('btn-reset-settings').addEventListener('click', () => {
        if (confirm("Restore default parameters?")) {
            localStorage.removeItem('guardian_ai_config');
            location.reload();
        }
    });
    
    document.getElementById('audio-alarm-switch').addEventListener('change', (e) => {
        config.audioAlert = e.target.checked;
        if (!config.audioAlert) {
            stopAlarm();
        }
    });
}

// Media Recording & Alert Playback functions
function getSurveillanceStream() {
    if (state.cameraMode === 'webcam' && state.webcamStream) {
        return state.webcamStream;
    } else {
        const canvas = document.getElementById('surveillance-canvas');
        return canvas.captureStream(20);
    }
}

function startRecording(alertId) {
    if (state.isRecordingClip) return;
    
    state.isRecordingClip = true;
    state.recordedChunks = [];
    state.clipSecondsElapsed = 0;
    
    const badge = document.getElementById('recording-clip-badge');
    const timerText = document.getElementById('recording-clip-timer');
    badge.style.display = 'flex';
    timerText.textContent = "REC: 0s";
    
    state.clipTimer = setInterval(() => {
        state.clipSecondsElapsed++;
        timerText.textContent = `REC: ${state.clipSecondsElapsed}s`;
    }, 1000);
    
    const stream = getSurveillanceStream();
    let options = {};
    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) {
        options = { mimeType: 'video/webm;codecs=vp8' };
    }
    
    try {
        state.mediaRecorder = new MediaRecorder(stream, options);
    } catch (e) {
        console.warn("MediaRecorder creation failed, fallback:", e);
        state.mediaRecorder = new MediaRecorder(stream);
    }
    
    state.mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
            state.recordedChunks.push(event.data);
        }
    };
    
    state.mediaRecorder.onstop = () => {
        clearInterval(state.clipTimer);
        badge.style.display = 'none';
        
        const blob = new Blob(state.recordedChunks, { type: 'video/webm' });
        uploadClipBlob(blob, alertId);
    };
    
    state.mediaRecorder.start();
    console.log(`Started recording 10s crime clip for Alert: ${alertId}`);
    
    setTimeout(() => {
        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
            state.mediaRecorder.stop();
            state.isRecordingClip = false;
        }
    }, 10000);
}

function uploadClipBlob(blob, alertId) {
    const formData = new FormData();
    formData.append('file', blob, `alert_${alertId}.webm`);
    formData.append('alert_id', alertId);
    
    fetch(`${config.apiHost}/api/upload_clip`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(result => {
        console.log("Alert clip uploaded and saved:", result);
        refreshAlerts();
    })
    .catch(err => {
        console.error("Failed to upload alert video clip:", err);
    });
}

window.playAlertClip = (url, type, timestamp, camId) => {
    const modal = document.getElementById('clip-modal');
    const player = document.getElementById('clip-modal-player');
    const meta = document.getElementById('clip-modal-metadata');
    
    player.src = `${config.apiHost}${url}`;
    meta.textContent = `Incident: ${type} | Detected: ${timestamp} | Source: ${camId}`;
    modal.style.display = 'flex';
    player.play();
};

function closeClipModal() {
    const modal = document.getElementById('clip-modal');
    const player = document.getElementById('clip-modal-player');
    player.pause();
    player.src = '';
    modal.style.display = 'none';
}
