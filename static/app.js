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
    let selectedTextRange = null; // Uchovává vybranou část textu pro inline AI přepis

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
        saveAd: "/api/listings/save",
        addAd: "/api/listings/add",
        action: "/api/action",
        cancel: "/api/action/cancel",
        aiImprove: "/api/ai/improve"
    };

    // ==========================================
    // 1. INICIALIZACE A NABÍHÁNÍ DAT
    // ==========================================

    const loadApp = async () => {
        await loadConfig();
        await loadListings();
    };

    const loadConfig = async () => {
        try {
            const res = await fetch(API.config);
            if (res.ok) {
                const config = await res.json();
                configName.value = config.name || "";
                configEmail.value = config.email || "";
                configPhone.value = config.phone || "";
                configZip.value = config.zip_code || "";
                configPassword.value = config.default_ad_password_b64 ? atob(config.default_ad_password_b64) : "";
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
                <p class="listing-desc">${escapeHtml(descText)}</p>
            </div>
            <div>
                <div class="listing-meta">
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

        const updatedAd = {
            ...currentAd,
            title: editTitle.value,
            price: parseInt(editPrice.value) || 0,
            category: editCategory.value.trim(),
            description: editDescription.value,
            notes: editNotes.value,
            local_photos_dir: editPhotosDir.value,
            excluded_photos: Array.from(excludedPhotos)
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
        addListingModal.classList.add("active");
    });

    addListingForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const newAdData = {
            title: newTitle.value,
            price: parseInt(newPrice.value) || 0,
            category: newCategory.value.trim(),
            description: newDescription.value
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
                showAiProposal(text, data.result);
            } else {
                showNotification(data.message || "AI asistent selhal.", "error");
            }
        } catch (err) {
            showNotification("Nepodařilo se spojit s AI službou.", "error");
        }
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

    // --- Modal s porovnáním AI návrhu ---
    const showAiProposal = (original, improved) => {
        document.getElementById("ai-original-text-preview").textContent = original;
        document.getElementById("ai-improved-text-preview").textContent = improved;
        aiProposalModal.classList.add("active");
    };

    // Přijetí AI návrhu
    document.getElementById("btn-accept-ai-proposal").addEventListener("click", () => {
        const improvedText = document.getElementById("ai-improved-text-preview").textContent;
        
        if (selectedTextRange) {
            // Pokud přepisujeme jen vybraný kus textu
            const fullText = editDescription.value;
            const updatedText = 
                fullText.substring(0, selectedTextRange.start) + 
                improvedText + 
                fullText.substring(selectedTextRange.end);
            
            editDescription.value = updatedText;
            selectedTextRange = null;
            showNotification("Vybraný text byl nahrazen AI verzí.", "success");
        } else {
            // Pokud přepisujeme celé pole (nadpis nebo celý popis)
            // Rozhodneme podle toho, zda se porovnávaný text shoduje s nadpisem
            if (document.getElementById("ai-original-text-preview").textContent === editTitle.value) {
                editTitle.value = improvedText;
                showNotification("Nadpis byl nahrazen AI verzí.", "success");
            } else {
                editDescription.value = improvedText;
                showNotification("Popis byl nahrazen AI verzí.", "success");
            }
        }
        
        aiProposalModal.classList.remove("active");
    });

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
        const isLocalDev = window.location.port === "5001";
        console.log("ℹ️ reloadVncSrc: port =", window.location.port, "isLocalDev =", isLocalDev);
        if (isLocalDev) {
            vncIframe.src = `http://${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
        } else {
            vncIframe.src = `${window.location.protocol}//${window.location.host}/novnc/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
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
