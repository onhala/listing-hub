/**
 * Bazoš Automat & AI Editor - Client Logic (app.js)
 * Brand: TERMS a.s. / Roboton Custom UI Engine
 */

// Global Cloudflare Access 2FA session handler
(function() {
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const response = await originalFetch.apply(this, args);
        try {
            const urlStr = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url ? args[0].url : "");
            const triggerReload = () => {
                const lastReload = parseInt(sessionStorage.getItem("cf_access_last_reload") || "0", 10);
                const now = Date.now();
                if (now - lastReload > 20000) {
                    sessionStorage.setItem("cf_access_last_reload", now.toString());
                    window.location.reload();
                } else {
                    console.warn("Cloudflare Access 2FA reload throttled to avoid reload loop.");
                }
            };
            // Detekce přesměrování na Cloudflare Access Login při vypršení relace
            if (response.redirected && (response.url.includes("cloudflareaccess.com") || response.url.includes("/cdn-cgi/access/"))) {
                triggerReload();
                return response;
            }
            if (urlStr.includes("/api/") && !urlStr.includes("/feed.ics")) {
                const contentType = response.headers.get("content-type") || "";
                if (contentType.includes("text/html") && (response.status === 200 || response.status === 302 || response.status === 401 || response.status === 403)) {
                    triggerReload();
                    return response;
                }
            }
        } catch (e) {
            console.debug("CF Access interceptor check:", e);
        }
        return response;
    };
})();

document.addEventListener("DOMContentLoaded", () => {
    // State state management
    let activeListings = [];
    let soldListings = [];
    let excludedPhotos = new Set(); // filenames the user wants to skip
    let currentAd = null;
    let userConfig = {};
    let selectedTextRange = null; // Uchovává vybranou část textu pro inline AI přepis
    let lastAiSourceText = "";
    let lastAiField = "";
    let lastAiInstruction = "improve";

    // Sorting & Filtering state
    let activeSort = "days_old_desc";
    let activeFilterQuery = "";
    let unsoldSort = "days_old_desc";
    let unsoldFilterQuery = "";
    let soldSort = "sold_at_desc";
    let soldFilterQuery = "";

    // Batch operations state
    let isBatchModeActive = false;
    let selectedBatchAdIds = new Set();
    let batchQueue = [];
    let batchIndex = 0;

    // Screencast zoom & Stepper state
    let currentScreencastZoom = "fit"; // "fit", 1.0, 1.25, 1.5, 0.75
    let confirmAutoAdvanceTimer = null;

    // UI elements
    const navItems = document.querySelectorAll(".nav-item");
    const tabContents = document.querySelectorAll(".tab-content");
    const activeListingsContainer = document.getElementById("active-listings-list");
    const unsoldListingsContainer = document.getElementById("unsold-listings-list");
    const soldListingsContainer = document.getElementById("sold-listings-list");
    const pageTitle = document.getElementById("page-title");
    
    // Stats elements
    const statActiveCount = document.getElementById("stat-active-count");
    const statUnsoldCount = document.getElementById("stat-unsold-count");
    const statTotalViews = document.getElementById("stat-total-views");
    const statSoldCount = document.getElementById("stat-sold-count");

    // Config elements
    const configForm = document.getElementById("config-form");
    const configName = document.getElementById("config-name");
    const configEmail = document.getElementById("config-email");
    const configPhone = document.getElementById("config-phone");
    const configZip = document.getElementById("config-zip");
    const configLocation = document.getElementById("config-location");
    const configPassword = document.getElementById("config-password");
    const configGeminiModel = document.getElementById("config-gemini-model");
    const btnRefreshGeminiModels = document.getElementById("btn-refresh-gemini-models");
    const refreshGeminiModelsIcon = document.getElementById("refresh-gemini-models-icon");
    const geminiModelsInfo = document.getElementById("gemini-models-info");
    const configGeminiKey = document.getElementById("config-gemini-key");
    const configAiDelivery = document.getElementById("config-ai-delivery");
    const configAiSeller = document.getElementById("config-ai-seller");
    const toggleGeminiKeyBtn = document.getElementById("toggle-gemini-key");
    const btnTestGemini = document.getElementById("btn-test-gemini");
    const geminiTestStatus = document.getElementById("gemini-test-status");
    const geminiTestStatusIcon = document.getElementById("gemini-test-status-icon");
    const geminiTestStatusText = document.getElementById("gemini-test-status-text");

    // TrueNAS elements
    const configTruenasUrl = document.getElementById("config-truenas-url");
    const configTruenasAppName = document.getElementById("config-truenas-app-name");
    const configTruenasApiKey = document.getElementById("config-truenas-api-key");
    const toggleTruenasKeyBtn = document.getElementById("toggle-truenas-key");
    const btnTriggerTruenasUpgrade = document.getElementById("btn-trigger-truenas-upgrade");

    // Auto refresh elements
    const configAutoRefresh = document.getElementById("config-auto-refresh");
    const configRefreshInterval = document.getElementById("config-refresh-interval");
    const smsWarningBanner = document.getElementById("sms-warning-banner");
    const btnSyncBanner = document.getElementById("btn-sync-banner");
    const lastSyncTimeLabel = document.getElementById("last-sync-time-label");

    // Calendar elements
    const calendarFeedUrl = document.getElementById("calendar-feed-url");
    const btnCopyCalendarUrl = document.getElementById("btn-copy-calendar-url");
    const btnRegenCalendarToken = document.getElementById("btn-regen-calendar-token");

    // App Update & Version Inspector elements
    const appUpdateBanner = document.getElementById("app-update-banner");
    const appUpdateMsg = document.getElementById("app-update-msg");
    const appUpdateVersionDiff = document.getElementById("app-update-version-diff");
    const btnAppUpdate = document.getElementById("btn-app-update");
    const btnDismissAppUpdate = document.getElementById("btn-dismiss-app-update");
    const appVersionWidget = document.getElementById("app-version-widget");
    const appVersionLabel = document.getElementById("app-version-label");
    const appCommitHash = document.getElementById("app-commit-hash");
    const appVersionBadge = document.getElementById("app-version-badge");
    const dockerUpdateModal = document.getElementById("docker-update-modal");
    const btnCloseDockerUpdate = document.getElementById("btn-close-docker-update");
    const btnCloseDockerUpdateOk = document.getElementById("btn-close-docker-update-ok");
    const btnCopyDockerCmd = document.getElementById("btn-copy-docker-cmd");
    const btnRecheckVersion = document.getElementById("btn-recheck-version");
    const btnDismissUpdateModal = document.getElementById("btn-dismiss-update-modal");
    const modalLocalVersion = document.getElementById("modal-local-version");
    const modalLocalHash = document.getElementById("modal-local-hash");
    const modalEnvironmentLabel = document.getElementById("modal-environment-label");
    const modalLatestVersion = document.getElementById("modal-latest-version");
    const modalLatestHash = document.getElementById("modal-latest-hash");
    const modalLatestDate = document.getElementById("modal-latest-date");
    const modalUpdateBadge = document.getElementById("modal-update-badge");
    const modalCommitMessage = document.getElementById("modal-commit-message");
    const modalDiffContainer = document.getElementById("modal-diff-container");
    const modalCompareLink = document.getElementById("modal-compare-link");
    const restartOverlay = document.getElementById("restart-overlay");
    const restartStatus = document.getElementById("restart-status");

    // Lightbox modal elements
    const lightboxModal = document.getElementById("lightbox-modal");
    const lightboxImg = document.getElementById("lightbox-img");
    const lightboxCaption = document.getElementById("lightbox-caption");
    const closeLightboxBtn = document.getElementById("close-lightbox-btn");

    // Photo Editor Modal elements
    const photoEditorModal = document.getElementById("photo-editor-modal");
    const btnClosePhotoEditor = document.getElementById("btn-close-photo-editor");
    const btnCancelPhotoEditor = document.getElementById("btn-cancel-photo-editor");
    const btnSavePhotoEditor = document.getElementById("btn-save-photo-editor");
    const photoEditorImg = document.getElementById("photo-editor-img");
    const photoEditorCanvas = document.getElementById("photo-editor-canvas");
    const photoEditorCanvasWrap = document.getElementById("photo-editor-canvas-wrap");
    const photoEditorDragBox = document.getElementById("photo-editor-drag-box");
    const photoEditorSpinner = document.getElementById("photo-editor-spinner");
    const photoEditorSpinnerText = document.getElementById("photo-editor-spinner-text");
    const photoEditorTargetName = document.getElementById("photo-editor-target-name");
    const btnToggleBoxBlur = document.getElementById("btn-toggle-box-blur");
    const boxBlurHint = document.getElementById("box-blur-hint");
    const btnComparePhoto = document.getElementById("btn-compare-photo");
    const btnResetPhotoEdits = document.getElementById("btn-reset-photo-edits");
    const bokehButtons = document.querySelectorAll(".btn-bokeh-preset");

    function openLightbox(dataUrl, filename) {
        if (lightboxModal && lightboxImg) {
            lightboxImg.src = dataUrl;
            lightboxCaption.textContent = filename || "";
            lightboxModal.style.display = "flex";
        }
    }

    // Modals
    const addListingModal = document.getElementById("add-listing-modal");
    const editListingModal = document.getElementById("edit-listing-modal");
    const aiProposalModal = document.getElementById("ai-proposal-modal");
    const repostConfirmModal = document.getElementById("repost-confirm-modal");
    const deleteListingModal = document.getElementById("delete-listing-modal");
    const markSoldModal = document.getElementById("mark-sold-modal");
    const manualPublishModal = document.getElementById("manual-publish-modal");
    const browserReviewBanner = document.getElementById("browser-review-banner");
    
    // Parent/child modal state helper to preserve currentAd
    let activeChildModal = null;
    let pendingActionAd = null;

    const openChildModal = (childModalEl) => {
        if (!childModalEl) return;
        childModalEl.style.display = "flex";
        childModalEl.classList.add("active");
        activeChildModal = childModalEl;
    };

    const closeChildModal = (childModalEl) => {
        if (!childModalEl) return;
        childModalEl.style.display = "none";
        childModalEl.classList.remove("active");
        if (activeChildModal === childModalEl) {
            activeChildModal = null;
        }
    };
    
    // Forms & inputs in modals
    const addListingForm = document.getElementById("add-listing-form");
    const newTitle = document.getElementById("new-title");
    const newPrice = document.getElementById("new-price");
    const newCategory = document.getElementById("new-category");
    const newDescription = document.getElementById("new-description");

    const editListingForm = document.getElementById("edit-listing-form");
    const editTitle = document.getElementById("edit-title");
    const editPrice = document.getElementById("edit-price");
    const editCategory = document.getElementById("edit-category");
    const editDescription = document.getElementById("edit-description");
    const editNotes = document.getElementById("edit-notes");
    const editPhotosDir = document.getElementById("edit-photos-dir");
    const photoGalleryGrid = document.getElementById("photo-gallery-grid");
    const photoCountLabel = document.getElementById("photo-count-label");

    // Character counters
    const newTitleCounter = document.getElementById("new-title-counter");
    const editTitleCounter = document.getElementById("edit-title-counter");
    const newDescCounter = document.getElementById("new-desc-counter");
    const editDescCounter = document.getElementById("edit-desc-counter");

    // Info panel elements in edit modal
    const infoUrlContainer = document.getElementById("info-url-container");
    const infoViews = document.getElementById("info-views");
    const infoPhotosDir = document.getElementById("info-photos-dir");

    // Playwright status & floating tooltip
    const playwrightStatus = document.getElementById("playwright-status");
    const inlineAiBtn = document.getElementById("inline-ai-btn");

    // API endpoints base
    const API = {
        listings: "/api/listings",
        config: "/api/config",
        photos: "/api/photos",
        refreshStatus: "/api/refresh/status",
        versionCheck: "/api/version/check",
        versionUpdate: "/api/version/update",
        saveAd: "/api/listings/save",
        addAd: "/api/listings/add",
        createWithPhotos: "/api/listings/create-with-photos",
        aiAnalyzePhotos: "/api/ai/analyze-photos",
        aiAnalyzeExisting: "/api/ai/analyze-existing",
        action: "/api/action",
        cancel: "/api/action/cancel",
        aiImprove: "/api/ai/improve",
        uploadPhotos: "/api/photos/upload"
    };

    // ==========================================
    // 1. INICIALIZACE A NABÍHÁNÍ DAT
    // ==========================================

    const updateCounter = (inputEl, counterEl, maxLength) => {
        if (!inputEl || !counterEl) return;
        const len = inputEl.value.length;
        if (maxLength) {
            counterEl.textContent = `${len} / ${maxLength}`;
            if (len >= maxLength) {
                counterEl.className = "input-hint counter-danger";
            } else if (len >= maxLength - 5) {
                counterEl.className = "input-hint counter-warning";
            } else {
                counterEl.className = "input-hint";
            }
        } else {
            counterEl.textContent = `${len} znaků`;
        }
    };

    const initCharacterCounters = () => {
        if (newTitle && newTitleCounter) {
            newTitle.addEventListener("input", () => updateCounter(newTitle, newTitleCounter, 50));
        }
        if (newDescription && newDescCounter) {
            newDescription.addEventListener("input", () => updateCounter(newDescription, newDescCounter));
        }
        if (editTitle && editTitleCounter) {
            editTitle.addEventListener("input", () => updateCounter(editTitle, editTitleCounter, 50));
        }
        if (editDescription && editDescCounter) {
            editDescription.addEventListener("input", () => updateCounter(editDescription, editDescCounter));
        }
    };

    const pollRefreshStatus = async () => {
        try {
            const res = await fetch(API.refreshStatus);
            if (res.ok) {
                const data = await res.json();
                
                // 1. Zobrazení SMS banneru
                if (data.auto_refresh_status === "needs_sms") {
                    smsWarningBanner.style.display = "flex";
                } else {
                    smsWarningBanner.style.display = "none";
                }
                
                // 2. Formátování a zobrazení času poslední synchronizace
                if (data.last_refresh_time) {
                    const date = new Date(data.last_refresh_time);
                    const formattedDate = date.toLocaleString("cs-CZ", {
                        day: "numeric",
                        month: "numeric",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit"
                    });
                    
                    // Výpočet před kolika minutami
                    const diffMs = new Date() - date;
                    const diffMins = Math.floor(diffMs / 60000);
                    let relativeStr = "";
                    if (diffMins < 1) {
                        relativeStr = "před malou chvílí";
                    } else if (diffMins < 60) {
                        relativeStr = `před ${diffMins} min`;
                    } else {
                        const diffHours = Math.floor(diffMins / 60);
                        relativeStr = `před ${diffHours} hod`;
                    }
                    
                    lastSyncTimeLabel.textContent = `Aktualizováno: ${formattedDate} (${relativeStr})`;
                } else {
                    lastSyncTimeLabel.textContent = "Dosud neaktualizováno";
                }
            }
        } catch (err) {
            console.error("Chyba při dotazování na stav aktualizace:", err);
        }
    };

    let currentVersionData = null;

    const populateVersionModal = (data) => {
        if (!data) return;
        const appVer = data.app_version || "3.8.8";
        const localHash = (data.local && data.local.hash) || data.local_hash || "unknown";
        const latestHash = (data.latest && data.latest.hash) || data.latest_hash || "unknown";
        const envName = (data.local && data.local.environment) || (data.is_docker ? "Docker kontejner" : "Lokální vývoj");

        if (modalLocalVersion) modalLocalVersion.textContent = `v${appVer}`;
        if (modalLocalHash) modalLocalHash.textContent = localHash;
        if (modalEnvironmentLabel) {
            const icon = data.is_docker ? 'fa-brands fa-docker' : 'fa-solid fa-laptop-code';
            modalEnvironmentLabel.innerHTML = `<i class="${icon}"></i> ${envName}`;
        }

        if (modalLatestVersion) modalLatestVersion.textContent = `v${(data.latest && data.latest.version) || appVer}`;
        if (modalLatestHash) modalLatestHash.textContent = latestHash;

        if (modalUpdateBadge) {
            if (data.update_available) {
                modalUpdateBadge.textContent = "K dispozici";
                modalUpdateBadge.style.background = "#eab308";
                modalUpdateBadge.style.color = "#000";
            } else {
                modalUpdateBadge.textContent = "Aktuální";
                modalUpdateBadge.style.background = "#10b981";
                modalUpdateBadge.style.color = "#000";
            }
        }

        if (modalLatestDate) {
            if (data.latest && data.latest.date) {
                try {
                    const d = new Date(data.latest.date);
                    modalLatestDate.textContent = isNaN(d) ? data.latest.date : d.toLocaleString("cs-CZ");
                } catch (e) {
                    modalLatestDate.textContent = data.latest.date;
                }
            } else {
                modalLatestDate.textContent = "Datum neuvedeno";
            }
        }

        if (modalCommitMessage) {
            const msg = (data.latest && data.latest.message) || data.latest_message || "Žádné informace o commitu.";
            modalCommitMessage.textContent = msg;
        }

        if (modalDiffContainer && modalCompareLink) {
            if (data.compare_url) {
                modalDiffContainer.style.display = "block";
                modalCompareLink.href = data.compare_url;
            } else if (data.latest && data.latest.url) {
                modalDiffContainer.style.display = "block";
                modalCompareLink.href = data.latest.url;
            } else {
                modalDiffContainer.style.display = "none";
            }
        }
    };

    const openVersionModal = () => {
        if (dockerUpdateModal) {
            dockerUpdateModal.classList.add("active");
            dockerUpdateModal.style.display = "flex";
            if (currentVersionData) {
                populateVersionModal(currentVersionData);
            }
        }
    };

    const closeVersionModal = () => {
        if (dockerUpdateModal) {
            dockerUpdateModal.classList.remove("active");
            dockerUpdateModal.style.display = "none";
        }
    };

    const checkAppVersion = async (force = false) => {
        try {
            const url = force ? `${API.versionCheck}?force=1` : API.versionCheck;
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                currentVersionData = data;
                
                const appVer = data.app_version || "3.8.8";
                const localHash = (data.local && data.local.hash !== "unknown") 
                    ? data.local.hash 
                    : (data.local_hash && data.local_hash !== "unknown" ? data.local_hash : "git");
                const latestHash = (data.latest && data.latest.hash !== "unknown")
                    ? data.latest.hash
                    : (data.latest_hash && data.latest_hash !== "unknown" ? data.latest_hash : "");

                // 1. Aktualizace sidebar widgetu
                if (appVersionLabel) {
                    appVersionLabel.textContent = `v${appVer}`;
                }
                if (appCommitHash) {
                    appCommitHash.textContent = localHash;
                }
                if (appVersionBadge) {
                    if (data.update_available) {
                        appVersionBadge.style.display = "inline-block";
                        if (appVersionWidget) {
                            appVersionWidget.style.borderColor = "rgba(234, 179, 8, 0.4)";
                            appVersionWidget.style.background = "rgba(234, 179, 8, 0.08)";
                        }
                    } else {
                        appVersionBadge.style.display = "none";
                        if (appVersionWidget) {
                            appVersionWidget.style.borderColor = "rgba(255,255,255,0.06)";
                            appVersionWidget.style.background = "rgba(255,255,255,0.03)";
                        }
                    }
                }

                // 2. Kontrola odložení notifikace v localStorage
                const dismissedHash = localStorage.getItem("listing_hub_dismissed_update");
                const isDismissed = (dismissedHash && latestHash && dismissedHash === latestHash);

                // 3. Zobrazení decentního toastu/banneru
                if (data.update_available && !isDismissed) {
                    if (appUpdateBanner) appUpdateBanner.style.display = "flex";
                    if (appUpdateVersionDiff) {
                        appUpdateVersionDiff.textContent = `${localHash} → ${latestHash || "nový"}`;
                    }
                    if (appUpdateMsg) {
                        const msg = (data.latest && data.latest.message) || data.latest_message;
                        appUpdateMsg.textContent = msg ? `"${msg}"` : "Dostupný novější commit na GitHubu.";
                    }
                } else {
                    if (appUpdateBanner) appUpdateBanner.style.display = "none";
                }

                // 4. Předvyplnění modalu verzí
                populateVersionModal(data);
            }
        } catch (err) {
            console.error("Chyba při kontrole verze:", err);
        }
    };

    const triggerLocalAppUpdate = async () => {
        if (!confirm("Opravdu chcete spustit aktualizaci aplikace? Server se po dokončení restartuje.")) {
            return;
        }
        
        restartOverlay.style.display = "flex";
        restartStatus.textContent = "Spouštím aktualizaci (git pull)...";
        
        try {
            const res = await fetch(API.versionUpdate, { method: "POST" });
            if (res.ok) {
                restartStatus.textContent = "Aktualizace dokončena. Čekám na restart serveru...";
                
                // Periodické dotazování na naběhnutí serveru
                let attempts = 0;
                const pollInterval = setInterval(async () => {
                    attempts++;
                    restartStatus.textContent = `Dotazuji se na server (pokus ${attempts}/15)...`;
                    try {
                        const checkRes = await fetch(API.config);
                        if (checkRes.ok) {
                            clearInterval(pollInterval);
                            restartStatus.textContent = "Server běží! Načítám stránku...";
                            setTimeout(() => {
                                window.location.reload();
                            }, 500);
                        }
                    } catch (e) {
                        // Server ještě nenaběhl
                    }
                    if (attempts >= 15) {
                        clearInterval(pollInterval);
                        restartStatus.textContent = "Restart trvá příliš dlouho. Zkuste stránku načíst ručně.";
                    }
                }, 1500);
                
            } else {
                const data = await res.json();
                alert("Aktualizace selhala: " + (data.message || "neznámá chyba"));
                restartOverlay.style.display = "none";
            }
        } catch (err) {
            alert("Během aktualizace nastala chyba: " + err.message);
            restartOverlay.style.display = "none";
        }
    };

    const loadApp = async () => {
        initCharacterCounters();
        await loadConfig();
        await loadListings();
        
        // Nastartovat periodické dotazování na stav aktualizace a banner
        pollRefreshStatus();
        setInterval(pollRefreshStatus, 5000);
        
        // Nastartovat kontrolu verze na GitHubu
        checkAppVersion();
        
        // Zprovoznit synchronizaci přes varovný banner
        if (btnSyncBanner) {
            btnSyncBanner.addEventListener("click", () => {
                triggerPlaywrightAction(null, "sync_views");
            });
        }

        // Zprovoznit otevírání modalu verze ze sidebaru i z toast notifikace
        if (appVersionWidget) {
            appVersionWidget.addEventListener("click", openVersionModal);
        }
        if (btnAppUpdate) {
            btnAppUpdate.addEventListener("click", openVersionModal);
        }

        // Odložení notifikace v toastu (uložení do localStorage)
        if (btnDismissAppUpdate) {
            btnDismissAppUpdate.addEventListener("click", (e) => {
                e.stopPropagation();
                if (currentVersionData) {
                    const latestHash = (currentVersionData.latest && currentVersionData.latest.hash) || currentVersionData.latest_hash;
                    if (latestHash) {
                        localStorage.setItem("listing_hub_dismissed_update", latestHash);
                    }
                }
                if (appUpdateBanner) appUpdateBanner.style.display = "none";
                showNotification("Upozornění na novou verzi bylo odloženo.", "info");
            });
        }

        // Odložení notifikace přímo z modalu
        if (btnDismissUpdateModal) {
            btnDismissUpdateModal.addEventListener("click", () => {
                if (currentVersionData) {
                    const latestHash = (currentVersionData.latest && currentVersionData.latest.hash) || currentVersionData.latest_hash;
                    if (latestHash) {
                        localStorage.setItem("listing_hub_dismissed_update", latestHash);
                    }
                }
                if (appUpdateBanner) appUpdateBanner.style.display = "none";
                closeVersionModal();
                showNotification("Upozornění na tuto verzi bylo odloženo.", "info");
            });
        }

        // Znovu zkontrolovat na GitHubu (vynutit refresh bez cache)
        if (btnRecheckVersion) {
            btnRecheckVersion.addEventListener("click", async () => {
                btnRecheckVersion.disabled = true;
                const origHtml = btnRecheckVersion.innerHTML;
                btnRecheckVersion.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Zjišťuji...';
                try {
                    await checkAppVersion(true);
                    showNotification("Data o verzi byla úspěšně aktualizována z GitHubu.", "success");
                } catch (e) {
                    showNotification("Chyba při dotazu na GitHub.", "error");
                } finally {
                    btnRecheckVersion.disabled = false;
                    btnRecheckVersion.innerHTML = origHtml;
                }
            });
        }

        // Zprovoznit zavírání Docker Update modalu
        if (btnCloseDockerUpdate) {
            btnCloseDockerUpdate.addEventListener("click", closeVersionModal);
        }
        if (btnCloseDockerUpdateOk) {
            btnCloseDockerUpdateOk.addEventListener("click", closeVersionModal);
        }
        if (dockerUpdateModal) {
            dockerUpdateModal.addEventListener("click", (e) => {
                if (e.target === dockerUpdateModal) {
                    closeVersionModal();
                }
            });
        }
        if (btnCopyDockerCmd) {
            btnCopyDockerCmd.addEventListener("click", () => {
                navigator.clipboard.writeText("docker compose pull && docker compose up -d");
                showNotification("Příkaz zkopírován do schránky.", "success");
            });
        }
    };

    const loadConfig = async () => {
        try {
            const res = await fetch(API.config);
            if (res.ok) {
                const config = await res.json();
                userConfig = config;
                configName.value = config.name || "";
                configEmail.value = config.email || "";
                configPhone.value = config.phone || "";
                configZip.value = config.zip_code || "";
                if (configLocation) configLocation.value = config.location || "";
                configPassword.value = config.default_ad_password_b64 ? atob(config.default_ad_password_b64) : "";
                
                // Auto refresh
                configAutoRefresh.checked = config.auto_refresh_enabled || false;
                configRefreshInterval.value = config.auto_refresh_interval || "720";
                
                // Google AI (Gemini)
                if (configGeminiModel) {
                    configGeminiModel.value = config.gemini_model || "gemini-2.5-flash";
                }
                if (visionLoadingText) {
                    visionLoadingText.textContent = `${getActiveModelDisplayName()} detailně analyzuje fotografie předmětu...`;
                }
                loadGeminiModels(false);
                if (config.gemini_api_key) {
                    configGeminiKey.placeholder = "••••••••••••••••••••••••••••••••";
                } else {
                    configGeminiKey.placeholder = "AIza... (ponech prázdné pro beze změny)";
                }
                if (configAiDelivery) configAiDelivery.value = config.ai_delivery_options || "";
                if (configAiSeller) configAiSeller.value = config.ai_seller_context || "";

                // TrueNAS nastavení
                if (configTruenasUrl) configTruenasUrl.value = config.truenas_url || "";
                if (configTruenasAppName) configTruenasAppName.value = config.truenas_app_name || "listing-hub";
                if (config.truenas_api_key && configTruenasApiKey) {
                    configTruenasApiKey.placeholder = "••••••••••••••••••••••••••••••••";
                }

                // Google Kalendář & iCal feed
                if (calendarFeedUrl && config.calendar_token) {
                    const feedUrl = `${window.location.origin}/api/calendar/feed.ics?token=${config.calendar_token}`;
                    calendarFeedUrl.value = feedUrl;
                }
            }
        } catch (err) {
            showNotification("Nepodařilo se načíst konfiguraci", "error");
        }
    };

    const loadListings = async () => {
        try {
            const res = await fetch(API.listings);
            if (res.ok) {
                const data = await res.json();
                activeListings = data.active_listings || [];
                soldListings = data.sold_listings || [];
                renderListings();
                updateStats();
            }
        } catch (err) {
            showNotification("Nepodařilo se načíst seznam inzerátů", "error");
        }
    };

    const updateStats = () => {
        const liveListings = activeListings.filter(ad => ad.status === "Aktivní");
        const unsoldListings = activeListings.filter(ad => ad.status !== "Aktivní");
        
        statActiveCount.textContent = liveListings.length;
        statUnsoldCount.textContent = unsoldListings.length;
        statSoldCount.textContent = soldListings.length;
        
        const totalViews = liveListings.reduce((sum, ad) => sum + parseInt(ad.views || 0), 0);
        statTotalViews.textContent = totalViews;

        loadSoldStats();
    };

    const loadSoldStats = async () => {
        try {
            const res = await fetch("/api/listings/sold_stats");
            if (res.ok) {
                const data = await res.json();
                const stats = data.stats || data;
                const totalCountEl = document.getElementById("sold-stat-total-count");
                const totalProfitEl = document.getElementById("sold-stat-total-profit");
                const avgPriceEl = document.getElementById("sold-stat-avg-price");

                const totalSold = stats.total_sold !== undefined ? stats.total_sold : (data.total_sold || 0);
                const totalProfit = stats.total_profit !== undefined ? stats.total_profit : (data.total_profit || 0);
                const avgPrice = stats.avg_price !== undefined ? stats.avg_price : (data.avg_price || 0);

                if (totalCountEl) totalCountEl.textContent = `${totalSold} ks`;
                if (totalProfitEl) totalProfitEl.textContent = `${totalProfit.toLocaleString("cs-CZ")} Kč`;
                if (avgPriceEl) avgPriceEl.textContent = `${avgPrice.toLocaleString("cs-CZ")} Kč`;
            }
        } catch (err) {
            console.error("Chyba při načítání statistik prodeje:", err);
        }
    };

    // ==========================================
    // 2. RENDEROVÁNÍ KARET INZERÁTŮ
    // ==========================================

    const getDaysOld = (dateStr) => {
        if (!dateStr) return null;
        const parts = String(dateStr).split(" ")[0].split("-");
        if (parts.length === 3) {
            const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
            const now = new Date();
            now.setHours(0, 0, 0, 0);
            d.setHours(0, 0, 0, 0);
            const diffDays = Math.round((now - d) / (1000 * 60 * 60 * 24));
            return Math.max(0, diffDays);
        }
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return null;
        const now = new Date();
        return Math.max(0, Math.floor((now - d) / (1000 * 60 * 60 * 24)));
    };

    const getStagnationInfo = (ad) => {
        if (!ad || ad.status !== "Aktivní") {
            return { isStagnant: false, severity: "none", daysOld: 0, reason: "", discountPrice: 0, discountDiff: 0 };
        }

        const bState = (ad.portal_states && ad.portal_states.bazos) || {};
        const daysOld = getDaysOld(ad.date_created) || 0;
        const isTop = Boolean(ad.is_top && ad.top_expires_at && !isTopExpired(ad.top_expires_at));
        const topExpired = Boolean(ad.top_expires_at && isTopExpired(ad.top_expires_at));
        const rank = (ad.search_rank !== undefined && ad.search_rank !== null) ? ad.search_rank : bState.search_rank;
        const rankChecked = Boolean(ad.search_rank_checked_at || bState.search_rank_checked_at);

        // Výpočet doporučeného zlevnění (-5 %)
        const currentPrice = ad.price ? parseInt(ad.price, 10) : 0;
        let discountPrice = 0;
        let discountDiff = 0;
        if (currentPrice > 0) {
            const rawDiscount = currentPrice * 0.95;
            if (currentPrice >= 100000) {
                discountPrice = Math.floor(rawDiscount / 1000) * 1000;
            } else if (currentPrice >= 10000) {
                discountPrice = Math.floor(rawDiscount / 500) * 500;
            } else {
                discountPrice = Math.floor(rawDiscount / 50) * 50;
            }
            discountDiff = currentPrice - discountPrice;
        }

        // 1. Kritické hnití:
        // - Inzerát visí >= 14 dní A (vypršel TOP nebo rank > 20 nebo nebyl v top 100)
        // - NEBO inzerát visí >= 25 dní bez ohledu na ostatní faktory
        const isCriticallyOld = daysOld >= 14;
        const hasRankIssue = rankChecked && (rank === null || rank > 20);
        
        if ((isCriticallyOld && (topExpired || !isTop || hasRankIssue)) || daysOld >= 25) {
            let reason = `Inzerát visí už ${daysOld} dní`;
            if (topExpired) {
                reason += `, placený TOP vypršel ${formatTopExpiry(ad.top_expires_at)}`;
            } else if (!isTop) {
                reason += `, je bez placeného TOPu`;
            }
            if (rank) {
                reason += ` a propadl na #${rank} pozici`;
            } else if (rankChecked) {
                reason += ` a propadl mimo prvních 100 inzerátů`;
            }
            return {
                isStagnant: true,
                severity: "critical",
                daysOld: daysOld,
                reason: reason,
                discountPrice: discountPrice,
                discountDiff: discountDiff
            };
        }

        // 2. Začínající stagnace:
        // - Inzerát visí 7 až 13 dní bez TOPu, nebo rank 21–50
        if ((daysOld >= 7 && !isTop) || (rankChecked && rank !== null && rank > 20)) {
            let reason = `Visí ${daysOld} dní`;
            if (topExpired) reason += ` (TOP vypršel)`;
            if (rank) reason += `, aktuální pozice #${rank}`;
            return {
                isStagnant: true,
                severity: "warning",
                daysOld: daysOld,
                reason: reason,
                discountPrice: discountPrice,
                discountDiff: discountDiff
            };
        }

        return {
            isStagnant: false,
            severity: "fresh",
            daysOld: daysOld,
            reason: "",
            discountPrice: discountPrice,
            discountDiff: discountDiff
        };
    };

    const sortListingsArray = (arr, sortType) => {
        return [...arr].sort((a, b) => {
            if (sortType === "stagnant_desc") {
                const stagA = getStagnationInfo(a);
                const stagB = getStagnationInfo(b);
                const scoreA = (stagA.severity === "critical" ? 300 : stagA.severity === "warning" ? 150 : 0) + (stagA.daysOld || 0);
                const scoreB = (stagB.severity === "critical" ? 300 : stagB.severity === "warning" ? 150 : 0) + (stagB.daysOld || 0);
                return scoreB - scoreA;
            }

            const daysA = getDaysOld(a.date_created);
            const daysB = getDaysOld(b.date_created);
            
            if (sortType === "days_old_desc") {
                const valA = daysA !== null ? daysA : -1;
                const valB = daysB !== null ? daysB : -1;
                return valB - valA;
            } else if (sortType === "days_old_asc") {
                const valA = daysA !== null ? daysA : 99999;
                const valB = daysB !== null ? daysB : 99999;
                return valA - valB;
            } else if (sortType === "sold_at_desc") {
                const dateA = a.sold_at || a.date_created || "";
                const dateB = b.sold_at || b.date_created || "";
                return dateB.localeCompare(dateA);
            } else if (sortType === "sold_at_asc") {
                const dateA = a.sold_at || a.date_created || "";
                const dateB = b.sold_at || b.date_created || "";
                return dateA.localeCompare(dateB);
            } else if (sortType === "views_desc") {
                return (parseInt(b.views || 0, 10)) - (parseInt(a.views || 0, 10));
            } else if (sortType === "price_desc") {
                const pA = a.sale_price !== undefined && a.sale_price !== null ? a.sale_price : (a.price || 0);
                const pB = b.sale_price !== undefined && b.sale_price !== null ? b.sale_price : (b.price || 0);
                return (parseInt(pB, 10)) - (parseInt(pA, 10));
            } else if (sortType === "price_asc") {
                const pA = a.sale_price !== undefined && a.sale_price !== null ? a.sale_price : (a.price || 0);
                const pB = b.sale_price !== undefined && b.sale_price !== null ? b.sale_price : (b.price || 0);
                return (parseInt(pA, 10)) - (parseInt(pB, 10));
            } else if (sortType === "title_asc") {
                return (a.title || "").localeCompare(b.title || "", "cs");
            }
            return 0;
        });
    };

    const filterListingsArray = (arr, q) => {
        if (!q || !q.trim()) return arr;
        const needle = q.trim().toLowerCase();
        return arr.filter(ad => {
            return (ad.title && ad.title.toLowerCase().includes(needle)) ||
                   (ad.description && ad.description.toLowerCase().includes(needle)) ||
                   (ad.price && String(ad.price).includes(needle)) ||
                   (ad.sale_price && String(ad.sale_price).includes(needle)) ||
                   (ad.sold_notes && ad.sold_notes.toLowerCase().includes(needle)) ||
                   (ad.notes && ad.notes.toLowerCase().includes(needle));
        });
    };

    const updateBatchActionBar = () => {
        const batchBar = document.getElementById("batch-action-bar");
        const countBadge = document.getElementById("batch-selected-count");
        if (!batchBar) return;
        
        if (selectedBatchAdIds.size > 0) {
            batchBar.style.display = "flex";
            if (countBadge) countBadge.textContent = selectedBatchAdIds.size;
        } else {
            batchBar.style.display = "none";
        }
    };

    const renderListings = () => {
        // Filtrování aktivních a neaktivních (expirovaných/draftů)
        let liveListings = activeListings.filter(ad => ad.status === "Aktivní");
        let unsoldListings = activeListings.filter(ad => ad.status !== "Aktivní");
        let displayedSoldListings = [...soldListings];

        // Aplikace vyhledávání a řazení
        liveListings = filterListingsArray(liveListings, activeFilterQuery);
        liveListings = sortListingsArray(liveListings, activeSort);

        unsoldListings = filterListingsArray(unsoldListings, unsoldFilterQuery);
        unsoldListings = sortListingsArray(unsoldListings, unsoldSort);

        displayedSoldListings = filterListingsArray(displayedSoldListings, soldFilterQuery);
        displayedSoldListings = sortListingsArray(displayedSoldListings, soldSort);

        // Aktivní inzeráty
        activeListingsContainer.innerHTML = "";
        if (liveListings.length === 0) {
            activeListingsContainer.innerHTML = `<div class="loading-state"><i class="fa-solid fa-face-smile"></i> Žádné aktivní inzeráty k zobrazení.</div>`;
        } else {
            liveListings.forEach(ad => {
                const card = createAdCard(ad, false);
                activeListingsContainer.appendChild(card);
            });
        }

        // Smart Drop Alert pro aktivní inzeráty (vypršelý TOP nebo propadlá pozice)
        if (typeof updateSmartDropAlerts === "function") {
            updateSmartDropAlerts(liveListings);
        }

        // Věci k prodeji (expirované/drafty)
        unsoldListingsContainer.innerHTML = "";
        if (unsoldListings.length === 0) {
            unsoldListingsContainer.innerHTML = `<div class="loading-state"><i class="fa-solid fa-tags"></i> Žádné věci k prodeji.</div>`;
        } else {
            unsoldListings.forEach(ad => {
                const card = createAdCard(ad, false);
                unsoldListingsContainer.appendChild(card);
            });
        }

        // Prodané inzeráty
        soldListingsContainer.innerHTML = "";
        if (displayedSoldListings.length === 0) {
            soldListingsContainer.innerHTML = `<div class="loading-state"><i class="fa-solid fa-box"></i> Žádné prodané věci.</div>`;
        } else {
            displayedSoldListings.forEach(ad => {
                const card = createAdCard(ad, true);
                soldListingsContainer.appendChild(card);
            });
        }

        // Aktualizujeme stav spodní lišty hromadných akcí
        updateBatchActionBar();

        // Spustíme IntersectionObserver pro price chipy
        if (typeof initPriceChipObserver === "function") {
            initPriceChipObserver();
        }
    };

    const isTopExpired = (top_expires_at) => {
        if (!top_expires_at) return true;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const expDate = new Date(top_expires_at);
        return expDate < today;
    };

    const formatTopExpiry = (top_expires_at) => {
        if (!top_expires_at) return '';
        const [year, month, day] = top_expires_at.split('-');
        return `${parseInt(day)}. ${parseInt(month)}.`;
    };

    const formatChannelName = (channel) => {
        if (!channel) return "";
        const ch = channel.toLowerCase();
        if (ch === "bazos") return "Bazoš.cz";
        if (ch === "facebook" || ch === "fb") return "FB Marketplace";
        if (ch === "sbazar") return "Sbazar.cz";
        if (ch === "vinted") return "Vinted";
        if (ch === "aukro") return "Aukro.cz";
        if (ch === "osobne") return "Osobní předání / Známý";
        if (ch === "jiny") return "Jiný kanál";
        return channel;
    };

    const getPortalBadgeConfig = (portalKey, label) => {
        const key = (portalKey || "").toLowerCase();
        switch (key) {
            case "bazos":
                return { icon: "fa-solid fa-cube", color: "var(--accent, #835cdf)", bg: "rgba(131, 92, 223, 0.18)", border: "rgba(131, 92, 223, 0.4)", name: "Bazoš" };
            case "facebook":
            case "fb":
                return { icon: "fa-brands fa-facebook", color: "#38bdf8", bg: "rgba(56, 189, 248, 0.18)", border: "rgba(56, 189, 248, 0.4)", name: "FB Marketplace" };
            case "sbazar":
                return { icon: "fa-solid fa-store", color: "#f87171", bg: "rgba(248, 113, 113, 0.18)", border: "rgba(248, 113, 113, 0.4)", name: "Sbazar" };
            case "vinted":
                return { icon: "fa-solid fa-shirt", color: "#2dd4bf", bg: "rgba(45, 212, 191, 0.18)", border: "rgba(45, 212, 191, 0.4)", name: "Vinted" };
            case "aukro":
                return { icon: "fa-solid fa-gavel", color: "#eab308", bg: "rgba(234, 179, 8, 0.18)", border: "rgba(234, 179, 8, 0.4)", name: "Aukro" };
            default:
                return { icon: "fa-solid fa-globe", color: "#cbd5e1", bg: "rgba(255, 255, 255, 0.08)", border: "rgba(255, 255, 255, 0.2)", name: label || portalKey || "Portál" };
        }
    };

    const renderPortalBadgesHtml = (ad) => {
        let badgesHtml = "";
        const pStates = ad.portal_states || {};
        const renderedPortals = new Set();

        // 1. Vykreslit všechny portály přítomné v portal_states
        Object.entries(pStates).forEach(([portalKey, state]) => {
            const normKey = portalKey.toLowerCase();
            renderedPortals.add(normKey);
            const cfg = getPortalBadgeConfig(normKey, state.portal_label);
            const label = escapeHtml(state.portal_label || cfg.name);
            const url = state.url || (normKey === "bazos" ? ad.url : "");
            const viewsVal = (state.views !== undefined && state.views !== null) ? state.views : (normKey === "bazos" ? (ad.views || 0) : 0);
            const viewsHtml = `
                <span class="badge-portal-views" data-ad-id="${ad.id}" data-portal="${escapeHtml(normKey)}" data-portal-label="${label}" data-views="${viewsVal}" data-url="${escapeHtml(url)}" style="cursor: pointer; display: inline-flex; align-items: center; gap: 2px; padding: 1px 4px; background: rgba(0, 0, 0, 0.32); border-radius: 4px; margin-left: 2px; font-size: 0.65rem;" title="Klikni pro změnu počtu zhlédnutí na ${label} (aktuálně: ${viewsVal})">
                    <i class="fa-regular fa-eye" style="font-size: 0.6rem;"></i> ${viewsVal}
                </span>
            `;

            let actionHtml = "";
            if (url) {
                actionHtml = `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none; margin-left: 2px;" title="Přejít na živý inzerát (${label})"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.65rem;"></i></a>`;
            } else {
                actionHtml = `<span class="badge-add-url" data-ad-id="${ad.id}" data-portal="${escapeHtml(normKey)}" data-portal-label="${label}" style="cursor: pointer; opacity: 0.7; font-size: 0.65rem; margin-left: 2px; text-decoration: underline;" title="Klikni pro doplnění odkazu">+URL</span>`;
            }

            badgesHtml += `
                <span class="portal-badge badge-${escapeHtml(normKey)}" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; background: ${cfg.bg}; color: ${cfg.color}; border: 1px solid ${cfg.border};">
                    <i class="${cfg.icon}"></i> ${label} ${viewsHtml} ${actionHtml}
                </span>
            `;
        });

        // 2. Fallbacky pro Bazoš a Aukro pokud nejsou v portal_states
        if (!renderedPortals.has("bazos")) {
            const hasBazos = ad.target_bazos || Boolean(ad.url);
            badgesHtml += `
                <span class="portal-badge badge-bazos" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; ${hasBazos ? 'background: rgba(131, 92, 223, 0.2); color: var(--accent); border: 1px solid rgba(131, 92, 223, 0.4);' : 'background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1);'}">
                    <i class="fa-solid ${hasBazos ? 'fa-square-check' : 'fa-square'}"></i> Bazoš ${ad.url ? `<a href="${escapeHtml(ad.url)}" target="_blank" style="color: inherit; text-decoration: none; margin-left: 2px;"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.65rem;"></i></a>` : ''}
                </span>
            `;
        }

        if (!renderedPortals.has("aukro") && ad.target_aukro) {
            badgesHtml += `
                <span class="portal-badge badge-aukro" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(234, 179, 8, 0.2); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.4);">
                    <i class="fa-solid fa-square-check"></i> Aukro
                </span>
            `;
        }

        // 3. Počet vystavení / obnovení
        if (ad.is_reposted) {
            badgesHtml += `
                <span class="portal-badge" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4);" title="${ad.publication_count}. vystavení (přeceněno/obnoveno)">
                    <i class="fa-solid fa-arrows-rotate"></i> ${ad.publication_count}. vystavení
                </span>
            `;
        }

        // 4. Bazoš TOP odznak
        if (ad.is_top && ad.top_expires_at && !isTopExpired(ad.top_expires_at)) {
            badgesHtml += `
                <span class="portal-badge" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 700; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(255, 165, 0, 0.2); color: #ff9900; border: 1px solid rgba(255, 165, 0, 0.5); box-shadow: 0 0 6px rgba(255,140,0,0.3);" title="${escapeHtml(ad.top_info || 'Aktivní placené TOPování na Bazoši')}">
                    🔥 TOP <span style="font-size:0.65rem;opacity:0.85;">(do ${formatTopExpiry(ad.top_expires_at)})</span>
                </span>
            `;
        } else if (ad.top_expires_at && isTopExpired(ad.top_expires_at)) {
            badgesHtml += `
                <span class="portal-badge badge-top-expired btn-open-sms-top" data-ad-id="${ad.id}" style="cursor: pointer; font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35);" title="Placený TOP vypršel ${formatTopExpiry(ad.top_expires_at)}. Klikni pro 1-Click TOPování!">
                    ⚠️ TOP vypršel <span style="font-size:0.65rem;opacity:0.85;">(${formatTopExpiry(ad.top_expires_at)})</span>
                </span>
            `;
        }

        // 5. Bazoš Search Rank Badge
        const hasBazosAd = ad.target_bazos || Boolean(ad.url) || Boolean(pStates.bazos);
        if (hasBazosAd && !ad.is_sold) {
            const bState = pStates.bazos || {};
            const rank = (ad.search_rank !== undefined && ad.search_rank !== null) ? ad.search_rank : bState.search_rank;
            const page = (ad.search_rank_page !== undefined && ad.search_rank_page !== null) ? ad.search_rank_page : bState.search_rank_page;
            const total = (ad.search_rank_total !== undefined && ad.search_rank_total !== null) ? ad.search_rank_total : bState.search_rank_total;
            const q = ad.search_query || bState.search_query || "";
            const checkedAt = ad.search_rank_checked_at || bState.search_rank_checked_at;

            let rankStyle = "";
            let rankText = "";
            let rankTip = "";

            if (rank !== null && rank !== undefined) {
                if (rank <= 5) {
                    rankStyle = "background: rgba(234, 179, 8, 0.22); color: #fbbf24; border: 1px solid rgba(234, 179, 8, 0.5);";
                    rankText = `🏆 #${rank} (1. str.)`;
                    rankTip = `Pozice #${rank} z ${total || '?'} výsledků pro '${q}'. Špičková viditelnost!`;
                } else if (rank <= 20) {
                    rankStyle = "background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);";
                    rankText = `🟢 #${rank} (1. str.)`;
                    rankTip = `Pozice #${rank} z ${total || '?'} výsledků pro '${q}'. Na 1. straně.`;
                } else if (rank <= 50) {
                    rankStyle = "background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);";
                    rankText = `🟡 #${rank} (${page}. str.)`;
                    rankTip = `Pozice #${rank} z ${total || '?'} výsledků pro '${q}'. Zvažte TOPování.`;
                } else {
                    rankStyle = "background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);";
                    rankText = `📉 #${rank} (${page}. str.)`;
                    rankTip = `Pozice #${rank} z ${total || '?'} výsledků pro '${q}'. Inzerát zapadá!`;
                }
            } else if (checkedAt) {
                rankStyle = "background: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.5);";
                rankText = `📉 >100 (zapadlé)`;
                rankTip = `Nenalezeno v prvních 5 stranách (z ${total || '>100'} výsledků pro '${q}').`;
            } else {
                rankStyle = "background: rgba(255, 255, 255, 0.06); color: var(--text-muted); border: 1px solid rgba(255, 255, 255, 0.15);";
                rankText = `🔍 Pozice: zjistit`;
                rankTip = `Klikni pro vyhledání aktuální pozice na Bazoši`;
            }

            badgesHtml += `
                <span class="portal-badge badge-bazos-rank" data-ad-id="${ad.id}" data-current-query="${escapeHtml(q)}" style="cursor: pointer; font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; ${rankStyle}" title="${escapeHtml(rankTip)} (Klikni pro kontrolu)">
                    ${rankText} <i class="fa-solid fa-arrows-rotate" style="font-size: 0.6rem; opacity: 0.7;"></i>
                </span>
            `;

            // Tlačítko ⚡ Topovat (pokud inzerát nemá aktivní placený TOP nebo je mimo top 20)
            const hasActiveTop = ad.is_top && ad.top_expires_at && !isTopExpired(ad.top_expires_at);
            if (!hasActiveTop || (rank !== null && rank > 20)) {
                badgesHtml += `
                    <span class="portal-badge btn-open-sms-top" data-ad-id="${ad.id}" style="cursor: pointer; font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 700; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(255, 153, 0, 0.18); color: #ff9900; border: 1px solid rgba(255, 153, 0, 0.45); box-shadow: 0 0 6px rgba(255,153,0,0.2);" title="Otevřít 1-Click TOPování (49 Kč)">
                        ⚡ Topovat (49 Kč)
                    </span>
                `;
            }
        }

        return badgesHtml;
    };

    const promptUpdatePortalUrl = async (listingId, portalName, portalLabel, currentUrl) => {
        const url = prompt(`Vlož odkaz na inzerát pro portál ${portalLabel}:`, currentUrl || "");
        if (url === null) return;
        const cleanUrl = url.trim();
        try {
            showNotification(`Ukládám odkaz na ${portalLabel}...`, "info");
            const res = await fetch(`/api/listings/${listingId}/portal-url`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    portal_name: portalName,
                    url: cleanUrl
                })
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showNotification(`Odkaz pro ${portalLabel} byl uložen!`, "success");
                loadListings();
            } else {
                showNotification(data.message || "Chyba při ukládání odkazu.", "error");
            }
        } catch (err) {
            showNotification("Chyba při ukládání odkazu: " + err.message, "error");
        }
    };

    const promptUpdatePortalViews = async (listingId, portalName, portalLabel, currentViews, url, spanElement) => {
        let msg = `Zadej aktuální počet zhlédnutí pro ${portalLabel}:`;
        if (url && (url.includes("sportovnivozy.cz") || url.includes("rajveteranu.cz") || url.includes("motorkari.cz") || url.includes("bazos.cz"))) {
            msg += "\n(Tip: Pro automatické stažení z webu zadej 'auto' nebo nech pole prázdné)";
        }
        const input = prompt(msg, currentViews !== undefined && currentViews !== null ? currentViews : 0);
        if (input === null) return;
        const cleanInput = input.trim().toLowerCase();

        if (cleanInput === "auto" || (cleanInput === "" && url)) {
            try {
                showNotification(`Stahuji zhlédnutí z webu pro ${portalLabel}...`, "info");
                const res = await fetch(`/api/listings/${listingId}/portal-views-refresh`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ portal_name: portalName })
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification(data.message || `Zhlédnutí pro ${portalLabel} aktualizováno!`, "success");
                    if (spanElement) {
                        spanElement.innerHTML = `<i class="fa-regular fa-eye" style="font-size: 0.6rem;"></i> ${data.views}`;
                        spanElement.setAttribute("data-views", data.views);
                        spanElement.setAttribute("title", `Klikni pro změnu počtu zhlédnutí na ${portalLabel} (aktuálně: ${data.views})`);
                    } else {
                        loadListings();
                    }
                } else {
                    showNotification(data.message || "Nepodařilo se automaticky stáhnout zhlédnutí.", "warning");
                }
            } catch (err) {
                showNotification("Chyba při stahování: " + err.message, "error");
            }
            return;
        }

        const viewsNum = parseInt(cleanInput, 10);
        if (isNaN(viewsNum) || viewsNum < 0) {
            showNotification("Zadej platné nezáporné číslo zhlédnutí.", "error");
            return;
        }

        try {
            showNotification(`Ukládám zhlédnutí pro ${portalLabel}...`, "info");
            const res = await fetch(`/api/listings/${listingId}/portal-views`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    portal_name: portalName,
                    views: viewsNum
                })
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showNotification(`Počet zhlédnutí pro ${portalLabel} nastaven na ${viewsNum}!`, "success");
                if (spanElement) {
                    spanElement.innerHTML = `<i class="fa-regular fa-eye" style="font-size: 0.6rem;"></i> ${viewsNum}`;
                    spanElement.setAttribute("data-views", viewsNum);
                    spanElement.setAttribute("title", `Klikni pro změnu počtu zhlédnutí na ${portalLabel} (aktuálně: ${viewsNum})`);
                } else {
                    loadListings();
                }
            } else {
                showNotification(data.message || "Chyba při ukládání zhlédnutí.", "error");
            }
        } catch (err) {
            showNotification("Chyba při ukládání zhlédnutí: " + err.message, "error");
        }
    };

    // --- BAZOŠ SEARCH RANK & SMS TOP HELPER ---
    let currentSmsTopListingId = null;

    const checkBazosRank = async (listingId, query = null, triggerEl = null) => {
        try {
            if (triggerEl) {
                triggerEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="font-size:0.6rem;"></i> Ověřuji...`;
                triggerEl.style.opacity = "0.7";
                triggerEl.style.pointerEvents = "none";
            }
            showNotification("Zjišťuji pozici na Bazoši...", "info");
            const res = await fetch(`/api/listings/${listingId}/check_rank`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                const rd = data.data;
                if (rd.found) {
                    showNotification(`Pozice nalezena: #${rd.rank_position} (${rd.rank_page}. strana) pro dotaz '${rd.query}'`, "success");
                } else {
                    showNotification(`Inzerát nebyl nalezen v prvních 5 stránkách pro '${rd.query}' (>100. pozice).`, "warning");
                }
                await loadListings();
            } else {
                showNotification(data.message || "Chyba při zjišťování pozice na Bazoši.", "error");
                if (triggerEl) {
                    triggerEl.style.opacity = "1";
                    triggerEl.style.pointerEvents = "auto";
                }
            }
        } catch (err) {
            showNotification("Chyba sítě při ověřování pozice: " + err.message, "error");
            if (triggerEl) {
                triggerEl.style.opacity = "1";
                triggerEl.style.pointerEvents = "auto";
            }
        }
    };

    const promptCheckBazosRank = async (listingId, currentQuery, triggerEl) => {
        const customQuery = prompt(
            `Zadej hledanou frázi na Bazoši pro ověření pozice:\n(Ponech výchozí nebo uprav, např. 'VW Arteon' či 'VW Arteon SB')`,
            currentQuery || ""
        );
        if (customQuery === null) return;
        await checkBazosRank(listingId, customQuery.trim() || null, triggerEl);
    };

    const closeSmsTopModal = () => {
        const modal = document.getElementById("sms-top-modal");
        if (modal) modal.style.display = "none";
        currentSmsTopListingId = null;
    };

    const openSmsTopModal = async (listingId) => {
        currentSmsTopListingId = listingId;
        const modal = document.getElementById("sms-top-modal");
        if (!modal) return;

        const titleEl = document.getElementById("sms-top-listing-title");
        const mobileLink = document.getElementById("sms-top-mobile-link");
        const qrContainer = document.getElementById("sms-top-qr-container");
        const textCopy = document.getElementById("sms-top-text-copy");
        const numberCopy = document.getElementById("sms-top-number-copy");

        if (titleEl) titleEl.textContent = "Načítám inzerát...";
        if (textCopy) textCopy.textContent = "BAZOS ...";
        if (numberCopy) numberCopy.textContent = "90333";
        if (qrContainer) qrContainer.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="color: #666; font-size: 1.5rem;"></i>';

        modal.style.display = "flex";

        try {
            const res = await fetch(`/api/listings/${listingId}/sms_top_info`);
            const data = await res.json();
            if (!res.ok || data.status !== "success") {
                showNotification(data.message || "Nepodařilo se načíst instrukce pro TOPování.", "error");
                closeSmsTopModal();
                return;
            }

            if (titleEl) titleEl.textContent = data.title || "Inzerát";
            if (textCopy) textCopy.textContent = data.sms_body;
            if (numberCopy) numberCopy.textContent = data.phone_number;

            // Správný odkaz pro mobil (iOS vyžaduje &body=, Android ?body=)
            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
            if (mobileLink) {
                mobileLink.href = isIOS ? data.sms_uri_ios : data.sms_uri;
            }

            // QR kód
            if (qrContainer) {
                qrContainer.innerHTML = "";
                const qrText = data.qr_content;
                if (typeof QRCode !== "undefined") {
                    new QRCode(qrContainer, {
                        text: qrText,
                        width: 108,
                        height: 108,
                        colorDark: "#000000",
                        colorLight: "#ffffff",
                        correctLevel: QRCode.CorrectLevel.M
                    });
                } else {
                    const qrImg = document.createElement("img");
                    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=108x108&data=${encodeURIComponent(qrText)}`;
                    qrImg.alt = "SMS QR";
                    qrImg.style.width = "108px";
                    qrImg.style.height = "108px";
                    qrImg.style.display = "block";
                    qrContainer.appendChild(qrImg);
                }
            }
        } catch (e) {
            showNotification(`Chyba načítání SMS TOP: ${e.message}`, "error");
            closeSmsTopModal();
        }
    };

    const updateSmartDropAlerts = (activeListings) => {
        const container = document.getElementById("smart-drop-alert-container");
        if (!container) return;

        // Inzeráty, které spadly z předních pozic nebo jim vypršel TOP
        const droppedListings = (activeListings || []).filter(ad => {
            const bState = (ad.portal_states && ad.portal_states.bazos) || {};
            const hasBazos = ad.target_bazos || bState.portal_item_id || ad.url;
            if (!hasBazos) return false;

            const isTop = ad.is_top && !isTopExpired(ad.top_expires_at);
            const rank = (ad.search_rank !== undefined && ad.search_rank !== null) ? ad.search_rank : bState.search_rank;
            const checkedAt = ad.search_rank_checked_at || bState.search_rank_checked_at;
            
            // 1. Zkontrolovaný rank a je mimo top 20 nebo zapadlý (>100)
            if (!isTop && checkedAt && (rank === null || rank > 20)) {
                return true;
            }
            // 2. Vypršel placený TOP
            if (!isTop && ad.top_expires_at && isTopExpired(ad.top_expires_at)) {
                return true;
            }
            return false;
        });

        if (droppedListings.length === 0) {
            container.style.display = "none";
            container.innerHTML = "";
            return;
        }

        const firstDropped = droppedListings[0];
        const bState = (firstDropped.portal_states && firstDropped.portal_states.bazos) || {};
        const rank = (firstDropped.search_rank !== undefined && firstDropped.search_rank !== null) ? firstDropped.search_rank : bState.search_rank;
        const rankLabel = rank ? `#${rank}` : `>100 (zapadlý)`;

        container.style.display = "block";
        container.innerHTML = `
            <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(245, 158, 11, 0.12)); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 12px; padding: 0.9rem 1.25rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <div style="display: flex; align-items: center; gap: 0.85rem; flex-grow: 1;">
                    <div style="background: rgba(245, 158, 11, 0.2); width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fbbf24; font-size: 1.15rem; flex-shrink: 0;">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                    </div>
                    <div>
                        <div style="font-weight: 700; color: #fff; font-size: 0.92rem;">
                            ⚠️ <strong>${escapeHtml(firstDropped.title)}</strong> je na pozici <span style="color: #fbbf24; font-weight: 800;">${rankLabel}</span> (vypršel TOP)
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">
                            Před víkendem doporučujeme provést SMS TOP nebo znovuvystavení pro okamžitý návrat na 1. stranu.
                            ${droppedListings.length > 1 ? `<span style="color: #67e8f9; margin-left: 4px;">(+${droppedListings.length - 1} další inzerát vyžaduje pozornost)</span>` : ''}
                        </div>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <button type="button" class="btn btn-primary btn-alert-sms-top" data-ad-id="${firstDropped.id}" style="background: linear-gradient(135deg, #ff9900, #f59e0b); border: none; color: #000; font-weight: 700; font-size: 0.85rem; padding: 0.45rem 0.95rem; border-radius: 8px; display: inline-flex; align-items: center; gap: 0.4rem; box-shadow: 0 2px 10px rgba(255,153,0,0.3); cursor: pointer;">
                        <i class="fa-solid fa-bolt"></i> Topovat (49 Kč)
                    </button>
                    <button type="button" class="btn btn-secondary btn-alert-repost" data-ad-id="${firstDropped.id}" style="font-size: 0.85rem; padding: 0.45rem 0.95rem; border-radius: 8px; display: inline-flex; align-items: center; gap: 0.4rem; cursor: pointer;">
                        <i class="fa-solid fa-arrows-rotate"></i> Znovu vystavit zdarma
                    </button>
                </div>
            </div>
        `;

        container.querySelector(".btn-alert-sms-top")?.addEventListener("click", () => {
            openSmsTopModal(firstDropped.id);
        });

        container.querySelector(".btn-alert-repost")?.addEventListener("click", () => {
            const adCard = document.querySelector(`.listing-card[data-ad-id="${firstDropped.id}"]`);
            const postBtn = adCard?.querySelector(".btn-post-action");
            if (postBtn) {
                postBtn.click();
            } else {
                openEditModal(firstDropped);
            }
        });
    };

    const createAdCard = (ad, isSold) => {
        const card = document.createElement("div");
        card.className = "listing-card";
        if (isSold) {
            card.classList.add("is-sold");
        }
        if (selectedBatchAdIds.has(ad.id)) {
            card.classList.add("batch-selected");
            card.classList.add("selected-batch-card");
        }
        
        const titleText = ad.title || "Bez názvu";
        const descText = ad.description || "Žádný popis...";
        const priceVal = ad.price ? `${ad.price} Kč` : "Dohodou";
        const viewsCount = ad.views || 0;
        const dateStr = ad.date_created || "Dosud nevystaveno";
        const urlStr = ad.url || "";
        
        // Výpočet stagnace / hnití inzerátu
        const stag = getStagnationInfo(ad);
        if (stag.isStagnant) {
            if (stag.severity === "critical") {
                card.classList.add("card-stagnant-critical");
            } else if (stag.severity === "warning") {
                card.classList.add("card-stagnant-warning");
            }
        }

        // Výpočet stáří inzerátu pro indikaci potřeby přetopování
        const daysOld = getDaysOld(ad.date_created);
        let ageBadgeHtml = "";
        if (daysOld !== null && ad.status === "Aktivní") {
            let ageClass = "age-fresh";
            let ageLabel = `před ${daysOld} dny`;
            if (daysOld === 0) ageLabel = "dnes";
            else if (daysOld === 1) ageLabel = "včera";
            
            if (daysOld >= 30) {
                ageClass = "age-stale";
                ageLabel = `${daysOld} dní (k obnově)`;
            } else if (daysOld >= 14) {
                ageClass = "age-warning";
                ageLabel = `${daysOld} dní`;
            }
            ageBadgeHtml = `<span class="age-badge ${ageClass}" title="Stáří inzerátu od vystavení">${ageLabel}</span>`;
        }

        let stagnantHeaderBadgeHtml = "";
        if (stag.isStagnant) {
            if (stag.severity === "critical") {
                stagnantHeaderBadgeHtml = `<span class="stagnant-pill-critical" title="${escapeHtml(stag.reason)}"><i class="fa-solid fa-skull-crossbones"></i> Hnije (${stag.daysOld} dní)</span>`;
            } else {
                stagnantHeaderBadgeHtml = `<span class="stagnant-pill-warning" title="${escapeHtml(stag.reason)}"><i class="fa-solid fa-triangle-exclamation"></i> Stagnuje (${stag.daysOld} dní)</span>`;
            }
        }

        let stagnationBoxHtml = "";
        if (stag.isStagnant && !isSold) {
            const discountLabel = stag.discountDiff > 0 ? `-${stag.discountDiff.toLocaleString("cs-CZ")} Kč` : `-5 %`;
            stagnationBoxHtml = `
                <div class="stagnation-action-box">
                    <div class="stagnation-status">
                        <i class="fa-solid ${stag.severity === 'critical' ? 'fa-triangle-exclamation' : 'fa-clock'}"></i>
                        <div>
                            <strong>${stag.severity === 'critical' ? '🥀 Inzerát hnije na Bazoši:' : '⚠️ Začínající stagnace:'}</strong>
                            <span>${escapeHtml(stag.reason)}. Doporučená akce:</span>
                        </div>
                    </div>
                    <div class="stagnation-actions">
                        <button type="button" class="btn-stagnant-action btn-stagnant-top btn-quick-top-action" data-ad-id="${ad.id}" title="Otevřít 1-Click TOP">
                            <i class="fa-solid fa-bolt"></i> 1-Click TOP (49 Kč)
                        </button>
                        <button type="button" class="btn-stagnant-action btn-stagnant-repost btn-quick-repost-action" data-ad-id="${ad.id}" title="Smazat a vystavit znovu na 1. pozici zdarma">
                            <i class="fa-solid fa-arrows-rotate"></i> Znovuvystavit zdarma
                        </button>
                        ${stag.discountPrice > 0 ? `
                        <button type="button" class="btn-stagnant-action btn-stagnant-discount btn-quick-discount-action" data-ad-id="${ad.id}" data-new-price="${stag.discountPrice}" data-diff="${stag.discountDiff}" title="Znovuvystavit se slevou 5 % na ${stag.discountPrice.toLocaleString('cs-CZ')} Kč">
                            <i class="fa-solid fa-arrow-trend-down"></i> Zlevnit o 5 % (${discountLabel})
                        </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            ${!isSold ? `
                <input type="checkbox" class="card-select-checkbox" data-ad-id="${ad.id}" ${selectedBatchAdIds.has(ad.id) ? 'checked' : ''} style="${isBatchModeActive ? 'display: block;' : 'display: none;'}" title="Vybrat do dávky">
            ` : ''}
            <div>
                <div class="listing-header">
                    <h4 class="listing-title" title="Klikni pro editaci">${escapeHtml(titleText)}</h4>
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        ${stagnantHeaderBadgeHtml}
                        <span class="price-badge">${priceVal}</span>
                        <button type="button" class="btn-card-delete" title="Smazat inzerát" style="background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; font-size: 0.85rem; border-radius: 4px; transition: color 0.2s;">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </div>
                <div class="portal-badges" style="display: flex; gap: 0.5rem; margin-top: -0.25rem; margin-bottom: 0.75rem; flex-wrap: wrap;">
                    ${renderPortalBadgesHtml(ad)}
                </div>
                <p class="listing-desc">${escapeHtml(descText)}</p>
                ${stagnationBoxHtml}
                ${!isSold && ad.price ? `
                <div class="price-chip chip-loading" data-ad-id="${ad.id}" data-ad-price="${ad.price || 0}" data-loaded="false" title="Klikni pro detail cenového srovnání">
                    <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 0.7rem;"></i>
                    <span class="chip-text">Analyzuji trh...</span>
                </div>` : ''}
            </div>
            <div>
                <div class="listing-meta">
                    <div class="meta-item" title="Fotky k nahrání (k nahrání / celkem ve složce)">
                        <i class="fa-solid fa-camera"></i>
                        <span>${ad.photos_count !== undefined ? `${ad.photos_upload_count}/${ad.photos_count}` : '0'} fotek</span>
                    </div>
                    <div class="meta-item" title="${ad.cumulative_views && ad.cumulative_views > viewsCount ? `Tento cyklus: ${viewsCount}, Celkem přes všechny cykly: ${ad.cumulative_views}` : `${viewsCount} zhlédnutí`}">
                        <i class="fa-solid fa-eye"></i>
                        <span>${viewsCount} zhl.${ad.cumulative_views && ad.cumulative_views > viewsCount ? ` (celk. ${ad.cumulative_views})` : ''}</span>
                    </div>
                    <div class="meta-item" style="display: flex; align-items: center; gap: 0.4rem;">
                        <i class="fa-solid fa-calendar"></i>
                        <span>${dateStr}</span>
                        ${ageBadgeHtml}
                    </div>
                    ${urlStr ? `
                        <div class="meta-item">
                            <i class="fa-solid fa-link"></i>
                            <a href="${urlStr}" target="_blank" class="text-muted" style="color: var(--secondary); text-decoration: none;">Odkaz</a>
                        </div>
                    ` : ''}
                </div>
                <div class="listing-actions">
                    <button class="btn btn-secondary btn-edit"><i class="fa-solid fa-pen-to-square"></i> Upravit</button>
                    ${!isSold ? `
                        <button class="btn btn-secondary btn-manual-publish-action" title="Zveřejnit ručně na FB Marketplace, Sbazar, Vinted..."><i class="fa-solid fa-share-nodes"></i> Zveřejnit jinde...</button>
                        <button class="btn btn-secondary btn-mark-sold" title="Zaznamenat prodej položky"><i class="fa-solid fa-handshake"></i> Prodáno</button>
                        <button class="btn btn-secondary btn-advisor" style="background: rgba(255,193,7,0.1); color: #ffc107; border: 1px solid rgba(255,193,7,0.3);"><i class="fa-solid fa-lightbulb"></i> Poradce</button>
                        <button class="btn btn-primary btn-post-action">
                            <i class="fa-solid ${urlStr ? 'fa-arrows-rotate' : 'fa-cloud-arrow-up'}"></i> ${urlStr ? 'Znovu vystavit' : 'Vystavit'}
                        </button>
                    ` : `
                        <button class="btn btn-secondary btn-restore-sold" title="Vrátit položku zpět do věcí k prodeji"><i class="fa-solid fa-rotate-left"></i> Vrátit k prodeji</button>
                    `}
                </div>
            </div>
        `;

        // Pokud je prodáno, vložíme do těla karty box s realizovaným prodejem
        if (isSold) {
            const soldHeaderEl = card.querySelector(".listing-header");
            if (soldHeaderEl) {
                const soldPill = document.createElement("span");
                soldPill.className = "sold-card-badge";
                soldPill.innerHTML = `<i class="fa-solid fa-check"></i> PRODÁNO`;
                soldHeaderEl.prepend(soldPill);
            }

            const realizedPrice = ad.sale_price !== undefined && ad.sale_price !== null ? ad.sale_price : (ad.price || 0);
            const origPrice = ad.price || 0;
            let diffBadgeHtml = "";
            if (origPrice > 0 && realizedPrice > 0) {
                const diff = realizedPrice - origPrice;
                const pct = Math.round((diff / origPrice) * 100);
                if (pct < 0) {
                    diffBadgeHtml = `<span class="price-diff-pill discount" title="Sleva oproti nabídkové ceně">${pct}% (${diff} Kč)</span>`;
                } else if (pct > 0) {
                    diffBadgeHtml = `<span class="price-diff-pill surplus" title="Vyšší cena než nabídková">+${pct}% (+${diff} Kč)</span>`;
                } else {
                    diffBadgeHtml = `<span class="price-diff-pill exact" title="Prodáno přesně za inzerovanou cenu">100% ceny</span>`;
                }
            }

            const soldDateFormatted = ad.sold_at ? ad.sold_at.split("T")[0] : (ad.date_created || "-");
            const infoBox = document.createElement("div");
            infoBox.className = "sold-info-box";
            infoBox.innerHTML = `
                <div class="sold-info-row">
                    <span style="color: var(--text-muted);"><i class="fa-solid fa-receipt"></i> Realizovaná cena:</span>
                    <strong style="color: #10b981; font-size: 1.05rem;">${realizedPrice.toLocaleString("cs-CZ")} Kč ${diffBadgeHtml}</strong>
                </div>
                ${ad.sold_channel ? `
                <div class="sold-info-row">
                    <span style="color: var(--text-muted);"><i class="fa-solid fa-store"></i> Prodejní kanál:</span>
                    <span style="color: #38bdf8; font-weight: 600;">${escapeHtml(formatChannelName(ad.sold_channel))}</span>
                </div>
                ` : ""}
                <div class="sold-info-row">
                    <span style="color: var(--text-muted);"><i class="fa-solid fa-calendar-check"></i> Datum prodeje:</span>
                    <span style="color: #cbd5e1;">${soldDateFormatted}</span>
                </div>
                ${ad.sold_notes ? `
                <div class="sold-info-row" style="margin-top: 4px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 4px;">
                    <span style="color: var(--text-muted); font-size: 0.8rem;"><i class="fa-solid fa-comment-dots"></i> Poznámka:</span>
                    <span style="color: #cbd5e1; font-size: 0.82rem; font-style: italic;">${escapeHtml(ad.sold_notes)}</span>
                </div>
                ` : ""}
            `;
            // Vložíme bezpečně před popis inzerátu v těle karty
            const descEl = card.querySelector(".listing-desc");
            if (descEl && descEl.parentNode) {
                descEl.parentNode.insertBefore(infoBox, descEl);
            } else {
                card.appendChild(infoBox);
            }
        }

        // Checkbox pro hromadný výběr
        const selectCb = card.querySelector(".card-select-checkbox");
        if (selectCb) {
            selectCb.addEventListener("change", (e) => {
                e.stopPropagation();
                if (selectCb.checked) {
                    selectedBatchAdIds.add(ad.id);
                    card.classList.add("batch-selected");
                    card.classList.add("selected-batch-card");
                } else {
                    selectedBatchAdIds.delete(ad.id);
                    card.classList.remove("batch-selected");
                    card.classList.remove("selected-batch-card");
                }
                updateBatchActionBar();
            });
        }

        // Event Listeners
        const editBtn = card.querySelector(".btn-edit");
        const titleEl = card.querySelector(".listing-title");
        const postBtn = card.querySelector(".btn-post-action");
        const cardDeleteBtn = card.querySelector(".btn-card-delete");
        const markSoldBtn = card.querySelector(".btn-mark-sold");
        const restoreSoldBtn = card.querySelector(".btn-restore-sold");
        const manualPublishBtn = card.querySelector(".btn-manual-publish-action");

        const openEditor = () => openEditModal(ad);
        editBtn.addEventListener("click", openEditor);
        titleEl.addEventListener("click", openEditor);

        if (manualPublishBtn) {
            manualPublishBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openManualPublishModal(ad);
            });
        }

        // Doplnění URL k portálovým odznakům
        card.querySelectorAll(".badge-add-url").forEach(span => {
            span.addEventListener("click", (e) => {
                e.stopPropagation();
                const listingId = span.getAttribute("data-ad-id");
                const portal = span.getAttribute("data-portal");
                const pLabel = span.getAttribute("data-portal-label");
                promptUpdatePortalUrl(listingId, portal, pLabel, "");
            });
        });

        // 1-Click úprava a synchronizace zhlédnutí na portálových odznacích
        card.querySelectorAll(".badge-portal-views").forEach(span => {
            span.addEventListener("click", (e) => {
                e.stopPropagation();
                const listingId = span.getAttribute("data-ad-id");
                const portal = span.getAttribute("data-portal");
                const pLabel = span.getAttribute("data-portal-label");
                const curViews = parseInt(span.getAttribute("data-views") || "0", 10);
                const url = span.getAttribute("data-url") || "";
                promptUpdatePortalViews(listingId, portal, pLabel, curViews, url, span);
            });
        });

        // Bazoš Search Rank - kliknutí pro ověření nebo změnu dotazu
        card.querySelectorAll(".badge-bazos-rank").forEach(badge => {
            badge.addEventListener("click", (e) => {
                e.stopPropagation();
                const listingId = badge.getAttribute("data-ad-id");
                const curQuery = badge.getAttribute("data-current-query");
                if (typeof promptCheckBazosRank === "function") {
                    promptCheckBazosRank(listingId, curQuery, badge);
                }
            });
        });

        // 1-Click SMS Topování Bazoš
        card.querySelectorAll(".btn-open-sms-top").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const listingId = btn.getAttribute("data-ad-id");
                if (typeof openSmsTopModal === "function") {
                    openSmsTopModal(listingId);
                }
            });
        });

        // Stagnation Action Box tlačítka
        card.querySelectorAll(".btn-quick-top-action").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const listingId = btn.getAttribute("data-ad-id");
                if (typeof openSmsTopModal === "function") {
                    openSmsTopModal(listingId);
                }
            });
        });

        card.querySelectorAll(".btn-quick-repost-action").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                openRepostModal(ad);
            });
        });

        card.querySelectorAll(".btn-quick-discount-action").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const newPrice = parseInt(btn.getAttribute("data-new-price"), 10);
                openRepostModal(ad, newPrice);
            });
        });

        if (markSoldBtn) {
            markSoldBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openMarkSoldModal(ad);
            });
        }

        if (restoreSoldBtn) {
            restoreSoldBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                handleRestoreSoldListing(ad);
            });
        }

        if (cardDeleteBtn) {
            cardDeleteBtn.addEventListener("mouseenter", () => cardDeleteBtn.style.color = "#ef4444");
            cardDeleteBtn.addEventListener("mouseleave", () => cardDeleteBtn.style.color = "var(--text-muted)");
            cardDeleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openDeleteModal(ad);
            });
        }

        if (postBtn) {
            postBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openRepostModal(ad);
            });
        }

        return card;
    };

    // Toolbar Event Listeners (Vyhledávání, řazení, hromadný režim)
    const activeSearchInput = document.getElementById("active-search-input");
    if (activeSearchInput) {
        activeSearchInput.addEventListener("input", (e) => {
            activeFilterQuery = e.target.value;
            renderListings();
        });
    }

    const activeSortSelect = document.getElementById("active-sort-select");
    if (activeSortSelect) {
        activeSortSelect.addEventListener("change", (e) => {
            activeSort = e.target.value;
            renderListings();
        });
    }

    const btnToggleBatchActive = document.getElementById("btn-toggle-batch-active");
    if (btnToggleBatchActive) {
        btnToggleBatchActive.addEventListener("click", () => {
            isBatchModeActive = !isBatchModeActive;
            btnToggleBatchActive.classList.toggle("active", isBatchModeActive);
            const btnToggleUnsold = document.getElementById("btn-toggle-batch-unsold");
            if (btnToggleUnsold) btnToggleUnsold.classList.toggle("active", isBatchModeActive);
            renderListings();
        });
    }

    const unsoldSearchInput = document.getElementById("unsold-search-input");
    if (unsoldSearchInput) {
        unsoldSearchInput.addEventListener("input", (e) => {
            unsoldFilterQuery = e.target.value;
            renderListings();
        });
    }

    const unsoldSortSelect = document.getElementById("unsold-sort-select");
    if (unsoldSortSelect) {
        unsoldSortSelect.addEventListener("change", (e) => {
            unsoldSort = e.target.value;
            renderListings();
        });
    }

    const soldSearchInput = document.getElementById("sold-search-input");
    if (soldSearchInput) {
        soldSearchInput.addEventListener("input", (e) => {
            soldFilterQuery = e.target.value;
            renderListings();
        });
    }

    const soldSortSelect = document.getElementById("sold-sort-select");
    if (soldSortSelect) {
        soldSortSelect.addEventListener("change", (e) => {
            soldSort = e.target.value;
            renderListings();
        });
    }

    const btnToggleBatchUnsold = document.getElementById("btn-toggle-batch-unsold");
    if (btnToggleBatchUnsold) {
        btnToggleBatchUnsold.addEventListener("click", () => {
            isBatchModeActive = !isBatchModeActive;
            btnToggleBatchUnsold.classList.toggle("active", isBatchModeActive);
            if (btnToggleBatchActive) btnToggleBatchActive.classList.toggle("active", isBatchModeActive);
            renderListings();
        });
    }

    // Spodní plovoucí lišta pro hromadné akce
    const btnBatchSelectAll = document.getElementById("btn-batch-select-all");
    if (btnBatchSelectAll) {
        btnBatchSelectAll.addEventListener("click", () => {
            const activeTab = document.querySelector(".tab-content.active");
            const isUnsoldTab = activeTab && (activeTab.id === "tab-unsold-listings" || activeTab.getAttribute("data-tab") === "unsold-listings");
            const targetListings = isUnsoldTab ?
                sortListingsArray(filterListingsArray(activeListings.filter(ad => ad.status !== "Aktivní"), unsoldFilterQuery), unsoldSort) :
                sortListingsArray(filterListingsArray(activeListings.filter(ad => ad.status === "Aktivní"), activeFilterQuery), activeSort);
            
            targetListings.forEach(ad => {
                if (ad && ad.id) selectedBatchAdIds.add(ad.id);
            });
            isBatchModeActive = true;
            if (btnToggleBatchActive) btnToggleBatchActive.classList.add("active");
            const btnToggleUnsold = document.getElementById("btn-toggle-batch-unsold");
            if (btnToggleUnsold) btnToggleUnsold.classList.add("active");
            renderListings();
        });
    }

    const btnBatchCancelSelection = document.getElementById("btn-batch-cancel-selection");
    if (btnBatchCancelSelection) {
        btnBatchCancelSelection.addEventListener("click", () => {
            selectedBatchAdIds.clear();
            isBatchModeActive = false;
            if (btnToggleBatchActive) btnToggleBatchActive.classList.remove("active");
            const btnToggleUnsold = document.getElementById("btn-toggle-batch-unsold");
            if (btnToggleUnsold) btnToggleUnsold.classList.remove("active");
            renderListings();
        });
    }

    // --- KOMPLETNÍ SEZNAM VŠECH 20 RUBRIK BAZOŠE S AI DOPORUČENÍM ---
    const BAZOS_ALL_RUBRIKY = [
        { domain: "deti.bazos.cz", label: "Děti a hračky", icon: "fa-child" },
        { domain: "dum.bazos.cz", label: "Dům a zahrada", icon: "fa-house-chimney-window" },
        { domain: "nabytek.bazos.cz", label: "Nábytek", icon: "fa-couch" },
        { domain: "elektro.bazos.cz", label: "Elektro a spotřebiče", icon: "fa-bolt" },
        { domain: "sport.bazos.cz", label: "Sport a outdoor", icon: "fa-person-running" },
        { domain: "auto.bazos.cz", label: "Auto", icon: "fa-car" },
        { domain: "motorky.bazos.cz", label: "Motorky a čtyřkolky", icon: "fa-motorcycle" },
        { domain: "stroje.bazos.cz", label: "Stroje a dílna", icon: "fa-gears" },
        { domain: "pc.bazos.cz", label: "PC a počítače", icon: "fa-laptop" },
        { domain: "mobil.bazos.cz", label: "Mobily a chytré hodinky", icon: "fa-mobile-screen" },
        { domain: "foto.bazos.cz", label: "Foto a kamery", icon: "fa-camera" },
        { domain: "hudba.bazos.cz", label: "Hudba a nástroje", icon: "fa-guitar" },
        { domain: "obleceni.bazos.cz", label: "Oblečení a obuv", icon: "fa-shirt" },
        { domain: "knihy.bazos.cz", label: "Knihy a časopisy", icon: "fa-book" },
        { domain: "zvirata.bazos.cz", label: "Zvířata a chovatelství", icon: "fa-paw" },
        { domain: "vstupenky.bazos.cz", label: "Vstupenky a lístky", icon: "fa-ticket" },
        { domain: "reality.bazos.cz", label: "Reality a nemovitosti", icon: "fa-building" },
        { domain: "prace.bazos.cz", label: "Práce a brigády", icon: "fa-briefcase" },
        { domain: "sluzby.bazos.cz", label: "Služby a řemesla", icon: "fa-handshake" },
        { domain: "ostatni.bazos.cz", label: "Ostatní", icon: "fa-box-archive" }
    ];

    const BAZOS_DOMAIN_KEYWORDS = {
        "deti.bazos.cz": ["plamenak", "hrack", "kocarek", "postylk", "detsk", "odrazedlo", "autosedack", "plen", "babov", "panenk", "lego", "plysak", "stavebnic", "duplo", "kojeneck", "choditko", "nositko", "fusak", "detske", "detska", "detsky"],
        "dum.bazos.cz": ["sekac", "sekack", "drtic", "stepkov", "zahrada", "zahradni", "vrtack", "pila", "krovinorez", "naradi", "gril", "bazen", "cerpadlo", "kotel", "kamna", "dvere", "okna", "malotraktor", "kultivator", "vyzinac", "strunovka", "kosa", "hadice", "sklenik", "foliovnik", "plot", "dlazba", "stavebni", "thuje", "rostlin"],
        "nabytek.bazos.cz": ["stul", "stoly", "zidle", "skrin", "komoda", "postel", "matrace", "sedacka", "pohovka", "kreslo", "stolek", "jidelni", "sedak", "skrinka", "policka", "police", "nabytek", "obyvaci", "kuchyn", "linka", "botnik", "regal", "knihovna", "valenda", "palanda", "letiste", "satna"],
        "elektro.bazos.cz": ["prack", "lednic", "mrazak", "susick", "kavovar", "vysavac", "televiz", "tv", "mikrovln", "trouba", "sporak", "mycka", "reproduktor", "repro", "soundbar", "mixer", "zehlicka", "ventilator", "klimatizace", "robot"],
        "sport.bazos.cz": ["kolo", "horske kolo", "silnicni kolo", "ebike", "elektrokolo", "lyze", "snowboard", "fitness", "cinky", "stan", "spacak", "raketa", "brusle", "kolobezka", "paddleboard", "surfing", "kajak", "clun", "posilovac", "rotoped", "helma lyzarska"],
        "auto.bazos.cz": ["auto", "automobil", "osobni auto", "skoda", "vw", "volkswagen", "audi", "bmw", "ford", "peugeot", "renault", "mercedes", "hyundai", "kia", "alu kola", "pneumatiky", "pneu", "zimni pneu", "letni pneu", "autodily", "tazne", "stresni box", "r line", "tsi", "tdi"],
        "motorky.bazos.cz": ["motorka", "motorky", "motocykl", "skutr", "ctyrkolka", "moped", "enduro", "babeta", "babetta", "yamaha", "honda", "suzuki", "kawasaki", "ktm", "pitbike", "helma na moto", "moto bunda", "kombineza moto"],
        "stroje.bazos.cz": ["stroj", "soustruh", "frezk", "freza", "vysokozdviz", "traktorbagr", "vzv", "hydraulick", "svarecka", "kompresor", "lis", "hoblovka", "protahovacka", "pasova pila", "zetor", "desta"],
        "pc.bazos.cz": ["pocitac", "notebook", "laptop", "monitor", "grafick", "rtx", "gtx", "geforce", "intel", "amd", "ryzen", "ram", "ssd", "procesor", "zakladni deska", "klavesnice", "mys herni", "ipad", "macbook", "imac"],
        "mobil.bazos.cz": ["mobil", "telefon", "mobilni telefon", "iphone", "samsung galaxy", "xiaomi", "redmi", "smartphone", "smartwatch", "apple watch", "kryt na mobil", "nabijecka"],
        "foto.bazos.cz": ["foto", "fotoaparat", "objektiv", "zrcadlovka", "bezzrcadlovka", "canon", "nikon", "sony alpha", "fujifilm", "gopro", "stativ", "blesk", "dron", "dji"],
        "hudba.bazos.cz": ["kytara", "akusticka kytara", "elektricka kytara", "baskytara", "klavesy", "piano", "klavir", "bici", "kombo", "mikrofon", "syntezator", "housle", "akordeon", "harmonika"],
        "obleceni.bazos.cz": ["obleceni", "bunda", "kabat", "saty", "sukne", "kalhoty", "dziny", "boty", "tenisky", "lodicky", "kabelka", "mikina", "tricko", "svetr", "sako", "oblek"],
        "knihy.bazos.cz": ["kniha", "knihy", "roman", "encyklopedie", "ucebnice", "komiks", "casopis", "cteni", "sci fi", "fantasy", "knizka", "knizky"],
        "zvirata.bazos.cz": ["pes", "fena", "stene", "kocka", "kote", "kun", "akvarium", "terarium", "klec", "papousek", "kralik", "morce", "granule", "jezdecke"],
        "vstupenky.bazos.cz": ["vstupenk", "listek", "listky", "voucher", "darkovy poukaz", "permanentka", "koncert", "festival", "divadlo", "zapas"],
        "reality.bazos.cz": ["byt", "byty", "pozemek", "chata", "chalupa", "pronajem", "garaz", "kancelar", "nebytovy", "prodej bytu", "najem"],
        "prace.bazos.cz": ["prace", "brigada", "zamestnani", "volne misto", "prijmeme", "hpp", "dpp", "mzda", "plat", "nastup"],
        "sluzby.bazos.cz": ["sluzby", "remeslo", "zednik", "instalater", "stehovani", "rekonstrukce", "doucovani", "opravy", "malir", "preprava", "cisteni"],
        "ostatni.bazos.cz": ["ostatni", "sberatel", "mince", "bankovky", "znamky", "starozitnost", "vojenske", "odznak", "model"]
    };

    const normalizeCzStr = (str) => {
        if (!str) return "";
        return str.toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, " ").trim();
    };

    const rankRubrikyForAd = (ad) => {
        if (!ad) return [{ domain: "dum.bazos.cz", label: "Dům a zahrada", score: 0, matched: [] }];
        const titleNorm = normalizeCzStr(ad.title || "");
        const descNorm = normalizeCzStr(ad.description || "");
        const catNorm = normalizeCzStr(ad.category || "");
        const urlStr = (ad.url || "").toLowerCase();

        let existingSub = "";
        const m = urlStr.match(/https?:\/\/([^/]+\.bazos\.cz)/i);
        if (m && m[1] !== "www.bazos.cz") existingSub = m[1].toLowerCase();

        const results = BAZOS_ALL_RUBRIKY.map(item => {
            let score = 0;
            const matched = [];
            if (existingSub && existingSub === item.domain) {
                score += 1000;
                matched.push(`původní adresa (${item.domain})`);
            }
            if (item.domain === "motorky.bazos.cz") {
                if (/\b(moto|motorka|motorky|motocykl|skutr|ctyrkolka|moped|enduro|babeta)\b/.test(titleNorm)) {
                    score += 120;
                    matched.push("motocykl/skútr");
                }
            }
            const domBase = item.domain.split(".")[0];
            if (catNorm && catNorm.includes(domBase)) {
                score += 80;
                matched.push(`kategorie (${domBase})`);
            }
            const kws = BAZOS_DOMAIN_KEYWORDS[item.domain] || [];
            for (const kw of kws) {
                if (titleNorm.includes(kw)) {
                    score += 90;
                    if (!matched.includes(kw)) matched.push(kw);
                } else if (descNorm.includes(kw)) {
                    score += 20;
                    if (!matched.includes(kw) && matched.length < 4) matched.push(kw);
                }
            }
            return {
                domain: item.domain,
                label: item.label,
                icon: item.icon,
                score,
                matched
            };
        });

        results.sort((a, b) => b.score - a.score);
        return results;
    };

    const predictRubrikaDomain = (ad) => {
        const ranked = rankRubrikyForAd(ad);
        if (ranked.length > 0 && ranked[0].score > 0) {
            return ranked[0].domain;
        }
        return "dum.bazos.cz";
    };

    const populateRubrikaSelect = (selectEl, ad, badgeEl = null) => {
        if (!selectEl) return;
        const ranked = rankRubrikyForAd(ad);
        const topChoice = ranked[0] || { domain: "dum.bazos.cz", label: "Dům a zahrada", score: 0, matched: [] };
        
        let recommended = ranked.filter(r => r.score > 0).slice(0, 3);
        if (recommended.length === 0) {
            recommended = [topChoice];
        }

        selectEl.innerHTML = "";

        // 1. Optgroup Doporučené
        const optGroupRec = document.createElement("optgroup");
        optGroupRec.label = "✨ Doporučené podle inzerátu (AI)";
        recommended.forEach(rec => {
            const opt = document.createElement("option");
            opt.value = rec.domain;
            opt.textContent = `${rec.label} (${rec.domain})${rec.score > 0 ? " — doporučeno" : ""}`;
            if (rec.domain === topChoice.domain) {
                opt.selected = true;
            }
            optGroupRec.appendChild(opt);
        });
        selectEl.appendChild(optGroupRec);

        // 2. Optgroup Všechny rubriky
        const optGroupAll = document.createElement("optgroup");
        optGroupAll.label = "Všechny rubriky Bazoše";
        BAZOS_ALL_RUBRIKY.forEach(rub => {
            const opt = document.createElement("option");
            opt.value = rub.domain;
            opt.textContent = `${rub.label} (${rub.domain})`;
            optGroupAll.appendChild(opt);
        });
        selectEl.appendChild(optGroupAll);

        selectEl.value = topChoice.domain;

        if (badgeEl) {
            const badgeTextEl = badgeEl.querySelector("#repost-rubrika-badge-text") || badgeEl;
            if (topChoice.score > 0 && topChoice.matched && topChoice.matched.length > 0) {
                const kwStr = topChoice.matched.slice(0, 3).join(", ");
                badgeTextEl.innerHTML = `AI doporučuje: <strong>${escapeHtml(topChoice.label)}</strong> (na základě: <em>${escapeHtml(kwStr)}</em>)`;
                badgeEl.style.display = "flex";
            } else {
                badgeTextEl.innerHTML = `AI doporučuje výchozí rubriku: <strong>${escapeHtml(topChoice.label)}</strong>`;
                badgeEl.style.display = "flex";
            }
        }
    };

    // Modal dávkového znovuvystavení
    const batchRepostModal = document.getElementById("batch-repost-modal");
    const btnBatchRepostOpen = document.getElementById("btn-batch-repost-open");
    const batchItemsContainer = document.getElementById("batch-items-container");
    const batchModalTotalBtn = document.getElementById("batch-modal-total-btn");

    const openBatchRepostModal = () => {
        if (!batchRepostModal || !batchItemsContainer) return;
        const selectedAds = activeListings.filter(ad => selectedBatchAdIds.has(ad.id));
        if (selectedAds.length === 0) {
            showNotification("Není vybrán žádný inzerát pro dávku.", "warning");
            return;
        }

        batchItemsContainer.innerHTML = "";
        selectedAds.forEach(ad => {
            const row = document.createElement("div");
            row.className = "batch-item-row";
            row.setAttribute("data-ad-id", ad.id);
            row.style.cssText = "display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.75rem 1rem; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px;";
            
            const daysOld = getDaysOld(ad.date_created);

            row.innerHTML = `
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 600; color: #fff; font-size: 0.92rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(ad.title || '')}">${escapeHtml(ad.title || 'Bez názvu')}</div>
                    <div style="font-size: 0.78rem; color: #94a3b8; display: flex; gap: 0.6rem; align-items: center; margin-top: 2px;">
                        <span>Stávající cena: ${ad.price || 0} Kč</span>
                        ${daysOld !== null ? `<span>• Stáří: ${daysOld} dní</span>` : ''}
                        ${ad.url ? `<a href="${ad.url}" target="_blank" style="color: var(--secondary); text-decoration: none;"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ''}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <select class="batch-row-rubrika" style="background: rgba(11,8,22,0.9); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 0.35rem 0.55rem; border-radius: 6px; font-size: 0.82rem; outline: none; max-width: 220px;">
                    </select>
                    <div style="display: flex; align-items: center; gap: 0.25rem;">
                        <input type="number" class="batch-row-price" value="${ad.price || 0}" style="width: 80px; background: rgba(11,8,22,0.9); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 0.35rem 0.55rem; border-radius: 6px; font-size: 0.82rem; text-align: right; outline: none;">
                        <span style="font-size: 0.8rem; color: #94a3b8;">Kč</span>
                    </div>
                    <button type="button" class="btn-remove-batch-row" title="Odebrat z dávky" style="background: none; border: none; color: #ef4444; cursor: pointer; padding: 4px; font-size: 0.9rem;">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            `;

            const rubrikaSelect = row.querySelector(".batch-row-rubrika");
            if (rubrikaSelect) {
                populateRubrikaSelect(rubrikaSelect, ad);
            }

            const btnRemove = row.querySelector(".btn-remove-batch-row");
            if (btnRemove) {
                btnRemove.addEventListener("click", () => {
                    selectedBatchAdIds.delete(ad.id);
                    row.remove();
                    if (batchModalTotalBtn) batchModalTotalBtn.textContent = selectedBatchAdIds.size;
                    updateBatchActionBar();
                    renderListings();
                    if (selectedBatchAdIds.size === 0 && batchRepostModal) {
                        batchRepostModal.style.display = "none";
                    }
                });
            }

            batchItemsContainer.appendChild(row);
        });

        if (batchModalTotalBtn) batchModalTotalBtn.textContent = selectedAds.length;
        batchRepostModal.style.display = "flex";
    };

    if (btnBatchRepostOpen) {
        btnBatchRepostOpen.addEventListener("click", openBatchRepostModal);
    }

    document.querySelectorAll(".btn-close-batch-modal").forEach(btn => {
        btn.addEventListener("click", () => {
            if (batchRepostModal) batchRepostModal.style.display = "none";
        });
    });

    const btnStartBatchQueue = document.getElementById("btn-start-batch-queue");
    if (btnStartBatchQueue) {
        btnStartBatchQueue.addEventListener("click", () => {
            const rows = document.querySelectorAll(".batch-item-row");
            batchQueue = [];
            rows.forEach(row => {
                const adId = row.getAttribute("data-ad-id");
                const rubrikaSelect = row.querySelector(".batch-row-rubrika");
                const priceInput = row.querySelector(".batch-row-price");
                const ad = activeListings.find(a => a.id === adId);
                if (ad) {
                    batchQueue.push({
                        ad,
                        domain: rubrikaSelect ? rubrikaSelect.value : "dum.bazos.cz",
                        price: priceInput && priceInput.value ? parseInt(priceInput.value, 10) : ad.price,
                        autoDelete: true
                    });
                }
            });

            if (batchQueue.length === 0) {
                showNotification("Žádné položky k vystavení v dávce.", "warning");
                return;
            }

            if (batchRepostModal) batchRepostModal.style.display = "none";
            batchIndex = 0;
            const currentItem = batchQueue[0];

            // Indikátor fronty v prohlížeči
            const indicator = document.getElementById("batch-queue-indicator");
            if (indicator) {
                indicator.style.display = "flex";
                const curEl = document.getElementById("batch-queue-current");
                const totEl = document.getElementById("batch-queue-total");
                const nameEl = document.getElementById("batch-queue-name");
                if (curEl) curEl.textContent = 1;
                if (totEl) totEl.textContent = batchQueue.length;
                if (nameEl) nameEl.textContent = `Položka: ${currentItem.ad.title || "Bez názvu"}`;
            }

            showNotification(`Spouštím dávku (1/${batchQueue.length}): ${currentItem.ad.title}...`, "info");
            triggerPlaywrightAction(currentItem.ad, "repost", currentItem.price, currentItem.domain, currentItem.autoDelete);
        });
    }

    const btnBatchSkip = document.getElementById("btn-batch-skip");
    if (btnBatchSkip) {
        btnBatchSkip.addEventListener("click", () => {
            if (batchQueue.length > 0 && batchIndex < batchQueue.length - 1) {
                batchIndex++;
                const currentItem = batchQueue[batchIndex];
                const curEl = document.getElementById("batch-queue-current");
                const nameEl = document.getElementById("batch-queue-name");
                if (curEl) curEl.textContent = batchIndex + 1;
                if (nameEl) nameEl.textContent = `Položka: ${currentItem.ad.title || "Bez názvu"}`;
                showNotification(`Přeskočeno. Spouštím ${batchIndex + 1}/${batchQueue.length}...`, "info");
                triggerPlaywrightAction(currentItem.ad, "repost", currentItem.price, currentItem.domain, currentItem.autoDelete);
            } else {
                showNotification("Dávka ukončena.", "info");
                batchQueue = [];
                const indicator = document.getElementById("batch-queue-indicator");
                if (indicator) indicator.style.display = "none";
                switchToTab("active-listings");
                loadListings();
            }
        });
    }

    const btnBatchCancel = document.getElementById("btn-batch-cancel");
    if (btnBatchCancel) {
        btnBatchCancel.addEventListener("click", () => {
            batchQueue = [];
            const indicator = document.getElementById("batch-queue-indicator");
            if (indicator) indicator.style.display = "none";
            showNotification("Dávkové zpracování bylo zastaveno.", "warning");
        });
    }

    // ==========================================
    // 3. EDITACE A DETAIL MODAL LOGIKA
    // ==========================================

    const openEditModal = (ad) => {
        currentAd = ad;
        
        // Předvyplnit formulář
        editTitle.value = ad.title || "";
        editPrice.value = ad.price || 0;
        editCategory.value = ad.category || "";
        editDescription.value = ad.description || "";
        editNotes.value = ad.notes || "";
        editPhotosDir.value = ad.local_photos_dir || "";
        
        // Portal checkboxes
        const editTargetBazos = document.getElementById("edit-target-bazos");
        const editTargetAukro = document.getElementById("edit-target-aukro");
        if (editTargetBazos) editTargetBazos.checked = ad.target_bazos !== 0;
        if (editTargetAukro) editTargetAukro.checked = ad.target_aukro === 1;

        // Inicializovat čítače
        updateCounter(editTitle, editTitleCounter, 50);
        updateCounter(editDescription, editDescCounter);

        // Načteme fotogalerii
        excludedPhotos = new Set(ad.excluded_photos || []);
        loadPhotoGallery(ad.local_photos_dir || "");

        // Předvyplnit info sidebar
        if (ad.url) {
            infoUrlContainer.innerHTML = `<a href="${ad.url}" target="_blank" style="color: var(--secondary); text-decoration: none; word-break: break-all;">${ad.url}</a>`;
        } else {
            infoUrlContainer.textContent = "Dosud nevystaveno";
        }
        if (ad.cumulative_views && ad.cumulative_views > (ad.views || 0)) {
            infoViews.innerHTML = `${ad.views || 0} <span style="font-size: 0.75rem; color: #94a3b8;">(celkem ${ad.cumulative_views})</span>`;
        } else {
            infoViews.textContent = ad.views || 0;
        }
        infoPhotosDir.textContent = ad.local_photos_dir || "photos/";

        // Načíst historii publikací
        loadListingHistory(ad.id);

        // Aktualizovat stav tlačítka pro označení/úpravu prodeje
        const isAdSold = ad.status === "Prodané" || ad.status === "Sold" || Boolean(ad.sold_at) || (ad.sale_price !== null && ad.sale_price !== undefined);
        const btnMarkSold = document.getElementById("btn-mark-sold-modal");
        if (btnMarkSold) {
            if (isAdSold) {
                btnMarkSold.innerHTML = `<i class="fa-solid fa-handshake"></i> Upravit prodej`;
                btnMarkSold.title = "Upravit realizovanou cenu, datum nebo poznámku k prodeji";
            } else {
                btnMarkSold.innerHTML = `<i class="fa-solid fa-handshake"></i> Označit jako prodané`;
                btnMarkSold.title = "Zaznamenat prodej položky a přesunout do archivu";
            }
        }

        const btnManualPublishOpen = document.getElementById("btn-manual-publish-open");
        if (btnManualPublishOpen) {
            btnManualPublishOpen.onclick = () => {
                if (currentAd) {
                    openManualPublishModal(currentAd);
                }
            };
        }

        // Zobrazit modal
        editListingModal.classList.add("active");
    };

    const loadListingHistory = async (listingId) => {
        const historyTimeline = document.getElementById("listing-history-timeline");
        const badgeEl = document.getElementById("history-iteration-badge");
        if (!historyTimeline) return;

        historyTimeline.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8rem; margin: 0;"><i class="fa-solid fa-spinner fa-spin"></i> Načítám historii...</p>';
        try {
            const res = await fetch(`/api/listings/${encodeURIComponent(listingId)}/history`);
            if (!res.ok) throw new Error("Nelze načíst historii");
            const data = await res.json();
            const pubs = data.publications || [];
            const stats = data.cumulative_stats || {};

            if (badgeEl) {
                const count = stats.publication_count || (pubs.length || 1);
                badgeEl.textContent = `${count}. vystavení`;
                badgeEl.style.display = count > 1 ? "inline-block" : "none";
            }

            if (!pubs || pubs.length === 0) {
                historyTimeline.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8rem; margin: 0;">Zatím žádná historie.</p>';
                return;
            }

            historyTimeline.innerHTML = pubs.map((pub, idx) => {
                const isActive = pub.status === "active";
                const badgeColor = isActive ? "#22c55e" : "#64748b";
                const badgeBg = isActive ? "rgba(34, 197, 94, 0.15)" : "rgba(100, 116, 139, 0.15)";
                const statusLabel = isActive ? "Aktivní" : (pub.close_reason === "reposted" ? "Nahrazeno" : (pub.close_reason || "Ukončeno"));
                const dateRange = pub.closed_at ? `${pub.published_at} – ${pub.closed_at}` : `Od ${pub.published_at}`;
                const urlLink = pub.url ? `<a href="${pub.url}" target="_blank" style="color: var(--secondary); text-decoration: none; margin-left: 4px;" title="Otevřít odkaz"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.7rem;"></i></a>` : '';

                return `
                    <div style="border-left: 2px solid ${badgeColor}; padding-left: 8px; margin-bottom: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 600; color: #fff;">#${idx + 1} (${pub.price} Kč)</span>
                            <span style="background: ${badgeBg}; color: ${badgeColor}; padding: 1px 5px; border-radius: 4px; font-size: 0.72rem;">${statusLabel}</span>
                        </div>
                        <div style="color: #94a3b8; font-size: 0.75rem; margin-top: 1px; display: flex; justify-content: space-between;">
                            <span>${dateRange}</span>
                            <span>${pub.views || 0} zhl. ${urlLink}</span>
                        </div>
                    </div>
                `;
            }).reverse().join("");
        } catch (e) {
            historyTimeline.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8rem; margin: 0;">Historie není k dispozici.</p>';
        }
    };

    // ----------------------------------------
    // Fotogalerie
    // ----------------------------------------
    const loadPhotoGallery = async (photosDir) => {
        photoGalleryGrid.innerHTML = '<p class="photo-gallery-empty">Načítám fotky...</p>';
        if (!photosDir) {
            photoGalleryGrid.innerHTML = '<p class="photo-gallery-empty">Složka s fotkami není nastavena.</p>';
            return;
        }
        try {
            const res = await fetch(`${API.photos}?photos_dir=${encodeURIComponent(photosDir)}`);
            const data = await res.json();
            if (!data.photos || data.photos.length === 0) {
                photoGalleryGrid.innerHTML = '<p class="photo-gallery-empty">Ve složce nejsou žádné fotky (JPG/PNG).</p>';
                photoCountLabel.textContent = "";
                return;
            }
            renderPhotoGallery(data.photos);
        } catch (e) {
            console.error("Chyba při loadPhotoGallery:", e);
            photoGalleryGrid.innerHTML = '<p class="photo-gallery-empty">Nepodařilo se načíst fotky.</p>';
        }
    };

    // --- Klientská komprese obrázků před uploadem ---
    const compressImageFile = (file, maxWidth = 1920, maxHeight = 1920, quality = 0.85) => {
        return new Promise((resolve) => {
            if (!file.type.startsWith("image/")) {
                resolve(file);
                return;
            }
            const img = new Image();
            const url = URL.createObjectURL(file);
            img.onload = () => {
                URL.revokeObjectURL(url);
                let w = img.width;
                let h = img.height;
                if (w > maxWidth || h > maxHeight) {
                    if (w > h) {
                        h = Math.round((h * maxWidth) / w);
                        w = maxWidth;
                    } else {
                        w = Math.round((w * maxHeight) / h);
                        h = maxHeight;
                    }
                }
                const canvas = document.createElement("canvas");
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, w, h);
                canvas.toBlob(
                    (blob) => {
                        if (!blob) {
                            resolve(file);
                            return;
                        }
                        const newFile = new File([blob], file.name.replace(/\.[^/.]+$/, ".jpg"), {
                            type: "image/jpeg",
                            lastModified: Date.now()
                        });
                        resolve(newFile);
                    },
                    "image/jpeg",
                    quality
                );
            };
            img.onerror = () => {
                URL.revokeObjectURL(url);
                resolve(file);
            };
            img.src = url;
        });
    };

    const handlePhotoUpload = async (files) => {
        const photosDir = editPhotosDir.value;
        if (!photosDir) {
            showNotification("Složka pro fotky není nastavená.", "error");
            return;
        }
        if (!files || files.length === 0) return;

        const count = files.length;
        showNotification(`Zpracovávám a komprimuji ${count} ${count === 1 ? "fotku" : count < 5 ? "fotky" : "fotek"}...`, "info");
        
        const compressedFiles = [];
        for (let i = 0; i < files.length; i++) {
            const comp = await compressImageFile(files[i]);
            compressedFiles.push(comp);
        }

        const formData = new FormData();
        formData.append("photos_dir", photosDir);
        for (let file of compressedFiles) {
            formData.append("photos", file);
        }

        showNotification(`Nahrávám ${compressedFiles.length} ${compressedFiles.length === 1 ? "fotku" : compressedFiles.length < 5 ? "fotky" : "fotek"}...`, "info");
        try {
            const res = await fetch(API.uploadPhotos, {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showNotification(data.message || "Fotky byly úspěšně nahrány!", "success");
                loadPhotoGallery(photosDir);
            } else {
                showNotification(data.message || "Chyba při nahrávání fotek.", "error");
            }
        } catch (err) {
            showNotification("Chyba při nahrávání fotek.", "error");
        }
    };

    // Paste event support (Cmd+V / Ctrl+V)
    document.addEventListener("paste", (e) => {
        const modal = document.getElementById("edit-listing-modal");
        if (!modal || modal.style.display === "none") return;
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        const imageFiles = [];
        for (let item of items) {
            if (item.type.indexOf("image") !== -1) {
                const blob = item.getAsFile();
                if (blob) {
                    const file = new File([blob], `pasted_photo_${Date.now()}.png`, { type: blob.type });
                    imageFiles.push(file);
                }
            }
        }
        if (imageFiles.length > 0) {
            e.preventDefault();
            handlePhotoUpload(imageFiles);
        }
    });

    const photoDropzone = document.getElementById("photo-dropzone");
    const editPhotoFileInput = document.getElementById("edit-photo-file-input");

    if (photoDropzone && editPhotoFileInput) {
        photoDropzone.addEventListener("click", (e) => {
            // Prevent file picker if user clicked button or gallery child
            if (e.target.closest("button") || e.target.closest(".photo-thumb-wrapper") || e.target.closest(".btn")) return;
            editPhotoFileInput.click();
        });

        editPhotoFileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handlePhotoUpload(e.target.files);
                e.target.value = "";
            }
        });

        photoDropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            if (draggedItemIdx === null) {
                photoDropzone.style.background = "rgba(59, 130, 246, 0.15)";
                photoDropzone.style.borderColor = "var(--primary-color, #3b82f6)";
            }
        });

        photoDropzone.addEventListener("dragleave", (e) => {
            e.preventDefault();
            photoDropzone.style.background = "rgba(255, 255, 255, 0.03)";
            photoDropzone.style.borderColor = "var(--border-color, #cbd5e1)";
        });

        photoDropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            photoDropzone.style.background = "rgba(255, 255, 255, 0.03)";
            photoDropzone.style.borderColor = "var(--border-color, #cbd5e1)";
            
            // Ignore if internal photo drag-to-reorder
            if (draggedItemIdx !== null) return;

            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handlePhotoUpload(e.dataTransfer.files);
            }
        });
    }

    let draggedItemIdx = null;
    let currentPhotosList = [];

    const renderPhotoGallery = (photos) => {
        photoGalleryGrid.innerHTML = "";
        currentPhotosList = photos;

        photos.forEach((photo, idx) => {
            const isExcluded = excludedPhotos.has(photo.filename);
            const wrapper = document.createElement("div");
            wrapper.className = `photo-thumb-wrapper${isExcluded ? " excluded" : ""}`;
            wrapper.dataset.filename = photo.filename;
            wrapper.dataset.index = idx;
            wrapper.draggable = true;

            // Thumbnail Image
            const img = document.createElement("img");
            img.src = photo.data_url || "";
            img.alt = photo.filename;
            img.loading = "lazy";
            img.style.cursor = "pointer";
            img.onerror = () => {
                img.style.display = "none";
                const placeholder = document.createElement("div");
                placeholder.style.cssText = "display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;min-height:80px;color:#64748b;font-size:0.72rem;gap:4px;padding:8px;box-sizing:border-box;";
                placeholder.innerHTML = `<i class="fa-solid fa-image-slash" style="font-size:1.4rem;color:#475569;"></i><span style="text-align:center;word-break:break-all;">${photo.filename}</span><span style="color:#ef4444;font-size:0.65rem;">Poškozená fotka</span>`;
                wrapper.insertBefore(placeholder, img);
            };
            img.addEventListener("click", (e) => {
                e.stopPropagation();
                if (photo.data_url) openLightbox(photo.data_url, photo.filename);
            });

            // Cover Badge on 1st photo
            if (idx === 0) {
                const coverBadge = document.createElement("div");
                coverBadge.className = "cover-photo-badge";
                coverBadge.style.cssText = "position: absolute; top: 6px; left: 6px; background: rgba(16, 185, 129, 0.9); color: #fff; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; z-index: 5; backdrop-filter: blur(4px); shadow: 0 2px 4px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 4px;";
                coverBadge.innerHTML = '<i class="fa-solid fa-star"></i> Hlavní fotka';
                wrapper.appendChild(coverBadge);
            }

            // Drag Grip Handle (top right)
            const gripIcon = document.createElement("div");
            gripIcon.className = "drag-grip-handle";
            gripIcon.style.cssText = "position: absolute; top: 6px; right: 6px; background: rgba(15, 23, 42, 0.75); color: #cbd5e1; border-radius: 4px; padding: 2px 5px; font-size: 0.72rem; z-index: 5; pointer-events: none; backdrop-filter: blur(2px); border: 1px solid rgba(255,255,255,0.1);";
            gripIcon.title = "Přetáhněte pro změnu pořadí";
            gripIcon.innerHTML = '<i class="fa-solid fa-grip-vertical"></i>';
            wrapper.appendChild(gripIcon);

            // Controls Overlay Action Buttons
            const overlay = document.createElement("div");
            overlay.className = "photo-actions-overlay";
            overlay.style.cssText = "position: absolute; bottom: 0; left: 0; right: 0; background: rgba(15, 23, 42, 0.88); display: flex; justify-content: space-around; align-items: center; padding: 6px 4px; backdrop-filter: blur(4px); opacity: 0; transition: opacity 0.2s; z-index: 6;";
            
            // Show overlay on hover
            wrapper.addEventListener("mouseenter", () => overlay.style.opacity = "1");
            wrapper.addEventListener("mouseleave", () => overlay.style.opacity = "0");

            // 0. Set as Cover Photo button (for index > 0)
            if (idx > 0) {
                const btnSetCover = document.createElement("button");
                btnSetCover.type = "button";
                btnSetCover.title = "Nastavit jako Hlavní titulní fotku";
                btnSetCover.style.cssText = "background: none; border: none; color: #f59e0b; cursor: pointer; padding: 4px; font-size: 0.9rem;";
                btnSetCover.innerHTML = '<i class="fa-solid fa-star"></i>';
                btnSetCover.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    showNotification("Nastavuji jako Hlavní fotku...", "info");
                    const reordered = [...currentPhotosList];
                    const [movedItem] = reordered.splice(idx, 1);
                    reordered.splice(0, 0, movedItem);
                    const filenames = reordered.map(p => p.filename);
                    try {
                        const res = await fetch("/api/photos/reorder", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ photos_dir: editPhotosDir.value, filenames: filenames })
                        });
                        if (res.ok) {
                            showNotification("Hlavní fotka byla nastavena!", "success");
                            loadPhotoGallery(editPhotosDir.value);
                        }
                    } catch (err) {
                        showNotification("Chyba při nastavování hlavní fotky.", "error");
                    }
                });
                overlay.appendChild(btnSetCover);
            }

            // 1. Toggle Include/Exclude button
            const btnToggle = document.createElement("button");
            btnToggle.type = "button";
            btnToggle.title = isExcluded ? "Zahrnout do inzerátu" : "Přeskočit na Bazoši";
            btnToggle.style.cssText = "background: none; border: none; color: #fff; cursor: pointer; padding: 4px; font-size: 0.85rem;";
            btnToggle.innerHTML = isExcluded ? '<i class="fa-solid fa-eye-slash" style="color: #ef4444;"></i>' : '<i class="fa-solid fa-eye" style="color: #10b981;"></i>';
            btnToggle.addEventListener("click", (e) => {
                e.stopPropagation();
                if (excludedPhotos.has(photo.filename)) {
                    excludedPhotos.delete(photo.filename);
                } else {
                    excludedPhotos.add(photo.filename);
                }
                renderPhotoGallery(currentPhotosList);
            });

            // 2. Rotate button
            const btnRotate = document.createElement("button");
            btnRotate.type = "button";
            btnRotate.title = "Otočit o 90°";
            btnRotate.style.cssText = "background: none; border: none; color: #fff; cursor: pointer; padding: 4px; font-size: 0.85rem;";
            btnRotate.innerHTML = '<i class="fa-solid fa-rotate-right"></i>';
            btnRotate.addEventListener("click", async (e) => {
                e.stopPropagation();
                showNotification("Otáčím fotku...", "info");
                try {
                    const res = await fetch("/api/photos/rotate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ photos_dir: editPhotosDir.value, filename: photo.filename, angle: 90 })
                    });
                    const resData = await res.json();
                    if (resData.status === "success") {
                        loadPhotoGallery(editPhotosDir.value);
                    } else {
                        showNotification(resData.message, "error");
                    }
                } catch (err) {
                    showNotification("Chyba při otáčení.", "error");
                }
            });

            // 3. Zoom Lightbox button
            const btnZoom = document.createElement("button");
            btnZoom.type = "button";
            btnZoom.title = "Zvětšit (Lightbox)";
            btnZoom.style.cssText = "background: none; border: none; color: #fff; cursor: pointer; padding: 4px; font-size: 0.85rem;";
            btnZoom.innerHTML = '<i class="fa-solid fa-magnifying-glass-plus"></i>';
            btnZoom.addEventListener("click", (e) => {
                e.stopPropagation();
                openLightbox(photo.data_url, photo.filename);
            });

            // 3.5. Edit Photo (Bokeh & SPZ Blur) button
            const btnEdit = document.createElement("button");
            btnEdit.type = "button";
            btnEdit.className = "btn-edit-photo";
            btnEdit.title = "Upravit fotku (AI Bokeh / Zamazat SPZ)";
            btnEdit.style.cssText = "background: none; border: none; color: #a78bfa; cursor: pointer; padding: 4px; font-size: 0.85rem;";
            btnEdit.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i>';
            btnEdit.addEventListener("click", (e) => {
                e.stopPropagation();
                openPhotoEditorForExisting(editPhotosDir.value, photo.filename, photo.data_url);
            });
            overlay.appendChild(btnEdit);

            // 4. Delete button
            const btnDelete = document.createElement("button");
            btnDelete.type = "button";
            btnDelete.title = "Smazat fotku z disku";
            btnDelete.style.cssText = "background: none; border: none; color: #ef4444; cursor: pointer; padding: 4px; font-size: 0.85rem;";
            btnDelete.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
            btnDelete.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (confirm(`Opravdu smazat fotku '${photo.filename}'?`)) {
                    try {
                        const res = await fetch("/api/photos/delete", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ photos_dir: editPhotosDir.value, filename: photo.filename })
                        });
                        const resData = await res.json();
                        if (resData.status === "success") {
                            showNotification("Fotka byla smazána.", "success");
                            excludedPhotos.delete(photo.filename);
                            loadPhotoGallery(editPhotosDir.value);
                        } else {
                            showNotification(resData.message, "error");
                        }
                    } catch (err) {
                        showNotification("Chyba při mazání.", "error");
                    }
                }
            });

            overlay.appendChild(btnToggle);
            overlay.appendChild(btnRotate);
            overlay.appendChild(btnZoom);
            overlay.appendChild(btnDelete);

            const nameLabel = document.createElement("div");
            nameLabel.className = "photo-thumb-name";
            nameLabel.textContent = photo.filename;

            wrapper.appendChild(img);
            wrapper.appendChild(overlay);
            wrapper.appendChild(nameLabel);

            // Drag and Drop reordering logic
            wrapper.addEventListener("dragstart", (e) => {
                draggedItemIdx = idx;
                e.dataTransfer.effectAllowed = "move";
                wrapper.style.opacity = "0.4";
            });

            wrapper.addEventListener("dragend", () => {
                wrapper.style.opacity = "1";
            });

            wrapper.addEventListener("dragover", (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
            });

            wrapper.addEventListener("drop", async (e) => {
                e.preventDefault();
                if (draggedItemIdx !== null && draggedItemIdx !== idx) {
                    const reordered = [...currentPhotosList];
                    const [movedItem] = reordered.splice(draggedItemIdx, 1);
                    reordered.splice(idx, 0, movedItem);

                    const filenames = reordered.map(p => p.filename);
                    showNotification("Měním pořadí fotek...", "info");
                    try {
                        const res = await fetch("/api/photos/reorder", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ photos_dir: editPhotosDir.value, filenames: filenames })
                        });
                        const resData = await res.json();
                        if (resData.status === "success") {
                            loadPhotoGallery(editPhotosDir.value);
                        }
                    } catch (err) {
                        showNotification("Chyba při změně pořadí.", "error");
                    }
                }
            });

            photoGalleryGrid.appendChild(wrapper);
        });
        updatePhotoCount(photos.length);
    };

    const updatePhotoCount = (total) => {
        if (!photoCountLabel) return;
        const included = total - excludedPhotos.size;
        photoCountLabel.textContent = `${included} / ${total} fotek bude nahráno`;
        photoCountLabel.style.color = excludedPhotos.size > 0 ? "var(--warning, #f39c12)" : "var(--text-muted)";
    };

    if (closeLightboxBtn && lightboxModal) {
        closeLightboxBtn.addEventListener("click", () => lightboxModal.style.display = "none");
        lightboxModal.addEventListener("click", (e) => {
            if (e.target === lightboxModal) lightboxModal.style.display = "none";
        });
    }



    // Uložit změny v detailu inzerátu
    document.getElementById("btn-save-listing-changes").addEventListener("click", async () => {
        if (!currentAd) return;

        const editTargetBazos = document.getElementById("edit-target-bazos");
        const editTargetAukro = document.getElementById("edit-target-aukro");

        const updatedAd = {
            ...currentAd,
            title: editTitle.value,
            price: parseInt(editPrice.value) || 0,
            category: editCategory.value.trim(),
            description: editDescription.value,
            notes: editNotes.value,
            local_photos_dir: editPhotosDir.value,
            excluded_photos: Array.from(excludedPhotos),
            target_bazos: editTargetBazos && editTargetBazos.checked ? 1 : 0,
            target_aukro: editTargetAukro && editTargetAukro.checked ? 1 : 0
        };

        try {
            const res = await fetch(API.saveAd, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedAd)
            });

            if (res.ok) {
                showNotification("Inzerát byl úspěšně uložen.", "success");
                editListingModal.classList.remove("active");
                loadListings();
            } else {
                const data = await res.json();
                showNotification(data.message || "Ukládání selhalo", "error");
            }
        } catch (err) {
            showNotification("Nastala chyba při ukládání inzerátu.", "error");
        }
    });

    // ==========================================
    // 4. VYTVOŘENÍ NOVÉHO INZERÁTU (AI SMART WIZARD)
    // ==========================================

    let wizardSelectedFiles = [];
    let wizardCoverIndex = 0;

    const newPhotoDropzone = document.getElementById("new-photo-dropzone");
    const newPhotoFileInput = document.getElementById("new-photo-file-input");
    const newPhotoPreviewGrid = document.getElementById("new-photo-preview-grid");
    const newAiActionBar = document.getElementById("new-ai-action-bar");
    const newUserNotes = document.getElementById("new-user-notes");
    const btnRunVisionAi = document.getElementById("btn-run-vision-ai");
    const visionAiLoading = document.getElementById("vision-ai-loading");
    const visionLoadingText = document.getElementById("vision-loading-text");
    const visionLoadingSubtext = document.getElementById("vision-loading-subtext");
    
    const newAiDetectedBanner = document.getElementById("new-ai-detected-banner");
    const detectedItemName = document.getElementById("detected-item-name");
    const detectedConditionBadge = document.getElementById("detected-condition-badge");
    const aiQualityTips = document.getElementById("ai-quality-tips");
    
    const newTitlesChipsContainer = document.getElementById("new-titles-chips-container");
    const newTitlesChips = document.getElementById("new-titles-chips");
    
    const newPriceRadarContainer = document.getElementById("new-price-radar-container");
    const valPriceQuick = document.getElementById("val-price-quick");
    const valPriceFair = document.getElementById("val-price-fair");
    const valPricePremium = document.getElementById("val-price-premium");
    const cardPriceQuick = document.getElementById("card-price-quick");
    const cardPriceFair = document.getElementById("card-price-fair");
    const cardPricePremium = document.getElementById("card-price-premium");

    const populatePriceRadar = (stats, fallbackPrice, sources) => {
        if (!newPriceRadarContainer) return;
        
        let validStats = (stats && stats.median && stats.median > 0) ? stats : null;
        if (!validStats && fallbackPrice && fallbackPrice > 0) {
            const fb = parseInt(fallbackPrice);
            validStats = {
                min: Math.round(fb * 0.8),
                max: Math.round(fb * 1.2),
                median: fb,
                suggested_quick_sale: Math.round(fb * 0.9),
                suggested_fair: fb,
                suggested_premium: Math.round(fb * 1.1)
            };
        }

        if (!validStats) return;

        const quick = validStats.suggested_quick_sale || Math.round(validStats.median * 0.9);
        const fair = validStats.suggested_fair || validStats.median;
        const premium = validStats.suggested_premium || Math.round(validStats.median * 1.1);

        if (valPriceQuick) valPriceQuick.textContent = `${quick.toLocaleString("cs-CZ")} Kč`;
        if (valPriceFair) valPriceFair.textContent = `${fair.toLocaleString("cs-CZ")} Kč`;
        if (valPricePremium) valPricePremium.textContent = `${premium.toLocaleString("cs-CZ")} Kč`;

        const radarBadge = document.getElementById("radar-sources-badge");
        if (radarBadge && sources && sources.length) {
            radarBadge.textContent = sources.join(" + ");
        }

        const selectPrice = (val, cardEl) => {
            if (newPrice) newPrice.value = val;
            [cardPriceQuick, cardPriceFair, cardPricePremium].forEach(c => c && c.classList.remove("active"));
            if (cardEl) cardEl.classList.add("active");
        };

        if (cardPriceQuick) cardPriceQuick.onclick = () => selectPrice(quick, cardPriceQuick);
        if (cardPriceFair) cardPriceFair.onclick = () => selectPrice(fair, cardPriceFair);
        if (cardPricePremium) cardPricePremium.onclick = () => selectPrice(premium, cardPricePremium);

        selectPrice(fair, cardPriceFair);
        newPriceRadarContainer.style.display = "block";
    };

    const resetWizardState = () => {
        wizardSelectedFiles = [];
        wizardCoverIndex = 0;
        if (newPhotoFileInput) newPhotoFileInput.value = "";
        if (newUserNotes) newUserNotes.value = "";
        if (newPhotoPreviewGrid) {
            newPhotoPreviewGrid.innerHTML = "";
            newPhotoPreviewGrid.style.display = "none";
        }
        if (newAiActionBar) newAiActionBar.style.display = "none";
        if (visionAiLoading) visionAiLoading.style.display = "none";
        if (newAiDetectedBanner) newAiDetectedBanner.style.display = "none";
        if (newTitlesChipsContainer) {
            newTitlesChipsContainer.style.display = "none";
            newTitlesChips.innerHTML = "";
        }
        if (newPriceRadarContainer) newPriceRadarContainer.style.display = "none";
        const radarBadge = document.getElementById("radar-sources-badge");
        if (radarBadge) radarBadge.textContent = "";
    };

    const renderWizardPhotoPreviews = () => {
        if (!newPhotoPreviewGrid) return;
        newPhotoPreviewGrid.innerHTML = "";

        if (wizardSelectedFiles.length === 0) {
            newPhotoPreviewGrid.style.display = "none";
            if (newAiActionBar) newAiActionBar.style.display = "none";
            return;
        }

        newPhotoPreviewGrid.style.display = "grid";
        if (newAiActionBar) newAiActionBar.style.display = "block";

        if (wizardCoverIndex >= wizardSelectedFiles.length) {
            wizardCoverIndex = 0;
        }

        wizardSelectedFiles.forEach((file, index) => {
            const isCover = index === wizardCoverIndex;
            const thumbCard = document.createElement("div");
            thumbCard.className = `wizard-photo-thumb ${isCover ? "is-cover" : ""}`;
            thumbCard.title = isCover ? "Hlavní titulní fotografie" : `Fotka #${index + 1} (kliknutím zvolíte jako hlavní)`;

            const img = document.createElement("img");
            img.src = URL.createObjectURL(file);
            img.alt = file.name;

            // Index / cover badge (top-left)
            const badge = document.createElement("div");
            badge.className = `thumb-badge ${isCover ? "badge-cover" : ""}`;
            badge.innerHTML = isCover ? '<i class="fa-solid fa-star"></i> Hlavní' : `#${index + 1}`;

            // Remove button (top-right)
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "btn-remove-thumb";
            removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            removeBtn.title = "Odebrat fotku";
            removeBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                wizardSelectedFiles.splice(index, 1);
                if (wizardCoverIndex >= wizardSelectedFiles.length) {
                    wizardCoverIndex = Math.max(0, wizardSelectedFiles.length - 1);
                }
                renderWizardPhotoPreviews();
            });

            // Set cover button (bottom-left)
            const coverBtn = document.createElement("button");
            coverBtn.type = "button";
            coverBtn.className = "btn-set-cover";
            coverBtn.innerHTML = isCover
                ? '<i class="fa-solid fa-star"></i> Titulní'
                : '<i class="fa-regular fa-star"></i> Jako hlavní';
            coverBtn.title = isCover ? "Hlavní titulní fotografie" : "Zvolit jako hlavní fotku";
            coverBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                wizardCoverIndex = index;
                renderWizardPhotoPreviews();
            });

            // Clicking the card itself also selects it as cover
            thumbCard.addEventListener("click", () => {
                if (wizardCoverIndex !== index) {
                    wizardCoverIndex = index;
                    renderWizardPhotoPreviews();
                }
            });

            // Edit photo button (bottom-right)
            const editBtn = document.createElement("button");
            editBtn.type = "button";
            editBtn.className = "btn-edit-thumb";
            editBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Upravit';
            editBtn.title = "AI Bokeh / Zamazat SPZ";
            editBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openPhotoEditorForWizard(index, file);
            });

            thumbCard.appendChild(img);
            thumbCard.appendChild(badge);
            thumbCard.appendChild(removeBtn);
            thumbCard.appendChild(coverBtn);
            thumbCard.appendChild(editBtn);
            newPhotoPreviewGrid.appendChild(thumbCard);
        });
    };

    const addFilesToWizard = (files) => {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (file.type.startsWith("image/")) {
                wizardSelectedFiles.push(file);
            }
        }
        renderWizardPhotoPreviews();
    };

    if (newPhotoFileInput) {
        newPhotoFileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                addFilesToWizard(e.target.files);
            }
        });
    }

    if (newPhotoDropzone) {
        newPhotoDropzone.addEventListener("click", () => {
            if (newPhotoFileInput) newPhotoFileInput.click();
        });

        newPhotoDropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            newPhotoDropzone.style.borderColor = "var(--accent)";
            newPhotoDropzone.style.background = "rgba(131, 92, 223, 0.15)";
        });

        newPhotoDropzone.addEventListener("dragleave", () => {
            newPhotoDropzone.style.borderColor = "rgba(255,255,255,0.15)";
            newPhotoDropzone.style.background = "rgba(0,0,0,0.2)";
        });

        newPhotoDropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            newPhotoDropzone.style.borderColor = "rgba(255,255,255,0.15)";
            newPhotoDropzone.style.background = "rgba(0,0,0,0.2)";
            if (e.dataTransfer && e.dataTransfer.files) {
                addFilesToWizard(e.dataTransfer.files);
            }
        });
    }

    // Window paste handler for Ctrl+V / Cmd+V images
    window.addEventListener("paste", (e) => {
        if (!addListingModal || !addListingModal.classList.contains("active")) return;
        
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
        if (activeTag === "input" || activeTag === "textarea") return;

        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        let pastedImages = [];
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf("image") !== -1) {
                const blob = items[i].getAsFile();
                if (blob) {
                    const file = new File([blob], `screenshot_${Date.now()}.png`, { type: blob.type });
                    pastedImages.push(file);
                }
            }
        }
        if (pastedImages.length > 0) {
            addFilesToWizard(pastedImages);
            showNotification(`Vloženo ${pastedImages.length} fotek ze schránky.`, "info");
        }
    });

    function getActiveModelDisplayName() {
        if (configGeminiModel && configGeminiModel.selectedOptions && configGeminiModel.selectedOptions[0]) {
            const txt = configGeminiModel.selectedOptions[0].text;
            return txt.split('(')[0].trim();
        }
        if (userConfig && userConfig.gemini_model) {
            const m = userConfig.gemini_model;
            if (configGeminiModel) {
                const opt = Array.from(configGeminiModel.options).find(o => o.value === m);
                if (opt) return opt.text.split('(')[0].trim();
            }
            return m.replace(/^models\//, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        }
        return "Gemini 2.5 Flash";
    }

    // Run Vision AI analysis
    if (btnRunVisionAi) {
        btnRunVisionAi.addEventListener("click", async () => {
            if (wizardSelectedFiles.length === 0) {
                showNotification("Nejprve přetáhněte nebo vyberte fotografie předmětu.", "warning");
                return;
            }

            if (newAiActionBar) newAiActionBar.style.display = "none";
            if (visionLoadingText) {
                visionLoadingText.textContent = `${getActiveModelDisplayName()} detailně analyzuje fotografie předmětu...`;
            }
            if (visionAiLoading) visionAiLoading.style.display = "block";
            btnRunVisionAi.disabled = true;

            const formData = new FormData();
            wizardSelectedFiles.forEach((file) => {
                formData.append("photos", file);
            });
            if (newUserNotes) {
                formData.append("notes", newUserNotes.value.trim());
            }
            if (configGeminiModel && configGeminiModel.value) {
                formData.append("model", configGeminiModel.value);
            }

            try {
                const res = await fetch(API.aiAnalyzePhotos, {
                    method: "POST",
                    body: formData
                });

                const data = await res.json();
                if (!res.ok || data.status !== "success") {
                    showNotification(data.message || "Analýza fotografií selhala.", "error");
                    return;
                }

                const visionData = data.data;

                if (visionData._fallback_notice) {
                    showNotification(visionData._fallback_notice, "warning");
                }

                // 1. Detected item banner & Quality Tips
                if (newAiDetectedBanner) {
                    const itemIdent = visionData.item_identification || {};
                    if (detectedItemName) {
                        detectedItemName.textContent = itemIdent.full_name || itemIdent.model || visionData.recommended_title || "Předmět rozpoznán";
                    }
                    if (detectedConditionBadge) {
                        detectedConditionBadge.textContent = itemIdent.condition_cz || itemIdent.condition || "Zachovalý stav";
                    }
                    if (aiQualityTips) {
                        const tips = (visionData.photo_recommendations && visionData.photo_recommendations.quality_tips) || visionData.quality_tips || [];
                        if (tips.length > 0) {
                            aiQualityTips.innerHTML = `<i class="fa-solid fa-lightbulb" style="color: #ffc107;"></i> <strong>Rádce kvality:</strong> ${tips.join(" ")}`;
                        } else {
                            aiQualityTips.innerHTML = `<i class="fa-solid fa-check" style="color: #10b981;"></i> Fotografie jsou ostré a obsahují všechny potřebné detaily.`;
                        }
                    }
                    newAiDetectedBanner.style.display = "block";
                }

                // 2. Titles Chips & Selection
                const titles = visionData.titles || [];
                if (newTitlesChipsContainer && newTitlesChips) {
                    newTitlesChips.innerHTML = "";
                    titles.forEach((t) => {
                        const chip = document.createElement("div");
                        chip.className = `title-chip ${t === visionData.recommended_title ? "selected" : ""}`;
                        chip.innerHTML = `<span>${t}</span><span class="title-chip-badge">${t.length}/50</span>`;
                        chip.addEventListener("click", () => {
                            document.querySelectorAll(".title-chip").forEach(c => c.classList.remove("selected"));
                            chip.classList.add("selected");
                            newTitle.value = t;
                            updateCounter(newTitle, newTitleCounter, 50);
                        });
                        newTitlesChips.appendChild(chip);
                    });
                    newTitlesChipsContainer.style.display = "block";
                }

                if (visionData.recommended_title) {
                    newTitle.value = visionData.recommended_title;
                    updateCounter(newTitle, newTitleCounter, 50);
                }

                // 3. Category pre-fill
                const cat = (visionData.item_identification && visionData.item_identification.category_general) || visionData.category || "";
                if (cat) {
                    newCategory.value = cat;
                }

                // 4. Description pre-fill
                if (visionData.description) {
                    newDescription.value = visionData.description;
                    updateCounter(newDescription, newDescCounter);
                }

                // 5. Market Price Radar Cards & Suggested Price
                const stats = visionData.market_analysis && visionData.market_analysis.statistics;
                const fbPrice = visionData.estimated_price_czk || (visionData.pricing && visionData.pricing.estimated_fair_czk) || 0;
                const sources = (visionData.market_analysis && visionData.market_analysis.sources_checked) || ["Bazoš.cz", "Sbazar.cz"];
                
                populatePriceRadar(stats, fbPrice, sources);

                // Fallback guarantee: if price is still empty or 0, set fbPrice
                if ((!newPrice.value || parseInt(newPrice.value) <= 0) && fbPrice > 0) {
                    newPrice.value = fbPrice;
                }

                // 6. Cover photo recommendation
                const recCoverIdx = visionData.best_cover_photo_index || (visionData.photo_recommendations && visionData.photo_recommendations.cover_photo_index);
                if (typeof recCoverIdx === "number" && recCoverIdx >= 0 && recCoverIdx < wizardSelectedFiles.length) {
                    wizardCoverIndex = recCoverIdx;
                    renderWizardPhotoPreviews();
                }

                showNotification("AI Vision úspěšně vygenerovala podklady pro inzerát!", "success");
            } catch (err) {
                showNotification("Chyba při komunikaci s AI Vision: " + err.message, "error");
            } finally {
                if (visionAiLoading) visionAiLoading.style.display = "none";
                if (newAiActionBar) newAiActionBar.style.display = "block";
                btnRunVisionAi.disabled = false;
            }
        });
    }

    const btnRefreshPriceRadar = document.getElementById("btn-refresh-price-radar");
    if (btnRefreshPriceRadar) {
        btnRefreshPriceRadar.addEventListener("click", async () => {
            const query = (newTitle && newTitle.value) ? newTitle.value.trim() : "";
            if (!query) {
                showNotification("Nejprve zadejte název inzerátu.", "error");
                return;
            }
            const origHtml = btnRefreshPriceRadar.innerHTML;
            btnRefreshPriceRadar.disabled = true;
            btnRefreshPriceRadar.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Hledám...';
            try {
                const res = await fetch("/api/advisor/market-search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        query: query,
                        fallback_price: parseInt(newPrice ? newPrice.value : 0) || 0
                    })
                });
                const json = await res.json();
                if (json.status === "success" && json.data) {
                    const stats = json.data.statistics;
                    const sources = json.data.sources_checked || ["Bazoš.cz", "Sbazar.cz"];
                    populatePriceRadar(stats, parseInt(newPrice ? newPrice.value : 0) || 0, sources);
                    showNotification(`Nalezeno ${json.data.total_found || 0} inzerátů (${sources.join(', ')}).`, "success");
                } else {
                    showNotification(json.message || "Nepodařilo se načíst tržní data.", "error");
                }
            } catch (err) {
                showNotification("Chyba při hledání tržních cen: " + err.message, "error");
            } finally {
                btnRefreshPriceRadar.disabled = false;
                btnRefreshPriceRadar.innerHTML = origHtml;
            }
        });
    }

    document.getElementById("btn-add-listing-modal").addEventListener("click", () => {
        addListingForm.reset();
        resetWizardState();
        updateCounter(newTitle, newTitleCounter, 50);
        updateCounter(newDescription, newDescCounter);
        addListingModal.classList.add("active");
    });

    addListingForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const newTargetBazos = document.getElementById("new-target-bazos");
        const newTargetAukro = document.getElementById("new-target-aukro");
        const submitBtn = document.getElementById("btn-submit-new-listing");
        if (submitBtn) submitBtn.disabled = true;

        try {
            if (wizardSelectedFiles.length > 0) {
                const formData = new FormData();
                formData.append("title", newTitle.value.trim());
                formData.append("price", parseInt(newPrice.value) || 0);
                formData.append("category", newCategory.value.trim());
                formData.append("description", newDescription.value);
                formData.append("notes", (newUserNotes ? newUserNotes.value.trim() : ""));
                formData.append("target_bazos", newTargetBazos && newTargetBazos.checked ? 1 : 0);
                formData.append("target_aukro", newTargetAukro && newTargetAukro.checked ? 1 : 0);
                formData.append("cover_photo_index", wizardCoverIndex);

                wizardSelectedFiles.forEach((file) => {
                    formData.append("photos", file);
                });

                const res = await fetch(API.createWithPhotos, {
                    method: "POST",
                    body: formData
                });

                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification(`Inzerát byl úspěšně vytvořen s ${data.saved_photos_count} fotkami!`, "success");
                    addListingModal.classList.remove("active");
                    resetWizardState();
                    loadListings();
                } else {
                    showNotification(data.message || "Vytváření inzerátu selhalo", "error");
                }
            } else {
                const newAdData = {
                    title: newTitle.value.trim(),
                    price: parseInt(newPrice.value) || 0,
                    category: newCategory.value.trim(),
                    description: newDescription.value,
                    target_bazos: newTargetBazos && newTargetBazos.checked ? 1 : 0,
                    target_aukro: newTargetAukro && newTargetAukro.checked ? 1 : 0
                };

                const res = await fetch(API.addAd, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(newAdData)
                });

                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification(`Inzerát vytvořen. Fotky můžeš vložit do ${data.ad.local_photos_dir}`, "success");
                    addListingModal.classList.remove("active");
                    resetWizardState();
                    loadListings();
                } else {
                    showNotification(data.message || "Vytváření selhalo", "error");
                }
            }
        } catch (err) {
            showNotification("Chyba při vytváření inzerátu: " + err.message, "error");
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });

    // Also handle Re-analyze existing listing photos in editListingModal
    const btnReanalyzeExisting = document.getElementById("btn-reanalyze-existing-photos");
    if (btnReanalyzeExisting) {
        btnReanalyzeExisting.addEventListener("click", async () => {
            if (!currentAd || !currentAd.id) {
                showNotification("Není vybrán žádný inzerát.", "error");
                return;
            }

            const modelName = getActiveModelDisplayName();
            btnReanalyzeExisting.disabled = true;
            btnReanalyzeExisting.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzuji fotky...';
            showNotification(`Spouštím ${modelName} na fotografiích inzerátu...`, "info");

            try {
                const res = await fetch(`${API.aiAnalyzeExisting}/${currentAd.id}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        notes: editNotes ? editNotes.value : "",
                        model: configGeminiModel ? configGeminiModel.value : ""
                    })
                });

                const data = await res.json();
                if (!res.ok || data.status !== "success") {
                    showNotification(data.message || "Analýza fotografií selhala.", "error");
                    return;
                }

                const visionData = data.data;

                if (visionData._fallback_notice) {
                    showNotification(visionData._fallback_notice, "warning");
                }

                if (visionData.description) {
                    openAiModal("description", "improve", visionData.description);
                }

                if (visionData.recommended_title) {
                    editTitle.value = visionData.recommended_title;
                    updateCounter(editTitle, editTitleCounter, 50);
                }

                if (visionData.category || (visionData.item_identification && visionData.item_identification.category_general)) {
                    editCategory.value = visionData.category || visionData.item_identification.category_general;
                }

                showNotification("Fotky byly analyzovány! Texty byly aktualizovány a otevřen AI návrh.", "success");
            } catch (err) {
                showNotification("Chyba při analýze: " + err.message, "error");
            } finally {
                btnReanalyzeExisting.disabled = false;
                btnReanalyzeExisting.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> AI Vision z fotek';
            }
        });
    }

    // ==========================================
    // 5. BAZOŠ AUTOMATIZACE (PLAYWRIGHT)
    // ==========================================

    const triggerPlaywrightAction = async (ad, actionType, extraVal = null, targetDomain = null, autoDeleteOld = true) => {
        // Okamžitě zavřít editační modal, pokud je aktivní, abychom viděli VNC prohlížeč
        if (editListingModal.classList.contains("active")) {
            editListingModal.classList.remove("active");
        }
        if (activeChildModal) {
            closeChildModal(activeChildModal);
        }

        setPlaywrightActive(true);
        showNotification(`Spouštím akci '${actionType}' přes Playwright...`, "info");
        
        // Resetujeme stavový text description
        const statusDesc = document.getElementById("playwright-status-desc");
        if (statusDesc) {
            if (actionType === "sync_views") {
                statusDesc.textContent = "Probíhá synchronizace inzerátů s Bazošem...";
            } else if (actionType === "post" || actionType === "repost") {
                statusDesc.textContent = "Probíhá předvyplňování nového inzerátu na Bazoši...";
            } else if (actionType === "delete") {
                statusDesc.textContent = "Probíhá mazání inzerátu na Bazoši...";
            } else if (actionType === "edit_price") {
                statusDesc.textContent = "Probíhá změna ceny inzerátu na Bazoši...";
            } else {
                statusDesc.textContent = "Sleduj otevřené Chrome okno a případně zadej SMS...";
            }
        }

        // Skryjeme a resetujeme banner kontroly z předchozích akcí
        if (browserReviewBanner) {
            browserReviewBanner.style.display = "none";
            browserReviewBanner.style.background = "rgba(16, 185, 129, 0.15)";
            browserReviewBanner.style.borderColor = "rgba(16, 185, 129, 0.4)";
            const bannerIcon = browserReviewBanner.querySelector(".fa-circle-check, .fa-triangle-exclamation");
            if (bannerIcon) {
                bannerIcon.className = "fa-solid fa-circle-check";
                bannerIcon.style.color = "#10b981";
            }
            const textContainer = browserReviewBanner.querySelector("div > div");
            if (textContainer) {
                textContainer.innerHTML = `
                    <div style="font-weight: 600; font-size: 0.95rem;">Formulář inzerátu byl předvyplněn!</div>
                    <div style="font-size: 0.8rem; color: #cbd5e1;">Zkontroluj údaje na obrazovce, v prohlížeči klikni na <strong>Odeslat</strong> a poté potvrď zde:</div>
                `;
            }
            const confirmBtn = document.getElementById("btn-browser-confirm-post");
            if (confirmBtn) {
                confirmBtn.style.background = "#10b981";
                confirmBtn.style.borderColor = "#059669";
                confirmBtn.style.boxShadow = "0 4px 12px rgba(16, 185, 129, 0.4)";
                confirmBtn.innerHTML = `<i class="fa-solid fa-check"></i> Potvrdit odeslání`;
            }
        }

        // Automaticky přepnout na záložku s živým prohlížečem, aby uživatel viděl spuštěné okno
        switchToTab("browser");
        
        try {
            const bodyPayload = {
                id: ad.id,
                local_photos_dir: ad.local_photos_dir,
                extra_val: extraVal,
                target_domain: targetDomain,
                auto_delete_old: autoDeleteOld
            };
            if (actionType === "repost" || actionType === "post") {
                if (extraVal && !isNaN(parseInt(extraVal))) {
                    bodyPayload.staged_price = parseInt(extraVal);
                }
            }

            const res = await fetch(`${API.action}/${actionType}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(bodyPayload)
            });

            const data = await res.json();
            if (res.ok) {
                // Začneme periodicky kontrolovat stav akce na pozadí
                const statusInterval = setInterval(async () => {
                    try {
                        const statusRes = await fetch("/api/action/status");
                        if (statusRes.ok) {
                            const statusData = await statusRes.json();
                            
                            // Režim kontroly před odesláním (ready_for_review)
                            if (statusData.state === "ready_for_review") {
                                clearInterval(statusInterval);
                                setPlaywrightActive(false);
                                if (browserReviewBanner) {
                                    browserReviewBanner.style.display = "flex";
                                }
                                showNotification("Formulář byl předvyplněn! Zkontroluj inzerát v prohlížeči a odešli jej.", "info");
                                return;
                            }

                            if (!statusData.running) {
                                clearInterval(statusInterval);
                                setPlaywrightActive(false);
                                if (statusData.error) {
                                    showNotification(statusData.error, "error");
                                } else {
                                    showNotification("Akce byla úspěšně dokončena.", "success");
                                    loadListings();
                                }
                            }
                        }
                    } catch (statusErr) {
                        console.error("Chyba při dotazování na stav operace:", statusErr);
                    }
                }, 1000);
            } else {
                showNotification(data.message || "Chyba při spouštění automatizace", "error");
                setPlaywrightActive(false);
            }
        } catch (err) {
            showNotification("Spojení se serverem selhalo při spouštění.", "error");
            setPlaywrightActive(false);
        }
    };

    // --- REPOST CONFIRM MODAL (Rubrika) LOGIKA ---
    const openRepostModal = (ad, prefillPrice = null) => {
        pendingActionAd = ad;
        const rubrikaSelect = document.getElementById("repost-rubrika-select");
        const badgeEl = document.getElementById("repost-rubrika-badge");
        if (rubrikaSelect) {
            populateRubrikaSelect(rubrikaSelect, ad, badgeEl);
        }

        const priceInput = document.getElementById("repost-price-input");
        if (priceInput) {
            priceInput.value = prefillPrice !== null ? prefillPrice : (ad.price || "");
        }
        const autoDeleteCheckbox = document.getElementById("repost-autodelete-checkbox");
        // TOP safety: if active paid TOP, uncheck auto-delete by default and show warning
        const hasActivePaidTop = ad.is_top && ad.top_expires_at && !isTopExpired(ad.top_expires_at);
        if (autoDeleteCheckbox) {
            autoDeleteCheckbox.checked = !hasActivePaidTop;
        }
        // Show/hide TOP warning
        const topWarning = document.getElementById("repost-top-warning-container");
        if (topWarning) {
            if (hasActivePaidTop) {
                const expStr = formatTopExpiry(ad.top_expires_at);
                topWarning.innerHTML = `<div style="background: rgba(220,38,38,0.12); border: 1px solid rgba(220,38,38,0.5); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.75rem; display:flex; align-items:flex-start; gap:0.6rem;">
                    <span style="font-size:1.2rem;">🔥</span>
                    <div>
                        <div style="font-size:0.88rem; font-weight:700; color:#f87171;">Pozor: Aktivní placené TOPování na Bazoši!</div>
                        <div style="font-size:0.8rem; color:#fca5a5; margin-top:3px;">Tento inzerát má aktivní TOPování platné do <strong>${expStr}</strong>. Smazáním inzerátu by zaplacené zvýhodnění nenávratně propadlo. Automatické smazání bylo proto odškrtnuto – překontroluj nastavení níže.</div>
                    </div>
                </div>`;
                topWarning.style.display = 'block';
            } else {
                topWarning.innerHTML = '';
                topWarning.style.display = 'none';
            }
        }

        openChildModal(repostConfirmModal);
    };

    // Naslouchání na ruční změnu rubriky pro aktualizaci badge
    const repostRubrikaSelectEl = document.getElementById("repost-rubrika-select");
    if (repostRubrikaSelectEl) {
        repostRubrikaSelectEl.addEventListener("change", () => {
            const badgeEl = document.getElementById("repost-rubrika-badge");
            if (badgeEl) {
                const selOpt = repostRubrikaSelectEl.options[repostRubrikaSelectEl.selectedIndex];
                const badgeTextEl = badgeEl.querySelector("#repost-rubrika-badge-text") || badgeEl;
                badgeTextEl.innerHTML = `Vybraná rubrika: <strong>${escapeHtml(selOpt ? selOpt.textContent : "")}</strong>`;
            }
        });
    }

    // Zavření repost modalu
    document.querySelectorAll(".btn-close-repost-modal").forEach(btn => {
        btn.addEventListener("click", () => closeChildModal(repostConfirmModal));
    });

    // Spuštění z repost modalu
    document.getElementById("btn-repost-confirm-start").addEventListener("click", () => {
        const rubrikaSelect = document.getElementById("repost-rubrika-select");
        const chosenDomain = rubrikaSelect ? rubrikaSelect.value : "dum.bazos.cz";
        const priceInput = document.getElementById("repost-price-input");
        const stagedPrice = priceInput && priceInput.value ? parseInt(priceInput.value) : null;
        const autoDeleteCheckbox = document.getElementById("repost-autodelete-checkbox");
        const autoDelete = autoDeleteCheckbox ? autoDeleteCheckbox.checked : true;
        const targetAd = pendingActionAd || currentAd;
        closeChildModal(repostConfirmModal);
        if (targetAd) {
            triggerPlaywrightAction(targetAd, "repost", stagedPrice, chosenDomain, autoDelete);
        }
    });

    // --- DELETE MODAL LOGIKA ---
    const openDeleteModal = (ad) => {
        pendingActionAd = ad;
        const titleEl = document.getElementById("delete-modal-listing-title");
        if (titleEl) titleEl.textContent = ad.title || "Inzerát";

        const choiceCards = document.getElementById("delete-choice-cards-container");
        const draftNote = document.getElementById("delete-draft-note");
        const deletePhotosCheckbox = document.getElementById("delete-photos-checkbox");
        if (deletePhotosCheckbox) deletePhotosCheckbox.checked = false;

        const isPublished = Boolean(ad.url && ad.url.trim());
        if (isPublished) {
            if (choiceCards) choiceCards.style.display = "flex";
            if (draftNote) draftNote.style.display = "none";
        } else {
            if (choiceCards) choiceCards.style.display = "none";
            if (draftNote) draftNote.style.display = "block";
        }

        openChildModal(deleteListingModal);
    };

    // Zavření delete modalu
    document.querySelectorAll(".btn-close-delete-modal").forEach(btn => {
        btn.addEventListener("click", () => closeChildModal(deleteListingModal));
    });

    // Tlačítko pro smazání v detailu inzerátu (v patičce)
    const btnDeleteListingModal = document.getElementById("btn-delete-listing-modal");
    if (btnDeleteListingModal) {
        btnDeleteListingModal.addEventListener("click", () => {
            if (currentAd) {
                openDeleteModal(currentAd);
            }
        });
    }

    // Potvrzení smazání v delete modalu
    document.getElementById("btn-confirm-delete-action").addEventListener("click", async () => {
        const targetAd = pendingActionAd || currentAd;
        if (!targetAd) return;

        const deletePhotos = document.getElementById("delete-photos-checkbox")?.checked || false;
        const isPublished = Boolean(targetAd.url && targetAd.url.trim());
        const selectedScope = document.querySelector("input[name='delete_scope']:checked")?.value || "bazos_and_db";

        closeChildModal(deleteListingModal);

        if (selectedScope === "mark_sold") {
            openMarkSoldModal(targetAd);
            return;
        }

        if (isPublished && selectedScope === "bazos_and_db") {
            // Smazání přes Bazoš robota a následné smazání z DB v backendu
            triggerPlaywrightAction(targetAd, "delete");
        } else {
            // Pouze lokální smazání z databáze (a volitelně fotek)
            try {
                showNotification("Mažu inzerát z databáze...", "info");
                const res = await fetch("/api/listings/delete", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: targetAd.id,
                        delete_photos: deletePhotos
                    })
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification(data.message || "Inzerát byl úspěšně smazán.", "success");
                    if (editListingModal.classList.contains("active")) {
                        editListingModal.classList.remove("active");
                    }
                    loadListings();
                } else {
                    showNotification(data.message || "Chyba při mazání inzerátu.", "error");
                }
            } catch (err) {
                showNotification("Chyba při komunikaci se serverem.", "error");
            }
        }
    });

    // --- MARK AS SOLD LOGIKA ---
    let pendingSoldAd = null;

    const openMarkSoldModal = (ad) => {
        pendingSoldAd = ad;
        const titleEl = document.getElementById("mark-sold-title");
        if (titleEl) titleEl.textContent = ad.title || "Položka";

        const priceInput = document.getElementById("mark-sold-price");
        const origPriceHint = document.getElementById("mark-sold-original-price-hint");
        const diffPill = document.getElementById("mark-sold-diff-pill");
        const dateInput = document.getElementById("mark-sold-date");
        const notesInput = document.getElementById("mark-sold-notes");
        const deleteBazosCheckbox = document.getElementById("mark-sold-delete-bazos");
        const deleteBazosWrapper = document.getElementById("mark-sold-bazos-delete-wrapper");

        const origPrice = ad.price ? parseInt(ad.price, 10) : 0;
        const currentSalePrice = (ad.sale_price !== undefined && ad.sale_price !== null) ? ad.sale_price : origPrice;
        if (priceInput) priceInput.value = currentSalePrice || "";
        if (origPriceHint) origPriceHint.textContent = `Původně inzerováno: ${origPrice.toLocaleString("cs-CZ")} Kč`;

        // Datum prodeje (existující datum nebo dnešní datum)
        if (dateInput) {
            const todayStr = new Date().toISOString().split("T")[0];
            dateInput.value = ad.sold_at ? ad.sold_at.split("T")[0] : todayStr;
        }

        if (notesInput) notesInput.value = ad.sold_notes || "";

        const channelSelect = document.getElementById("mark-sold-channel-select");
        if (channelSelect) {
            channelSelect.value = ad.sold_channel || "bazos";
        }

        // Smazání na Bazoši zobrazit jen pokud má inzerát URL
        const hasUrl = Boolean(ad.url && ad.url.trim());
        if (deleteBazosWrapper) {
            deleteBazosWrapper.style.display = hasUrl ? "block" : "none";
        }
        if (deleteBazosCheckbox) {
            deleteBazosCheckbox.checked = hasUrl;
        }

        // Aktualizovat pill rozdílu cen
        const updateDiffPill = () => {
            if (!diffPill) return;
            const currentVal = parseInt(priceInput.value, 10);
            if (!isNaN(currentVal) && origPrice > 0) {
                const diff = currentVal - origPrice;
                const pct = Math.round((diff / origPrice) * 100);
                diffPill.style.display = "inline-block";
                if (pct < 0) {
                    diffPill.className = "price-diff-pill discount";
                    diffPill.textContent = `Sleva ${pct}% (${diff} Kč)`;
                } else if (pct > 0) {
                    diffPill.className = "price-diff-pill surplus";
                    diffPill.textContent = `Příplatek +${pct}% (+${diff} Kč)`;
                } else {
                    diffPill.className = "price-diff-pill exact";
                    diffPill.textContent = "100% ceny";
                }
            } else {
                diffPill.style.display = "none";
            }
        };

        if (priceInput) {
            priceInput.oninput = updateDiffPill;
            updateDiffPill();
        }

        openChildModal(markSoldModal);
    };

    // Zavření mark-sold modalu
    document.querySelectorAll(".btn-close-mark-sold-modal").forEach(btn => {
        btn.addEventListener("click", () => closeChildModal(markSoldModal));
    });

    // Otevření mark-sold z detailu inzerátu (v patičce edit modalu)
    const btnMarkSoldModal = document.getElementById("btn-mark-sold-modal");
    if (btnMarkSoldModal) {
        btnMarkSoldModal.addEventListener("click", () => {
            if (currentAd) {
                openMarkSoldModal(currentAd);
            }
        });
    }

    // Odeslání prodeje
    const btnSubmitMarkSold = document.getElementById("btn-submit-mark-sold");
    if (btnSubmitMarkSold) {
        btnSubmitMarkSold.addEventListener("click", async () => {
            const targetAd = pendingSoldAd || currentAd;
            if (!targetAd) return;

            const priceInput = document.getElementById("mark-sold-price");
            const dateInput = document.getElementById("mark-sold-date");
            const notesInput = document.getElementById("mark-sold-notes");
            const channelSelect = document.getElementById("mark-sold-channel-select");
            const deleteBazosCheckbox = document.getElementById("mark-sold-delete-bazos");

            const salePrice = priceInput && priceInput.value ? parseInt(priceInput.value, 10) : (targetAd.price || 0);
            const soldAt = dateInput ? dateInput.value : "";
            const notes = notesInput ? notesInput.value.trim() : "";
            const soldChannel = channelSelect ? channelSelect.value : "";
            const deleteOnBazos = deleteBazosCheckbox ? deleteBazosCheckbox.checked : false;

            closeChildModal(markSoldModal);

            try {
                showNotification("Ukládám prodej položky...", "info");
                const res = await fetch(`/api/listings/${targetAd.id}/mark_sold`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        sale_price: salePrice,
                        sold_at: soldAt,
                        notes: notes,
                        sold_channel: soldChannel,
                        delete_on_bazos: deleteOnBazos
                    })
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification("🎉 Položka byla úspěšně označena jako prodaná!", "success");
                    if (editListingModal.classList.contains("active")) {
                        editListingModal.classList.remove("active");
                    }
                    loadListings();
                } else {
                    showNotification(data.message || "Chyba při označování za prodané.", "error");
                }
            } catch (err) {
                showNotification("Chyba při komunikaci se serverem: " + err.message, "error");
            }
        });
    }

    // Vrácení prodané položky zpět k prodeji
    const handleRestoreSoldListing = async (ad) => {
        if (!confirm(`Opravdu chceš vrátit položku "${ad.title || 'Inzerát'}" zpět mezi věci k prodeji?`)) {
            return;
        }

        try {
            showNotification("Vracím položku k prodeji...", "info");
            const res = await fetch(`/api/listings/${ad.id}/restore_sold`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showNotification("Položka byla vrácena do věcí k prodeji.", "success");
                loadListings();
            } else {
                showNotification(data.message || "Chyba při vracení položky.", "error");
            }
        } catch (err) {
            showNotification("Chyba při komunikaci se serverem: " + err.message, "error");
        }
    };

    // --- 1-CLICK SMS TOP MODAL LISTENERS ---
    document.querySelectorAll(".btn-close-sms-top-modal").forEach(btn => {
        btn.addEventListener("click", closeSmsTopModal);
    });

    const smsTopModalEl = document.getElementById("sms-top-modal");
    if (smsTopModalEl) {
        smsTopModalEl.addEventListener("click", (e) => {
            if (e.target.id === "sms-top-modal") {
                closeSmsTopModal();
            }
        });
    }

    const textCopyEl = document.getElementById("sms-top-text-copy");
    if (textCopyEl) {
        textCopyEl.addEventListener("click", () => {
            const text = textCopyEl.textContent || "";
            if (text && text !== "BAZOS ...") {
                navigator.clipboard.writeText(text);
                showNotification(`Text SMS '${text}' zkopírován do schránky!`, "success");
            }
        });
    }

    const numberCopyEl = document.getElementById("sms-top-number-copy");
    if (numberCopyEl) {
        numberCopyEl.addEventListener("click", () => {
            const num = numberCopyEl.textContent || "90333";
            navigator.clipboard.writeText(num);
            showNotification(`Telefonní číslo '${num}' zkopírováno!`, "success");
        });
    }

    const btnRecheckRankAfterTop = document.getElementById("btn-recheck-rank-after-top");
    if (btnRecheckRankAfterTop) {
        btnRecheckRankAfterTop.addEventListener("click", async () => {
            if (!currentSmsTopListingId) return;
            const origHtml = btnRecheckRankAfterTop.innerHTML;
            btnRecheckRankAfterTop.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Ověřuji novou pozici...`;
            btnRecheckRankAfterTop.disabled = true;
            try {
                await checkBazosRank(currentSmsTopListingId);
            } finally {
                btnRecheckRankAfterTop.innerHTML = origHtml;
                btnRecheckRankAfterTop.disabled = false;
                closeSmsTopModal();
            }
        });
    }

    // --- MANUAL PUBLISH MODAL LOGIKA ---
    let pendingManualPublishAd = null;
    let selectedManualPortal = "facebook";
    let selectedManualLabel = "Facebook Marketplace";

    const openManualPublishModal = (ad) => {
        pendingManualPublishAd = ad;

        const adTitleHeader = document.getElementById("manual-publish-ad-title");
        if (adTitleHeader) {
            adTitleHeader.textContent = ad.title || "Inzerát";
        }

        // 1-click copy inputs
        const copyTitleInput = document.getElementById("manual-copy-title-input");
        const copyPriceInput = document.getElementById("manual-copy-price-input");
        const copyDescInput = document.getElementById("manual-copy-desc-input");
        const zipBtnLabel = document.getElementById("manual-zip-btn-label");

        if (copyTitleInput) copyTitleInput.value = ad.title || "";
        if (copyPriceInput) copyPriceInput.value = ad.price ? `${ad.price} Kč` : "Dohodou";
        if (copyDescInput) copyDescInput.value = ad.description || "";
        if (zipBtnLabel) zipBtnLabel.textContent = `Stáhnout fotky (ZIP: ${ad.photos_count || 0})`;

        // Reset inputs
        const urlInput = document.getElementById("manual-portal-url-input");
        const notesInput = document.getElementById("manual-portal-notes-input");
        const customContainer = document.getElementById("manual-custom-portal-input-container");
        const customNameInput = document.getElementById("manual-custom-portal-name");

        if (urlInput) urlInput.value = "";
        if (notesInput) notesInput.value = "";
        if (customNameInput) customNameInput.value = "";
        if (customContainer) customContainer.style.display = "none";

        // Default: Facebook Marketplace
        selectedManualPortal = "facebook";
        selectedManualLabel = "Facebook Marketplace";

        const chips = document.querySelectorAll(".btn-portal-chip");
        chips.forEach(chip => {
            const p = chip.getAttribute("data-portal");
            if (p === "facebook") {
                chip.classList.add("active");
            } else {
                chip.classList.remove("active");
            }
        });

        // Prefill existing URL for default portal if present
        if (ad.portal_states && ad.portal_states.facebook && ad.portal_states.facebook.url) {
            if (urlInput) urlInput.value = ad.portal_states.facebook.url;
        }

        openChildModal(manualPublishModal);
    };

    // Přepínání čipů portálů v manual publish modalu
    document.querySelectorAll(".btn-portal-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".btn-portal-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            selectedManualPortal = chip.getAttribute("data-portal");
            selectedManualLabel = chip.getAttribute("data-label") || selectedManualPortal;

            const customContainer = document.getElementById("manual-custom-portal-input-container");
            const customInput = document.getElementById("manual-custom-portal-name");
            const urlInput = document.getElementById("manual-portal-url-input");

            if (selectedManualPortal === "custom") {
                if (customContainer) customContainer.style.display = "block";
                if (customInput) customInput.focus();
            } else {
                if (customContainer) customContainer.style.display = "none";
            }

            // Pokud inzerát už má pro tento portál evidovanou URL, předvyplníme ji
            if (pendingManualPublishAd && pendingManualPublishAd.portal_states && urlInput) {
                const existingState = pendingManualPublishAd.portal_states[selectedManualPortal];
                if (existingState && existingState.url) {
                    urlInput.value = existingState.url;
                } else if (selectedManualPortal === "bazos" && pendingManualPublishAd.url) {
                    urlInput.value = pendingManualPublishAd.url;
                } else {
                    urlInput.value = "";
                }
            }
        });
    });

    // 1-Click Copy pomocníci
    const setupManualCopyHelper = (btnId, inputId) => {
        const btn = document.getElementById(btnId);
        const input = document.getElementById(inputId);
        if (!btn || !input) return;

        btn.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(input.value);
                const origHtml = btn.innerHTML;
                btn.innerHTML = `<i class="fa-solid fa-check"></i> Zkopírováno!`;
                btn.classList.add("copied");
                setTimeout(() => {
                    btn.innerHTML = origHtml;
                    btn.classList.remove("copied");
                }, 1500);
            } catch (err) {
                showNotification("Nepodařilo se zkopírovat text do schránky.", "error");
            }
        });
    };

    setupManualCopyHelper("btn-copy-manual-title", "manual-copy-title-input");
    setupManualCopyHelper("btn-copy-manual-price", "manual-copy-price-input");
    setupManualCopyHelper("btn-copy-manual-desc", "manual-copy-desc-input");

    // Stažení fotografií jako ZIP
    const btnManualDownloadZip = document.getElementById("btn-manual-download-zip");
    if (btnManualDownloadZip) {
        btnManualDownloadZip.addEventListener("click", () => {
            if (!pendingManualPublishAd) return;
            showNotification("Stahuji ZIP archiv s fotografiemi...", "info");
            const downloadLink = document.createElement("a");
            downloadLink.href = `/api/photos/${pendingManualPublishAd.id}/zip`;
            downloadLink.download = `fotky-${pendingManualPublishAd.id}.zip`;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
        });
    }

    // Odeslání a uložení ručního zveřejnění
    const btnConfirmManualPublish = document.getElementById("btn-confirm-manual-publish");
    if (btnConfirmManualPublish) {
        btnConfirmManualPublish.addEventListener("click", async () => {
            const targetAd = pendingManualPublishAd || currentAd;
            if (!targetAd) return;

            let portalName = selectedManualPortal;
            let portalLabel = selectedManualLabel;

            if (portalName === "custom") {
                const customInput = document.getElementById("manual-custom-portal-name");
                const customVal = customInput ? customInput.value.trim() : "";
                if (!customVal) {
                    showNotification("Zadej prosím název vlastního portálu.", "error");
                    if (customInput) customInput.focus();
                    return;
                }
                portalLabel = customVal;
            }

            const urlInput = document.getElementById("manual-portal-url-input");
            const notesInput = document.getElementById("manual-portal-notes-input");
            const url = urlInput ? urlInput.value.trim() : "";
            const notes = notesInput ? notesInput.value.trim() : "";

            closeChildModal(manualPublishModal);

            try {
                showNotification(`Ukládám evidenci pro ${portalLabel}...`, "info");
                const res = await fetch(`/api/listings/${targetAd.id}/publish-manual`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        portal_name: portalName,
                        portal_label: portalLabel,
                        url: url,
                        notes: notes
                    })
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification(`🎉 Inzerát byl úspěšně zaevidován na ${portalLabel}!`, "success");
                    loadListings();
                } else {
                    showNotification(data.message || "Chyba při ukládání evidence.", "error");
                }
            } catch (err) {
                showNotification("Chyba při komunikaci se serverem: " + err.message, "error");
            }
        });
    }

    // Zavření manual-publish modalu
    document.querySelectorAll(".btn-close-manual-publish-modal").forEach(btn => {
        btn.addEventListener("click", () => closeChildModal(manualPublishModal));
    });

    // Zavření child modalů při kliknutí do pozadí (backdrop)
    [repostConfirmModal, deleteListingModal, markSoldModal, manualPublishModal].forEach(modal => {
        if (modal) {
            modal.addEventListener("click", (e) => {
                if (e.target === modal) {
                    closeChildModal(modal);
                }
            });
        }
    });

    // Escape klávesa pro zavření aktivního child modalu
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && activeChildModal) {
            closeChildModal(activeChildModal);
        }
    });

    // --- BROWSER REVIEW BANNER & CONFIRM STEPPER LOGIKA ---
    const btnBrowserConfirmPost = document.getElementById("btn-browser-confirm-post");
    const confirmProgressModal = document.getElementById("confirm-progress-modal");
    const stepRowVerify = document.getElementById("step-row-verify");
    const stepRowDelete = document.getElementById("step-row-delete");
    const stepRowSave = document.getElementById("step-row-save");
    const confirmStatusAlert = document.getElementById("confirm-status-alert");
    const confirmModalFooter = document.getElementById("confirm-modal-footer");
    const btnConfirmProgressDone = document.getElementById("btn-confirm-progress-done");

    const resetConfirmModalUI = () => {
        if (confirmAutoAdvanceTimer) {
            clearTimeout(confirmAutoAdvanceTimer);
            confirmAutoAdvanceTimer = null;
        }

        if (stepRowVerify) {
            stepRowVerify.className = "confirm-step-row active";
            stepRowVerify.style.opacity = "1";
            const icon = stepRowVerify.querySelector(".step-icon-col i");
            if (icon) icon.className = "fa-solid fa-circle-notch fa-spin";
            if (icon) icon.style.color = "var(--primary-color)";
            const detail = stepRowVerify.querySelector(".step-detail");
            if (detail) detail.textContent = "Zjišťuji novou URL a kontroluji stav formuláře...";
        }

        if (stepRowDelete) {
            stepRowDelete.className = "confirm-step-row";
            stepRowDelete.style.opacity = "0.45";
            const icon = stepRowDelete.querySelector(".step-icon-col i");
            if (icon) icon.className = "fa-regular fa-circle";
            if (icon) icon.style.color = "var(--text-muted)";
            const detail = stepRowDelete.querySelector(".step-detail");
            if (detail) detail.textContent = "Čeká na ověření nového inzerátu...";
        }

        if (stepRowSave) {
            stepRowSave.className = "confirm-step-row";
            stepRowSave.style.opacity = "0.45";
            const icon = stepRowSave.querySelector(".step-icon-col i");
            if (icon) icon.className = "fa-regular fa-circle";
            if (icon) icon.style.color = "var(--text-muted)";
            const detail = stepRowSave.querySelector(".step-detail");
            if (detail) detail.textContent = "Čeká na dokončení úklidu...";
        }

        if (confirmStatusAlert) confirmStatusAlert.style.display = "none";
        if (confirmModalFooter) confirmModalFooter.style.display = "none";
    };

    const handleConfirmProgressNext = () => {
        if (confirmAutoAdvanceTimer) {
            clearTimeout(confirmAutoAdvanceTimer);
            confirmAutoAdvanceTimer = null;
        }
        if (confirmProgressModal) confirmProgressModal.style.display = "none";

        // Pokud je v kroku chyba, zůstáváme v prohlížeči pro nápravu
        const hasError = stepRowVerify && stepRowVerify.classList.contains("error");
        if (hasError) return;

        // Pokud běží dávková fronta a jsou další položky
        if (batchQueue.length > 0 && batchIndex < batchQueue.length - 1) {
            batchIndex++;
            const currentItem = batchQueue[batchIndex];
            const indicator = document.getElementById("batch-queue-indicator");
            if (indicator) {
                indicator.style.display = "flex";
                const curEl = document.getElementById("batch-queue-current");
                const totEl = document.getElementById("batch-queue-total");
                const nameEl = document.getElementById("batch-queue-name");
                if (curEl) curEl.textContent = batchIndex + 1;
                if (totEl) totEl.textContent = batchQueue.length;
                if (nameEl) nameEl.textContent = `Položka: ${currentItem.ad.title || "Bez názvu"}`;
            }
            showNotification(`Dávka: Spouštím ${batchIndex + 1}/${batchQueue.length} (${currentItem.ad.title})...`, "info");
            setTimeout(() => {
                triggerPlaywrightAction(currentItem.ad, "repost", currentItem.price, currentItem.domain, currentItem.autoDelete);
            }, 800);
        } else {
            if (batchQueue.length > 0) {
                showNotification("Celá dávka byla úspěšně zpracována!", "success");
                batchQueue = [];
                selectedBatchAdIds.clear();
                updateBatchActionBar();
                const indicator = document.getElementById("batch-queue-indicator");
                if (indicator) indicator.style.display = "none";
            }
            switchToTab("active-listings");
            loadListings();
        }
    };

    if (btnConfirmProgressDone) {
        btnConfirmProgressDone.addEventListener("click", () => {
            handleConfirmProgressNext();
        });
    }

    if (btnBrowserConfirmPost) {
        btnBrowserConfirmPost.addEventListener("click", async () => {
            btnBrowserConfirmPost.disabled = true;
            btnBrowserConfirmPost.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Zpracovávám...`;

            resetConfirmModalUI();
            if (confirmProgressModal) confirmProgressModal.style.display = "flex";

            try {
                const res = await fetch("/api/action/confirm", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });
                const data = await res.json();

                if (res.ok && data.status === "success") {
                    // Krok 1: Ověření OK
                    if (stepRowVerify) {
                        stepRowVerify.className = "confirm-step-row completed";
                        stepRowVerify.style.opacity = "1";
                        const icon = stepRowVerify.querySelector(".step-icon-col i");
                        if (icon) {
                            icon.className = "fa-solid fa-circle-check";
                            icon.style.color = "#10b981";
                        }
                        const detail = stepRowVerify.querySelector(".step-detail");
                        if (detail) {
                            detail.textContent = data.recovered_from_502 ?
                                "Inzerát ověřen záložním dohledáním (Bazoš 502 vyřešen)!" :
                                `Nový inzerát ověřen: ${data.url || "OK"}`;
                        }
                    }

                    // Krok 2: Úklid starého inzerátu
                    if (stepRowDelete) {
                        stepRowDelete.className = "confirm-step-row completed";
                        stepRowDelete.style.opacity = "1";
                        const icon = stepRowDelete.querySelector(".step-icon-col i");
                        const detail = stepRowDelete.querySelector(".step-detail");
                        if (data.old_deleted) {
                            if (data.old_deleted.status === "deleted") {
                                if (icon) { icon.className = "fa-solid fa-circle-check"; icon.style.color = "#10b981"; }
                                if (detail) detail.textContent = "Původní inzerát byl na Bazoši automaticky smazán.";
                            } else if (data.old_deleted.status === "expired") {
                                if (icon) { icon.className = "fa-solid fa-circle-check"; icon.style.color = "#10b981"; }
                                if (detail) detail.textContent = "Původní inzerát na Bazoši již dříve expiroval.";
                            } else {
                                if (icon) { icon.className = "fa-solid fa-triangle-exclamation"; icon.style.color = "#eab308"; }
                                if (detail) detail.textContent = `Úklid: ${data.old_deleted.reason || "Původní inzerát nebyl nalezen."}`;
                            }
                        } else {
                            if (icon) { icon.className = "fa-solid fa-circle-check"; icon.style.color = "#10b981"; }
                            if (detail) detail.textContent = "Nebylo vyžadováno smazání původního inzerátu.";
                        }
                    }

                    // Krok 3: Databáze
                    if (stepRowSave) {
                        stepRowSave.className = "confirm-step-row completed";
                        stepRowSave.style.opacity = "1";
                        const icon = stepRowSave.querySelector(".step-icon-col i");
                        if (icon) { icon.className = "fa-solid fa-circle-check"; icon.style.color = "#10b981"; }
                        const detail = stepRowSave.querySelector(".step-detail");
                        if (detail) detail.textContent = "Inzerát aktivován a zapsán do historie publikací.";
                    }

                    // Status alert
                    if (confirmStatusAlert) {
                        confirmStatusAlert.style.display = "block";
                        confirmStatusAlert.style.background = "rgba(16, 185, 129, 0.15)";
                        confirmStatusAlert.style.border = "1px solid rgba(16, 185, 129, 0.4)";
                        confirmStatusAlert.style.color = "#4ade80";
                        confirmStatusAlert.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${escapeHtml(data.message || "Hotovo!")}`;
                    }

                    if (browserReviewBanner) browserReviewBanner.style.display = "none";

                    // Footer button konfigurace
                    if (confirmModalFooter && btnConfirmProgressDone) {
                        confirmModalFooter.style.display = "flex";
                        if (batchQueue.length > 0 && batchIndex < batchQueue.length - 1) {
                            btnConfirmProgressDone.innerHTML = `<i class="fa-solid fa-forward-step"></i> Další inzerát z dávky (${batchIndex + 2}/${batchQueue.length})`;
                        } else {
                            btnConfirmProgressDone.innerHTML = `<i class="fa-solid fa-arrow-left"></i> Zpět na přehled inzerátů`;
                        }
                    }

                    // Auto-advance po 2.6s
                    confirmAutoAdvanceTimer = setTimeout(() => {
                        handleConfirmProgressNext();
                    }, 2600);

                } else {
                    // Chyba při potvrzení
                    if (stepRowVerify) {
                        stepRowVerify.className = "confirm-step-row error";
                        stepRowVerify.style.opacity = "1";
                        const icon = stepRowVerify.querySelector(".step-icon-col i");
                        if (icon) {
                            icon.className = "fa-solid fa-circle-xmark";
                            icon.style.color = "#ef4444";
                        }
                        const detail = stepRowVerify.querySelector(".step-detail");
                        if (detail) detail.textContent = `Chyba: ${data.message || "Ověření selhalo."}`;
                    }

                    if (confirmStatusAlert) {
                        confirmStatusAlert.style.display = "block";
                        confirmStatusAlert.style.background = "rgba(239, 68, 68, 0.15)";
                        confirmStatusAlert.style.border = "1px solid rgba(239, 68, 68, 0.4)";
                        confirmStatusAlert.style.color = "#f87171";
                        confirmStatusAlert.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(data.message || "Ověření inzerátu selhalo. Zkontrolujte prohlížeč.")}`;
                    }

                    if (confirmModalFooter && btnConfirmProgressDone) {
                        confirmModalFooter.style.display = "flex";
                        btnConfirmProgressDone.innerHTML = `<i class="fa-solid fa-xmark"></i> Zavřít a vrátit se do prohlížeče`;
                    }
                }
            } catch (err) {
                if (stepRowVerify) {
                    stepRowVerify.className = "confirm-step-row error";
                    const icon = stepRowVerify.querySelector(".step-icon-col i");
                    if (icon) { icon.className = "fa-solid fa-circle-xmark"; icon.style.color = "#ef4444"; }
                    const detail = stepRowVerify.querySelector(".step-detail");
                    if (detail) detail.textContent = `Chyba spojení: ${err.message}`;
                }
                if (confirmStatusAlert) {
                    confirmStatusAlert.style.display = "block";
                    confirmStatusAlert.style.background = "rgba(239, 68, 68, 0.15)";
                    confirmStatusAlert.style.border = "1px solid rgba(239, 68, 68, 0.4)";
                    confirmStatusAlert.style.color = "#f87171";
                    confirmStatusAlert.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> Chyba spojení se serverem.`;
                }
                if (confirmModalFooter && btnConfirmProgressDone) {
                    confirmModalFooter.style.display = "flex";
                    btnConfirmProgressDone.innerHTML = `<i class="fa-solid fa-xmark"></i> Zavřít`;
                }
            } finally {
                btnBrowserConfirmPost.disabled = false;
                btnBrowserConfirmPost.innerHTML = `<i class="fa-solid fa-check"></i> Potvrdit odeslání`;
            }
        });
    }

    const btnBrowserCancelPost = document.getElementById("btn-browser-cancel-post");
    if (btnBrowserCancelPost) {
        btnBrowserCancelPost.addEventListener("click", async () => {
            if (browserReviewBanner) browserReviewBanner.style.display = "none";
            showNotification("Akce vystavení byla zrušena.", "info");
            try {
                await fetch(API.cancel, { method: "POST" });
            } catch (e) {}
        });
    }

    // Připojení akčních tlačítek v detailu inzerátu
    document.getElementById("action-post").addEventListener("click", async () => {
        if (!currentAd) return;
        
        // Auto-save form data before opening repost modal
        const editTargetBazos = document.getElementById("edit-target-bazos");
        const editTargetAukro = document.getElementById("edit-target-aukro");
        const updatedAd = {
            ...currentAd,
            title: editTitle.value,
            price: parseInt(editPrice.value) || 0,
            category: editCategory.value.trim(),
            description: editDescription.value,
            notes: editNotes.value,
            local_photos_dir: editPhotosDir.value,
            excluded_photos: Array.from(excludedPhotos),
            target_bazos: editTargetBazos && editTargetBazos.checked ? 1 : 0,
            target_aukro: editTargetAukro && editTargetAukro.checked ? 1 : 0
        };

        try {
            await fetch(API.saveAd, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedAd)
            });
            currentAd = updatedAd;
        } catch (e) {}

        openRepostModal(currentAd);
    });

    document.getElementById("action-edit-price").addEventListener("click", () => {
        if (currentAd) {
            const price = editPrice.value;
            triggerPlaywrightAction(currentAd, "edit_price", price);
        }
    });

    // Globální synchronizace views
    document.getElementById("btn-sync-views").addEventListener("click", () => {
        triggerPlaywrightAction({ local_photos_dir: "all" }, "sync_views");
    });

    // Přerušení běžící akce
    const cancelBtn = document.getElementById("btn-cancel-action");
    cancelBtn.addEventListener("click", async () => {
        cancelBtn.disabled = true;
        cancelBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Ruším...`;
        showNotification("Odesílám požadavek na přerušení...", "info");
        try {
            const res = await fetch(API.cancel, { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                showNotification(data.message || "Operace byla přerušena.", "success");
            } else {
                showNotification(data.message || "Nepodařilo se přerušit operaci.", "error");
                cancelBtn.disabled = false;
                cancelBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Přerušit`;
            }
        } catch (err) {
            showNotification("Chyba při komunikaci se serverem.", "error");
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Přerušit`;
        }
    });

    const setPlaywrightActive = (isActive) => {
        const cancelBtn = document.getElementById("btn-cancel-action");
        if (isActive) {
            playwrightStatus.classList.add("active");
            document.querySelectorAll(".listing-card").forEach(card => card.classList.add("locked"));
        } else {
            playwrightStatus.classList.remove("active");
            document.querySelectorAll(".listing-card").forEach(card => card.classList.remove("locked"));
            
            // Obnovíme tlačítko stornování do výchozího stavu
            if (cancelBtn) {
                cancelBtn.disabled = false;
                cancelBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Přerušit`;
            }
        }
    };

    // ==========================================
    // 6. AI EDITOR LOGIKA (GEMINI INTEGRACE)
    // ==========================================

    const triggerAiImprovement = async (text, field, instruction) => {
        lastAiSourceText = text;
        lastAiField = field;
        lastAiInstruction = instruction;
        
        showNotification("Volám AI asistenta Gemini...", "info");
        
        try {
            const res = await fetch(API.aiImprove, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    field: field,
                    instruction: instruction
                })
            });

            const data = await res.json();
            if (res.ok) {
                showAiProposal(text, data.result, instruction);
            } else {
                showNotification(data.message || "AI asistent selhal.", "error");
            }
        } catch (err) {
            showNotification("Nepodařilo se spojit s AI službou.", "error");
        }
    };

    const showAiProposal = (original, improved, instruction) => {
        document.getElementById("ai-original-text-preview").textContent = original;
        
        const improvedInput = document.getElementById("ai-improved-text-input");
        if (improvedInput) {
            improvedInput.value = improved;
        }
        
        const select = document.getElementById("modal-ai-instruction");
        if (select) {
            select.value = instruction || "improve";
        }
        
        aiProposalModal.classList.add("active");
    };

    // AI tlačítka v editoru pro celý nadpis nebo popis
    document.getElementById("ai-improve-title").addEventListener("click", () => {
        triggerAiImprovement(editTitle.value, "title", "improve");
    });

    document.getElementById("ai-improve-desc").addEventListener("click", () => {
        triggerAiImprovement(editDescription.value, "description", "improve");
    });

    document.getElementById("ai-fix-desc").addEventListener("click", () => {
        triggerAiImprovement(editDescription.value, "description", "fix");
    });

    document.getElementById("ai-shorten-desc").addEventListener("click", () => {
        triggerAiImprovement(editDescription.value, "description", "shorten");
    });

    // --- Inline výběr textu a plovoucí AI tooltip ---
    editDescription.addEventListener("mouseup", (e) => {
        const selection = editDescription.value.substring(
            editDescription.selectionStart,
            editDescription.selectionEnd
        ).trim();

        if (selection.length > 5) {
            // Uložíme si rozsah výběru
            selectedTextRange = {
                start: editDescription.selectionStart,
                end: editDescription.selectionEnd,
                text: selection
            };

            // Zobrazíme plovoucí tlačítko poblíž myši
            inlineAiBtn.style.left = `${e.pageX}px`;
            inlineAiBtn.style.top = `${e.pageY - 45}px`;
            inlineAiBtn.style.display = "inline-flex";
        } else {
            selectedTextRange = null;
            inlineAiBtn.style.display = "none";
        }
    });

    // Kliknutí na inline AI tlačítko
    inlineAiBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (selectedTextRange) {
            triggerAiImprovement(selectedTextRange.text, "description", "improve");
            inlineAiBtn.style.display = "none";
        }
    });

    // Skrytí inline AI tlačítka při kliknutí jinam
    document.addEventListener("mousedown", (e) => {
        if (e.target !== inlineAiBtn && !inlineAiBtn.contains(e.target) && e.target !== editDescription) {
            inlineAiBtn.style.display = "none";
            selectedTextRange = null;
        }
    });

    // Přijetí AI návrhu
    document.getElementById("btn-accept-ai-proposal").addEventListener("click", () => {
        const improvedInput = document.getElementById("ai-improved-text-input");
        const improvedText = improvedInput ? improvedInput.value : "";
        
        if (selectedTextRange) {
            const fullText = editDescription.value;
            const updatedText = 
                fullText.substring(0, selectedTextRange.start) + 
                improvedText + 
                fullText.substring(selectedTextRange.end);
            
            editDescription.value = updatedText;
            selectedTextRange = null;
            showNotification("Vybraný text byl nahrazen vaší upravenou AI verzí.", "success");
        } else {
            if (document.getElementById("ai-original-text-preview").textContent === editTitle.value) {
                editTitle.value = improvedText;
                showNotification("Nadpis byl nahrazen vaší upravenou AI verzí.", "success");
            } else {
                editDescription.value = improvedText;
                showNotification("Popis byl nahrazen vaší upravenou AI verzí.", "success");
            }
        }
        
        aiProposalModal.classList.remove("active");
    });

    // Sync active instruction if selection changes in modal
    const modalSelect = document.getElementById("modal-ai-instruction");
    if (modalSelect) {
        modalSelect.addEventListener("change", (e) => {
            lastAiInstruction = e.target.value;
        });
    }

    // "Try again" regeneration handler
    const btnRegenerate = document.getElementById("btn-regenerate-ai");
    if (btnRegenerate) {
        btnRegenerate.addEventListener("click", async () => {
            if (!lastAiSourceText) return;
            
            btnRegenerate.disabled = true;
            btnRegenerate.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generuji...`;
            
            showNotification("Generuji nový návrh...", "info");
            
            try {
                const res = await fetch(API.aiImprove, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        text: lastAiSourceText,
                        field: lastAiField,
                        instruction: lastAiInstruction
                    })
                });

                const data = await res.json();
                if (res.ok) {
                    const improvedInput = document.getElementById("ai-improved-text-input");
                    if (improvedInput) {
                        improvedInput.value = data.result;
                    }
                    showNotification("Nový návrh je připraven.", "success");
                } else {
                    showNotification(data.message || "Regenerace selhala.", "error");
                }
            } catch (err) {
                showNotification("Chyba při komunikaci se serverem.", "error");
            } finally {
                btnRegenerate.disabled = false;
                btnRegenerate.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Zkusit znovu (Regenerovat)`;
            }
        });
    }

    // Zavírání AI modalu
    document.querySelectorAll(".btn-close-ai-modal").forEach(btn => {
        btn.addEventListener("click", () => {
            aiProposalModal.classList.remove("active");
            selectedTextRange = null;
        });
    });

    // ==========================================
    // 7. NASTAVENÍ (KONFIGURACE) FORMULÁŘ
    // ==========================================

    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        // Zjistíme, zda uživatel napsal nový klíč
        let geminiKeyVal = configGeminiKey.value;
        
        const updatedConfig = {
            name: configName.value,
            email: configEmail.value,
            phone: configPhone.value,
            zip_code: configZip.value,
            default_ad_password_b64: configPassword.value ? btoa(configPassword.value) : "",
            auto_refresh_enabled: configAutoRefresh.checked,
            auto_refresh_interval: parseInt(configRefreshInterval.value) || 720,
        };

        if (geminiKeyVal) {
            updatedConfig.gemini_api_key = geminiKeyVal;
        }

        if (configGeminiModel) {
            updatedConfig.gemini_model = configGeminiModel.value;
        }

        if (configTruenasUrl) updatedConfig.truenas_url = configTruenasUrl.value.trim();
        if (configTruenasAppName) updatedConfig.truenas_app_name = configTruenasAppName.value.trim();
        if (configTruenasApiKey && configTruenasApiKey.value.trim()) {
            updatedConfig.truenas_api_key = configTruenasApiKey.value.trim();
        }

        if (configLocation) updatedConfig.location = configLocation.value.trim();
        if (configAiDelivery) updatedConfig.ai_delivery_options = configAiDelivery.value.trim();
        if (configAiSeller) updatedConfig.ai_seller_context = configAiSeller.value.trim();

        try {
            const res = await fetch(API.config, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedConfig)
            });

            if (res.ok) {
                showNotification("Nastavení bylo úspěšně uloženo.", "success");
                configGeminiKey.value = "";
                if (configTruenasApiKey) configTruenasApiKey.value = "";
                loadConfig();
            } else {
                const data = await res.json();
                showNotification(data.message || "Ukládání selhalo.", "error");
            }
        } catch (err) {
            showNotification("Chyba při ukládání nastavení.", "error");
        }
    });

    // Dynamické načítání a aktualizace dostupných Google AI (Gemini) modelů
    async function loadGeminiModels(force = false) {
        if (!configGeminiModel) return;

        const currentSelected = configGeminiModel.value;
        // Klíč posíláme POUZE pokud uživatel právě zadal nový (input není prázdný).
        // Po uložení se input vždy vymaže → backend použije uložený klíč ze serveru.
        const apiKey = configGeminiKey ? configGeminiKey.value.trim() : "";

        if (btnRefreshGeminiModels) {
            btnRefreshGeminiModels.disabled = true;
        }
        if (refreshGeminiModelsIcon) {
            refreshGeminiModelsIcon.className = "fa-solid fa-arrows-rotate fa-spin";
        }
        if (geminiModelsInfo) {
            geminiModelsInfo.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Zjišťuji dostupné modely z účtu...';
        }

        try {
            const queryParams = new URLSearchParams();
            // Posíláme api_key jen pokud uživatel zadal nový klíč do pole (není placeholder)
            if (apiKey) queryParams.append("api_key", apiKey);
            if (force) queryParams.append("force", "true");

            const res = await fetch(`/api/ai/models?${queryParams.toString()}`);

            const data = await res.json();

            if (res.ok && data.status === "success" && Array.isArray(data.models) && data.models.length > 0) {
                configGeminiModel.innerHTML = "";
                let targetModel = currentSelected || data.current_model || "gemini-2.5-flash";
                let modelFound = false;

                data.models.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m.id;
                    opt.textContent = m.label || m.name || m.id;
                    if (m.description) {
                        opt.title = m.description;
                    }
                    if (m.id === targetModel) {
                        opt.selected = true;
                        modelFound = true;
                    }
                    configGeminiModel.appendChild(opt);
                });

                // Pokud dříve vybraný model (např. ukončený gemini-2.5-pro) již v účtu neexistuje, zvolíme doporučený
                if (!modelFound) {
                    const fallbackModel = data.models.find(m => m.recommended) || data.models[0];
                    if (fallbackModel) {
                        configGeminiModel.value = fallbackModel.id;
                        if (currentSelected && currentSelected !== fallbackModel.id && currentSelected !== "gemini-2.5-pro") {
                            showNotification(`Původní model '${currentSelected}' není dostupný, nastaven ${fallbackModel.name}.`, "info");
                        }
                    }
                }

                if (visionLoadingText) {
                    visionLoadingText.textContent = `${getActiveModelDisplayName()} detailně analyzuje fotografie předmětu...`;
                }

                if (geminiModelsInfo) {
                    if (data.is_fallback) {
                        geminiModelsInfo.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color: #f39c12;"></i> ${data.message || "Výchozí seznam modelů (zadejte API klíč pro načtení z vašeho účtu)."}`;
                    } else {
                        geminiModelsInfo.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #2ecc71;"></i> Načteno z vašeho Google AI účtu (${data.models.length} modelů).`;
                    }
                }
            } else {
                if (geminiModelsInfo) {
                    const msg = data.message || "Nepodařilo se načíst seznam modelů.";
                    geminiModelsInfo.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:#f39c12;"></i> ${msg}`;
                }
            }
        } catch (err) {
            console.error("loadGeminiModels err:", err);
            if (geminiModelsInfo) {
                geminiModelsInfo.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:#e74c3c;"></i> Chyba spojení se serverem: ${err.message}`;
            }
        } finally {
            if (btnRefreshGeminiModels) {
                btnRefreshGeminiModels.disabled = false;
            }
            if (refreshGeminiModelsIcon) {
                refreshGeminiModelsIcon.className = "fa-solid fa-arrows-rotate";
            }
        }
    }

    if (btnRefreshGeminiModels) {
        btnRefreshGeminiModels.addEventListener("click", () => {
            loadGeminiModels(true);
        });
    }

    if (configGeminiModel) {
        configGeminiModel.addEventListener("change", () => {
            if (visionLoadingText) {
                visionLoadingText.textContent = `${getActiveModelDisplayName()} detailně analyzuje fotografie předmětu...`;
            }
        });
    }

    if (configGeminiKey) {
        configGeminiKey.addEventListener("change", () => {
            if (configGeminiKey.value.trim()) {
                loadGeminiModels(true);
            }
        });
    }

    // Toggle viditelnosti API klíče
    toggleGeminiKeyBtn.addEventListener("click", () => {
        const type = configGeminiKey.getAttribute("type") === "password" ? "text" : "password";
        configGeminiKey.setAttribute("type", type);
        toggleGeminiKeyBtn.querySelector("i").className = type === "password" ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
    });

    // Test spojení s Google AI (Gemini)
    if (btnTestGemini) {
        btnTestGemini.addEventListener("click", async () => {
            const model = configGeminiModel ? configGeminiModel.value : "gemini-2.5-flash";
            const apiKey = configGeminiKey.value.trim();

            if (geminiTestStatus) {
                geminiTestStatus.style.display = "flex";
                if (geminiTestStatusIcon) {
                    geminiTestStatusIcon.className = "fa-solid fa-circle-notch fa-spin";
                    geminiTestStatusIcon.style.color = "var(--accent)";
                }
                if (geminiTestStatusText) {
                    geminiTestStatusText.style.color = "var(--text-muted)";
                    geminiTestStatusText.textContent = `Testuji spojení s modelem ${model}...`;
                }
            }
            btnTestGemini.disabled = true;

            try {
                const res = await fetch("/api/ai/test", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        model: model,
                        api_key: apiKey
                    })
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    if (geminiTestStatusIcon) {
                        geminiTestStatusIcon.className = "fa-solid fa-circle-check";
                        geminiTestStatusIcon.style.color = "#2ecc71";
                    }
                    if (geminiTestStatusText) {
                        geminiTestStatusText.style.color = "#2ecc71";
                        geminiTestStatusText.textContent = `Spojení úspěšné! Odezva: ${data.latency_ms} ms (${data.model})`;
                    }
                    showNotification(`Google AI (${data.model}) je aktivní a funkční (${data.latency_ms} ms).`, "success");
                } else {
                    if (geminiTestStatusIcon) {
                        geminiTestStatusIcon.className = "fa-solid fa-circle-xmark";
                        geminiTestStatusIcon.style.color = "#e74c3c";
                    }
                    if (geminiTestStatusText) {
                        geminiTestStatusText.style.color = "#e74c3c";
                        geminiTestStatusText.textContent = `${data.message || "Nepodařilo se připojit k modelu."}`;
                    }
                    showNotification(data.message || "Test spojení selhal.", "error");
                }
            } catch (err) {
                if (geminiTestStatusIcon) {
                    geminiTestStatusIcon.className = "fa-solid fa-circle-xmark";
                    geminiTestStatusIcon.style.color = "#e74c3c";
                }
                if (geminiTestStatusText) {
                    geminiTestStatusText.style.color = "#e74c3c";
                    geminiTestStatusText.textContent = `Chyba sítě: ${err.message}`;
                }
                showNotification("Chyba při komunikaci se serverem.", "error");
            } finally {
                btnTestGemini.disabled = false;
            }
        });
    }

    if (toggleTruenasKeyBtn && configTruenasApiKey) {
        toggleTruenasKeyBtn.addEventListener("click", () => {
            const type = configTruenasApiKey.getAttribute("type") === "password" ? "text" : "password";
            configTruenasApiKey.setAttribute("type", type);
            toggleTruenasKeyBtn.querySelector("i").className = type === "password" ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
        });
    }

    if (btnTriggerTruenasUpgrade) {
        btnTriggerTruenasUpgrade.addEventListener("click", async () => {
            btnTriggerTruenasUpgrade.disabled = true;
            btnTriggerTruenasUpgrade.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Odesílám požadavek do TrueNAS...';

            try {
                const res = await fetch("/api/version/truenas-upgrade", { method: "POST" });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    closeVersionModal();
                    showNotification(data.message, "success");

                    const restartOverlay = document.getElementById("restart-overlay");
                    const restartStatus = document.getElementById("restart-status");
                    if (restartOverlay) {
                        restartOverlay.style.display = "flex";
                        let seconds = 30;
                        const interval = setInterval(() => {
                            seconds--;
                            if (restartStatus) restartStatus.textContent = `Čekám na TrueNAS restart (cca ${seconds}s)...`;
                            if (seconds <= 0) {
                                clearInterval(interval);
                                window.location.reload();
                            }
                        }, 1000);
                    }
                } else {
                    showNotification(data.message || "Aktualizace přes TrueNAS selhala.", "error");
                }
            } catch (err) {
                showNotification("Chyba při volání aktualizace: " + err.message, "error");
            } finally {
                btnTriggerTruenasUpgrade.disabled = false;
                btnTriggerTruenasUpgrade.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Aktualizovat ihned na TrueNAS';
            }
        });
    }

    // Google Kalendář & iCal akce
    if (btnCopyCalendarUrl && calendarFeedUrl) {
        btnCopyCalendarUrl.addEventListener("click", async () => {
            const url = calendarFeedUrl.value;
            if (!url) {
                showNotification("Odkaz na kalendář není připraven.", "error");
                return;
            }
            try {
                await navigator.clipboard.writeText(url);
                showNotification("URL kalendáře zkopírována do schránky! Vložte ji do Google/Apple kalendáře.", "success");
            } catch (err) {
                calendarFeedUrl.select();
                document.execCommand("copy");
                showNotification("URL kalendáře zkopírována do schránky!", "success");
            }
        });
    }

    if (btnRegenCalendarToken) {
        btnRegenCalendarToken.addEventListener("click", async () => {
            if (!confirm("Opravdu vygenerovat nový token pro kalendář? Starý odkaz v Google Kalendáři přestane fungovat a budete muset zadat nový.")) {
                return;
            }
            try {
                const res = await fetch("/api/calendar/token/regenerate", { method: "POST" });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    showNotification("Bezpečnostní token kalendáře byl obnoven.", "success");
                    loadConfig();
                } else {
                    showNotification(data.message || "Nepodařilo se obnovit token.", "error");
                }
            } catch (err) {
                showNotification("Chyba při komunikaci se serverem: " + err.message, "error");
            }
        });
    }

    let screencastWs = null;

    // --- SCREENCAST ZOOM & PAN OVLÁDÁNÍ ---
    const updateZoomControlsUI = () => {
        const btnFit = document.getElementById("btn-zoom-fit");
        const btn100 = document.getElementById("btn-zoom-100");
        const badge = document.getElementById("zoom-level-badge");
        if (btnFit) btnFit.classList.toggle("active", currentScreencastZoom === "fit");
        if (btn100) btn100.classList.toggle("active", currentScreencastZoom === 1.0);
        if (badge) {
            badge.textContent = currentScreencastZoom === "fit" ? "Fit" : `${Math.round(currentScreencastZoom * 100)} %`;
        }
    };

    function fitCanvasToContainer() {
        const canvas = document.getElementById("screencast-canvas");
        if (!canvas || !canvas.width || !canvas.height) return;
        const parent = canvas.parentElement;
        if (!parent) return;

        if (currentScreencastZoom === "fit") {
            parent.style.overflow = "hidden";
            const pw = parent.clientWidth;
            const ph = parent.clientHeight;
            if (!pw || !ph) return;

            const imgAspect = canvas.width / canvas.height;
            const containerAspect = pw / ph;

            if (containerAspect > imgAspect) {
                canvas.style.height = `${ph}px`;
                canvas.style.width = `${Math.round(ph * imgAspect)}px`;
            } else {
                canvas.style.width = `${pw}px`;
                canvas.style.height = `${Math.round(pw / imgAspect)}px`;
            }
        } else {
            parent.style.overflow = "auto";
            const baseW = canvas.width || 1280;
            const baseH = canvas.height || 800;
            canvas.style.width = `${Math.round(baseW * currentScreencastZoom)}px`;
            canvas.style.height = `${Math.round(baseH * currentScreencastZoom)}px`;
        }
    }

    const setScreencastZoom = (newZoom) => {
        currentScreencastZoom = newZoom;
        updateZoomControlsUI();
        fitCanvasToContainer();
    };

    // Zoom Buttons
    const btnZoomFit = document.getElementById("btn-zoom-fit");
    if (btnZoomFit) {
        btnZoomFit.addEventListener("click", () => setScreencastZoom("fit"));
    }
    const btnZoom100 = document.getElementById("btn-zoom-100");
    if (btnZoom100) {
        btnZoom100.addEventListener("click", () => setScreencastZoom(1.0));
    }
    const btnZoomIn = document.getElementById("btn-zoom-in");
    if (btnZoomIn) {
        btnZoomIn.addEventListener("click", () => {
            if (currentScreencastZoom === "fit") {
                setScreencastZoom(1.0);
            } else {
                const nextZoom = Math.min(2.5, +(currentScreencastZoom + 0.25).toFixed(2));
                setScreencastZoom(nextZoom);
            }
        });
    }
    const btnZoomOut = document.getElementById("btn-zoom-out");
    if (btnZoomOut) {
        btnZoomOut.addEventListener("click", () => {
            if (currentScreencastZoom === "fit") {
                setScreencastZoom(0.75);
            } else if (currentScreencastZoom > 0.5) {
                const prevZoom = Math.max(0.5, +(currentScreencastZoom - 0.25).toFixed(2));
                setScreencastZoom(prevZoom);
            } else {
                setScreencastZoom("fit");
            }
        });
    }

    const initScreencast = () => {
        const canvas = document.getElementById("screencast-canvas");
        const placeholder = document.getElementById("screencast-placeholder");
        const toggleInteractive = document.getElementById("vnc-interactive-toggle");
        const modeLabel = document.getElementById("vnc-mode-label");
        
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        
        const isInteractive = toggleInteractive ? toggleInteractive.checked : false;
        if (modeLabel) {
            modeLabel.textContent = isInteractive ? "Režim: Plné ovládání" : "Režim: Pouze náhled";
            modeLabel.style.color = isInteractive ? "#4ade80" : "var(--text-muted)";
        }
        canvas.style.cursor = isInteractive ? "pointer" : "default";

        if (screencastWs && (screencastWs.readyState === WebSocket.OPEN || screencastWs.readyState === WebSocket.CONNECTING)) {
            return;
        }

        // Ujistit se, že Playwright worker na backendu běží
        fetch("/api/screencast/start", { method: "POST" }).catch(() => {});

        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${wsProtocol}//${window.location.host}/api/screencast/ws`;
        
        screencastWs = new WebSocket(wsUrl);
        screencastWs.binaryType = "arraybuffer";

        window.addEventListener("resize", fitCanvasToContainer);

        screencastWs.onmessage = (event) => {
            const blob = new Blob([event.data], { type: "image/jpeg" });
            const url = URL.createObjectURL(blob);
            const img = new Image();
            img.onload = () => {
                canvas.width = img.width;
                canvas.height = img.height;
                fitCanvasToContainer();
                ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(url);
                if (placeholder) placeholder.style.display = "none";
            };
            img.src = url;
        };

        screencastWs.onclose = () => {
            screencastWs = null;
            // Automatický reconnect při odpojení vlivem Cloudflare 100s idle timeoutu, pokud je tab stále aktivní
            setTimeout(() => {
                const activeTab = document.querySelector(".tab-content.active");
                if (activeTab && (activeTab.id === "tab-browser" || activeTab.getAttribute("data-tab") === "browser")) {
                    console.log("🔄 Reconnecting screencast WebSocket after idle timeout...");
                    initScreencast();
                }
            }, 1500);
        };
    };

    function switchToTab(tabName) {
        console.log("➡️ switchToTab called with:", tabName);
        const item = Array.from(navItems).find(nav => nav.getAttribute("data-tab") === tabName);
        if (!item) {
            console.log("⚠️ Tab item not found for:", tabName);
            return;
        }

        navItems.forEach(nav => nav.classList.remove("active"));
        tabContents.forEach(tab => tab.classList.remove("active"));

        item.classList.add("active");
        const tabId = `tab-${tabName}`;
        const tabEl = document.getElementById(tabId);
        if (tabEl) {
            tabEl.classList.add("active");
        } else {
            console.log("⚠️ Tab content element not found:", tabId);
        }

        if (tabName === "active-listings") {
            pageTitle.textContent = "Aktivní inzeráty";
        } else if (tabName === "unsold-listings") {
            pageTitle.textContent = "Věci k prodeji";
        } else if (tabName === "sold-listings") {
            pageTitle.textContent = "Prodané věci";
        } else if (tabName === "browser") {
            pageTitle.textContent = "Živý prohlížeč";
            initScreencast();
        } else if (tabName === "config") {
            pageTitle.textContent = "Nastavení aplikace";
        }
    }

    const canvasElem = document.getElementById("screencast-canvas");
    if (canvasElem) {
        const handleCanvasClick = (e) => {
            const toggleInteractive = document.getElementById("vnc-interactive-toggle");
            if (!toggleInteractive || !toggleInteractive.checked) return;

            const rect = canvasElem.getBoundingClientRect();
            if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;

            const canvasWidth = canvasElem.width || 1280;
            const canvasHeight = canvasElem.height || 800;

            const scaleX = canvasWidth / rect.width;
            const scaleY = canvasHeight / rect.height;

            const clickX = Math.round((e.clientX - rect.left) * scaleX);
            const clickY = Math.round((e.clientY - rect.top) * scaleY);

            console.log(`🖱️ Screencast Click: (${clickX}, ${clickY}) [Canvas DOM size: ${Math.round(rect.width)}x${Math.round(rect.height)}]`);

            // Vytvoříme vizuální klesající kroužek (ripple) na přesném místě kurzoru (fixed position)
            const ripple = document.createElement("div");
            ripple.style.position = "fixed";
            ripple.style.left = `${e.clientX - 12}px`;
            ripple.style.top = `${e.clientY - 12}px`;
            ripple.style.width = "24px";
            ripple.style.height = "24px";
            ripple.style.borderRadius = "50%";
            ripple.style.border = "2px solid #4ade80";
            ripple.style.background = "rgba(74, 222, 128, 0.4)";
            ripple.style.pointerEvents = "none";
            ripple.style.zIndex = "99999";
            ripple.style.transition = "transform 0.4s ease-out, opacity 0.4s ease-out";

            document.body.appendChild(ripple);
            requestAnimationFrame(() => {
                ripple.style.transform = "scale(2.5)";
                ripple.style.opacity = "0";
            });
            setTimeout(() => ripple.remove(), 400);

            fetch("/api/screencast/input", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "click", x: clickX, y: clickY })
            });

            const hiddenInput = document.getElementById("screencast-hidden-input");
            if (hiddenInput) {
                hiddenInput.focus();
            }
        };

        canvasElem.addEventListener("mousedown", handleCanvasClick);

        // Plynulé skrolování kolečkem myši / touchpadem (Mouse Wheel Scroll)
        canvasElem.addEventListener("wheel", (e) => {
            const toggleInteractive = document.getElementById("vnc-interactive-toggle");
            const browserTab = document.getElementById("tab-browser");
            if (!toggleInteractive || !toggleInteractive.checked || !browserTab || !browserTab.classList.contains("active")) return;

            e.preventDefault();
            const rect = canvasElem.getBoundingClientRect();
            const canvasWidth = canvasElem.width || 1280;
            const canvasHeight = canvasElem.height || 800;
            const scaleX = canvasWidth / rect.width;
            const scaleY = canvasHeight / rect.height;
            const scrollX = Math.round((e.clientX - rect.left) * scaleX);
            const scrollY = Math.round((e.clientY - rect.top) * scaleY);

            fetch("/api/screencast/input", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "scroll",
                    x: scrollX,
                    y: scrollY,
                    deltaX: Math.round(e.deltaX),
                    deltaY: Math.round(e.deltaY)
                })
            });
        }, { passive: false });

        // Nativní zachytávání psaní přes skryté fokusační pole (Invisible Input Capture Layer)
        const hiddenInput = document.getElementById("screencast-hidden-input");
        if (hiddenInput) {
            hiddenInput.addEventListener("input", (e) => {
                const toggleInteractive = document.getElementById("vnc-interactive-toggle");
                const browserTab = document.getElementById("tab-browser");
                if (!toggleInteractive || !toggleInteractive.checked || !browserTab || !browserTab.classList.contains("active")) return;

                const textVal = hiddenInput.value;
                if (!textVal) return;
                hiddenInput.value = "";

                fetch("/api/screencast/input", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action: "type", text: textVal })
                });
            });

            hiddenInput.addEventListener("keydown", (e) => {
                const toggleInteractive = document.getElementById("vnc-interactive-toggle");
                const browserTab = document.getElementById("tab-browser");
                if (!toggleInteractive || !toggleInteractive.checked || !browserTab || !browserTab.classList.contains("active")) return;

                if (["Backspace", "Enter", "Tab", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Delete"].includes(e.key)) {
                    e.preventDefault();
                    fetch("/api/screencast/input", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ action: "key", key: e.key })
                    });
                }
            });
        }

        // Postranní posuvník a skrolovací tlačítka
        const btnScrollUp = document.getElementById("btn-scroll-up");
        const btnScrollDown = document.getElementById("btn-scroll-down");
        const scrollTrack = document.getElementById("screencast-scroll-track");
        const scrollThumb = document.getElementById("screencast-scroll-thumb");

        const sendScrollCmd = (dy) => {
            fetch("/api/screencast/input", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "scroll", x: 600, y: 400, deltaX: 0, deltaY: dy })
            });
        };

        if (btnScrollUp) {
            btnScrollUp.onclick = (e) => { e.preventDefault(); sendScrollCmd(-300); };
        }
        if (btnScrollDown) {
            btnScrollDown.onclick = (e) => { e.preventDefault(); sendScrollCmd(300); };
        }

        if (scrollTrack && scrollThumb) {
            let isDragging = false;
            let startY = 0;
            let startThumbTop = 0;

            scrollTrack.onclick = (e) => {
                if (e.target === scrollThumb) return;
                const rect = scrollTrack.getBoundingClientRect();
                const clickRatio = (e.clientY - rect.top) / rect.height;
                const targetTop = Math.max(0, Math.min(rect.height - scrollThumb.offsetHeight, clickRatio * rect.height));
                scrollThumb.style.top = `${targetTop}px`;
                sendScrollCmd((clickRatio - 0.5) * 600);
            };

            scrollThumb.onmousedown = (e) => {
                e.preventDefault();
                e.stopPropagation();
                isDragging = true;
                startY = e.clientY;
                startThumbTop = scrollThumb.offsetTop;
            };

            document.addEventListener("mousemove", (e) => {
                if (!isDragging || !scrollTrack || !scrollThumb) return;
                const rect = scrollTrack.getBoundingClientRect();
                const dy = e.clientY - startY;
                const maxTop = rect.height - scrollThumb.offsetHeight;
                const newTop = Math.max(0, Math.min(maxTop, startThumbTop + dy));
                scrollThumb.style.top = `${newTop}px`;
                sendScrollCmd(dy * 4);
                startY = e.clientY;
                startThumbTop = newTop;
            });

            document.addEventListener("mouseup", () => {
                isDragging = false;
            });
        }

        // Quick Text / SMS bar handler
        const sendQuickText = async () => {
            const input = document.getElementById("screencast-quick-text");
            const btn = document.getElementById("btn-send-quick-text");
            if (!input || !input.value) return;
            const textVal = input.value.trim();
            if (!textVal) return;

            // Očistíme SMS kód od mezer pokud jde o číslo
            const cleanCode = textVal.replace(/\s+/g, "");

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Odesílám...`;
            }
            input.disabled = true;

            showNotification("Odesílám kód do prohlížeče...", "info");

            try {
                // Nejprve zkusíme specializovaný endpoint pro Bazoš SMS kód
                const res = await fetch("/api/sms_code", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: cleanCode })
                });
                const data = await res.json();

                if (res.ok && data.submitted) {
                    showNotification(data.message || "SMS kód byl úspěšně zadán a odeslán do Bazoše.", "success");
                    input.value = "";
                    if (typeof refreshBrowserInspect === "function") refreshBrowserInspect(false);
                } else {
                    const warnMsg = (data && data.message) ? data.message : "SMS pole nenalezeno, zkouším odeslat do aktivního elementu...";
                    showNotification(warnMsg, "warning");
                    // Fallback: vepsat jako text přes CDP a stisknout Enter
                    await fetch("/api/screencast/input", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ action: "type", text: cleanCode })
                    });
                    await fetch("/api/screencast/input", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ action: "key", key: "Enter" })
                    });
                    showNotification("Text byl zapsán do prohlížeče a odeslán (Enter).", "info");
                    input.value = "";
                    if (typeof refreshBrowserInspect === "function") refreshBrowserInspect(false);
                }
            } catch (err) {
                console.error("Chyba při odesílání textu do prohlížeče:", err);
                showNotification("Chyba při komunikaci: " + err.message, "error");
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Odeslat text`;
                }
                if (input) {
                    input.disabled = false;
                    input.focus();
                }
            }
        };

        const btnQuickText = document.getElementById("btn-send-quick-text");
        if (btnQuickText) {
            btnQuickText.onclick = (e) => {
                e.preventDefault();
                sendQuickText();
            };
        }
        const inputQuickText = document.getElementById("screencast-quick-text");
        if (inputQuickText) {
            inputQuickText.onkeydown = (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    sendQuickText();
                }
            };
        }

        // Tlačítko "🎯 Zaměřit pole" – manuální fokus SMS/code inputu v prohlížeči
        const btnFocusInput = document.getElementById("btn-focus-input");
        if (btnFocusInput) {
            btnFocusInput.onclick = async (e) => {
                e.preventDefault();
                btnFocusInput.disabled = true;
                btnFocusInput.textContent = "⏳ Hledám...";
                try {
                    const res = await fetch("/api/browser/focus-input", { method: "POST" });
                    const data = await res.json();
                    if (data.focused) {
                        const fieldLabel = data.field || "pole";
                        showNotification(`✅ Zaměřeno: "${fieldLabel}" – nyní zadej SMS kód a stiskni Odeslat.`, "success");
                        const qi = document.getElementById("screencast-quick-text");
                        if (qi) qi.focus();
                        if (typeof refreshBrowserInspect === "function") refreshBrowserInspect(false);
                    } else {
                        showNotification(`⚠️ ${data.message || "Žádné pole nenalezeno. Zkus kliknout přímo do prohlížeče."}`, "warning");
                    }
                } catch (err) {
                    showNotification("Chyba při zaměřování pole: " + err.message, "error");
                } finally {
                    btnFocusInput.disabled = false;
                    btnFocusInput.textContent = "🎯 Zaměřit pole";
                }
            };
        }

        // ==========================================
        // ŽIVÁ DIAGNOSTIKA FORMULÁŘE A INTERAKTIVNÍ ČIPY POLÍ
        // ==========================================
        const browserStepBadge = document.getElementById("browser-step-badge");
        const browserDetectedFields = document.getElementById("browser-detected-fields");
        const modalBrowserInspect = document.getElementById("modal-browser-inspect");
        const btnInspectPage = document.getElementById("btn-inspect-page");
        const btnCloseInspect = document.getElementById("btn-close-inspect");
        const btnCloseInspectFooter = document.getElementById("btn-close-inspect-footer");
        const btnRefreshInspect = document.getElementById("btn-refresh-inspect");
        const inspectStepDesc = document.getElementById("inspect-step-desc");
        const inspectUrl = document.getElementById("inspect-url");
        const inspectAlertsContainer = document.getElementById("inspect-alerts-container");
        const inspectAlertsList = document.getElementById("inspect-alerts-list");
        const inspectFieldsTable = document.getElementById("inspect-fields-table");

        const updateBrowserStepBadge = (step, desc) => {
            if (!browserStepBadge) return;
            browserStepBadge.title = desc || "";
            if (step === "sms_new_ad") {
                browserStepBadge.textContent = "🔑 Krok 2: SMS Mobilní klíč (klic)";
                browserStepBadge.style.background = "rgba(16, 185, 129, 0.25)";
                browserStepBadge.style.color = "#6ee7b7";
                browserStepBadge.style.border = "1px solid rgba(16, 185, 129, 0.4)";
            } else if (step === "sms_login") {
                browserStepBadge.textContent = "🔑 SMS kód (kodd)";
                browserStepBadge.style.background = "rgba(16, 185, 129, 0.25)";
                browserStepBadge.style.color = "#6ee7b7";
                browserStepBadge.style.border = "1px solid rgba(16, 185, 129, 0.4)";
            } else if (step === "phone_new_ad") {
                browserStepBadge.textContent = "📱 Krok 1: Telefon (teloverit)";
                browserStepBadge.style.background = "rgba(59, 130, 246, 0.25)";
                browserStepBadge.style.color = "#93c5fd";
                browserStepBadge.style.border = "1px solid rgba(59, 130, 246, 0.4)";
            } else if (step === "ad_form") {
                browserStepBadge.textContent = "📝 Formulář inzerátu";
                browserStepBadge.style.background = "rgba(139, 92, 246, 0.25)";
                browserStepBadge.style.color = "#c4b5fd";
                browserStepBadge.style.border = "1px solid rgba(139, 92, 246, 0.4)";
            } else if (step === "login_form") {
                browserStepBadge.textContent = "👤 Přihlášení";
                browserStepBadge.style.background = "rgba(139, 92, 246, 0.25)";
                browserStepBadge.style.color = "#c4b5fd";
                browserStepBadge.style.border = "1px solid rgba(139, 92, 246, 0.4)";
            } else if (step === "gateway_502") {
                browserStepBadge.textContent = "⚠️ 502 Bad Gateway (Bazoš)";
                browserStepBadge.style.background = "rgba(245, 158, 11, 0.25)";
                browserStepBadge.style.color = "#fcd34d";
                browserStepBadge.style.border = "1px solid rgba(245, 158, 11, 0.4)";
            } else if (step === "navigating" || step === "busy") {
                browserStepBadge.textContent = "⏳ Načítám...";
                browserStepBadge.style.background = "rgba(59, 130, 246, 0.25)";
                browserStepBadge.style.color = "#93c5fd";
                browserStepBadge.style.border = "1px solid rgba(59, 130, 246, 0.4)";
            } else if (step === "closed") {
                browserStepBadge.textContent = "Prohlížeč neběží";
                browserStepBadge.style.background = "rgba(255, 255, 255, 0.05)";
                browserStepBadge.style.color = "var(--text-muted)";
                browserStepBadge.style.border = "none";
            } else {
                browserStepBadge.textContent = "🌐 Bazoš aktivní";
                browserStepBadge.style.background = "rgba(255, 255, 255, 0.1)";
                browserStepBadge.style.color = "#e2e8f0";
                browserStepBadge.style.border = "none";
            }
        };

        const fillSpecificField = async (fieldName, textVal = "", submit = false) => {
            try {
                const res = await fetch("/api/browser/fill-field", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ field_name: fieldName, value: textVal, submit: submit })
                });
                const data = await res.json();
                if (res.ok && data.status === "ok") {
                    showNotification(data.message, "success");
                    const qi = document.getElementById("screencast-quick-text");
                    if (qi) {
                        if (textVal) qi.value = "";
                        qi.focus();
                    }
                    refreshBrowserInspect(false);
                } else {
                    showNotification(data.message || `Chyba při manipulaci s polem ${fieldName}`, "error");
                }
            } catch (err) {
                showNotification(`Chyba: ${err.message}`, "error");
            }
        };

        const refreshBrowserInspect = async (openModal = false) => {
            if (openModal && btnRefreshInspect) {
                btnRefreshInspect.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Obnovuji...`;
            }
            try {
                const res = await fetch("/api/browser/inspect");
                const data = await res.json();

                if (!res.ok || data.status === "closed") {
                    updateBrowserStepBadge("closed", "Prohlížeč není spuštěn.");
                    if (browserDetectedFields) browserDetectedFields.innerHTML = "";
                    if (openModal && inspectStepDesc) inspectStepDesc.textContent = "Prohlížeč není spuštěn.";
                    return;
                }

                updateBrowserStepBadge(data.detected_step, data.step_description);

                // Dynamická reakce na 502 Bad Gateway po odeslání inzerátu
                if (data.is_gateway_error || data.detected_step === "gateway_502") {
                    if (browserReviewBanner && browserReviewBanner.style.display !== "none") {
                        browserReviewBanner.style.background = "rgba(245, 158, 11, 0.2)";
                        browserReviewBanner.style.borderColor = "rgba(245, 158, 11, 0.6)";
                        const bannerIcon = browserReviewBanner.querySelector(".fa-circle-check, .fa-triangle-exclamation");
                        if (bannerIcon) {
                            bannerIcon.className = "fa-solid fa-triangle-exclamation";
                            bannerIcon.style.color = "#f59e0b";
                        }
                        const textContainer = browserReviewBanner.querySelector("div > div");
                        if (textContainer) {
                            textContainer.innerHTML = `
                                <div style="font-weight: 700; font-size: 0.95rem; color: #fde68a;">Bazoš vrátil 502 Bad Gateway (častý timeout při ukládání fotek)</div>
                                <div style="font-size: 0.82rem; color: #fef3c7;">Inzerát byl v databázi Bazoše pravděpodobně úspěšně vytvořen! Klikni na <strong>Potvrdit odeslání</strong> pro automatické dohledání a uložení:</div>
                            `;
                        }
                        const confirmBtn = document.getElementById("btn-browser-confirm-post");
                        if (confirmBtn) {
                            confirmBtn.style.background = "#f59e0b";
                            confirmBtn.style.borderColor = "#d97706";
                            confirmBtn.style.boxShadow = "0 0 16px rgba(245, 158, 11, 0.6)";
                            confirmBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Dohledat a potvrdit`;
                        }
                    }
                }

                // Vykreslíme rychlé čipy polí pod screencastem
                if (browserDetectedFields) {
                    browserDetectedFields.innerHTML = "";
                    const visibleInputs = (data.inputs || []).filter(i => i.visible && i.type !== "hidden" && i.type !== "submit");
                    if (visibleInputs.length === 0) {
                        browserDetectedFields.innerHTML = `<span style="color: var(--text-muted); font-size: 0.75rem;">Žádná viditelná pole</span>`;
                    } else {
                        visibleInputs.slice(0, 5).forEach(inp => {
                            const name = inp.name || inp.id || "pole";
                            const isKey = name === "klic" || name === "kodd";
                            const isPhone = name === "teloverit" || name === "telefoni" || name === "telefon";
                            const icon = isKey ? "🔑" : (isPhone ? "📱" : "🎯");
                            const label = isKey ? `${icon} ${name} (SMS kód)` : (isPhone ? `${icon} ${name}` : `${icon} ${name}`);

                            const chip = document.createElement("button");
                            chip.type = "button";
                            chip.className = "btn btn-secondary";
                            chip.style.cssText = "padding: 0.2rem 0.55rem; font-size: 0.75rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.3rem; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; white-space: nowrap;";
                            if (isKey) {
                                chip.style.background = "rgba(16, 185, 129, 0.2)";
                                chip.style.borderColor = "rgba(16, 185, 129, 0.5)";
                                chip.style.color = "#a7f3d0";
                            }
                            chip.innerHTML = `${label}${inp.value ? ` <span style="opacity: 0.75; font-size: 0.7rem;">(${inp.value})</span>` : ""}`;
                            chip.title = `Kliknutím zaměříte pole '${name}'. Pokud je v řádku vepsán kód, okamžitě se do něj vloží.`;

                            chip.onclick = (e) => {
                                e.preventDefault();
                                const qi = document.getElementById("screencast-quick-text");
                                const textVal = qi ? qi.value.trim() : "";
                                fillSpecificField(name, textVal, false);
                            };
                            browserDetectedFields.appendChild(chip);
                        });
                    }
                }

                // Pokud je vyžádán modal, naplníme jej daty
                if (openModal || (modalBrowserInspect && modalBrowserInspect.style.display === "flex")) {
                    if (inspectStepDesc) inspectStepDesc.textContent = data.step_description || "Běžná stránka";
                    if (inspectUrl) inspectUrl.textContent = data.url || "-";

                    // Alerty / Upozornění
                    if (inspectAlertsContainer && inspectAlertsList) {
                        if (data.alerts && data.alerts.length > 0) {
                            inspectAlertsList.innerHTML = data.alerts.map(a => `<li>${a}</li>`).join("");
                            inspectAlertsContainer.style.display = "block";
                        } else {
                            inspectAlertsContainer.style.display = "none";
                        }
                    }

                    // Tabulka polí
                    if (inspectFieldsTable) {
                        if (!data.inputs || data.inputs.length === 0) {
                            inspectFieldsTable.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 1rem; color: var(--text-muted);">Na stránce nebyla nalezena žádná pole formuláře.</td></tr>`;
                        } else {
                            inspectFieldsTable.innerHTML = data.inputs.map(inp => {
                                const name = inp.name || inp.id || "(bezejmenné)";
                                const safeName = escapeHtml(name);
                                const safeVal = inp.value ? escapeHtml(inp.value) : '<span style="color: rgba(255,255,255,0.2);">&lt;prázdné&gt;</span>';
                                const encName = encodeURIComponent(name);
                                const isSMS = name === "klic" || name === "kodd";
                                const isPhone = name === "teloverit" || name === "telefoni" || name === "telefon";
                                const focusBadge = inp.focused ? `<span style="background: rgba(245, 158, 11, 0.2); color: #fcd34d; font-size: 0.7rem; padding: 1px 4px; border-radius: 4px; margin-left: 4px;">Fokus</span>` : "";
                                const visBadge = inp.visible ? `<span style="color: #10b981;">Viditelné</span>` : `<span style="color: var(--text-muted);">Skryté</span>`;
                                const rowStyle = isSMS ? "background: rgba(16, 185, 129, 0.08);" : (inp.focused ? "background: rgba(245, 158, 11, 0.05);" : "");

                                return `
                                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); ${rowStyle}">
                                        <td style="padding: 0.45rem 0.5rem; font-family: monospace; font-weight: ${isSMS ? 'bold' : 'normal'}; color: ${isSMS ? '#a7f3d0' : '#fff'};">
                                            ${isSMS ? '🔑 ' : (isPhone ? '📱 ' : '')}${safeName} ${focusBadge}
                                        </td>
                                        <td style="padding: 0.45rem 0.5rem; font-size: 0.8rem; color: var(--text-muted);">
                                            ${inp.type || inp.tag} · ${visBadge}
                                        </td>
                                        <td style="padding: 0.45rem 0.5rem; font-family: monospace; font-size: 0.8rem; color: #cbd5e1;">
                                            ${safeVal}
                                        </td>
                                        <td style="padding: 0.45rem 0.5rem; text-align: right;">
                                            <button class="btn btn-secondary btn-sm" onclick="window._fillInspectField(decodeURIComponent('${encName}'), false)" style="padding: 2px 7px; font-size: 0.75rem; border-radius: 4px;" title="Zaměřit toto pole v prohlížeči">
                                                🎯 Zaměřit
                                            </button>
                                            <button class="btn btn-primary btn-sm" onclick="window._fillInspectField(decodeURIComponent('${encName}'), true)" style="padding: 2px 7px; font-size: 0.75rem; border-radius: 4px; margin-left: 4px;" title="Vepsat text z horního řádku a odeslat">
                                                ✏️ Vložit a odeslat
                                            </button>
                                        </td>
                                    </tr>
                                `;
                            }).join("");
                        }
                    }

                    if (openModal && modalBrowserInspect) {
                        modalBrowserInspect.style.display = "flex";
                    }
                }
            } catch (err) {
                console.error("Chyba při diagnostice prohlížeče:", err);
            } finally {
                if (btnRefreshInspect) {
                    btnRefreshInspect.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Obnovit`;
                }
            }
        };

        // Globální pomocník pro tlačítka v tabulce modalu
        window._fillInspectField = (fieldName, submit) => {
            const qi = document.getElementById("screencast-quick-text");
            let textVal = qi ? qi.value.trim() : "";
            if (submit && !textVal) {
                textVal = prompt(`Zadej text nebo SMS kód pro pole '${fieldName}':`) || "";
                if (!textVal) return;
            }
            fillSpecificField(fieldName, textVal, submit);
        };

        if (btnInspectPage) {
            btnInspectPage.addEventListener("click", () => {
                refreshBrowserInspect(true);
            });
        }
        if (btnRefreshInspect) {
            btnRefreshInspect.addEventListener("click", () => {
                refreshBrowserInspect(true);
            });
        }
        if (btnCloseInspect) {
            btnCloseInspect.addEventListener("click", () => {
                if (modalBrowserInspect) modalBrowserInspect.style.display = "none";
            });
        }
        if (btnCloseInspectFooter) {
            btnCloseInspectFooter.addEventListener("click", () => {
                if (modalBrowserInspect) modalBrowserInspect.style.display = "none";
            });
        }
        if (modalBrowserInspect) {
            modalBrowserInspect.addEventListener("click", (e) => {
                if (e.target === modalBrowserInspect) {
                    modalBrowserInspect.style.display = "none";
                }
            });
        }

        // Periodické obnovování detekce stavu formuláře každých 5s (pokud je okno viditelné)
        setInterval(() => {
            if (document.visibilityState === "visible") {
                const screencastContainer = document.getElementById("screencast-container");
                if (screencastContainer && screencastContainer.offsetParent !== null) {
                    refreshBrowserInspect(false);
                }
            }
        }, 5000);

        // Počáteční načtení diagnostiky
        setTimeout(() => refreshBrowserInspect(false), 2000);
    }

    const btnReloadVnc = document.getElementById("btn-reload-vnc");
    if (btnReloadVnc) {
        btnReloadVnc.addEventListener("click", () => {
            if (screencastWs) screencastWs.close();
            fetch("/api/screencast/start", { method: "POST" }).finally(() => {
                initScreencast();
            });
        });
    }

    const toggleInteractive = document.getElementById("vnc-interactive-toggle");
    if (toggleInteractive) {
        toggleInteractive.addEventListener("change", () => {
            initScreencast();
        });
    }

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabName = item.getAttribute("data-tab");
            switchToTab(tabName);
        });
    });

    // Zavírání modalů na křížek nebo storno tlačítko
    document.querySelectorAll(".btn-close-modal").forEach(btn => {
        btn.addEventListener("click", () => {
            addListingModal.classList.remove("active");
            editListingModal.classList.remove("active");
            currentAd = null;
        });
    });

    // Systémová notifikace (luxusní toast)
    const showNotification = (message, type = "info") => {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            Object.assign(container.style, {
                position: "fixed",
                top: "1.5rem",
                right: "1.5rem",
                zIndex: "99999",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
                pointerEvents: "none",
                maxWidth: "420px"
            });
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast-notification ${type}`;
        
        let icon = "fa-info-circle";
        if (type === "success") icon = "fa-circle-check";
        if (type === "error") icon = "fa-triangle-exclamation";
        if (type === "info") icon = "fa-circle-info";

        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;

        Object.assign(toast.style, {
            background: "rgba(15, 23, 42, 0.95)",
            border: `1px solid ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'}`,
            boxShadow: "0 10px 25px rgba(0, 0, 0, 0.5)",
            backdropFilter: "blur(10px)",
            color: "#fff",
            padding: "0.85rem 1.25rem",
            borderRadius: "10px",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            opacity: "0",
            transform: "translateY(-15px)",
            transition: "all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)",
            fontSize: "0.88rem",
            fontWeight: "500"
        });

        container.appendChild(toast);

        // Animace naběhnutí
        setTimeout(() => {
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
        }, 10);

        // Animace odstranění
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-15px)";
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 4000);
    };

    // ==========================================================
    // Price Advisor & Auto-Repost Client Integration
    // ==========================================================

    // --- In-memory cache pro výsledky cenové analýzy (key = ad.id) ---
    const priceCache = {};

    // Aktualizuje vizuál price chipu na dlaždicích
    const updatePriceChip = (chipEl, data) => {
        if (!chipEl) return;
        const stats = data.statistics || {};
        const marketMedian = stats.median || stats.avg || 0;
        const myPrice = parseInt(chipEl.dataset.adPrice) || 0;

        chipEl.removeAttribute("data-loaded"); // mark done
        chipEl.classList.remove("chip-loading", "chip-bargain", "chip-fair", "chip-overpriced", "chip-no-data");

        let icon = "📊";
        let chipClass = "chip-fair";
        let diffText = "";

        if (data.status === "NO_COMPETITION" || !marketMedian) {
            chipEl.classList.add("chip-no-data");
            chipEl.querySelector(".chip-text").textContent = "📊 Bez srovnání na trhu";
            chipEl.querySelector("i")?.remove();
            chipEl.style.cursor = "default";
            chipEl.style.pointerEvents = "none";
            return;
        }

        const pct = myPrice && marketMedian ? Math.round(((myPrice - marketMedian) / marketMedian) * 100) : 0;

        if (data.status === "BARGAIN") {
            chipClass = "chip-bargain";
            icon = "✅";
            diffText = pct < 0 ? ` · Levnější o ${Math.abs(pct)} %` : ` · Výhodná cena`;
        } else if (data.status === "OVERPRICED") {
            chipClass = "chip-overpriced";
            icon = "⬆";
            diffText = pct > 0 ? ` · Dražší o ${pct} %` : ` · Nad trhem`;
        } else {
            chipClass = "chip-fair";
            icon = "≈";
            diffText = ` · Odpovídá trhu`;
        }

        chipEl.classList.add(chipClass);
        const iEl = chipEl.querySelector("i");
        if (iEl) iEl.remove();
        chipEl.querySelector(".chip-text").textContent =
            `${icon} Trh: ~${marketMedian.toLocaleString("cs-CZ")} Kč${diffText}`;
    };

    // Načte cenová data pro jeden inzerát a updatuje všechny chipy se stejným ad.id
    const loadPriceChip = async (adId, adPrice) => {
        // Pokud máme cache, hned updatujeme
        if (priceCache[adId]) {
            document.querySelectorAll(`.price-chip[data-ad-id="${adId}"]`).forEach(chip => {
                updatePriceChip(chip, priceCache[adId]);
            });
            return;
        }

        try {
            const res = await fetch(`/api/advisor/price/${adId}`);
            if (!res.ok) throw new Error("HTTP " + res.status);
            const json = await res.json();
            if (json.status !== "success") throw new Error(json.message || "err");

            priceCache[adId] = json.data;
            document.querySelectorAll(`.price-chip[data-ad-id="${adId}"]`).forEach(chip => {
                updatePriceChip(chip, json.data);
            });
        } catch {
            // Neupravuj chip – nech ho skrytý nebo přepni na no-data
            document.querySelectorAll(`.price-chip[data-ad-id="${adId}"][data-loaded="false"]`).forEach(chip => {
                chip.classList.remove("chip-loading");
                chip.classList.add("chip-no-data");
                chip.querySelector(".chip-text").textContent = "📊 Nelze načíst";
                chip.querySelector("i")?.remove();
                chip.style.pointerEvents = "none";
            });
        }
    };

    // IntersectionObserver – spustí loadPriceChip jakmile chip vstoupí do viewportu
    const initPriceChipObserver = () => {
        const inFlight = new Set(); // zabrání duplicate volání
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const chip = entry.target;
                if (chip.dataset.loaded === "false" && chip.dataset.adId) {
                    const adId = chip.dataset.adId;
                    if (inFlight.has(adId)) return;
                    inFlight.add(adId);
                    chip.dataset.loaded = "pending";
                    loadPriceChip(adId, parseInt(chip.dataset.adPrice) || 0)
                        .finally(() => inFlight.delete(adId));
                    observer.unobserve(chip); // stačí jednou
                }
            });
        }, { rootMargin: "100px", threshold: 0.1 });

        document.querySelectorAll(".price-chip[data-loaded='false']").forEach(chip => {
            observer.observe(chip);
        });
        return observer;
    };

    // Kliknutí na price chip → otevři Poradce (z cache pokud možno)
    document.addEventListener("click", (e) => {
        const chip = e.target.closest(".price-chip");
        if (!chip || chip.classList.contains("chip-loading") || chip.classList.contains("chip-no-data")) return;
        const adId = chip.dataset.adId;
        if (!adId) return;
        const ad = activeListings.find(item => String(item.id) === String(adId));
        if (!ad) return;
        e.stopPropagation();
        openAdvisor(ad);
    });

    const advisorModal = document.getElementById("price-advisor-modal");
    const closeAdvisorBtn = document.getElementById("btn-close-advisor-modal");
    const closeAdvisorBtnFooter = document.getElementById("btn-close-advisor-modal-footer");
    const applyAdvisorPriceBtn = document.getElementById("btn-apply-advisor-price");

    let activeAdvisorListingId = null;

    // Odchytávání kliknutí na karty (Cenový poradce)
    document.addEventListener("click", async (e) => {
        const btn = e.target.closest(".btn-advisor");
        if (!btn) return;
        
        const card = btn.closest(".listing-card");
        if (!card) return;
        
        // Získáme inzerát z načteného pole
        // (musíme prohledat activeListings podle indexu nebo názvu, případně ID)
        // Karty ukládáme v renderListings, můžeme najít inzerát podle titulu
        const titleEl = card.querySelector(".listing-title");
        if (!titleEl) return;
        const title = titleEl.innerText.trim();
        
        const ad = activeListings.find(item => item.title === title);
        if (!ad) return;

        activeAdvisorListingId = ad.id;
        openAdvisor(ad);
    });

    const _renderAdvisorData = (data) => {
        const stats = data.statistics;
        const sourcesListEl = document.getElementById("advisor-sources-list");
        const statusAlert = document.getElementById("advisor-status-alert");

        if (sourcesListEl && data.sources_checked && data.sources_checked.length) {
            sourcesListEl.innerText = `Zdroje: ${data.sources_checked.join(", ")}`;
        }

        statusAlert.className = "alert";
        if (data.status === "OVERPRICED") {
            statusAlert.style.background = "rgba(220, 53, 69, 0.15)";
            statusAlert.style.color = "#ea868f";
            statusAlert.style.border = "1px solid rgba(220, 53, 69, 0.3)";
        } else if (data.status === "BARGAIN") {
            statusAlert.style.background = "rgba(25, 135, 84, 0.15)";
            statusAlert.style.color = "#75b798";
            statusAlert.style.border = "1px solid rgba(25, 135, 84, 0.3)";
        } else {
            statusAlert.style.background = "rgba(131, 92, 223, 0.15)";
            statusAlert.style.color = "var(--accent)";
            statusAlert.style.border = "1px solid rgba(131, 92, 223, 0.3)";
        }

        const fullMsg = data.reasoning ? `${data.message} ${data.reasoning}` : data.message;
        document.getElementById("advisor-message").innerText = fullMsg;

        if (data.status === "NO_COMPETITION") {
            document.getElementById("advisor-competitors-container").innerHTML = '<div class="loading-state" style="padding: 1rem;"><i class="fa-solid fa-triangle-exclamation"></i> Nebyla nalezena žádná konkurence.</div>';
            document.getElementById("advisor-opt-quick").innerText = "- Kč";
            document.getElementById("advisor-opt-fair").innerText = "- Kč";
            document.getElementById("advisor-opt-premium").innerText = "- Kč";
            return;
        }

        document.getElementById("advisor-opt-quick").innerText = `${stats.suggested_quick_sale.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-opt-fair").innerText = `${stats.suggested_fair.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-opt-premium").innerText = `${stats.suggested_premium.toLocaleString("cs-CZ")} Kč`;

        const selectBtns = document.querySelectorAll(".btn-select-advisor-price");
        selectBtns[0].setAttribute("data-price", stats.suggested_quick_sale);
        selectBtns[1].setAttribute("data-price", stats.suggested_fair);
        selectBtns[2].setAttribute("data-price", stats.suggested_premium);

        document.getElementById("advisor-selected-price").value = stats.suggested_fair;

        document.getElementById("advisor-range-min").innerText = `${stats.min.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-range-median").innerText = `${stats.median.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-range-avg").innerText = `${stats.avg.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-range-max").innerText = `${stats.max.toLocaleString("cs-CZ")} Kč`;

        const competitorsContainer = document.getElementById("advisor-competitors-container");
        competitorsContainer.innerHTML = "";

        data.listings.forEach(item => {
            const itemEl = document.createElement("div");
            itemEl.style.display = "flex";
            itemEl.style.justifyContent = "space-between";
            itemEl.style.alignItems = "center";
            itemEl.style.background = "rgba(255, 255, 255, 0.02)";
            itemEl.style.border = "1px solid var(--border)";
            itemEl.style.padding = "0.6rem 0.85rem";
            itemEl.style.borderRadius = "6px";
            itemEl.style.fontSize = "0.85rem";

            const topText = item.is_top ? '<span style="color: #ffc107; font-weight: bold; margin-left: 0.25rem;">[TOP]</span>' : '';

            const sourceName = item.source || "Bazoš.cz";
            let badgeStyle = "background: rgba(255, 152, 0, 0.15); color: #ff9800; border: 1px solid rgba(255, 152, 0, 0.3);";
            if (sourceName.toLowerCase().includes("sbazar")) {
                badgeStyle = "background: rgba(220, 53, 69, 0.15); color: #ea868f; border: 1px solid rgba(220, 53, 69, 0.3);";
            } else if (sourceName.toLowerCase().includes("web")) {
                badgeStyle = "background: rgba(13, 110, 253, 0.15); color: #6ea8fe; border: 1px solid rgba(13, 110, 253, 0.3);";
            } else if (sourceName.toLowerCase().includes("gemini")) {
                badgeStyle = "background: rgba(131, 92, 223, 0.15); color: #c29ffa; border: 1px solid rgba(131, 92, 223, 0.3);";
            }
            const sourceBadge = `<span style="display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-right: 0.4rem; ${badgeStyle}">${escapeHtml(sourceName)}</span>`;

            const extraMeta = [];
            if (item.location) extraMeta.push(escapeHtml(item.location));
            if (item.views) extraMeta.push(`👀 ${item.views} zhlédnutí`);
            if (item.date) extraMeta.push(`📅 ${item.date}`);

            itemEl.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 0.15rem; max-width: 75%;">
                    <div style="display: flex; align-items: center; gap: 0.25rem; overflow: hidden;">
                        ${sourceBadge}
                        <a href="${item.link}" target="_blank" style="color: #a5d6ff; text-decoration: none; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${escapeHtml(item.title)}</a>
                    </div>
                    <span style="font-size: 0.75rem; color: var(--text-muted);">${extraMeta.join(" | ")}</span>
                </div>
                <strong style="color: #fff; white-space: nowrap; margin-left: 0.5rem;">${item.price_text || (item.price ? `${item.price.toLocaleString("cs-CZ")} Kč` : "Cena neuvedena")}${topText}</strong>
            `;
            competitorsContainer.appendChild(itemEl);
        });
    };

    const openAdvisor = async (ad) => {
        activeAdvisorListingId = ad.id;

        // Základní info do modalu
        document.getElementById("advisor-listing-title").innerText = ad.title;
        document.getElementById("advisor-current-price").innerText = `${ad.price.toLocaleString("cs-CZ")} Kč`;
        document.getElementById("advisor-selected-price").value = ad.price;
        advisorModal.classList.add("active");

        // Pokud máme cache z chipu → render okamžitě, žádný API call
        if (priceCache[ad.id]) {
            _renderAdvisorData(priceCache[ad.id]);
            return;
        }

        // Jinak loading stav a API call
        const sourcesListEl = document.getElementById("advisor-sources-list");
        if (sourcesListEl) sourcesListEl.innerText = "";
        const statusAlert = document.getElementById("advisor-status-alert");
        statusAlert.className = "alert alert-warning";
        statusAlert.style.background = "rgba(255, 193, 7, 0.1)";
        statusAlert.style.color = "#ffc107";
        statusAlert.style.border = "";
        document.getElementById("advisor-message").innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzuji konkurenční nabídky (Bazoš, Sbazar, Web)...';
        document.getElementById("advisor-opt-quick").innerText = "- Kč";
        document.getElementById("advisor-opt-fair").innerText = "- Kč";
        document.getElementById("advisor-opt-premium").innerText = "- Kč";
        document.getElementById("advisor-range-min").innerText = "- Kč";
        document.getElementById("advisor-range-median").innerText = "- Kč";
        document.getElementById("advisor-range-avg").innerText = "- Kč";
        document.getElementById("advisor-range-max").innerText = "- Kč";
        document.getElementById("advisor-competitors-container").innerHTML = '<div class="loading-state" style="padding: 1.5rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Hledám inzeráty na portálech...</div>';

        try {
            const res = await fetch(`/api/advisor/price/${ad.id}`);
            const json = await res.json();
            if (json.status === "error") {
                showNotification(`Chyba analýzy: ${json.message}`, "error");
                closeAdvisor();
                return;
            }
            priceCache[ad.id] = json.data;
            _renderAdvisorData(json.data);
            // Aktualizujeme i chip pokud je viditelný
            document.querySelectorAll(`.price-chip[data-ad-id="${ad.id}"]`).forEach(chip => {
                updatePriceChip(chip, json.data);
            });
        } catch (e) {
            showNotification("Chyba při komunikaci s analyzátorem cen.", "error");
            closeAdvisor();
        }
    };

    // Zvolení doporučené ceny z tlačítek
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-select-advisor-price");
        if (!btn) return;
        const price = btn.getAttribute("data-price");
        if (price) {
            document.getElementById("advisor-selected-price").value = price;
            showNotification(`Zvolena cena ${parseInt(price).toLocaleString("cs-CZ")} Kč.`, "success");
        }
    });

    const closeAdvisor = () => {
        if (advisorModal) advisorModal.classList.remove("active");
        activeAdvisorListingId = null;
    };

    if (closeAdvisorBtn) closeAdvisorBtn.addEventListener("click", closeAdvisor);
    if (closeAdvisorBtnFooter) closeAdvisorBtnFooter.addEventListener("click", closeAdvisor);

    // Odeslání akce znovuvystavení se zlevněním
    if (applyAdvisorPriceBtn) {
        applyAdvisorPriceBtn.addEventListener("click", async () => {
            const newPriceInput = document.getElementById("advisor-selected-price");
            const newPrice = parseInt(newPriceInput.value);
            
            if (!activeAdvisorListingId || isNaN(newPrice) || newPrice <= 0) {
                showNotification("Zadejte platnou cenu.", "error");
                return;
            }

            closeAdvisor();
            
            // Zobrazíme running status bar
            const statusDesc = document.getElementById("playwright-status-desc");
            if (statusDesc) statusDesc.innerText = "Robot zlevňuje inzerát v SQLite a spouští znovuvystavení na Bazoši...";
            const statusContainer = document.getElementById("playwright-status");
            if (statusContainer) statusContainer.classList.add("active");

            try {
                const res = await fetch("/api/action/repost_with_new_price", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        listing_id: activeAdvisorListingId,
                        new_price: newPrice
                    })
                });
                const json = await res.json();
                
                if (json.status === "success") {
                    showNotification(json.message, "success");
                    // Refreshujeme aplikaci pro načtení nové ceny
                    loadApp();
                } else {
                    showNotification(json.message, "error");
                    if (statusContainer) statusContainer.classList.remove("active");
                }
            } catch (e) {
                showNotification("Nepodařilo se spustit znovuvystavení.", "error");
                if (statusContainer) statusContainer.classList.remove("active");
            }
        });
    }

    // Pomocná funkce pro bezpečné parsování HTML
    function escapeHtml(unsafe) {
        if (!unsafe) return "";
        return String(unsafe)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ==========================================
    // 8. AI PHOTO EDITOR (BOKEH & SPZ BLUR)
    // ==========================================
    let photoEditorState = {
        mode: null, // "wizard" | "existing"
        wizardIndex: null,
        file: null,
        photosDir: null,
        filename: null,
        originalDataUrl: null,
        currentDataUrl: null,
        bokehStrength: "none",
        isDrawingBox: false,
        boxToolActive: false,
        startCoord: null,
        boxBlurs: [] // array of [x1, y1, x2, y2]
    };

    const fileToDataUrl = (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    };

    const openPhotoEditorForWizard = async (index, file) => {
        try {
            const dataUrl = await fileToDataUrl(file);
            photoEditorState = {
                mode: "wizard",
                wizardIndex: index,
                file: file,
                photosDir: null,
                filename: file.name,
                originalDataUrl: dataUrl,
                currentDataUrl: dataUrl,
                bokehStrength: "none",
                isDrawingBox: false,
                boxToolActive: false,
                startCoord: null,
                boxBlurs: []
            };
            initPhotoEditorView();
        } catch (err) {
            showNotification("Nepodařilo se otevřít fotku v editoru.", "error");
        }
    };

    const openPhotoEditorForExisting = (photosDir, filename, dataUrl) => {
        photoEditorState = {
            mode: "existing",
            wizardIndex: null,
            file: null,
            photosDir: photosDir,
            filename: filename,
            originalDataUrl: dataUrl,
            currentDataUrl: dataUrl,
            bokehStrength: "none",
            isDrawingBox: false,
            boxToolActive: false,
            startCoord: null,
            boxBlurs: []
        };
        initPhotoEditorView();
    };

    const initPhotoEditorView = () => {
        if (!photoEditorModal || !photoEditorImg) return;
        photoEditorTargetName.textContent = photoEditorState.filename;
        photoEditorImg.src = photoEditorState.currentDataUrl;
        
        // Reset toolbar UI
        bokehButtons.forEach(btn => {
            if (btn.dataset.strength === photoEditorState.bokehStrength) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
        if (btnToggleBoxBlur) btnToggleBoxBlur.classList.remove("active");
        if (boxBlurHint) boxBlurHint.style.display = "none";
        if (photoEditorDragBox) photoEditorDragBox.style.display = "none";
        if (photoEditorSpinner) photoEditorSpinner.style.display = "none";
        photoEditorCanvasWrap.classList.remove("photo-editor-crosshair");

        photoEditorModal.style.display = "flex";
    };

    const closePhotoEditor = () => {
        if (photoEditorModal) photoEditorModal.style.display = "none";
        photoEditorState.isDrawingBox = false;
        photoEditorState.boxToolActive = false;
        if (photoEditorDragBox) photoEditorDragBox.style.display = "none";
        if (photoEditorSpinner) photoEditorSpinner.style.display = "none";
    };

    if (btnClosePhotoEditor) btnClosePhotoEditor.addEventListener("click", closePhotoEditor);
    if (btnCancelPhotoEditor) btnCancelPhotoEditor.addEventListener("click", closePhotoEditor);

    // Bokeh preset buttons
    bokehButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const strength = btn.dataset.strength;
            if (strength === photoEditorState.bokehStrength) return;
            photoEditorState.bokehStrength = strength;
            bokehButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            triggerPhotoEditPreview();
        });
    });

    // Box blur toggle tool
    if (btnToggleBoxBlur) {
        btnToggleBoxBlur.addEventListener("click", () => {
            photoEditorState.boxToolActive = !photoEditorState.boxToolActive;
            if (photoEditorState.boxToolActive) {
                btnToggleBoxBlur.classList.add("active");
                if (boxBlurHint) boxBlurHint.style.display = "inline";
                photoEditorCanvasWrap.classList.add("photo-editor-crosshair");
            } else {
                btnToggleBoxBlur.classList.remove("active");
                if (boxBlurHint) boxBlurHint.style.display = "none";
                photoEditorCanvasWrap.classList.remove("photo-editor-crosshair");
            }
        });
    }

    // Reset edits button
    if (btnResetPhotoEdits) {
        btnResetPhotoEdits.addEventListener("click", () => {
            photoEditorState.bokehStrength = "none";
            photoEditorState.boxBlurs = [];
            photoEditorState.currentDataUrl = photoEditorState.originalDataUrl;
            photoEditorImg.src = photoEditorState.originalDataUrl;
            bokehButtons.forEach(b => {
                b.classList.toggle("active", b.dataset.strength === "none");
            });
            if (btnToggleBoxBlur) btnToggleBoxBlur.classList.remove("active");
            photoEditorState.boxToolActive = false;
            if (boxBlurHint) boxBlurHint.style.display = "none";
            photoEditorCanvasWrap.classList.remove("photo-editor-crosshair");
            showNotification("Úpravy byly resetovány na originál.", "info");
        });
    }

    // Hold to compare with original
    if (btnComparePhoto) {
        const showOriginal = () => {
            photoEditorImg.src = photoEditorState.originalDataUrl;
        };
        const showEdited = () => {
            photoEditorImg.src = photoEditorState.currentDataUrl;
        };
        btnComparePhoto.addEventListener("mousedown", showOriginal);
        btnComparePhoto.addEventListener("mouseup", showEdited);
        btnComparePhoto.addEventListener("mouseleave", showEdited);
        btnComparePhoto.addEventListener("touchstart", showOriginal, { passive: true });
        btnComparePhoto.addEventListener("touchend", showEdited);
    }

    // Drawing drag-box for sensitive blur
    if (photoEditorCanvasWrap) {
        photoEditorCanvasWrap.addEventListener("mousedown", (e) => {
            if (!photoEditorState.boxToolActive) return;
            const rect = photoEditorCanvasWrap.getBoundingClientRect();
            const startX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
            const startY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

            photoEditorState.isDrawingBox = true;
            photoEditorState.startCoord = { x: startX, y: startY, rectWidth: rect.width, rectHeight: rect.height };

            photoEditorDragBox.style.left = `${startX}px`;
            photoEditorDragBox.style.top = `${startY}px`;
            photoEditorDragBox.style.width = "0px";
            photoEditorDragBox.style.height = "0px";
            photoEditorDragBox.style.display = "block";
        });

        window.addEventListener("mousemove", (e) => {
            if (!photoEditorState.isDrawingBox || !photoEditorState.startCoord) return;
            const rect = photoEditorCanvasWrap.getBoundingClientRect();
            const currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
            const currentY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

            const minX = Math.min(photoEditorState.startCoord.x, currentX);
            const maxX = Math.max(photoEditorState.startCoord.x, currentX);
            const minY = Math.min(photoEditorState.startCoord.y, currentY);
            const maxY = Math.max(photoEditorState.startCoord.y, currentY);

            photoEditorDragBox.style.left = `${minX}px`;
            photoEditorDragBox.style.top = `${minY}px`;
            photoEditorDragBox.style.width = `${maxX - minX}px`;
            photoEditorDragBox.style.height = `${maxY - minY}px`;
        });

        window.addEventListener("mouseup", (e) => {
            if (!photoEditorState.isDrawingBox || !photoEditorState.startCoord) return;
            photoEditorState.isDrawingBox = false;
            photoEditorDragBox.style.display = "none";

            const rect = photoEditorCanvasWrap.getBoundingClientRect();
            const currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
            const currentY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

            const minX = Math.min(photoEditorState.startCoord.x, currentX);
            const maxX = Math.max(photoEditorState.startCoord.x, currentX);
            const minY = Math.min(photoEditorState.startCoord.y, currentY);
            const maxY = Math.max(photoEditorState.startCoord.y, currentY);

            const boxWidth = maxX - minX;
            const boxHeight = maxY - minY;

            // Ignorovat nepatrné kliky (< 10px)
            if (boxWidth < 10 || boxHeight < 10) return;

            // Normalizované souřadnice 0.0 - 1.0
            const normBox = [
                parseFloat((minX / rect.width).toFixed(4)),
                parseFloat((minY / rect.height).toFixed(4)),
                parseFloat((maxX / rect.width).toFixed(4)),
                parseFloat((maxY / rect.height).toFixed(4))
            ];

            photoEditorState.boxBlurs.push(normBox);
            triggerPhotoEditPreview();
        });
    }

    const triggerPhotoEditPreview = async () => {
        if (!photoEditorSpinner) return;
        photoEditorSpinner.style.display = "flex";
        if (photoEditorSpinnerText) {
            photoEditorSpinnerText.textContent = photoEditorState.bokehStrength !== "none"
                ? "AI počítá Bokeh a rozostření..."
                : "Aplikuji rozostření zóny...";
        }

        try {
            const payload = {
                bokeh_strength: photoEditorState.bokehStrength,
                box_blurs: photoEditorState.boxBlurs
            };

            if (photoEditorState.mode === "wizard") {
                payload.image_b64 = photoEditorState.originalDataUrl;
            } else {
                payload.photos_dir = photoEditorState.photosDir;
                payload.filename = photoEditorState.filename;
            }

            const res = await fetch("/api/photos/edit/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (res.ok && data.status === "success") {
                photoEditorState.currentDataUrl = data.data_url;
                photoEditorImg.src = data.data_url;
            } else {
                showNotification(data.message || "Náhled úpravy se nezdařil.", "error");
            }
        } catch (err) {
            showNotification("Chyba při renderování náhledu: " + err.message, "error");
        } finally {
            photoEditorSpinner.style.display = "none";
        }
    };

    // Save Photo Edits
    if (btnSavePhotoEditor) {
        btnSavePhotoEditor.addEventListener("click", async () => {
            btnSavePhotoEditor.disabled = true;
            btnSavePhotoEditor.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Ukládám fotku...';

            try {
                if (photoEditorState.mode === "wizard") {
                    // Konvertujeme data_url zpět na File a nahradíme v wizardSelectedFiles
                    const res = await fetch(photoEditorState.currentDataUrl);
                    const blob = await res.blob();
                    const newFile = new File([blob], photoEditorState.filename, {
                        type: "image/jpeg",
                        lastModified: Date.now()
                    });
                    wizardSelectedFiles[photoEditorState.wizardIndex] = newFile;
                    renderWizardPhotoPreviews();
                    closePhotoEditor();
                    showNotification("Fotka v průvodci byla upravena.", "success");
                } else {
                    // Uložíme přímo na disk do složky inzerátu
                    const payload = {
                        photos_dir: photoEditorState.photosDir,
                        filename: photoEditorState.filename,
                        bokeh_strength: photoEditorState.bokehStrength,
                        box_blurs: photoEditorState.boxBlurs
                    };
                    const res = await fetch("/api/photos/edit/save", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if (res.ok && data.status === "success") {
                        closePhotoEditor();
                        showNotification("Úprava fotky byla uložena na disk!", "success");
                        loadPhotoGallery(photoEditorState.photosDir);
                    } else {
                        showNotification(data.message || "Uložení fotky selhalo.", "error");
                    }
                }
            } catch (err) {
                showNotification("Chyba při ukládání fotky: " + err.message, "error");
            } finally {
                btnSavePhotoEditor.disabled = false;
                btnSavePhotoEditor.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Uložit úpravu fotky';
            }
        });
    }

    // --- Start up ---
    loadApp();
});
