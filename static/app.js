/**
 * Bazoš Automat & AI Editor - Client Logic (app.js)
 * Brand: TERMS a.s. / Roboton Custom UI Engine
 */

document.addEventListener("DOMContentLoaded", () => {
    // State state management
    let activeListings = [];
    let soldListings = [];
    let currentAd = null;
    let selectedTextRange = null; // Uchovává vybranou část textu pro inline AI přepis

    // UI elements
    const navItems = document.querySelectorAll(".nav-item");
    const tabContents = document.querySelectorAll(".tab-content");
    const activeListingsContainer = document.getElementById("active-listings-list");
    const soldListingsContainer = document.getElementById("sold-listings-list");
    const pageTitle = document.getElementById("page-title");
    
    // Stats elements
    const statActiveCount = document.getElementById("stat-active-count");
    const statTotalViews = document.getElementById("stat-total-views");
    const statSoldCount = document.getElementById("stat-sold-count");

    // Config elements
    const configForm = document.getElementById("config-form");
    const configName = document.getElementById("config-name");
    const configEmail = document.getElementById("config-email");
    const configPhone = document.getElementById("config-phone");
    const configZip = document.getElementById("config-zip");
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
    const newDescription = document.getElementById("new-description");

    const editListingForm = document.getElementById("edit-listing-form");
    const editTitle = document.getElementById("edit-title");
    const editPrice = document.getElementById("edit-price");
    const editDescription = document.getElementById("edit-description");
    const editNotes = document.getElementById("edit-notes");
    const editPhotosDir = document.getElementById("edit-photos-dir");

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
        saveAd: "/api/listings/save",
        addAd: "/api/listings/add",
        action: "/api/action",
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
        statActiveCount.textContent = activeListings.length;
        statSoldCount.textContent = soldListings.length;
        
        const totalViews = activeListings.reduce((sum, ad) => sum + parseInt(ad.views || 0), 0);
        statTotalViews.textContent = totalViews;
    };

    // ==========================================
    // 2. RENDEROVÁNÍ KARET INZERÁTŮ
    // ==========================================

    const renderListings = () => {
        // Aktivní inzeráty
        activeListingsContainer.innerHTML = "";
        if (activeListings.length === 0) {
            activeListingsContainer.innerHTML = `<div class="loading-state"><i class="fa-solid fa-face-smile"></i> Žádné aktivní inzeráty k zobrazení.</div>`;
        } else {
            activeListings.forEach(ad => {
                const card = createAdCard(ad, false);
                activeListingsContainer.appendChild(card);
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
        editDescription.value = ad.description || "";
        editNotes.value = ad.notes || "";
        editPhotosDir.value = ad.local_photos_dir || "";

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

    // Uložit změny v detailu inzerátu
    document.getElementById("btn-save-listing-changes").addEventListener("click", async () => {
        if (!currentAd) return;

        const updatedAd = {
            ...currentAd,
            title: editTitle.value,
            price: parseInt(editPrice.value) || 0,
            description: editDescription.value,
            notes: editNotes.value,
            local_photos_dir: editPhotosDir.value
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
        setPlaywrightActive(true);
        showNotification(`Spouštím akci '${actionType}' přes Playwright...`, "info");
        
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
                showNotification(data.message || "Akce úspěšně dokončena", "success");
                editListingModal.classList.remove("active");
                loadListings();
            } else {
                showNotification(data.message || "Chyba při běhu automatizace", "error");
            }
        } catch (err) {
            showNotification("Spojení se serverem selhalo při automatizaci.", "error");
        } finally {
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

    const setPlaywrightActive = (isActive) => {
        if (isActive) {
            playwrightStatus.classList.add("active");
        } else {
            playwrightStatus.classList.remove("active");
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
    const reloadVncSrc = () => {
        const vncIframe = document.getElementById("vnc-iframe");
        if (!vncIframe) return;
        const isLocalDev = window.location.port === "5001";
        if (isLocalDev) {
            vncIframe.src = `http://${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
        } else {
            vncIframe.src = `${window.location.protocol}//${window.location.host}/novnc/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
        }
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
            navItems.forEach(nav => nav.classList.remove("active"));
            tabContents.forEach(tab => tab.classList.remove("active"));

            item.classList.add("active");
            const tabId = `tab-${item.getAttribute("data-tab")}`;
            document.getElementById(tabId).classList.add("active");

            // Aktualizovat nadpis stránky
            if (item.getAttribute("data-tab") === "active-listings") {
                pageTitle.textContent = "Aktivní inzeráty";
            } else if (item.getAttribute("data-tab") === "sold-listings") {
                pageTitle.textContent = "Prodané věci";
            } else if (item.getAttribute("data-tab") === "browser") {
                pageTitle.textContent = "Živý prohlížeč (VNC)";
                const vncIframe = document.getElementById("vnc-iframe");
                if (vncIframe && !vncIframe.src) {
                    reloadVncSrc();
                }
            } else if (item.getAttribute("data-tab") === "config") {
                pageTitle.textContent = "Nastavení aplikace";
            }
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
