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
    const configGeminiKey = document.getElementById("config-gemini-key");
    const toggleGeminiKeyBtn = document.getElementById("toggle-gemini-key");

    // Auto refresh elements
    const configAutoRefresh = document.getElementById("config-auto-refresh");
    const configRefreshInterval = document.getElementById("config-refresh-interval");
    const smsWarningBanner = document.getElementById("sms-warning-banner");
    const btnSyncBanner = document.getElementById("btn-sync-banner");
    const lastSyncTimeLabel = document.getElementById("last-sync-time-label");

    // App Update elements
    const appUpdateBanner = document.getElementById("app-update-banner");
    const appUpdateMsg = document.getElementById("app-update-msg");
    const btnAppUpdate = document.getElementById("btn-app-update");
    const dockerUpdateModal = document.getElementById("docker-update-modal");
    const btnCloseDockerUpdate = document.getElementById("btn-close-docker-update");
    const btnCloseDockerUpdateOk = document.getElementById("btn-close-docker-update-ok");
    const btnCopyDockerCmd = document.getElementById("btn-copy-docker-cmd");
    const restartOverlay = document.getElementById("restart-overlay");
    const restartStatus = document.getElementById("restart-status");
    const appVersionLabel = document.getElementById("app-version-label");

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
        action: "/api/action",
        cancel: "/api/action/cancel",
        aiImprove: "/api/ai/improve"
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

    const checkAppVersion = async () => {
        try {
            const res = await fetch(API.versionCheck);
            if (res.ok) {
                const data = await res.json();
                
                // Formátování textu verze v sidebaru
                let versionText = "v3.2.0";
                if (data.local_hash && data.local_hash !== "unknown") {
                    versionText += ` (${data.local_hash})`;
                }
                if (data.is_docker) {
                    versionText += " [Docker]";
                } else {
                    versionText += " [Local]";
                }
                if (data.update_available) {
                    versionText += " ⚠️ update k dispozici";
                    appVersionLabel.style.color = "var(--accent)";
                } else {
                    appVersionLabel.style.color = "var(--text-muted)";
                }
                appVersionLabel.textContent = versionText;

                if (data.update_available) {
                    appUpdateBanner.style.display = "flex";
                    // Ukážeme zprávu posledního commitu, pokud je
                    appUpdateMsg.textContent = data.latest_message ? `"${data.latest_message}"` : "Dostupný nový kód na GitHubu.";
                    
                    // Nabindujeme chování podle prostředí
                    btnAppUpdate.onclick = () => {
                        if (data.is_docker) {
                            // Běží v Dockeru -> ukážeme modal s instrukcemi
                            dockerUpdateModal.style.display = "flex";
                        } else {
                            // Lokální vývoj -> spustíme in-place aktualizaci
                            triggerLocalAppUpdate();
                        }
                    };
                } else {
                    appUpdateBanner.style.display = "none";
                }
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

        // Zprovoznit zavírání Docker Update modalu
        if (btnCloseDockerUpdate) {
            btnCloseDockerUpdate.addEventListener("click", () => {
                dockerUpdateModal.style.display = "none";
            });
        }
        if (btnCloseDockerUpdateOk) {
            btnCloseDockerUpdateOk.addEventListener("click", () => {
                dockerUpdateModal.style.display = "none";
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
                
                // Gemini API klíč se nenačítá celý z bezpečnostních důvodů (pokud je, dáme tam placeholder)
                if (config.gemini_api_key) {
                    configGeminiKey.placeholder = "••••••••••••••••••••••••••••••••";
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
            photoGalleryGrid.innerHTML = '<p class="photo-gallery-empty">Nepodařilo se načíst fotky.</p>';
        }
    };

    const renderPhotoGallery = (photos) => {
        photoGalleryGrid.innerHTML = "";
        photos.forEach(photo => {
            const isExcluded = excludedPhotos.has(photo.filename);
            const wrapper = document.createElement("div");
            wrapper.className = `photo-thumb-wrapper${isExcluded ? " excluded" : ""}`;
            wrapper.dataset.filename = photo.filename;
            wrapper.title = isExcluded ? `${photo.filename} — PŘESKOČIT` : photo.filename;

            const img = document.createElement("img");
            img.src = photo.data_url || "";
            img.alt = photo.filename;
            img.loading = "lazy";

            const icon = document.createElement("div");
            icon.className = "photo-exclude-icon";
            icon.innerHTML = isExcluded
                ? '<i class="fa-solid fa-xmark"></i>'
                : '<i class="fa-solid fa-check"></i>';

            const nameLabel = document.createElement("div");
            nameLabel.className = "photo-thumb-name";
            nameLabel.textContent = photo.filename;

            wrapper.appendChild(img);
            wrapper.appendChild(icon);
            wrapper.appendChild(nameLabel);

            wrapper.addEventListener("click", () => {
                if (excludedPhotos.has(photo.filename)) {
                    excludedPhotos.delete(photo.filename);
                    wrapper.classList.remove("excluded");
                    wrapper.title = photo.filename;
                    icon.innerHTML = '<i class="fa-solid fa-check"></i>';
                } else {
                    excludedPhotos.add(photo.filename);
                    wrapper.classList.add("excluded");
                    wrapper.title = `${photo.filename} — PŘESKOČIT`;
                    icon.innerHTML = '<i class="fa-solid fa-xmark"></i>';
                }
                updatePhotoCount(photos.length);
            });

            photoGalleryGrid.appendChild(wrapper);
        });
        updatePhotoCount(photos.length);
    };

    const updatePhotoCount = (total) => {
        const included = total - excludedPhotos.size;
        photoCountLabel.textContent = `${included} / ${total} fotek bude nahráno`;
        photoCountLabel.style.color = excludedPhotos.size > 0 ? "var(--warning, #f39c12)" : "var(--text-muted)";
    };

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
    // 4. VYTVOŘENÍ NOVÉHO INZERÁTU
    // ==========================================

    document.getElementById("btn-add-listing-modal").addEventListener("click", () => {
        addListingForm.reset();
        updateCounter(newTitle, newTitleCounter, 50);
        updateCounter(newDescription, newDescCounter);
        addListingModal.classList.add("active");
    });

    addListingForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const newTargetBazos = document.getElementById("new-target-bazos");
        const newTargetAukro = document.getElementById("new-target-aukro");

        const newAdData = {
            title: newTitle.value,
            price: parseInt(newPrice.value) || 0,
            category: newCategory.value.trim(),
            description: newDescription.value,
            target_bazos: newTargetBazos && newTargetBazos.checked ? 1 : 0,
            target_aukro: newTargetAukro && newTargetAukro.checked ? 1 : 0
        };

        try {
            const res = await fetch(API.addAd, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newAdData)
            });

            if (res.ok) {
                const data = await res.json();
                showNotification(`Inzerát byl vytvořen. Fotky vlož do složky: ${data.ad.local_photos_dir}`, "success");
                addListingModal.classList.remove("active");
                loadListings();
            } else {
                const data = await res.json();
                showNotification(data.message || "Vytváření selhalo", "error");
            }
        } catch (err) {
            showNotification("Chyba při vytváření inzerátu.", "error");
        }
    });

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

        try {
            const res = await fetch(API.config, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedConfig)
            });

            if (res.ok) {
                showNotification("Nastavení bylo úspěšně uloženo.", "success");
                configGeminiKey.value = ""; // Vynulujeme pole po uložení
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

    // ==========================================
    // 8. GLOBÁLNÍ UTILITY (NOTIFIKACE, MODALY, TABS)
    // ==========================================

    // Přepínání tabů
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

        // Aktualizovat nadpis stránky
        if (tabName === "active-listings") {
            pageTitle.textContent = "Aktivní inzeráty";
        } else if (tabName === "unsold-listings") {
            pageTitle.textContent = "Věci k prodeji";
        } else if (tabName === "sold-listings") {
            pageTitle.textContent = "Prodané věci";
        } else if (tabName === "browser") {
            pageTitle.textContent = "Živý prohlížeč (VNC)";
            const vncIframe = document.getElementById("vnc-iframe");
            console.log("🔍 vncIframe:", vncIframe, "current attribute src:", vncIframe ? vncIframe.getAttribute("src") : "N/A");
            if (vncIframe && !vncIframe.getAttribute("src")) {
                reloadVncSrc();
            }
        } else if (tabName === "config") {
            pageTitle.textContent = "Nastavení aplikace";
        }
    }

    const reloadVncSrc = () => {
        const vncIframe = document.getElementById("vnc-iframe");
        if (!vncIframe) {
            console.log("⚠️ reloadVncSrc: vncIframe not found!");
            return;
        }
        
        // Pokud má uživatel nastavenou vlastní VNC URL, použijeme ji
        if (userConfig && userConfig.vnc_url) {
            vncIframe.src = userConfig.vnc_url;
            console.log("➡️ reloadVncSrc: set src to custom config URL =", vncIframe.src);
            return;
        }
        
        const isLocalDev = window.location.port === "5001";
        console.log("ℹ️ reloadVncSrc: port =", window.location.port, "isLocalDev =", isLocalDev);
        
        if (window.location.protocol === "https:") {
            // Přímé připojení na zabezpečený noVNC port 6080 (pokud NPM/Cloudflare proxy směřuje port 6080)
            // nebo na stejný host na portu 6080
            vncIframe.src = `https://${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
        } else {
            // Výchozí HTTP připojení na port 6080
            vncIframe.src = `http://${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
        }
        console.log("➡️ reloadVncSrc: set src to =", vncIframe.src);
    };

    const btnReloadVnc = document.getElementById("btn-reload-vnc");
    if (btnReloadVnc) {
        btnReloadVnc.addEventListener("click", () => {
            const vncIframe = document.getElementById("vnc-iframe");
            if (vncIframe) {
                vncIframe.src = "";
                setTimeout(reloadVncSrc, 100);
            }
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

        // Stylování a vložení toastu na stránku
        Object.assign(toast.style, {
            position: "fixed",
            top: "2rem",
            right: "2rem",
            background: "rgba(15, 12, 32, 0.9)",
            border: `1px solid ${type === 'success' ? 'var(--success)' : type === 'error' ? 'var(--danger)' : 'var(--primary)'}`,
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
            backdropFilter: "blur(10px)",
            color: "#fff",
            padding: "1rem 1.5rem",
            borderRadius: "12px",
            display: "flex",
            alignItems: "center",
            gap: "0.85rem",
            zIndex: "9999",
            opacity: "0",
            transform: "translateY(-20px)",
            transition: "all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)",
            pointerEvents: "none",
            fontSize: "0.9rem",
            fontWeight: "500"
        });

        document.body.appendChild(toast);

        // Animace naběhnutí
        setTimeout(() => {
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
        }, 10);

        // Animace odstranění
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-20px)";
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
        
        const statusAlert = document.getElementById("advisor-status-alert");
        statusAlert.className = "alert alert-warning";
        statusAlert.style.background = "rgba(255, 193, 7, 0.1)";
        statusAlert.style.color = "#ffc107";
        document.getElementById("advisor-message").innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzuji konkurenční nabídky na Bazoši...';
        
        document.getElementById("advisor-opt-quick").innerText = "- Kč";
        document.getElementById("advisor-opt-fair").innerText = "- Kč";
        document.getElementById("advisor-opt-premium").innerText = "- Kč";
        
        document.getElementById("advisor-range-min").innerText = "- Kč";
        document.getElementById("advisor-range-median").innerText = "- Kč";
        document.getElementById("advisor-range-avg").innerText = "- Kč";
        document.getElementById("advisor-range-max").innerText = "- Kč";
        
        document.getElementById("advisor-competitors-container").innerHTML = '<div class="loading-state" style="padding: 1.5rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Hledám inzeráty...</div>';
        document.getElementById("advisor-selected-price").value = ad.price;
        
        advisorModal.classList.add("active");

        try {
            const res = await fetch(`/api/advisor/price/${ad.id}`);
            const json = await res.json();
            
            if (json.status === "error") {
                showToast(`Chyba analýzy: ${json.message}`, "error");
                closeAdvisor();
                return;
            }
            
            const data = json.data;
            const stats = data.statistics;
            
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
            document.getElementById("advisor-message").innerText = data.message;
            
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
                
                itemEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 0.15rem; max-width: 75%;">
                        <a href="${item.link}" target="_blank" style="color: #a5d6ff; text-decoration: none; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${escapeHtml(item.title)}</a>
                        <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(item.location)} | 👀 ${item.views} zhlédnutí</span>
                    </div>
                    <strong style="color: #fff;">${item.price_text}${topText}</strong>
                `;
                competitorsContainer.appendChild(itemEl);
            });

        } catch (e) {
            showToast("Chyba při komunikaci s analyzátorem cen.", "error");
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
            showToast(`Zvolena cena ${parseInt(price).toLocaleString("cs-CZ")} Kč.`, "success");
        }
    });

    const closeAdvisor = () => {
        advisorModal.classList.remove("active");
        activeAdvisorListingId = null;
    };

    closeAdvisorBtn.addEventListener("click", closeAdvisor);
    closeAdvisorBtnFooter.addEventListener("click", closeAdvisor);

    // Odeslání akce znovuvystavení se zlevněním
    applyAdvisorPriceBtn.addEventListener("click", async () => {
        const newPriceInput = document.getElementById("advisor-selected-price");
        const newPrice = parseInt(newPriceInput.value);
        
        if (!activeAdvisorListingId || isNaN(newPrice) || newPrice <= 0) {
            showToast("Zadejte platnou cenu.", "error");
            return;
        }

        closeAdvisor();
        
        // Zobrazíme running status bar
        const statusDesc = document.getElementById("playwright-status-desc");
        statusDesc.innerText = "Robot zlevňuje inzerát v SQLite a spouští znovuvystavení na Bazoši...";
        const statusContainer = document.getElementById("playwright-status");
        statusContainer.classList.add("active");

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
                showToast(json.message, "success");
                // Refreshujeme aplikaci pro načtení nové ceny
                loadApp();
            } else {
                showToast(json.message, "error");
                statusContainer.classList.remove("active");
            }
        } catch (e) {
            showToast("Nepodařilo se spustit znovuvystavení.", "error");
            statusContainer.classList.remove("active");
        }
    });

    // Pomocná funkce pro bezpečné parsování HTML
    const escapeHtml = (unsafe) => {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };

    // --- Start up ---
    loadApp();
});
