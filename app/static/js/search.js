// LabCurate — Search & Lab Detail Logic
(function () {
    // Lab detail page
    if (typeof LAB_ID !== "undefined") {
        loadLabDetail(LAB_ID);
        return;
    }

    const searchInput = document.getElementById("search-input");
    const searchForm = document.getElementById("search-form");
    const searchBtn = document.getElementById("search-btn");
    const locationInput = document.getElementById("location-input");
    const resultsDiv = document.getElementById("results");
    const statusDiv = document.getElementById("status");
    const resultCount = document.getElementById("result-count");
    const countValue = document.getElementById("count-value");
    const aboutSection = document.getElementById("about-section");
    const exampleSearches = document.getElementById("example-searches");

    if (!searchInput) return;

    let debounceTimer = null;
    let searchMode = "labs"; // "labs" or "capabilities"
    let skipClarify = false; // set true after clarification or when query is specific

    // Mode toggle
    const modeDiv = document.getElementById("search-mode");
    if (modeDiv) {
        modeDiv.addEventListener("click", (e) => {
            const btn = e.target.closest("[data-mode]");
            if (!btn) return;
            searchMode = btn.dataset.mode;
            modeDiv.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("mode-btn-active"));
            btn.classList.add("mode-btn-active");
        });
    }

    // Restore from URL
    const params = new URLSearchParams(window.location.search);
    if (params.get("q")) {
        searchInput.value = params.get("q");
    }
    if (params.get("location") && locationInput) {
        locationInput.value = params.get("location");
    }

    // Form submit (button click)
    if (searchForm) {
        searchForm.addEventListener("submit", (e) => {
            e.preventDefault();
            doSearch();
        });
    }

    // Enter in textarea submits (Shift+Enter for newline)
    if (searchInput) {
        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                doSearch();
            }
        });
    }


    // Example search pills
    if (exampleSearches) {
        exampleSearches.addEventListener("click", (e) => {
            if (e.target.dataset.query) {
                searchInput.value = e.target.dataset.query;
                doSearch();
            }
        });
    }

    async function doSearch(enrichedQuery) {
        const q = enrichedQuery || searchInput.value.trim();
        if (q.length < 2) {
            resultsDiv.textContent = "";
            statusDiv.classList.add("hidden");
            resultCount.classList.add("hidden");
            if (aboutSection) aboutSection.classList.remove("hidden");
            return;
        }

        const location = locationInput ? locationInput.value.trim() : "";

        // Update URL
        const url = new URL(window.location);
        url.searchParams.set("q", searchInput.value.trim());
        if (location) url.searchParams.set("location", location);
        else url.searchParams.delete("location");
        history.replaceState(null, "", url);

        // Clarification step (only for Advisor mode, skip if already clarified or enriched)
        if (searchMode === "labs" && !skipClarify && !enrichedQuery) {
            if (aboutSection) aboutSection.classList.add("hidden");
            statusDiv.classList.remove("hidden");
            const statusText = statusDiv.querySelector("span:last-child");
            if (statusText) statusText.textContent = "Understanding your query...";
            if (searchBtn) searchBtn.classList.add("search-btn-loading");

            try {
                const clarifyResp = await fetch("/api/search/clarify?q=" + encodeURIComponent(q));
                const clarifyData = await clarifyResp.json();

                if (clarifyData.needs_clarification && clarifyData.questions) {
                    statusDiv.classList.add("hidden");
                    if (searchBtn) searchBtn.classList.remove("search-btn-loading");
                    showClarification(q, clarifyData.questions);
                    return;
                }
            } catch (e) {
                // Clarification failed — proceed with search anyway
            }
            if (statusText) statusText.textContent = "Analysing your requirements...";
        }

        skipClarify = false;

        // Loading state — skip global spinner if we came from clarification (inline spinner shown)
        if (!enrichedQuery) {
            statusDiv.classList.remove("hidden");
            const statusText2 = statusDiv.querySelector("span:last-child");
            if (statusText2) statusText2.textContent = "Analysing your requirements...";
        }
        resultCount.classList.add("hidden");
        if (searchBtn) searchBtn.classList.add("search-btn-loading");

        try {
            const searchQuery = enrichedQuery || q;
            const base = searchMode === "labs" ? "/api/search/labs" : "/api/search";
            const recommend = searchMode === "labs" ? "&recommend=true" : "";
            const locationParam = location ? "&location=" + encodeURIComponent(location) : "";
            const apiUrl = base + "?q=" + encodeURIComponent(searchQuery) + "&limit=20" + locationParam + recommend;
            const resp = await fetch(apiUrl);
            const data = await resp.json();

            statusDiv.classList.add("hidden");
            if (searchBtn) searchBtn.classList.remove("search-btn-loading");
            resultsDiv.textContent = "";

            // Hide about section when we have results
            if (aboutSection) aboutSection.classList.add("hidden");

            if (!data.results || data.results.length === 0) {
                const empty = document.createElement("div");
                empty.className = "empty-state";
                empty.textContent = "No matching capabilities found. Try a different query.";
                resultsDiv.appendChild(empty);
                resultCount.classList.add("hidden");
                return;
            }

            countValue.textContent = data.count;
            resultCount.classList.remove("hidden");

            const maxRrf = data.results[0].rrf_score || 1;

            // Interleaved recommendation groups + cards
            const rec = data.recommendation;
            const groups = rec && rec.groups ? rec.groups : (Array.isArray(rec) ? rec : null);

            if (groups && groups.length > 0) {
                // Standards advice panel
                if (rec.standards_advice) {
                    const advicePanel = el("div", "mb-6 p-5 rounded-xl border border-accent/20 bg-accent/5");
                    const adviceLabel = el("div", "font-mono text-[10px] text-accent tracking-widest uppercase mb-2");
                    adviceLabel.textContent = "Standards guidance";
                    advicePanel.appendChild(adviceLabel);
                    const adviceText = el("p", "text-sm text-slate-300 leading-relaxed");
                    adviceText.textContent = rec.standards_advice;
                    advicePanel.appendChild(adviceText);

                    // Subtle disclaimer within the advice panel
                    const disclaimer = el("p", "text-[10px] text-slate-600 mt-3 leading-relaxed font-mono");
                    disclaimer.textContent = "AI-generated guidance \u2014 verify accreditation at ukas.com and confirm suitability with the lab.";
                    advicePanel.appendChild(disclaimer);

                    resultsDiv.appendChild(advicePanel);
                }

                const groupedLabIds = new Set();
                let cardIdx = 0;

                groups.forEach((group) => {
                    // Group heading + explanation
                    const groupPanel = el("div", "mb-2 mt-6 first:mt-0");
                    const heading = el("h3", "font-display font-semibold text-accent text-sm mb-1");
                    heading.textContent = group.heading || "";
                    groupPanel.appendChild(heading);
                    const explanation = el("p", "text-sm text-slate-400 leading-relaxed mb-3");
                    explanation.textContent = group.explanation || "";
                    groupPanel.appendChild(explanation);
                    resultsDiv.appendChild(groupPanel);

                    // Cards for labs in this group (from search results)
                    const labIds = new Set((group.lab_ids || []).map(Number));
                    data.results.forEach((r) => {
                        if (labIds.has(r.lab_id) && !groupedLabIds.has(r.lab_id)) {
                            groupedLabIds.add(r.lab_id);
                            const card = searchMode === "labs"
                                ? buildLabCard(r, maxRrf, cardIdx++)
                                : buildResultCard(r, maxRrf, cardIdx++);
                            resultsDiv.appendChild(card);
                        }
                    });

                    // Extra labs confirmed by standard cross-reference
                    const extraIds = new Set((group.extra_lab_ids || []).map(Number));
                    if (extraIds.size > 0 && data.extra_results) {
                        data.extra_results.forEach((r) => {
                            if (extraIds.has(r.lab_id) && !groupedLabIds.has(r.lab_id)) {
                                groupedLabIds.add(r.lab_id);
                                const card = buildLabCard(r, maxRrf, cardIdx++);
                                resultsDiv.appendChild(card);
                            }
                        });
                    }
                });

                // Any remaining results not in a group
                const remaining = data.results.filter((r) => !groupedLabIds.has(r.lab_id));
                if (remaining.length > 0) {
                    const otherPanel = el("div", "mb-2 mt-6");
                    const otherHeading = el("h3", "font-display font-semibold text-slate-500 text-sm mb-3");
                    otherHeading.textContent = "Other results";
                    otherPanel.appendChild(otherHeading);
                    resultsDiv.appendChild(otherPanel);
                    remaining.forEach((r) => {
                        const card = searchMode === "labs"
                            ? buildLabCard(r, maxRrf, cardIdx++)
                            : buildResultCard(r, maxRrf, cardIdx++);
                        resultsDiv.appendChild(card);
                    });
                }
            } else {
                // No recommendation — just show cards
                data.results.forEach((r, idx) => {
                    const card = searchMode === "labs"
                        ? buildLabCard(r, maxRrf, idx)
                        : buildResultCard(r, maxRrf, idx);
                    resultsDiv.appendChild(card);
                });
            }

            // Bottom disclaimer on all advisor results
            if (searchMode === "labs" && data.results.length > 0) {
                resultsDiv.appendChild(buildDisclaimer());
            }
        } catch (err) {
            statusDiv.classList.add("hidden");
            if (searchBtn) searchBtn.classList.remove("search-btn-loading");
            resultsDiv.textContent = "";
            const errDiv = document.createElement("div");
            errDiv.className = "empty-state";
            errDiv.textContent = "Search failed. Please try again.";
            resultsDiv.appendChild(errDiv);
        }
    }

    function showClarification(originalQuery, questions) {
        resultsDiv.textContent = "";
        if (aboutSection) aboutSection.classList.add("hidden");

        const panel = el("div", "max-w-2xl mx-auto");
        const intro = el("p", "text-sm text-slate-400 mb-5");
        intro.textContent = "A couple of quick questions to help us find the best labs for you:";
        panel.appendChild(intro);

        // Container where questions appear sequentially
        const questionsContainer = el("div", "");
        panel.appendChild(questionsContainer);

        // Spinner placeholder — appears after final answer
        const spinnerSlot = el("div", "hidden mt-4");
        panel.appendChild(spinnerSlot);

        resultsDiv.appendChild(panel);

        const answers = {};
        let currentIdx = 0;

        function shouldSkipQuestion(qIdx) {
            // Heuristic: if this question's text contains a term from a previous
            // option that was available but NOT chosen, it's likely drilling into
            // the unchosen path — skip it.
            const qTextLower = questions[qIdx].text.toLowerCase();
            for (const [prevIdx, chosenOpt] of Object.entries(answers)) {
                const prevQ = questions[Number(prevIdx)];
                const unchosen = (prevQ.options || []).filter(
                    (o) => o.toLowerCase() !== chosenOpt.toLowerCase()
                );
                for (const opt of unchosen) {
                    // Check if any significant word (4+ chars) from the unchosen
                    // option appears in this question's text
                    const words = opt.toLowerCase().split(/\s+/).filter((w) => w.length >= 4);
                    if (words.length > 0 && words.some((w) => qTextLower.includes(w))) {
                        return true;
                    }
                }
            }
            return false;
        }

        function showNextQuestion() {
            // Find next non-skippable question
            while (currentIdx < questions.length && shouldSkipQuestion(currentIdx)) {
                currentIdx++;
            }
            if (currentIdx >= questions.length) {
                finishClarification(originalQuery, questions, answers, spinnerSlot);
                return;
            }

            const question = questions[currentIdx];
            const qIdx = currentIdx;
            currentIdx++;

            const qBlock = el("div", "mb-5 result-enter");
            const qText = el("p", "text-sm text-white font-semibold mb-2.5");
            qText.textContent = question.text;
            qBlock.appendChild(qText);

            const optionsWrap = el("div", "flex flex-wrap gap-2");

            (question.options || []).forEach((opt) => {
                const pill = el("button", "clarify-pill px-4 py-2 rounded-lg border border-white/10 bg-white/[0.04] text-sm text-slate-300 hover:border-accent/50 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer");
                pill.textContent = opt;
                pill.addEventListener("click", () => {
                    answers[qIdx] = opt;
                    // Lock this question: highlight chosen, disable all
                    optionsWrap.querySelectorAll(".clarify-pill").forEach((p) => {
                        p.classList.add("pointer-events-none", "opacity-40");
                        p.classList.remove("hover:border-accent/50", "hover:text-white", "hover:bg-white/[0.06]");
                    });
                    pill.classList.remove("opacity-40", "border-white/10", "bg-white/[0.04]", "text-slate-300");
                    pill.classList.add("border-accent", "bg-accent/10", "text-white", "opacity-100");
                    // Remove skip button for this question
                    const skipBtn = qBlock.querySelector(".clarify-skip");
                    if (skipBtn) skipBtn.remove();
                    setTimeout(showNextQuestion, 250);
                });
                optionsWrap.appendChild(pill);
            });

            // Per-question skip
            const skipBtn = el("button", "clarify-skip px-3 py-2 text-xs text-slate-600 hover:text-slate-400 transition-colors cursor-pointer");
            skipBtn.textContent = "skip";
            skipBtn.addEventListener("click", () => {
                // Fade out question
                qBlock.classList.add("opacity-40");
                optionsWrap.querySelectorAll(".clarify-pill").forEach((p) => {
                    p.classList.add("pointer-events-none");
                });
                skipBtn.remove();
                setTimeout(showNextQuestion, 150);
            });
            optionsWrap.appendChild(skipBtn);

            qBlock.appendChild(optionsWrap);
            questionsContainer.appendChild(qBlock);
        }

        showNextQuestion();
    }

    function finishClarification(originalQuery, questions, answers, spinnerSlot) {
        // Show inline spinner
        spinnerSlot.classList.remove("hidden");
        const spinnerInner = el("div", "inline-flex items-center gap-3 text-sm text-slate-500 font-mono");
        const spinner = el("span", "search-spinner");
        const spinnerText = el("span", "");
        spinnerText.textContent = "Analysing your requirements...";
        spinnerInner.appendChild(spinner);
        spinnerInner.appendChild(spinnerText);
        spinnerSlot.appendChild(spinnerInner);

        // Build enriched query
        const parts = [originalQuery];
        for (const [idx, answer] of Object.entries(answers)) {
            const q = questions[Number(idx)];
            parts.push(q.text + " " + answer);
        }
        const enriched = parts.join(". ");
        skipClarify = true;
        doSearch(enriched);
    }

    function buildDisclaimer() {
        const wrapper = el("div", "mt-6 mb-2 px-1");
        const text = el("p", "text-[11px] text-slate-600 leading-relaxed font-mono");
        text.textContent = "AI-generated guidance \u2014 not a substitute for professional advice. Always verify lab accreditation status at ukas.com and confirm testing suitability directly with the laboratory before proceeding.";
        wrapper.appendChild(text);
        return wrapper;
    }

    function buildResultCard(r, maxRrf, idx) {
        const card = document.createElement("a");
        card.href = "/lab/" + r.lab_id;
        card.className = "result-card result-enter";
        card.style.animationDelay = (idx * 0.04) + "s";

        // Top row: lab name + accreditation
        const top = el("div", "flex items-center justify-between gap-4 mb-3");

        const nameWrap = el("div", "min-w-0 flex-1");
        const name = el("h3", "font-display font-semibold text-white text-[15px] truncate");
        name.textContent = r.lab_name || "";
        const accred = el("span", "font-mono text-[11px] text-slate-500 tracking-wide");
        accred.textContent = "UKAS #" + (r.accreditation_number || "");
        nameWrap.appendChild(name);
        nameWrap.appendChild(accred);

        top.appendChild(nameWrap);

        // Capability info
        const body = el("div", "grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 mb-3");

        const matWrap = el("div", "");
        const matLabel = el("span", "font-mono text-[10px] text-slate-600 uppercase tracking-wider");
        matLabel.textContent = "Materials";
        const matVal = el("p", "text-sm text-slate-300 leading-snug mt-0.5");
        matVal.textContent = truncate(r.materials_products || "", 100);
        matWrap.appendChild(matLabel);
        matWrap.appendChild(matVal);

        const testWrap = el("div", "");
        const testLabel = el("span", "font-mono text-[10px] text-slate-600 uppercase tracking-wider");
        testLabel.textContent = "Test Type";
        const testVal = el("p", "text-sm text-slate-300 leading-snug mt-0.5");
        testVal.textContent = truncate(r.test_type || "", 100);
        testWrap.appendChild(testLabel);
        testWrap.appendChild(testVal);

        body.appendChild(matWrap);
        body.appendChild(testWrap);

        // Address footer
        const footer = el("div", "flex items-center gap-2 text-xs text-slate-600");
        const pinIcon = el("span", "");
        pinIcon.textContent = "\u25CB";
        const addr = el("span", "truncate");
        addr.textContent = truncate(r.address || "", 70);
        footer.appendChild(pinIcon);
        footer.appendChild(addr);

        card.appendChild(top);
        card.appendChild(body);
        card.appendChild(footer);

        return card;
    }

    function buildLabCard(r, maxRrf, idx) {
        const card = document.createElement("a");
        card.href = "/lab/" + r.lab_id;
        card.className = "result-card result-enter";
        card.style.animationDelay = (idx * 0.04) + "s";

        // Top row: title + accreditation
        const top = el("div", "flex items-center justify-between gap-4 mb-2");

        const nameWrap = el("div", "min-w-0 flex-1");
        const name = el("h3", "font-display font-semibold text-white text-[15px] truncate");
        name.textContent = r.title || r.lab_name || "";
        const accred = el("span", "font-mono text-[11px] text-slate-500 tracking-wide");
        accred.textContent = "UKAS #" + (r.accreditation_number || "");
        nameWrap.appendChild(name);
        nameWrap.appendChild(accred);

        top.appendChild(nameWrap);

        // Brief
        const brief = el("p", "text-sm text-slate-300 leading-relaxed mb-3");
        brief.textContent = r.brief || "";

        // Tags
        const tagsWrap = el("div", "flex flex-wrap gap-1.5 mb-3");
        if (r.tags) {
            r.tags.slice(0, 8).forEach((t) => {
                const pill = el("span", "tag-pill");
                pill.textContent = t;
                tagsWrap.appendChild(pill);
            });
        }

        // Matched sites (when region filter matched via a branch/site)
        if (r.matched_sites && r.matched_sites.length > 0) {
            const sitesWrap = el("div", "mb-3 p-3 rounded-lg border border-accent/20 bg-accent/5");
            const sitesLabel = el("div", "font-mono text-[10px] text-accent tracking-widest uppercase mb-2");
            sitesLabel.textContent = "Matched sites";
            sitesWrap.appendChild(sitesLabel);
            r.matched_sites.forEach((s) => {
                const siteRow = el("div", "flex items-start gap-2 mb-1 last:mb-0");
                const pin = el("span", "text-accent text-xs mt-0.5");
                pin.textContent = "\u25CB";
                const siteInfo = el("div", "text-xs text-slate-300");
                const siteName = el("strong", "");
                siteName.textContent = s.site_name || "";
                siteInfo.appendChild(siteName);
                siteInfo.appendChild(document.createTextNode(" — " + truncate(s.address || "", 60)));
                if (s.capabilities) {
                    const capSpan = el("span", "text-slate-500");
                    capSpan.textContent = " (" + truncate(s.capabilities, 50) + ")";
                    siteInfo.appendChild(capSpan);
                }
                siteRow.appendChild(pin);
                siteRow.appendChild(siteInfo);
                sitesWrap.appendChild(siteRow);
            });
            card.appendChild(sitesWrap);
        }

        // Category + address footer
        const footer = el("div", "flex items-center gap-3 text-xs text-slate-600");
        if (r.category) {
            const cat = el("span", "font-mono text-[10px] text-accent/70 uppercase tracking-wider");
            cat.textContent = r.category;
            footer.appendChild(cat);
        }
        if (r.distance_km != null) {
            const dist = el("span", "font-mono text-[11px] text-accent/80 font-semibold flex-shrink-0");
            dist.textContent = r.distance_km < 1 ? "<1 km" : r.distance_km + " km";
            footer.appendChild(dist);
        }
        const dot = el("span", "");
        dot.textContent = "\u00B7";
        footer.appendChild(dot);
        const addr = el("span", "truncate");
        addr.textContent = truncate(r.address || "", 60);
        footer.appendChild(addr);

        card.appendChild(top);
        card.appendChild(brief);
        if (r.tags && r.tags.length > 0) card.appendChild(tagsWrap);
        card.appendChild(footer);

        return card;
    }

    // --- Lab Detail Page ---

    async function loadLabDetail(labId) {
        const header = document.getElementById("lab-header");
        const tableDiv = document.getElementById("capabilities-table");
        const backLink = document.getElementById("back-link");

        // Restore back link to search
        if (document.referrer && document.referrer.includes("?q=")) {
            backLink.href = document.referrer;
        }

        try {
            const resp = await fetch("/api/labs/" + labId);
            if (!resp.ok) {
                header.textContent = "";
                const err = el("div", "empty-state");
                err.textContent = "Lab not found.";
                header.appendChild(err);
                return;
            }
            const data = await resp.json();
            const lab = data.lab;
            const caps = data.capabilities;

            // Header
            header.textContent = "";

            const topMeta = el("div", "flex items-center gap-3 mb-4");
            const pill = el("span", "tag-pill");
            pill.textContent = "UKAS #" + (lab.accreditation_number || "");
            topMeta.appendChild(pill);
            if (lab.standard) {
                const stdPill = el("span", "font-mono text-[11px] text-slate-500");
                stdPill.textContent = lab.standard;
                topMeta.appendChild(stdPill);
            }
            header.appendChild(topMeta);

            const h1 = el("h1", "text-3xl sm:text-4xl font-display font-bold text-white leading-tight mb-8");
            h1.textContent = lab.lab_name;
            header.appendChild(h1);

            // Info grid
            const grid = el("div", "info-grid mb-10");
            const fields = [
                { label: "Address", value: lab.address },
                { label: "Contact", value: lab.contact },
                { label: "Phone", value: lab.phone },
                { label: "Email", value: lab.email, link: lab.email ? "mailto:" + lab.email : null },
                { label: "Website", value: lab.website, link: lab.website ? (lab.website.startsWith("http") ? lab.website : "https://" + lab.website) : null, external: true },
            ];

            fields.forEach((f) => {
                if (!f.value) return;
                const cell = el("div", "info-cell");
                const lbl = el("div", "info-cell-label");
                lbl.textContent = f.label;
                const val = el("div", "info-cell-value");
                if (f.link) {
                    const a = document.createElement("a");
                    a.href = f.link;
                    a.textContent = f.value;
                    if (f.external) { a.target = "_blank"; a.rel = "noopener"; }
                    val.appendChild(a);
                } else {
                    val.textContent = f.value || "\u2014";
                }
                cell.appendChild(lbl);
                cell.appendChild(val);
                grid.appendChild(cell);
            });

            header.appendChild(grid);

            // Fraglet summary (brief + capabilities from additional)
            if (data.fraglet) {
                const fragDiv = el("div", "mb-10 p-6 rounded-xl border border-white/[0.06] bg-white/[0.02]");

                // Brief
                if (data.fraglet.brief) {
                    const fragBrief = el("p", "text-sm text-slate-300 leading-relaxed mb-4");
                    fragBrief.textContent = data.fraglet.brief;
                    fragDiv.appendChild(fragBrief);
                }

                // Capability clusters from additional
                if (data.fraglet.additional && data.fraglet.additional.capabilities) {
                    const capsLabel = el("div", "font-mono text-[10px] text-accent tracking-widest uppercase mb-3");
                    capsLabel.textContent = "Accredited capabilities";
                    fragDiv.appendChild(capsLabel);
                    data.fraglet.additional.capabilities.forEach((cap) => {
                        const capCard = el("div", "mb-3 last:mb-0");
                        const capSummary = el("div", "text-sm text-white font-semibold mb-1");
                        capSummary.textContent = cap.summary || "";
                        capCard.appendChild(capSummary);
                        if (cap.materials_products) {
                            const matLine = el("div", "text-xs text-slate-400");
                            matLine.textContent = cap.materials_products;
                            capCard.appendChild(matLine);
                        }
                        if (cap.standards) {
                            const stdLine = el("div", "text-xs text-slate-500 font-mono mt-0.5");
                            stdLine.textContent = cap.standards;
                            capCard.appendChild(stdLine);
                        }
                        fragDiv.appendChild(capCard);
                    });
                }

                // Tags
                if (data.fraglet.tags && data.fraglet.tags.length > 0) {
                    const fragTags = el("div", "flex flex-wrap gap-1.5 mt-4");
                    data.fraglet.tags.forEach((t) => {
                        const pill = el("span", "tag-pill");
                        pill.textContent = t;
                        fragTags.appendChild(pill);
                    });
                    fragDiv.appendChild(fragTags);
                }

                header.appendChild(fragDiv);
            }

            // UKAS schedule PDF links
            if (data.schedule_pdfs && data.schedule_pdfs.length > 0) {
                const pdfDiv = el("div", "mb-10 flex flex-wrap gap-3");
                data.schedule_pdfs.forEach((url) => {
                    const a = document.createElement("a");
                    a.href = url;
                    a.target = "_blank";
                    a.rel = "noopener";
                    a.className = "inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 bg-white/[0.04] text-sm text-slate-300 hover:border-accent/50 hover:text-white transition-colors";
                    const label = url.includes("Calibration") ? "Calibration schedule" : "Testing schedule";
                    a.textContent = label + " (PDF)";
                    pdfDiv.appendChild(a);
                });
                header.appendChild(pdfDiv);
            }

            // Sites
            if (data.sites && data.sites.length > 0) {
                const sitesDiv = el("div", "mb-10");
                const sitesHeader = el("div", "flex items-center justify-between mb-4");
                const sitesTitle = el("h2", "text-xl font-display font-semibold text-white");
                sitesTitle.textContent = "Locations";
                const sitesCount = el("span", "font-mono text-xs text-slate-500");
                sitesCount.textContent = data.sites.length + " sites";
                sitesHeader.appendChild(sitesTitle);
                sitesHeader.appendChild(sitesCount);
                sitesDiv.appendChild(sitesHeader);

                const sitesGrid = el("div", "grid grid-cols-1 sm:grid-cols-2 gap-3");
                data.sites.forEach((s) => {
                    const siteCard = el("div", "p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]");
                    const sName = el("div", "font-semibold text-sm text-white mb-1");
                    sName.textContent = s.site_name || "Site";
                    siteCard.appendChild(sName);

                    const sAddr = el("div", "text-xs text-slate-400 mb-2");
                    sAddr.textContent = s.address || "";
                    siteCard.appendChild(sAddr);

                    if (s.capabilities_summary) {
                        const sCap = el("div", "text-xs text-slate-300");
                        sCap.textContent = s.capabilities_summary;
                        siteCard.appendChild(sCap);
                    }

                    if (!s.is_testing_site) {
                        const badge = el("span", "inline-block mt-2 font-mono text-[10px] text-slate-500 border border-slate-700 rounded px-1.5 py-0.5");
                        badge.textContent = "ADMIN ONLY";
                        siteCard.appendChild(badge);
                    }

                    sitesGrid.appendChild(siteCard);
                });
                sitesDiv.appendChild(sitesGrid);
                header.appendChild(sitesDiv);
            }

            // Capabilities
            if (!caps || caps.length === 0) {
                tableDiv.textContent = "";
                const empty = el("div", "empty-state");
                empty.textContent = "No capabilities listed.";
                tableDiv.appendChild(empty);
                return;
            }

            tableDiv.textContent = "";

            const capHeader = el("div", "flex items-center justify-between mb-4");
            const capTitle = el("h2", "text-xl font-display font-semibold text-white");
            capTitle.textContent = "Capabilities";
            const capCount = el("span", "font-mono text-xs text-slate-500");
            capCount.textContent = caps.length + " entries";
            capHeader.appendChild(capTitle);
            capHeader.appendChild(capCount);
            tableDiv.appendChild(capHeader);

            const wrapper = el("div", "overflow-x-auto rounded-xl border border-white/[0.06]");
            const table = document.createElement("table");
            table.className = "cap-table";

            const thead = document.createElement("thead");
            const headRow = document.createElement("tr");
            ["#", "Materials / Products", "Test Type", "Standards"].forEach((h) => {
                const th = document.createElement("th");
                th.textContent = h;
                headRow.appendChild(th);
            });
            thead.appendChild(headRow);
            table.appendChild(thead);

            const tbody = document.createElement("tbody");
            caps.forEach((c, i) => {
                const tr = document.createElement("tr");

                const idxTd = document.createElement("td");
                idxTd.className = "row-idx";
                idxTd.textContent = String(i + 1);
                tr.appendChild(idxTd);

                ["materials_products", "test_type", "standards"].forEach((field) => {
                    const td = document.createElement("td");
                    td.textContent = c[field] || "";
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });

            table.appendChild(tbody);
            wrapper.appendChild(table);
            tableDiv.appendChild(wrapper);

        } catch (err) {
            header.textContent = "";
            const errDiv = el("div", "empty-state");
            errDiv.textContent = "Failed to load lab details.";
            header.appendChild(errDiv);
        }
    }

    // --- Helpers ---

    function el(tag, className) {
        const e = document.createElement(tag);
        if (className) e.className = className;
        return e;
    }

    function renderMarkdownLight(container, text) {
        // Simple markdown: **bold**, - bullets, paragraphs
        const lines = text.split("\n");
        let ul = null;
        lines.forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed) {
                if (ul) { container.appendChild(ul); ul = null; }
                return;
            }
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                if (!ul) { ul = el("ul", "list-disc list-inside ml-2 mb-2 space-y-1"); }
                const li = document.createElement("li");
                applyBold(li, trimmed.slice(2));
                ul.appendChild(li);
            } else {
                if (ul) { container.appendChild(ul); ul = null; }
                const p = el("p", "mb-2");
                applyBold(p, trimmed);
                container.appendChild(p);
            }
        });
        if (ul) container.appendChild(ul);
    }

    function applyBold(parent, text) {
        // Split on **...**  and create <strong> elements
        const parts = text.split(/\*\*(.*?)\*\*/g);
        parts.forEach((part, i) => {
            if (i % 2 === 1) {
                const strong = document.createElement("strong");
                strong.className = "text-white";
                strong.textContent = part;
                parent.appendChild(strong);
            } else if (part) {
                parent.appendChild(document.createTextNode(part));
            }
        });
    }

    function truncate(s, n) {
        const clean = s.replace(/\n/g, " ").trim();
        return clean.length > n ? clean.slice(0, n) + "\u2026" : clean;
    }
})();
