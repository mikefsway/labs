// Search page logic
(function () {
    const searchInput = document.getElementById("search-input");
    const regionFilter = document.getElementById("region-filter");
    const resultsDiv = document.getElementById("results");
    const statusDiv = document.getElementById("status");

    // Lab detail page
    if (typeof LAB_ID !== "undefined") {
        loadLabDetail(LAB_ID);
        return;
    }

    if (!searchInput) return;

    let debounceTimer = null;

    // Restore from URL
    const params = new URLSearchParams(window.location.search);
    if (params.get("q")) {
        searchInput.value = params.get("q");
        if (params.get("region")) regionFilter.value = params.get("region");
        doSearch();
    }

    searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(doSearch, 400);
    });
    regionFilter.addEventListener("change", doSearch);

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            clearTimeout(debounceTimer);
            doSearch();
        }
    });

    async function doSearch() {
        const q = searchInput.value.trim();
        if (q.length < 2) {
            resultsDiv.textContent = "";
            statusDiv.classList.add("hidden");
            return;
        }

        const region = regionFilter.value;

        // Update URL
        const url = new URL(window.location);
        url.searchParams.set("q", q);
        if (region) url.searchParams.set("region", region);
        else url.searchParams.delete("region");
        history.replaceState(null, "", url);

        // Show loading
        statusDiv.textContent = "";
        const spinner = document.createElement("span");
        spinner.className = "spinner";
        statusDiv.appendChild(spinner);
        statusDiv.append(" Searching...");
        statusDiv.classList.remove("hidden");

        try {
            const apiUrl = `/api/search?q=${encodeURIComponent(q)}&limit=20${region ? "&region=" + encodeURIComponent(region) : ""}`;
            const resp = await fetch(apiUrl);
            const data = await resp.json();

            statusDiv.classList.add("hidden");
            resultsDiv.textContent = "";

            if (!data.results || data.results.length === 0) {
                const p = document.createElement("p");
                p.className = "text-center text-slate-400";
                p.textContent = "No results found.";
                resultsDiv.appendChild(p);
                return;
            }

            const maxRrf = data.results[0].rrf_score || 1;
            data.results.forEach((r) => resultsDiv.appendChild(buildResultCard(r, maxRrf)));
        } catch (err) {
            statusDiv.textContent = "";
            const errSpan = document.createElement("span");
            errSpan.className = "text-red-500";
            errSpan.textContent = "Search failed. Please try again.";
            statusDiv.appendChild(errSpan);
        }
    }

    function buildResultCard(r, maxRrf) {
        const pct = Math.round(((r.rrf_score || 0) / maxRrf) * 100);

        const card = document.createElement("a");
        card.href = `/lab/${r.lab_id}`;
        card.className = "block bg-white border border-slate-200 rounded-lg p-5 result-card";

        const topRow = document.createElement("div");
        topRow.className = "flex justify-between items-start mb-2";

        const info = document.createElement("div");
        const name = document.createElement("h3");
        name.className = "font-semibold text-blue-700";
        name.textContent = r.lab_name || "";
        const accred = document.createElement("span");
        accred.className = "text-xs text-slate-400";
        accred.textContent = "UKAS #" + (r.accreditation_number || "");
        info.appendChild(name);
        info.appendChild(accred);

        const barWrap = document.createElement("div");
        barWrap.className = "text-right";
        const bar = document.createElement("div");
        bar.className = "relevance-bar w-24";
        const fill = document.createElement("div");
        fill.className = "relevance-bar-fill";
        fill.style.width = pct + "%";
        bar.appendChild(fill);
        barWrap.appendChild(bar);

        topRow.appendChild(info);
        topRow.appendChild(barWrap);

        const materials = document.createElement("p");
        materials.className = "text-sm text-slate-700 mb-1";
        const matLabel = document.createElement("strong");
        matLabel.textContent = "Materials: ";
        materials.appendChild(matLabel);
        materials.append(truncate(r.materials_products || "", 120));

        const testType = document.createElement("p");
        testType.className = "text-sm text-slate-700 mb-1";
        const testLabel = document.createElement("strong");
        testLabel.textContent = "Test: ";
        testType.appendChild(testLabel);
        testType.append(truncate(r.test_type || "", 120));

        const addr = document.createElement("p");
        addr.className = "text-xs text-slate-400";
        addr.textContent = truncate(r.address || "", 80);

        card.appendChild(topRow);
        card.appendChild(materials);
        card.appendChild(testType);
        card.appendChild(addr);

        return card;
    }

    function truncate(s, n) {
        const clean = s.replace(/\n/g, " ").trim();
        return clean.length > n ? clean.slice(0, n) + "\u2026" : clean;
    }

    // Lab detail page
    async function loadLabDetail(labId) {
        const header = document.getElementById("lab-header");
        const tableDiv = document.getElementById("capabilities-table");

        try {
            const resp = await fetch(`/api/labs/${labId}`);
            if (!resp.ok) {
                header.textContent = "Lab not found.";
                return;
            }
            const data = await resp.json();
            const lab = data.lab;
            const caps = data.capabilities;

            // Build header
            header.textContent = "";

            const h1 = document.createElement("h1");
            h1.className = "text-3xl font-bold text-slate-800 mb-1";
            h1.textContent = lab.lab_name;

            const sub = document.createElement("p");
            sub.className = "text-slate-500 mb-4";
            sub.textContent = `UKAS Accreditation #${lab.accreditation_number} \u00B7 ${lab.standard || ""}`;

            const grid = document.createElement("div");
            grid.className = "grid grid-cols-1 md:grid-cols-2 gap-4 bg-white border border-slate-200 rounded-lg p-5";

            const addrBlock = document.createElement("div");
            const addrLabel = document.createElement("p");
            addrLabel.className = "text-sm text-slate-500";
            addrLabel.textContent = "Address";
            const addrVal = document.createElement("p");
            addrVal.className = "text-sm";
            addrVal.textContent = lab.address || "\u2014";
            addrBlock.appendChild(addrLabel);
            addrBlock.appendChild(addrVal);

            const contactBlock = document.createElement("div");
            const contactLabel = document.createElement("p");
            contactLabel.className = "text-sm text-slate-500";
            contactLabel.textContent = "Contact";
            contactBlock.appendChild(contactLabel);

            if (lab.contact) {
                const c = document.createElement("p");
                c.className = "text-sm";
                c.textContent = lab.contact;
                contactBlock.appendChild(c);
            }
            if (lab.phone) {
                const p = document.createElement("p");
                p.className = "text-sm";
                p.textContent = lab.phone;
                contactBlock.appendChild(p);
            }
            if (lab.email) {
                const p = document.createElement("p");
                p.className = "text-sm";
                const a = document.createElement("a");
                a.href = "mailto:" + lab.email;
                a.className = "text-blue-600 hover:underline";
                a.textContent = lab.email;
                p.appendChild(a);
                contactBlock.appendChild(p);
            }
            if (lab.website) {
                const p = document.createElement("p");
                p.className = "text-sm";
                const a = document.createElement("a");
                a.href = lab.website.startsWith("http") ? lab.website : "https://" + lab.website;
                a.target = "_blank";
                a.rel = "noopener";
                a.className = "text-blue-600 hover:underline";
                a.textContent = lab.website;
                p.appendChild(a);
                contactBlock.appendChild(p);
            }

            grid.appendChild(addrBlock);
            grid.appendChild(contactBlock);

            header.appendChild(h1);
            header.appendChild(sub);
            header.appendChild(grid);

            // Build capabilities table
            if (!caps || caps.length === 0) {
                tableDiv.textContent = "No capabilities listed.";
                return;
            }

            tableDiv.textContent = "";

            const heading = document.createElement("h2");
            heading.className = "text-xl font-semibold text-slate-700 mb-3";
            heading.textContent = caps.length + " Capabilities";
            tableDiv.appendChild(heading);

            const wrapper = document.createElement("div");
            wrapper.className = "overflow-x-auto";

            const table = document.createElement("table");
            table.className = "w-full text-sm border-collapse";

            const thead = document.createElement("thead");
            const headRow = document.createElement("tr");
            headRow.className = "bg-slate-100 text-left";
            ["Materials / Products", "Test Type", "Standards"].forEach((h) => {
                const th = document.createElement("th");
                th.className = "px-3 py-2 border-b font-medium text-slate-600";
                th.textContent = h;
                headRow.appendChild(th);
            });
            thead.appendChild(headRow);
            table.appendChild(thead);

            const tbody = document.createElement("tbody");
            caps.forEach((c) => {
                const tr = document.createElement("tr");
                tr.className = "border-b border-slate-100 hover:bg-slate-50";
                ["materials_products", "test_type", "standards"].forEach((field) => {
                    const td = document.createElement("td");
                    td.className = "px-3 py-2 align-top whitespace-pre-line";
                    td.textContent = c[field] || "";
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            wrapper.appendChild(table);
            tableDiv.appendChild(wrapper);

        } catch (err) {
            header.textContent = "Failed to load lab details.";
        }
    }
})();
