document.addEventListener('DOMContentLoaded', function () {
    const dailyCtx = document.getElementById('dailyChart');
    const weeklyCtx = document.getElementById('weeklyChart');
    const weeklyAvgCtx = document.getElementById('weeklyAvgChart');
    const monthlyAvgCtx = document.getElementById('monthlyAvgChart');
    const dailyLineCtx = document.getElementById('dailyLineChart');
    const monthlyLineCtx = document.getElementById('monthlyLineChart');
    const dailyAvgCtx = document.getElementById('dailyAvgChart');
    const miniDailyAvgCtx = document.getElementById('miniDailyAvgChart');
    const miniWeeklyAvgCtx = document.getElementById('miniWeeklyAvgChart');
    const miniMonthlyAvgCtx = document.getElementById('miniMonthlyAvgChart');

    function createChart(ctx, type, labels, data, label, options = {}) {
        if (!ctx) return null;

        const defaultStyles = {
            label: label,
            data: data,
            backgroundColor: type === 'bar'
                ? 'rgba(59, 130, 246, 0.35)'
                : 'rgba(37, 99, 235, 0.2)',
            borderColor: 'rgba(37, 99, 235, 1)',
            borderWidth: 2,
            fill: type !== 'bar',
            tension: 0.35,
            pointRadius: type === 'bar' ? 0 : 4,
            borderRadius: type === 'bar' ? 12 : 0,
            maxBarThickness: type === 'bar' ? 36 : undefined,
        };

        return new Chart(ctx, {
            type: type,
            data: {
                labels: labels,
                datasets: [defaultStyles],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: 10 },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 8,
                            font: { size: 11 },
                            color: '#4b5563',
                        },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#e5e7eb' },
                        ticks: {
                            maxTicksLimit: 5,
                            padding: 8,
                            font: { size: 11 },
                            color: '#4b5563',
                        },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { mode: 'index', intersect: false, padding: 10 },
                    ...options.plugins,
                },
                ...options,
            },
        });
    }

    function readChartData(id) {
        const container = document.getElementById(id);
        if (!container) return null;
        return {
            labels: JSON.parse(container.dataset.labels || '[]'),
            values: JSON.parse(container.dataset.values || '[]'),
        };
    }

    const dailyData = readChartData('dailyChart');
    const weeklyData = readChartData('weeklyChart');
    const weeklyAvgData = readChartData('weeklyAvgChart');
    const monthlyAvgData = readChartData('monthlyAvgChart');
    const dailyLineData = readChartData('dailyLineChart');
    const monthlyLineData = readChartData('monthlyLineChart');
    const dailyAvgData = readChartData('dailyAvgChart');

    const durationHistogramCtx = document.getElementById('durationHistogramChart');
    const durationHistogramData = readChartData('durationHistogramChart');
    const miniDailyAvgData = readChartData('miniDailyAvgChart');
    const miniWeeklyAvgData = readChartData('miniWeeklyAvgChart');
    const miniMonthlyAvgData = readChartData('miniMonthlyAvgChart');

    createChart(dailyCtx, 'line', dailyData?.labels || [], dailyData?.values || [], 'Daily Sessions');
    createChart(weeklyCtx, 'bar', weeklyData?.labels || [], weeklyData?.values || [], 'Weekly Sessions');
    createChart(weeklyAvgCtx, 'bar', weeklyAvgData?.labels || [], weeklyAvgData?.values || [], 'Weekly Avg Minutes', {
        plugins: {
            tooltip: { callbacks: { label: (context) => `${context.parsed.y} min` } },
        },
    });
    createChart(monthlyAvgCtx, 'bar', monthlyAvgData?.labels || [], monthlyAvgData?.values || [], 'Monthly Avg Minutes', {
        plugins: {
            tooltip: { callbacks: { label: (context) => `${context.parsed.y} min` } },
        },
    });
    createChart(durationHistogramCtx, 'bar', durationHistogramData?.labels || [], durationHistogramData?.values || [], 'Session Duration Distribution', {
        plugins: {
            tooltip: { callbacks: { label: (context) => `${context.parsed.y} sessions` } },
        },
    });
    createChart(dailyLineCtx, 'line', dailyLineData?.labels || [], dailyLineData?.values || [], 'Daily Trend');
    createChart(dailyAvgCtx, 'bar', dailyAvgData?.labels || [], dailyAvgData?.values || [], 'Daily Avg Minutes', {
        plugins: {
            tooltip: { callbacks: { label: (context) => `${context.parsed.y} min` } },
        },
    });
    createChart(monthlyLineCtx, 'line', monthlyLineData?.labels || [], monthlyLineData?.values || [], 'Monthly Trend');
    createChart(miniDailyAvgCtx, 'line', miniDailyAvgData?.labels || [], miniDailyAvgData?.values || [], 'Daily Avg', {
        scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
        elements: { point: { radius: 0 }, line: { tension: 0.35 } },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
    });
    createChart(miniWeeklyAvgCtx, 'line', miniWeeklyAvgData?.labels || [], miniWeeklyAvgData?.values || [], 'Weekly Avg', {
        scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
        elements: { point: { radius: 0 }, line: { tension: 0.35 } },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
    });
    createChart(miniMonthlyAvgCtx, 'line', miniMonthlyAvgData?.labels || [], miniMonthlyAvgData?.values || [], 'Monthly Avg', {
        scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
        elements: { point: { radius: 0 }, line: { tension: 0.35 } },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
    });
    async function updateCameraDeviceList() {
        const cameraSelect = document.getElementById('cameraSelect');
        const cameraStatus = document.getElementById('cameraStatus');

        if (!cameraSelect || !cameraStatus) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            cameraStatus.textContent = 'Camera access is not supported by this browser.';
            return;
        }

        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoInputs = devices.filter(device => device.kind === 'videoinput');
            cameraSelect.innerHTML = '';

            if (videoInputs.length === 0) {
                cameraSelect.innerHTML = '<option value="">No camera detected</option>';
                cameraStatus.textContent = 'No video input devices found.';
                return;
            }

            videoInputs.forEach((device, index) => {
                const option = document.createElement('option');
                option.value = device.deviceId;
                option.textContent = device.label || `Camera ${index + 1}`;
                cameraSelect.appendChild(option);
            });

            cameraStatus.textContent = 'Select a camera and click Connect.';
        } catch (error) {
            cameraStatus.textContent = `Unable to enumerate cameras: ${error.message}`;
            console.error('Camera enumeration error:', error);
        }
    }

    let cameraStream = null;

    async function connectSelectedCamera() {
        const cameraSelect = document.getElementById('cameraSelect');
        const cameraPreview = document.getElementById('cameraPreview');
        const cameraStatus = document.getElementById('cameraStatus');

        if (!cameraSelect || !cameraPreview || !cameraStatus) return;

        const selectedDeviceId = cameraSelect.value;
        if (!selectedDeviceId) {
            cameraStatus.textContent = 'Please select a camera device first.';
            return;
        }

        stopCameraStream();
        cameraStatus.textContent = 'Connecting to selected camera...';

        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { deviceId: { exact: selectedDeviceId } },
                audio: false,
            });
            cameraPreview.srcObject = cameraStream;
            cameraStatus.textContent = `Connected to ${cameraSelect.selectedOptions[0]?.textContent || 'selected camera'}.`;
        } catch (error) {
            cameraStatus.textContent = `Camera connection failed: ${error.message}`;
            console.error('Camera connection error:', error);
        }
    }

    function stopCameraStream() {
        const cameraPreview = document.getElementById('cameraPreview');
        const cameraStatus = document.getElementById('cameraStatus');

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }

        if (cameraPreview) {
            cameraPreview.srcObject = null;
        }

        if (cameraStatus) {
            cameraStatus.textContent = 'Camera stopped.';
        }
    }

    const cameraConnectButton = document.getElementById('cameraConnectButton');
    const cameraStopButton = document.getElementById('cameraStopButton');

    if (cameraConnectButton) {
        cameraConnectButton.addEventListener('click', connectSelectedCamera);
    }

    if (cameraStopButton) {
        cameraStopButton.addEventListener('click', stopCameraStream);
    }

    if (document.getElementById('cameraSelect')) {
        updateCameraDeviceList();
    }});
