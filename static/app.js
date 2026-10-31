// VORTEX SUITE — Enterprise Frontend Controller
// Features: Client-Side TOTP, Multi-Phone Live Fleet Telemetry, 300 Batch Auto Recovery Engine

let accountsData = [];
let screenStreaming = true;
let hasConnectedDevice = false;

// ─── RFC 6238 TOTP (Client-Side — Zero HTTP Server Overhead) ─────────────────
async function generateTOTP(base32Secret) {
    if (!base32Secret) return { code: "------", remaining: 0 };

    try {
        const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
        const cleaned = base32Secret.replace(/\s/g, "").toUpperCase();
        let bits = 0, val = 0;
        const bytes = [];
        for (const char of cleaned) {
            const idx = alphabet.indexOf(char);
            if (idx === -1) continue;
            val = (val << 5) | idx;
            bits += 5;
            if (bits >= 8) {
                bytes.push((val >>> (bits - 8)) & 0xFF);
                bits -= 8;
            }
        }
        const keyBytes = new Uint8Array(bytes);

        const epoch = Math.floor(Date.now() / 1000);
        const interval = 30;
        const counter = Math.floor(epoch / interval);
        const remaining = interval - (epoch % interval);

        const counterBuffer = new ArrayBuffer(8);
        const counterView = new DataView(counterBuffer);
        counterView.setUint32(4, counter, false);

        const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
        const sig = await crypto.subtle.sign("HMAC", key, counterBuffer);
        const hmac = new Uint8Array(sig);

        const offset = hmac[19] & 0x0F;
        const code = (
            ((hmac[offset] & 0x7F) << 24) |
            ((hmac[offset + 1] & 0xFF) << 16) |
            ((hmac[offset + 2] & 0xFF) << 8) |
            (hmac[offset + 3] & 0xFF)
        ) % 1000000;

        return { code: String(code).padStart(6, "0"), remaining };
    } catch (e) {
        return { code: "ERR32", remaining: 0 };
    }
}
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    fetchDeviceTelemetry();
    fetchIxBrowserStatus();
    fetchAccounts();
    fetchStateLogs();
    fetchBatchStatus();

    // Polling intervals
    setInterval(fetchBatchStatus, 1500);
    setInterval(fetchDeviceTelemetry, 3500);
    setInterval(fetchIxBrowserStatus, 5000);
    setInterval(fetchAccounts, 5000);
    setInterval(fetchStateLogs, 2000);
    setInterval(refreshScreenMirror, 2500);
});

// ─── 🚀 Batch Auto Recovery Controls ─────────────────────────────────────────
async function fetchBatchStatus() {
    try {
        const res = await fetch("/api/batch/status");
        const data = await res.json();

        const badge = document.getElementById("batchStateBadge");
        const dot = document.getElementById("batchDot");
        const pBar = document.getElementById("batchProgressBar");
        const pTxt = document.getElementById("batchProgressTxt");
        const rTxt = document.getElementById("batchRecoveredTxt");
        const fTxt = document.getElementById("batchFailedTxt");
        const curEmail = document.getElementById("batchCurrentEmail");
        const curLane = document.getElementById("batchCurrentLane");

        const btnStart = document.getElementById("btnBatchStart");
        const btnPause = document.getElementById("btnBatchPause");
        const btnResume = document.getElementById("btnBatchResume");
        const btnStop = document.getElementById("btnBatchStop");

        badge.innerText = data.state;
        badge.className = `status-tag ${data.state === 'RUNNING' ? 'RECOVERED' : (data.state === 'PAUSED' ? 'PENDING' : '')}`;

        dot.className = `batch-pulse-dot ${data.state === 'RUNNING' ? 'running' : (data.state === 'PAUSED' ? 'paused' : '')}`;

        pBar.style.width = `${data.progress_pct || 0}%`;
        pTxt.innerText = `${data.processed} / ${data.total} (${data.progress_pct || 0}%)`;
        rTxt.innerText = data.recovered;
        fTxt.innerText = data.failed;
        curEmail.innerText = data.current_email || "Standby";
        curLane.innerText = `${data.current_lane || 'Standby'} ${data.current_device ? '• ' + data.current_device : ''}`;

        // Render active parallel workers
        const workersBox = document.getElementById("activeWorkersContainer");
        if (workersBox && data.active_workers) {
            if (data.active_workers.length === 0) {
                workersBox.innerHTML = "";
            } else {
                workersBox.innerHTML = data.active_workers.map(w => `
                    <div style="background:rgba(0, 242, 254, 0.08); border:1px solid rgba(0, 242, 254, 0.25); border-radius:6px; padding:0.35rem 0.6rem; font-size:0.75rem; display:flex; align-items:center; gap:0.5rem;">
                        <span style="font-weight:700; color:var(--accent-cyan);">Worker #${w.worker_id + 1}</span>
                        <span style="font-family:var(--font-mono); color:#fff;">${escapeHtml(w.email)}</span>
                        <span style="color:var(--text-muted);">[${escapeHtml(w.lane)}]</span>
                        <span style="background:rgba(16, 185, 129, 0.2); color:#10B981; padding:1px 5px; border-radius:4px; font-weight:600;">${escapeHtml(w.step)}</span>
                    </div>
                `).join("");
            }
        }

        if (data.state === "RUNNING") {
            btnStart.style.display = "none";
            btnPause.style.display = "inline-block";
            btnResume.style.display = "none";
            btnStop.style.display = "inline-block";
        } else if (data.state === "PAUSED") {
            btnStart.style.display = "none";
            btnPause.style.display = "none";
            btnResume.style.display = "inline-block";
            btnStop.style.display = "inline-block";
        } else {
            btnStart.style.display = "inline-block";
            btnPause.style.display = "none";
            btnResume.style.display = "none";
            btnStop.style.display = "none";
        }
    } catch (e) {}
}

async function startBatchAuto() {
    const concSel = document.getElementById("batchConcurrency");
    const concurrency = concSel ? parseInt(concSel.value) || 3 : 3;
    if (!confirm(`Start full automated recovery queue for up to 300 accounts with ${concurrency}x Parallel Workers?\nEngine will auto-route via ixBrowser / Multi-phone hardware with rate-limit cooldowns.`)) return;
    try {
        const res = await fetch("/api/batch/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_accounts: 300, concurrency: concurrency })
        });
        const d = await res.json();
        fetchBatchStatus();
    } catch (e) {
        alert("Failed to start batch: " + e);
    }
}

async function pauseBatchAuto() {
    await fetch("/api/batch/pause", { method: "POST" });
    fetchBatchStatus();
}

async function resumeBatchAuto() {
    await fetch("/api/batch/resume", { method: "POST" });
    fetchBatchStatus();
}

async function stopBatchAuto() {
    if (!confirm("Are you sure you want to STOP the running batch queue?")) return;
    await fetch("/api/batch/stop", { method: "POST" });
    fetchBatchStatus();
}

// ─── ixBrowser Status ────────────────────────────────────────────────────────
async function fetchIxBrowserStatus() {
    try {
        const res = await fetch("/api/ixbrowser/status");
        const data = await res.json();
        const dot = document.getElementById("ixDot");
        const txt = document.getElementById("ixStatusText");
        if (data.online) {
            dot.className = "status-dot online";
            txt.innerText = "ixBrowser Online";
        } else {
            dot.className = "status-dot offline";
            txt.innerText = data.message || "ixBrowser Offline";
        }
    } catch (e) {}
}

// ─── Multi-Device Telemetry Fleet ────────────────────────────────────────────
async function fetchDeviceTelemetry() {
    try {
        const res = await fetch("/api/devices");
        const data = await res.json();
        const devices = data.devices || [];

        const multiPill = document.getElementById("multiDevicePill");
        const dot = document.getElementById("deviceDot");
        const text = document.getElementById("deviceStatusText");
        const devList = document.getElementById("deviceListContainer");

        const telModel = document.getElementById("telModel");
        const telCarrier = document.getElementById("telCarrier");
        const telBattery = document.getElementById("telBattery");

        if (devices.length > 0) {
            hasConnectedDevice = true;
            dot.className = "status-dot online";
            text.innerText = `${devices.length} Phone(s) Online`;

            // Active device telemetry
            const mainDev = devices[0];
            telModel.innerText = mainDev.name;
            telCarrier.innerText = mainDev.carrier;
            telBattery.innerText = mainDev.battery;

            // Render fleet list
            devList.innerHTML = devices.map((d, idx) => `
                <div class="device-card-item">
                    <div>
                        <span style="font-weight:600; color:var(--text-primary);">${escapeHtml(d.name)}</span>
                        <span style="font-size:0.72rem; color:var(--text-muted); margin-left:0.35rem;">(${d.id.substring(0, 8)})</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span style="font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(d.carrier)}</span>
                        <span class="status-tag RECOVERED" style="font-size:0.65rem; padding:0.15rem 0.4rem;">ONLINE</span>
                    </div>
                </div>
            `).join("");
        } else {
            hasConnectedDevice = false;
            dot.className = "status-dot offline";
            text.innerText = "No Phone Connected";
            telModel.innerText = "Disconnected";
            telCarrier.innerText = "No SIM";
            telBattery.innerText = "--";
            devList.innerHTML = `
                <div class="device-card-item" style="color:var(--text-muted);">
                    <span>No Android Phone Detected</span>
                    <span style="font-size:0.72rem;">Plug USB & enable USB Debugging</span>
                </div>
            `;
            // Immediately hide screen and show placeholder
            document.getElementById("phoneScreenImg").style.display = "none";
            document.getElementById("screenPlaceholder").style.display = "block";
        }
    } catch (e) {
        console.error("Telemetry fetch error", e);
    }
}

// ─── Screen Mirror Refresh (Zero 404 Overhead) ───────────────────────────────
function refreshScreenMirror() {
    if (!screenStreaming || !hasConnectedDevice) return;
    const img = document.getElementById("phoneScreenImg");
    img.src = "/api/screen?t=" + new Date().getTime();
}

function handleScreenLoad() {
    document.getElementById("phoneScreenImg").style.display = "block";
    document.getElementById("screenPlaceholder").style.display = "none";
}

function handleScreenError() {
    document.getElementById("phoneScreenImg").style.display = "none";
    document.getElementById("screenPlaceholder").style.display = "block";
}

// ─── State & Console Logs ────────────────────────────────────────────────────
async function fetchStateLogs() {
    try {
        const res = await fetch("/api/state");
        const data = await res.json();
        const logsBox = document.getElementById("consoleLogs");

        if (data.logs && data.logs.length > 0) {
            logsBox.innerHTML = data.logs.map(log => `
                <div class="log-entry">
                    <span class="log-time">[${log.time}]</span>
                    <span class="log-msg ${log.level}">${escapeHtml(log.msg)}</span>
                </div>
            `).join("");
            logsBox.scrollTop = logsBox.scrollHeight;
        }
    } catch (e) {}
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ─── Accounts Management ─────────────────────────────────────────────────────
async function fetchAccounts() {
    try {
        const res = await fetch("/api/accounts");
        const data = await res.json();
        accountsData = data.accounts || [];

        // Update top metric cards
        document.getElementById("metricTotal").innerText = data.stats.total;
        document.getElementById("metricRecovered").innerText = data.stats.recovered;
        document.getElementById("metricPending").innerText = data.stats.pending;
        document.getElementById("metricSuspended").innerText = data.stats.suspended;

        renderAccountsTable(accountsData);
    } catch (e) {
        console.error("Accounts fetch error", e);
    }
}

async function renderAccountsTable(accounts) {
    const tbody = document.getElementById("accountsTableBody");
    if (!accounts || accounts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:2rem;">No accounts loaded yet. Click "+ Add Account" to start.</td></tr>`;
        return;
    }

    let rowsHtml = "";
    for (let i = 0; i < accounts.length; i++) {
        const acc = accounts[i];
        const statusClass = escapeHtml(acc.status || "PENDING");
        const emailSafe = escapeHtml(acc.email || "");
        const notesSafe = escapeHtml(acc.notes || "Delegated Account");
        const hasTotp = !!acc.totp_secret;
        const hasProfile = !!acc.ixbrowser_profile_id;

        rowsHtml += `
            <tr id="acc-row-${i}">
                <td>
                    <div style="font-weight:600; color:var(--text-primary);">${emailSafe}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted);">${notesSafe}</div>
                </td>
                <td>
                    <span class="status-tag ${statusClass}">${statusClass}</span>
                </td>
                <td id="totp-cell-${i}">
                    ${hasTotp ? '<span style="color:var(--text-muted); font-size:0.8rem;">Loading...</span>' : '<span style="color:var(--text-muted); font-size:0.8rem;">No 2FA Key</span>'}
                </td>
                <td>
                    <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
                        <button class="btn btn-primary" style="padding:0.35rem 0.65rem; font-size:0.75rem; background:linear-gradient(135deg, #0284c7, #4f46e5);"
                            onclick="triggerIxRecovery(${i})" title="Auto-Recover inside ixBrowser Profile">
                            🌐 ixBrowser${hasProfile ? ' ✓' : ''}
                        </button>
                        <button class="btn btn-secondary" style="padding:0.35rem 0.65rem; font-size:0.75rem;"
                            onclick="triggerActionIdx('type_email', ${i})">
                            📧 Email
                        </button>
                        <button class="btn btn-secondary" style="padding:0.35rem 0.65rem; font-size:0.75rem;"
                            onclick="triggerActionIdx('type_password', ${i})">
                            🔑 Pass
                        </button>
                        ${hasTotp ? `
                        <button class="btn btn-primary" style="padding:0.35rem 0.65rem; font-size:0.75rem;"
                            onclick="triggerActionIdx('type_totp', ${i})">
                            🛡️ 2FA
                        </button>` : ''}
                    </div>
                </td>
                <td>
                    <div style="display:flex; gap:0.4rem;">
                        <button class="btn btn-secondary" style="padding:0.35rem 0.5rem; font-size:0.75rem; color:var(--success);"
                            onclick="markStatus(${i}, 'RECOVERED')" title="Mark Recovered">✔</button>
                        <button class="btn btn-secondary" style="padding:0.35rem 0.5rem; font-size:0.75rem; color:var(--danger);"
                            onclick="deleteAccount(${i})" title="Delete">✕</button>
                    </div>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = rowsHtml;

    // Client-side zero-latency TOTP injection
    for (let i = 0; i < accounts.length; i++) {
        const acc = accounts[i];
        if (acc.totp_secret) {
            generateTOTP(acc.totp_secret).then(({ code, remaining }) => {
                const cell = document.getElementById(`totp-cell-${i}`);
                if (cell) {
                    cell.innerHTML = `
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <span style="font-family:var(--font-mono); font-weight:700; color:var(--accent-cyan); font-size:1.1rem; letter-spacing:1px;">${code}</span>
                            <span style="font-size:0.75rem; color:var(--text-muted);">(${remaining}s)</span>
                        </div>
                    `;
                }
            });
        }
    }
}

function filterAccounts() {
    const q = document.getElementById("searchInput").value.toLowerCase();
    const filtered = accountsData.filter(a => a.email.toLowerCase().includes(q) || (a.notes && a.notes.toLowerCase().includes(q)));
    renderAccountsTable(filtered);
}

async function triggerActionIdx(action, accIndex) {
    const acc = accountsData[accIndex];
    if (!acc) return;

    let extra = "";
    if (action === "type_password") extra = acc.password || "";
    if (action === "type_totp") extra = acc.totp_secret || "";

    await triggerAction(action, acc.email, extra);
}

// ─── Action Dispatcher ───────────────────────────────────────────────────────
async function triggerAction(action, email = "", extra = "") {
    try {
        const res = await fetch("/api/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action, email, extra })
        });
        const data = await res.json();
        if (action === "rotate_ip" && data.new_ip) {
            document.getElementById("telIp").innerText = data.new_ip;
        }
        fetchStateLogs();
        if (action !== "rotate_ip") fetchAccounts();
    } catch (e) {
        console.error("Action error", e);
    }
}

// Send Key (Home, Back, Enter)
async function sendKey(code) {
    await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "inject_key", extra: code.toString() })
    });
}

// ─── Modal Actions ───────────────────────────────────────────────────────────
function openAddModal() {
    document.getElementById("addModal").style.display = "flex";
}

function closeAddModal() {
    document.getElementById("addModal").style.display = "none";
}

async function submitAddAccount() {
    const email = document.getElementById("modalEmail").value.trim();
    const password = document.getElementById("modalPassword").value.trim();
    const totp_secret = document.getElementById("modalSecret").value.trim();
    const profile_id = document.getElementById("modalProfile") ? document.getElementById("modalProfile").value.trim() : "";
    const notes = document.getElementById("modalNotes").value.trim();

    if (!email || !password) {
        alert("Email aur password likhna zaroori hai!");
        return;
    }

    const btn = document.querySelector("#addModal .btn-primary");
    if (btn) { btn.disabled = true; btn.innerText = "Saving..."; }

    await fetch("/api/accounts/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, totp_secret, notes, ixbrowser_profile_id: profile_id })
    });

    closeAddModal();
    document.getElementById("modalEmail").value = "";
    document.getElementById("modalPassword").value = "";
    document.getElementById("modalSecret").value = "";
    if (document.getElementById("modalProfile")) document.getElementById("modalProfile").value = "";
    document.getElementById("modalNotes").value = "";
    if (btn) { btn.disabled = false; btn.innerText = "Save to Vault"; }
    fetchAccounts();
}

async function markStatus(accIndex, status) {
    const acc = accountsData[accIndex];
    if (!acc) return;
    await fetch("/api/accounts/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: acc.email, status })
    });
    fetchAccounts();
}

async function deleteAccount(accIndex) {
    const acc = accountsData[accIndex];
    if (!acc) return;
    if (!confirm(`Is account ko vault se delete karna hai?\n${acc.email}`)) return;
    await fetch("/api/accounts/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: acc.id })
    });
    fetchAccounts();
}

function exportWarmupCsv() {
    window.location.href = "/api/export";
}

async function triggerIxRecovery(accIndex) {
    const acc = accountsData[accIndex];
    if (!acc) return;

    let profileId = acc.ixbrowser_profile_id;
    if (!profileId) {
        profileId = prompt(`ixBrowser Profile ID enter karein (${acc.email} ke liye):`);
        if (!profileId) return;
    }
    try {
        const res = await fetch("/api/ixbrowser/recover", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: acc.email, profile_id: profileId })
        });
        const d = await res.json();
        alert(d.message || "ixBrowser recovery process queued! Terminal log box dekhein.");
        fetchAccounts();
    } catch (e) {
        alert("Error dispatching recovery: " + e);
    }
}

// ─── Diagnostics Modal ───────────────────────────────────────────────────────
function openDiagModal() {
    document.getElementById("diagModal").style.display = "flex";
    runDiagnosticsAudit();
}

function closeDiagModal() {
    document.getElementById("diagModal").style.display = "none";
}

async function runDiagnosticsAudit() {
    const box = document.getElementById("diagContent");
    const badge = document.getElementById("diagOverallBadge");
    const timeTxt = document.getElementById("diagTimestamp");

    box.innerHTML = `<div style="text-align:center; padding:2rem; color:var(--text-muted);">Running diagnostic audit...</div>`;
    badge.innerText = "CHECKING...";
    badge.className = "status-tag PENDING";

    try {
        const res = await fetch("/api/diagnostics");
        const data = await res.json();

        badge.innerText = data.overall_status;
        badge.className = `status-tag ${data.overall_status === 'HEALTHY' ? 'RECOVERED' : (data.overall_status === 'WARNINGS' ? 'PENDING' : 'SUSPENDED')}`;
        timeTxt.innerText = `Audit Timestamp: ${data.timestamp}`;

        let html = "";
        let currentCat = "";
        for (const chk of data.checks) {
            if (chk.category !== currentCat) {
                currentCat = chk.category;
                html += `<div style="font-size:0.75rem; font-weight:700; color:var(--accent-cyan); text-transform:uppercase; margin-top:0.75rem; letter-spacing:0.5px;">${escapeHtml(currentCat)}</div>`;
            }
            const isPass = chk.passed;
            const badgeClass = isPass ? 'RECOVERED' : (chk.status === 'CRITICAL' ? 'SUSPENDED' : 'PENDING');
            html += `
                <div style="display:flex; justify-content:space-between; align-items:center; padding:0.45rem 0.65rem; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); border-radius:6px; font-size:0.8rem;">
                    <div>
                        <div style="font-weight:600; color:var(--text-primary);">${escapeHtml(chk.name)}</div>
                        <div style="font-size:0.72rem; color:var(--text-muted);">${escapeHtml(chk.details)}</div>
                    </div>
                    <span class="status-tag ${badgeClass}" style="font-size:0.68rem; padding:0.15rem 0.4rem;">${isPass ? 'PASS' : chk.status}</span>
                </div>
            `;
        }
        box.innerHTML = html;
    } catch (e) {
        box.innerHTML = `<div style="color:var(--danger); padding:1rem;">Failed to fetch diagnostics: ${escapeHtml(String(e))}</div>`;
        badge.innerText = "ERROR";
        badge.className = "status-tag SUSPENDED";
    }
}

// ─── 📡 4G Mobile Dongle & Proxy Controller ──────────────────────────────────
function openProxyModal() {
    document.getElementById("proxyModal").style.display = "flex";
    fetchProxyStatus();
}

function closeProxyModal() {
    document.getElementById("proxyModal").style.display = "none";
}

function updateProxyFields() {
    const mode = document.getElementById("proxyMode").value;
    const gGw = document.getElementById("groupDongleGateway");
    const gWb = document.getElementById("groupWebhook");
    const gPx = document.getElementById("groupProxyServer");

    gGw.style.display = (mode === "HUAWEI_DONGLE" || mode === "ZTE_DONGLE") ? "block" : "none";
    gWb.style.display = (mode === "ROTATING_WEBHOOK") ? "block" : "none";
    gPx.style.display = (mode === "DIRECT_PROXY" || mode === "ROTATING_WEBHOOK") ? "block" : "none";
}

async function fetchProxyStatus() {
    try {
        const res = await fetch("/api/proxy/status");
        const data = await res.json();
        const cfg = data.config || {};

        document.getElementById("proxyEnabled").checked = !!cfg.enabled;
        document.getElementById("proxyMode").value = cfg.mode || "PHONE_ADB";
        document.getElementById("proxyGateway").value = cfg.dongle_gateway || "http://192.168.8.1";
        document.getElementById("proxyWebhook").value = cfg.rotate_webhook_url || "";
        document.getElementById("proxyServer").value = cfg.proxy_server || "";
        document.getElementById("proxyRotateInterval").value = cfg.rotate_every_n_accounts || 3;

        const ip = data.current_public_ip || "Unknown";
        document.getElementById("proxyCurrentIpBadge").innerText = `IP: ${ip}`;
        document.getElementById("telPublicIp").innerText = ip;

        const hw = data.huawei_dongle || {};
        document.getElementById("telHuaweiStatus").innerText = hw.online ? `Online (${hw.network_type || 'LTE'}, ${hw.signal_bars || '4'} bars)` : "Offline / Unreachable";
        document.getElementById("telHuaweiStatus").style.color = hw.online ? "var(--success)" : "var(--text-muted)";

        const zte = data.zte_dongle || {};
        document.getElementById("telZteStatus").innerText = zte.online ? `Online (${zte.state || 'Connected'})` : "Offline / Unreachable";
        document.getElementById("telZteStatus").style.color = zte.online ? "var(--success)" : "var(--text-muted)";

        updateProxyFields();
    } catch (e) {
        console.error("Error fetching proxy status:", e);
    }
}

async function saveProxySettings() {
    const payload = {
        enabled: document.getElementById("proxyEnabled").checked,
        mode: document.getElementById("proxyMode").value,
        dongle_gateway: document.getElementById("proxyGateway").value.trim(),
        rotate_webhook_url: document.getElementById("proxyWebhook").value.trim(),
        proxy_server: document.getElementById("proxyServer").value.trim(),
        rotate_every_n_accounts: parseInt(document.getElementById("proxyRotateInterval").value) || 3
    };

    try {
        const res = await fetch("/api/proxy/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (d.success) {
            alert("✅ 4G Proxy / Dongle settings saved successfully!");
            closeProxyModal();
        } else {
            alert("Error saving proxy settings.");
        }
    } catch (e) {
        alert("Network error saving proxy settings: " + e);
    }
}

async function triggerUniversalRotate() {
    const badge = document.getElementById("proxyCurrentIpBadge");
    badge.innerText = "Rotating...";
    badge.className = "status-tag PENDING";

    try {
        const res = await fetch("/api/proxy/rotate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.status === "SUCCESS") {
            const newIp = data.new_ip || "New Lease Acquired";
            badge.innerText = `IP: ${newIp}`;
            badge.className = "status-tag RECOVERED";
            document.getElementById("telPublicIp").innerText = newIp;
            alert(`🎉 IP Rotation Successful!\nNew Public IP: ${newIp}\nRouted via: ${data.source || 'Carrier'}`);
        } else {
            badge.innerText = "Rotation Issue";
            badge.className = "status-tag SUSPENDED";
            alert(`⚠️ IP Rotation Warning: ${data.message || 'No IP change detected'}`);
        }
    } catch (e) {
        alert("Rotation request failed: " + e);
    }
}
