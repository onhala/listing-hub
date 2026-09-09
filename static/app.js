/**
 * Bazoš Automat & AI Editor - Client Logic (app.js)
 * Brand: TERMS a.s. / Roboton Custom UI Engine
 */

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
    const configPassword = document.getElementById("config-password");
    const configGeminiModel = document.getElementById("config-gemini-model");
    const configGeminiKey = document.getElementById("config-gemini-key");
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
        const appVer = data.app_version || "3.6.0";
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
                
                const appVer = data.app_version || "3.6.0";
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
                configPassword.value = config.default_ad_password_b64 ? atob(config.default_ad_password_b64) : "";
                
                // Auto refresh
                configAutoRefresh.checked = config.auto_refresh_enabled || false;
                configRefreshInterval.value = config.auto_refresh_interval || "720";
                
                // Google AI (Gemini)
                if (configGeminiModel) {
                    configGeminiModel.value = config.gemini_model || "gemini-2.5-flash";
                }
                if (config.gemini_api_key) {
                    configGeminiKey.placeholder = "••••••••••••••••••••••••••••••••";
                } else {
                    configGeminiKey.placeholder = "AIza... (ponech prázdné pro beze změny)";
                }

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
    };

    // ==========================================
    // 2. RENDEROVÁNÍ KARET INZERÁTŮ
    // ==========================================

    const renderListings = () => {
        // Filtrování aktivních a neaktivních (expirovaných/draftů)
        const liveListings = activeListings.filter(ad => ad.status === "Aktivní");
        const unsoldListings = activeListings.filter(ad => ad.status !== "Aktivní");

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
        if (soldListings.length === 0) {
            soldListingsContainer.innerHTML = `<div class="loading-state"><i class="fa-solid fa-box"></i> Žádné prodané věci.</div>`;
        } else {
            soldListings.forEach(ad => {
                const card = createAdCard(ad, true);
                soldListingsContainer.appendChild(card);
            });
        }
    };

    const createAdCard = (ad, isSold) => {
        const card = document.createElement("div");
        card.className = "listing-card";
        
        const titleText = ad.title || "Bez názvu";
        const descText = ad.description || "Žádný popis...";
        const priceVal = ad.price ? `${ad.price} Kč` : "Dohodou";
        const viewsCount = ad.views || 0;
        const dateStr = ad.date_created || "Dosud nevystaveno";
        const urlStr = ad.url || "";
        
        card.innerHTML = `
            <div>
                <div class="listing-header">
                    <h4 class="listing-title" title="Klikni pro editaci">${escapeHtml(titleText)}</h4>
                    <span class="price-badge">${priceVal}</span>
                </div>
                <div class="portal-badges" style="display: flex; gap: 0.5rem; margin-top: -0.25rem; margin-bottom: 0.75rem;">
                    <span class="portal-badge badge-bazos" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; ${ad.target_bazos ? 'background: rgba(131, 92, 223, 0.2); color: var(--accent); border: 1px solid rgba(131, 92, 223, 0.4);' : 'background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1);'}">
                        <i class="fa-solid ${ad.target_bazos ? 'fa-square-check' : 'fa-square'}"></i> Bazoš
                    </span>
                    <span class="portal-badge badge-aukro" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; ${ad.target_aukro ? 'background: rgba(234, 179, 8, 0.2); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.4);' : 'background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1);'}">
                        <i class="fa-solid ${ad.target_aukro ? 'fa-square-check' : 'fa-square'}"></i> Aukro
                    </span>
                </div>
                <p class="listing-desc">${escapeHtml(descText)}</p>
            </div>
            <div>
                <div class="listing-meta">
                    <div class="meta-item" title="Fotky k nahrání (k nahrání / celkem ve složce)">
                        <i class="fa-solid fa-camera"></i>
                        <span>${ad.photos_count !== undefined ? `${ad.photos_upload_count}/${ad.photos_count}` : '0'} fotek</span>
                    </div>
                    <div class="meta-item">
                        <i class="fa-solid fa-eye"></i>
                        <span>${viewsCount} zhlédnutí</span>
                    </div>
                    <div class="meta-item">
                        <i class="fa-solid fa-calendar"></i>
                        <span>${dateStr}</span>
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
                        <button class="btn btn-secondary btn-advisor" style="background: rgba(255,193,7,0.1); color: #ffc107; border: 1px solid rgba(255,193,7,0.3);"><i class="fa-solid fa-lightbulb"></i> Poradce</button>
                        <button class="btn btn-primary btn-post-action"><i class="fa-solid fa-rocket"></i> Vystavit</button>
                    ` : ""}
                </div>
            </div>
        `;

        // Event Listeners
        const editBtn = card.querySelector(".btn-edit");
        const titleEl = card.querySelector(".listing-title");
        const postBtn = card.querySelector(".btn-post-action");

        const openEditor = () => openEditModal(ad);
        editBtn.addEventListener("click", openEditor);
        titleEl.addEventListener("click", openEditor);

        if (postBtn) {
            postBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                triggerPlaywrightAction(ad, "post");
            });
        }

        return card;
    };

    // ==========================================
    // 3. EDITACE A DETAIl MODAL LOGIKA
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
        infoViews.textContent = ad.views || 0;
        infoPhotosDir.textContent = ad.local_photos_dir || "photos/";

        // Zobrazit modal
        editListingModal.classList.add("active");
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

    // Run Vision AI analysis
    if (btnRunVisionAi) {
        btnRunVisionAi.addEventListener("click", async () => {
            if (wizardSelectedFiles.length === 0) {
                showNotification("Nejprve přetáhněte nebo vyberte fotografie předmětu.", "warning");
                return;
            }

            if (newAiActionBar) newAiActionBar.style.display = "none";
            if (visionAiLoading) visionAiLoading.style.display = "block";
            btnRunVisionAi.disabled = true;

            const formData = new FormData();
            wizardSelectedFiles.forEach((file) => {
                formData.append("photos", file);
            });
            if (newUserNotes) {
                formData.append("notes", newUserNotes.value.trim());
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

            btnReanalyzeExisting.disabled = true;
            btnReanalyzeExisting.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzuji fotky...';
            showNotification("Spouštím Gemini Vision na fotografiích inzerátu...", "info");

            try {
                const res = await fetch(`${API.aiAnalyzeExisting}/${currentAd.id}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ notes: editNotes ? editNotes.value : "" })
                });

                const data = await res.json();
                if (!res.ok || data.status !== "success") {
                    showNotification(data.message || "Analýza fotografií selhala.", "error");
                    return;
                }

                const visionData = data.data;

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

    const triggerPlaywrightAction = async (ad, actionType, extraVal = null) => {
        // Okamžitě zavřít modal, pokud je aktivní, abychom viděli VNC prohlížeč
        if (editListingModal.classList.contains("active")) {
            editListingModal.classList.remove("active");
        }

        setPlaywrightActive(true);
        showNotification(`Spouštím akci '${actionType}' přes Playwright...`, "info");
        
        // Resetujeme stavový text description
        const statusDesc = document.getElementById("playwright-status-desc");
        if (statusDesc) {
            if (actionType === "sync_views") {
                statusDesc.textContent = "Probíhá synchronizace inzerátů s Bazošem...";
            } else if (actionType === "post") {
                statusDesc.textContent = "Probíhá vyplňování formuláře inzerátu na Bazoši...";
            } else if (actionType === "delete") {
                statusDesc.textContent = "Probíhá mazání inzerátu na Bazoši...";
            } else if (actionType === "edit_price") {
                statusDesc.textContent = "Probíhá změna ceny inzerátu na Bazoši...";
            } else {
                statusDesc.textContent = "Sleduj otevřené Chrome okno a případně zadej SMS...";
            }
        }

        // Automaticky přepnout na záložku s živým prohlížečem, aby uživatel viděl spuštěné okno
        switchToTab("browser");
        
        try {
            const res = await fetch(`${API.action}/${actionType}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    local_photos_dir: ad.local_photos_dir,
                    extra_val: extraVal
                })
            });

            const data = await res.json();
            if (res.ok) {
                // Začneme periodicky kontrolovat stav akce na pozadí
                const statusInterval = setInterval(async () => {
                    try {
                        const statusRes = await fetch("/api/action/status");
                        if (statusRes.ok) {
                            const statusData = await statusRes.json();
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

    // Připojení akčních tlačítek v detailu inzerátu
    document.getElementById("action-post").addEventListener("click", () => {
        if (currentAd) triggerPlaywrightAction(currentAd, "post");
    });

    document.getElementById("action-edit-price").addEventListener("click", () => {
        if (currentAd) {
            const price = editPrice.value;
            triggerPlaywrightAction(currentAd, "edit_price", price);
        }
    });

    document.getElementById("action-delete").addEventListener("click", () => {
        if (currentAd) {
            if (confirm(`Opravdu chceš smazat inzerát "${currentAd.title}" z Bazoše?`)) {
                triggerPlaywrightAction(currentAd, "delete");
            }
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

        function fitCanvasToContainer() {
            if (!canvas.width || !canvas.height) return;
            const parent = canvas.parentElement;
            if (!parent) return;

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
        }

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
            if (rect.width === 0 || rect.height === 0) return;

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
        const sendQuickText = () => {
            const input = document.getElementById("screencast-quick-text");
            if (!input || !input.value) return;
            const textVal = input.value.trim();
            if (!textVal) return;
            input.value = "";
            
            // Try direct SMS code submission endpoint first
            fetch("/api/sms_code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: textVal })
            }).then(r => r.json()).then(res => {
                if (!res.submitted) {
                    fetch("/api/screencast/input", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ action: "type", text: textVal })
                    });
                }
            }).catch(() => {
                fetch("/api/screencast/input", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action: "type", text: textVal })
                });
            });
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

    const openAdvisor = async (ad) => {
        // Inicializujeme modal do loading stavu
        document.getElementById("advisor-listing-title").innerText = ad.title;
        document.getElementById("advisor-current-price").innerText = `${ad.price.toLocaleString("cs-CZ")} Kč`;
        
        const sourcesListEl = document.getElementById("advisor-sources-list");
        if (sourcesListEl) sourcesListEl.innerText = "";

        const statusAlert = document.getElementById("advisor-status-alert");
        statusAlert.className = "alert alert-warning";
        statusAlert.style.background = "rgba(255, 193, 7, 0.1)";
        statusAlert.style.color = "#ffc107";
        document.getElementById("advisor-message").innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzuji konkurenční nabídky (Bazoš, Sbazar, Web)...';
        
        document.getElementById("advisor-opt-quick").innerText = "- Kč";
        document.getElementById("advisor-opt-fair").innerText = "- Kč";
        document.getElementById("advisor-opt-premium").innerText = "- Kč";
        
        document.getElementById("advisor-range-min").innerText = "- Kč";
        document.getElementById("advisor-range-median").innerText = "- Kč";
        document.getElementById("advisor-range-avg").innerText = "- Kč";
        document.getElementById("advisor-range-max").innerText = "- Kč";
        
        document.getElementById("advisor-competitors-container").innerHTML = '<div class="loading-state" style="padding: 1.5rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Hledám inzeráty na portálech...</div>';
        document.getElementById("advisor-selected-price").value = ad.price;
        
        advisorModal.classList.add("active");

        try {
            const res = await fetch(`/api/advisor/price/${ad.id}`);
            const json = await res.json();
            
            if (json.status === "error") {
                showNotification(`Chyba analýzy: ${json.message}`, "error");
                closeAdvisor();
                return;
            }
            
            const data = json.data;
            const stats = data.statistics;
            
            if (sourcesListEl && data.sources_checked && data.sources_checked.length) {
                sourcesListEl.innerText = `Zdroje: ${data.sources_checked.join(", ")}`;
            }

            // Vyhodnocení stavu a nastavení alertu
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
                return;
            }

            // Nastavení doporučených cen
            document.getElementById("advisor-opt-quick").innerText = `${stats.suggested_quick_sale.toLocaleString("cs-CZ")} Kč`;
            document.getElementById("advisor-opt-fair").innerText = `${stats.suggested_fair.toLocaleString("cs-CZ")} Kč`;
            document.getElementById("advisor-opt-premium").innerText = `${stats.suggested_premium.toLocaleString("cs-CZ")} Kč`;
            
            // Nastavení datasetů pro tlačítka "Zvolit"
            const selectBtns = document.querySelectorAll(".btn-select-advisor-price");
            selectBtns[0].setAttribute("data-price", stats.suggested_quick_sale);
            selectBtns[1].setAttribute("data-price", stats.suggested_fair);
            selectBtns[2].setAttribute("data-price", stats.suggested_premium);

            // Výchozí předvyplněná cena bude férová (medián)
            document.getElementById("advisor-selected-price").value = stats.suggested_fair;

            // Nastavení tabulky rozpětí
            document.getElementById("advisor-range-min").innerText = `${stats.min.toLocaleString("cs-CZ")} Kč`;
            document.getElementById("advisor-range-median").innerText = `${stats.median.toLocaleString("cs-CZ")} Kč`;
            document.getElementById("advisor-range-avg").innerText = `${stats.avg.toLocaleString("cs-CZ")} Kč`;
            document.getElementById("advisor-range-max").innerText = `${stats.max.toLocaleString("cs-CZ")} Kč`;

            // Vykreslení konkurenčních inzerátů
            const competitorsContainer = document.getElementById("advisor-competitors-container");
            competitorsContainer.innerHTML = "";
            
            data.listings.forEach(item => {
                const itemEl = document.createElement("div");
                itemEl.style.display = "flex";
                itemEl.style.justify = "space-between";
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
