/* Map page: markers, filters, sites list, nearby search, choropleth.
 *
 * All data comes from the REST API (/api/...). Text from the data is always
 * inserted with textContent (through el()), never as HTML.
 */
"use strict";

(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const desktop = window.matchMedia("(min-width: 992px)");
  const tablet = window.matchMedia("(min-width: 768px)");
  const $ = (selector) => document.querySelector(selector);

  const mapElement = $("#map");
  const filterForm = $("#filters");
  const sidebar = $("#sidebar");
  const HINT_KEY = "aidcm.hintDismissed";

  // ---- Small helpers --------------------------------------------------

  /** Create an element. Strings in children become text nodes. */
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (name === "class") node.className = value;
      else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
      else node.setAttribute(name, value === true ? "" : value);
    }
    for (const child of children.flat(Infinity)) {
      if (child !== null && child !== undefined) node.append(child);
    }
    return node;
  }

  const fmtMW = (mw) => `${Math.round(mw).toLocaleString("en")} MW`;
  const fmtCost = (busd) => `$${busd.toFixed(1)}B`;
  /** Short H100-equivalent count: 1.11M, 293k or 850. */
  function shortCount(n) {
    if (n >= 1e6) return `${Number((n / 1e6).toFixed(2))}M`;
    if (n >= 1e3) return `${Math.round(n / 1e3).toLocaleString("en")}k`;
    return String(Math.round(n));
  }
  const fmtH100e = (n) => `${shortCount(n)} H100e`;
  // Epoch AI records only current figures, so a site that is not running
  // yet has 0 MW and $0 cost. Show that in words instead of as a zero.
  const NOT_OPERATIONAL = "Not yet operational";
  const siteMW = (props) => (props.power_mw > 0 ? fmtMW(props.power_mw) : NOT_OPERATIONAL);
  const siteH100e = (props) => (props.h100e > 0 ? fmtH100e(props.h100e) : "—");
  const siteCost = (props) => (props.capital_cost_busd > 0 ? fmtCost(props.capital_cost_busd) : "—");
  const fmtKm = (km) => `${km < 10 ? km.toFixed(1) : Math.round(km).toLocaleString("en")} km`;
  const FIELD_LABELS = { lat: "Latitude", lon: "Longitude", km: "Radius", n: "Number of sites" };

  // ---- API ------------------------------------------------------------

  class ApiError extends Error {}

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  let pending = 0;
  function setLoading(delta) {
    pending += delta;
    $("#loading").hidden = pending === 0;
    mapElement.setAttribute("aria-busy", pending > 0 ? "true" : "false");
  }

  /** GET a JSON API path; failures become an ApiError with a plain message. */
  async function api(path, params) {
    const url = params && params.toString() ? `${path}?${params}` : path;
    setLoading(1);
    try {
      let response;
      try {
        response = await fetch(url, {
          credentials: "same-origin",
          headers: { Accept: "application/json", "X-CSRFToken": csrfToken() },
        });
      } catch {
        throw new ApiError("Cannot reach the server. Check your connection and try again.");
      }
      if (response.ok) return response.json();
      const body = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) {
        throw new ApiError("Your session has ended. Please sign in again.");
      }
      if (response.status === 404) throw new ApiError(body.detail || "Nothing was found here.");
      if (response.status === 400) {
        const messages = Object.entries(body).map(
          ([field, errors]) => `${FIELD_LABELS[field] || field}: ${[].concat(errors).join(" ")}`,
        );
        throw new ApiError(messages.join(" ") || "Some values are not valid.");
      }
      throw new ApiError("Something went wrong on the server. Please try again.");
    } finally {
      setLoading(-1);
    }
  }

  function showAlert(message) {
    const alert = el(
      "div",
      { class: "alert alert-app alert-dismissible", role: "alert" },
      el("span", { "aria-hidden": "true" }, "⚠ "),
      message,
      el("button", { type: "button", class: "btn-close", "data-bs-dismiss": "alert", "aria-label": "Close message" }),
    );
    $("#alerts").replaceChildren(alert);
  }

  /** Run an async task and show any error as an alert. */
  async function run(task) {
    try {
      await task();
    } catch (error) {
      if (error instanceof ApiError) showAlert(error.message);
      else {
        console.error(error);
        showAlert("Something went wrong. Please try again.");
      }
    }
  }

  // ---- Map ------------------------------------------------------------

  const map = L.map(mapElement, {
    keyboard: true,
    worldCopyJump: true,
    zoomAnimation: !reduceMotion,
    fadeAnimation: !reduceMotion,
    markerZoomAnimation: !reduceMotion,
  }).setView([30, 0], 2);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  map.attributionControl.addAttribution(
    'Data: <a href="https://epoch.ai/data/data_centers">Epoch AI</a> (CC BY) · Borders: Natural Earth',
  );

  map.createPane("choropleth").style.zIndex = 350; // below the markers and results
  const choroplethLayer = L.layerGroup();
  const linksLayer = L.layerGroup();
  const queryLayer = L.layerGroup().addTo(map);
  const resultsLayer = L.layerGroup().addTo(map);
  // From this zoom on every marker is drawn on its own, so a site chosen
  // from a list is visible under its popup.
  const SITE_ZOOM = 9;
  const cluster = L.markerClusterGroup({
    showCoverageOnHover: false,
    maxClusterRadius: 40,
    disableClusteringAtZoom: SITE_ZOOM,
    animate: !reduceMotion,
    iconCreateFunction: (group) =>
      L.divIcon({ html: String(group.getChildCount()), className: "cluster-icon", iconSize: L.point(36, 36) }),
  }).addTo(map);

  const fitOptions = { padding: [30, 30], maxZoom: 8, animate: !reduceMotion };

  // ---- Markers --------------------------------------------------------

  let sites = []; // GeoJSON features currently shown

  // Circle size: area proportional to the chosen value, as on the Epoch AI
  // map. legend[0] is drawn at MAX_RADIUS; the other two show the scale.
  const MAX_RADIUS = 22;
  const MIN_RADIUS = 3;
  const SIZES = {
    power_mw: { title: "IT Power (MW)", legend: [1000, 500, 100], format: fmtMW, short: (v) => v.toLocaleString("en") },
    capital_cost_busd: { title: "Capital cost ($B)", legend: [40, 16, 4], format: fmtCost, short: (v) => `$${v}B` },
    h100e: { title: "H100 equivalents", legend: [1e6, 4e5, 1e5], format: fmtH100e, short: shortCount },
  };
  const NAVY = "#13294b";
  const sizeMetric = () => filterForm.elements.size.value;

  function radiusFor(value, metric = sizeMetric()) {
    const reference = SIZES[metric].legend[0];
    return Math.max(MIN_RADIUS, MAX_RADIUS * Math.sqrt(Math.max(value, 0) / reference));
  }

  function markerStyle(props) {
    // bubblingMouseEvents: false, so tapping a site opens its popup and
    // does not also count as a tap on the map (which picks a search point).
    return {
      radius: radiusFor(props[sizeMetric()]), color: "#fff", weight: 1, fillColor: NAVY, fillOpacity: 0.9,
      bubblingMouseEvents: false,
    };
  }

  function popupContent(props) {
    const rows = [
      ["Owner", props.owner],
      ["Users", props.users || "—"],
      ["Country", props.country || "—"],
      ["IT Power", siteMW(props)],
      ["Capital cost", siteCost(props)],
      ["H100 equivalents", siteH100e(props)],
    ];
    if (props.nearest_km !== null && props.nearest_km !== undefined) {
      rows.push(["Nearest other site", fmtKm(props.nearest_km)]);
    }
    return el(
      "div",
      { class: "site-popup" },
      el("h2", { class: "h6" }, props.name),
      el("dl", {}, rows.map(([term, value]) => [el("dt", {}, term), el("dd", {}, value)])),
    );
  }

  function latLngOf(feature) {
    const [lon, lat] = feature.geometry.coordinates;
    return L.latLng(lat, lon);
  }

  function renderMarkers() {
    const metric = SIZES[sizeMetric()];
    // A marker removed under the mouse never gets "mouseout", so close its
    // tooltip first or it stays on the map.
    cluster.eachLayer((layer) => layer.closeTooltip());
    cluster.clearLayers();
    cluster.addLayers(
      sites.map((feature) => {
        const props = feature.properties;
        const marker = L.circleMarker(latLngOf(feature), markerStyle(props));
        marker.bindPopup(() => popupContent(props));
        // Hover shows the value the circle is sized by, e.g. "1,037 MW".
        const value = props[sizeMetric()];
        marker.bindTooltip(value > 0 ? metric.format(value) : NOT_OPERATIONAL, {
          direction: "top",
          offset: [0, -marker.getRadius()],
          className: "value-tooltip",
        });
        return marker;
      }),
    );
    renderSizeLegend();
  }

  /** Zoom to a site chosen from a list and open its popup.
   *
   * A standalone popup, not the marker's own: nearby searches cover all
   * sites, so the site may be hidden by the filters. (markercluster's
   * zoomToShowLayer never calls back for circle markers.)
   */
  function showSite(feature) {
    if (!desktop.matches) bootstrap.Offcanvas.getOrCreateInstance(sidebar).hide();
    const latlng = latLngOf(feature);
    map.once("moveend", () =>
      L.popup({ offset: [0, -4] }).setLatLng(latlng).setContent(popupContent(feature.properties)).openOn(map),
    );
    map.setView(latlng, Math.max(map.getZoom(), SITE_ZOOM), { animate: !reduceMotion });
  }

  function siteButton(feature, detail) {
    return el(
      "li",
      {},
      el(
        "button",
        { type: "button", "data-id": feature.id, onclick: () => showSite(feature) },
        feature.properties.name,
        el("span", { class: "detail" }, detail),
      ),
    );
  }

  // ---- Filters --------------------------------------------------------

  const RANGES = [
    { min: "mw_min", max: "mw_max", error: "#mw-error", label: "IT Power", unit: (v) => `${v.toLocaleString("en")} MW` },
    { min: "cost_min", max: "cost_max", error: "#cost-error", label: "Capital cost", unit: (v) => `$${v}B` },
    { min: "h100e_min", max: "h100e_max", error: "#h100e-error", label: "H100e", unit: shortCount },
  ];

  /** Check the min/max fields before calling the API. */
  function validateFilters() {
    let valid = true;
    for (const range of RANGES) {
      const inputs = [filterForm.elements[range.min], filterForm.elements[range.max]];
      const error = $(range.error);
      let message = "";
      inputs.forEach((input) => input.removeAttribute("aria-invalid"));
      for (const input of inputs) {
        const value = Number(input.value);
        if (input.validity.badInput || (input.value !== "" && (!Number.isFinite(value) || value < 0))) {
          message = `${range.label}: enter a number of 0 or more.`;
          input.setAttribute("aria-invalid", "true");
        }
      }
      const [min, max] = inputs.map((input) => input.value);
      if (!message && min !== "" && max !== "" && Number(min) > Number(max)) {
        message = `${range.label}: the minimum is larger than the maximum.`;
        inputs.forEach((input) => input.setAttribute("aria-invalid", "true"));
      }
      error.textContent = message ? `⚠ ${message}` : "";
      error.hidden = !message;
      if (message) valid = false;
    }
    return valid;
  }

  const inViewBox = $("#f-in-view");

  /** The visible map area as "min_lon,min_lat,max_lon,max_lat" for ?bbox=.
   *
   * Leaflet longitudes keep growing past ±180 when the user pans round the
   * world, so the box is shifted back into -180..180 first. A view that
   * crosses the date line, or shows the whole world, uses every longitude.
   */
  function viewBbox() {
    const bounds = map.getBounds();
    let west = bounds.getWest();
    let east = bounds.getEast();
    const shift = Math.floor((west + 180) / 360) * 360;
    west -= shift;
    east -= shift;
    if (east - west >= 360 || east > 180) [west, east] = [-180, 180];
    const south = Math.max(bounds.getSouth(), -90);
    const north = Math.min(bounds.getNorth(), 90);
    return [west, south, east, north].map((n) => n.toFixed(4)).join(",");
  }

  /** Query string for the API: search + filters ("size" only changes the drawing). */
  function filterParams() {
    const params = new URLSearchParams();
    for (const [name, value] of new FormData(filterForm)) {
      if (name !== "size" && String(value).trim() !== "") params.append(name, String(value).trim());
    }
    if (inViewBox.checked) params.set("bbox", viewBbox());
    return params;
  }

  /** Number of active filters, shown on the Filter button. */
  function updateFilterCount() {
    const active = [...filterParams().keys()].filter((name) => name !== "search");
    const owners = active.filter((name) => name === "owner").length;
    const count = active.length - Math.max(owners - 1, 0); // several owners count as one filter
    $("#filter-count").textContent = count ? String(count) : "";
    $("#filter-toggle").setAttribute("aria-label", count ? `Filter, ${count} active` : "Filter");
    renderChips();
  }

  // ---- Active filter chips ------------------------------------------
  // One removable chip per active filter under the toolbar, so the filters
  // stay visible with the menu closed (search has its own box).

  /** The active filters as {label, clear} pairs, read from the form. */
  function activeFilters() {
    const chips = [];
    for (const option of filterForm.elements.owner.selectedOptions) {
      chips.push({ label: `Owner: ${option.value}`, clear: () => (option.selected = false) });
    }
    const country = filterForm.elements.country;
    if (country.value) chips.push({ label: `Country: ${country.value}`, clear: () => (country.value = "") });
    for (const range of RANGES) {
      const min = filterForm.elements[range.min];
      const max = filterForm.elements[range.max];
      const [lo, hi] = [min.value.trim(), max.value.trim()];
      if (!lo && !hi) continue;
      const text = lo && hi ? `${range.unit(Number(lo))}–${range.unit(Number(hi))}`
        : lo ? `≥ ${range.unit(Number(lo))}` : `≤ ${range.unit(Number(hi))}`;
      chips.push({ label: `${range.label} ${text}`, clear: () => (min.value = max.value = "") });
    }
    if (inViewBox.checked) chips.push({ label: "In map view", clear: () => (inViewBox.checked = false) });
    return chips;
  }

  let chipFocus = null; // index of a removed chip, to move focus to its neighbour

  function removeFilters(clears, index) {
    clears.forEach((clear) => clear());
    chipFocus = index;
    if (validateFilters()) run(() => loadSites({ fit: false }));
  }

  function renderChips() {
    const box = $("#filter-chips");
    const chips = activeFilters();
    const buttons = chips.map(({ label, clear }, i) =>
      el(
        "button",
        { type: "button", class: "btn btn-sm filter-chip", "aria-label": `Remove filter: ${label}`, onclick: () => removeFilters([clear], i) },
        label,
        el("span", { "aria-hidden": "true" }, "×"),
      ),
    );
    if (chips.length > 1) {
      buttons.push(
        el("button", { type: "button", class: "btn btn-sm btn-link filter-chips-clear", onclick: () => removeFilters(chips.map((c) => c.clear), 0) }, "Clear all"),
      );
    }
    box.replaceChildren(...buttons);
    box.hidden = chips.length === 0;
    if (chipFocus !== null) {
      // The chip that had focus is gone: focus its neighbour, or the Filter button.
      const chipButtons = box.querySelectorAll(".filter-chip");
      (chipButtons[Math.min(chipFocus, chipButtons.length - 1)] || $("#filter-toggle")).focus();
      chipFocus = null;
    }
  }

  let latestLoad = 0;
  async function loadSites({ fit }) {
    const load = ++latestLoad;
    const data = await api("/api/datacenters/", filterParams());
    if (load !== latestLoad) return; // a newer search is already running
    sites = data.features;
    renderMarkers();
    updateFilterCount();
    $("#result-count").textContent = `${sites.length} ${sites.length === 1 ? "result" : "results"}`;
    $("#empty").hidden = sites.length > 0;
    // A rebuilt list (e.g. "Only sites in map view" after a pan) would drop
    // keyboard focus to the page: give it back to the same site, or to the
    // list panel if that site is no longer listed.
    const focused = document.activeElement.closest("#sites-list button")?.dataset.id;
    $("#sites-list").replaceChildren(
      ...sites.map((f) => siteButton(f, `${f.properties.owner} · ${siteMW(f.properties)}`)),
    );
    if (focused) ($(`#sites-list button[data-id="${focused}"]`) || $("#pane-sites")).focus();
    if (linksOn()) drawLinks();
    if (fit && sites.length) map.fitBounds(cluster.getBounds(), fitOptions);
  }

  function applyFilters() {
    if (!validateFilters()) return; // keep the menu open to show the errors
    bootstrap.Dropdown.getOrCreateInstance($("#filter-toggle")).hide();
    // With "Only sites in map view" the view is the filter, so keep it.
    run(() => loadSites({ fit: !inViewBox.checked }));
  }

  function resetFilters() {
    filterForm.reset();
    validateFilters();
    run(() => loadSites({ fit: false }));
    map.setView([30, 0], 2, { animate: !reduceMotion });
  }

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });
  $("#reset-filters").addEventListener("click", resetFilters);
  $("#empty-reset").addEventListener("click", resetFilters);

  // Search as you type, once typing pauses.
  let searchTimer;
  $("#f-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      if (validateFilters()) run(() => loadSites({ fit: false }));
    }, 300);
  });

  for (const toggle of filterForm.elements.size) toggle.addEventListener("change", renderMarkers);

  // The page itself never scrolls, so a dropdown taller than the space below
  // its button (phones, landscape) scrolls inside instead of being cut off.
  function fitMenu(menu) {
    // Measured from the button: Bootstrap positions the menu just after
    // "shown", so the menu's own position is not final yet.
    const button = menu.parentElement.querySelector("[data-bs-toggle='dropdown']");
    const top = button.getBoundingClientRect().bottom + 2; // Bootstrap's default 2 px offset
    menu.style.maxHeight = `${Math.max(160, window.innerHeight - top - 8)}px`;
  }
  for (const menu of document.querySelectorAll(".filter-menu, .help-menu")) {
    menu.parentElement.addEventListener("shown.bs.dropdown", () => fitMenu(menu));
  }
  window.addEventListener("resize", () => document.querySelectorAll(".dropdown-menu.show").forEach(fitMenu));

  // ⓘ buttons in the filter menu show or hide a one-line explanation.
  for (const button of document.querySelectorAll("[data-help-toggle]")) {
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      document.getElementById(button.getAttribute("aria-controls")).hidden = !open;
    });
  }

  // "Only sites in map view": reload when ticked, and after each pan or zoom.
  inViewBox.addEventListener("change", () => {
    if (validateFilters()) run(() => loadSites({ fit: false }));
  });
  let viewTimer;
  map.on("moveend", () => {
    if (!inViewBox.checked) return;
    clearTimeout(viewTimer);
    viewTimer = setTimeout(() => {
      if (validateFilters()) run(() => loadSites({ fit: false }));
    }, 300);
  });

  // ---- Sidebar placement on small screens ----------------------------

  function setPlacement(placement) {
    sidebar.classList.remove("offcanvas-start", "offcanvas-end", "offcanvas-bottom");
    sidebar.classList.add(`offcanvas-${placement}`);
  }

  /** Below 992 px the nearby panel slides in from the bottom (phone) or right (tablet). */
  function openNearbyPanel() {
    if (desktop.matches || sidebar.classList.contains("show")) return;
    setPlacement(tablet.matches ? "end" : "bottom");
    bootstrap.Offcanvas.getOrCreateInstance(sidebar).show();
  }

  sidebar.addEventListener("hidden.bs.offcanvas", () => {
    setPlacement("start"); // the ☰ button opens the filters from the left
    map.invalidateSize();
  });
  sidebar.addEventListener("shown.bs.offcanvas", () => map.invalidateSize());
  window.addEventListener("resize", () => map.invalidateSize());

  // ---- Nearby search -------------------------------------------------

  let queryPoint = null;
  const actionButtons = ["#run-nearest", "#run-within", "#run-country"].map((id) => $(id));

  function choosePoint(latlng) {
    queryPoint = latlng.wrap();
    queryLayer.clearLayers();
    clearResults();
    L.marker(latlng, {
      icon: L.divIcon({ className: "query-point", html: "✕", iconSize: [24, 24] }),
      interactive: false,
      keyboard: false,
    }).addTo(queryLayer);
    $("#query-point").textContent = `Point: ${queryPoint.lat.toFixed(2)}, ${queryPoint.lng.toFixed(2)}`;
    actionButtons.forEach((button) => (button.disabled = false));
    $("#clear-point").hidden = false;
    bootstrap.Tab.getOrCreateInstance($("#tab-nearby")).show();
    dismissHint();
  }

  function pointParams(extra = {}) {
    return new URLSearchParams({ lat: queryPoint.lat.toFixed(6), lon: queryPoint.lng.toFixed(6), ...extra });
  }

  function clearResults() {
    resultsLayer.clearLayers();
    $("#results-heading").hidden = true;
    $("#results").replaceChildren();
  }

  function showResults(heading, items) {
    $("#results-heading").textContent = heading;
    $("#results-heading").hidden = false;
    $("#results").replaceChildren(
      ...(items.length ? items : [el("li", { class: "text-secondary py-2" }, "No sites found.")]),
    );
  }

  function fitTo(layer) {
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, fitOptions);
  }

  async function nearest() {
    const data = await api("/api/datacenters/nearest/", pointParams({ n: 5 }));
    clearResults();
    const lines = L.geoJSON(
      data.features.map((f) => f.properties.link),
      { style: { color: "#000", weight: 2, dashArray: "6 6" }, interactive: false },
    ).addTo(resultsLayer);
    fitTo(lines);
    showResults(
      `Nearest ${data.features.length} sites`,
      data.features.map((f) =>
        siteButton(f, `${fmtKm(f.properties.distance_km)} · ${siteMW(f.properties)}`),
      ),
    );
  }

  function validRadius() {
    const input = $("#within-km");
    const error = $("#within-error");
    const km = Number(input.value);
    const ok = input.value !== "" && Number.isFinite(km) && km > 0 && km <= 5000;
    if (ok) input.removeAttribute("aria-invalid");
    else input.setAttribute("aria-invalid", "true");
    error.textContent = ok ? "" : "⚠ Enter a radius from 1 to 5000 km.";
    error.hidden = ok;
    return ok ? km : null;
  }

  async function within(km) {
    const data = await api("/api/datacenters/within/", pointParams({ km }));
    clearResults();
    const buffer = L.geoJSON(data.buffer, {
      style: { color: "#000", weight: 2, fillColor: "#000", fillOpacity: 0.1 },
      interactive: false,
    }).addTo(resultsLayer);
    fitTo(buffer);
    const found = data.sites.features;
    showResults(
      `${found.length} ${found.length === 1 ? "site" : "sites"} within ${fmtKm(km)}`,
      found.map((f) => siteButton(f, `${fmtKm(f.properties.distance_km)} · ${siteMW(f.properties)}`)),
    );
  }

  async function countryHere() {
    clearResults();
    const data = await api("/api/countries/at/", pointParams());
    const outline = L.geoJSON(data.country, { style: { color: "#000", weight: 4, fill: false }, interactive: false })
      .addTo(resultsLayer);
    fitTo(outline);
    const c = data.country.properties;
    showResults(
      `${c.name}: ${c.site_count} ${c.site_count === 1 ? "site" : "sites"} · ${fmtMW(c.total_mw)} · ${fmtCost(c.total_cost_busd)}`,
      data.sites.features.map((f) => siteButton(f, `${f.properties.owner} · ${siteMW(f.properties)}`)),
    );
  }

  /** Popup at a tapped point offering the three nearby searches.
   *
   * Phones and tablets only: there the panel is hidden (a bottom sheet or a
   * side drawer) and opens only once the user picks a search, so a tap to
   * look around the map does not cover it. On desktop the Nearby tab is
   * always visible and already has these buttons.
   */
  function pointPopup(latlng) {
    const action = (label, primary, task) => {
      const button = el("button", { class: `btn ${primary ? "btn-dark" : "btn-outline-dark"} btn-sm`, type: "button" }, label);
      button.addEventListener("click", () => {
        map.closePopup();
        openNearbyPanel();
        task();
      });
      return button;
    };
    const content = el(
      "div",
      { class: "point-popup" },
      el("h2", { class: "h6" }, "Search near this point"),
      action($("#run-nearest").textContent, true, () => run(nearest)),
      action($("#run-within").textContent, true, () => {
        const radius = validRadius();
        if (radius !== null) run(() => within(radius));
      }),
      action("Country here", false, () => run(countryHere)),
    );
    L.popup({ className: "point-popup-wrap", maxWidth: 240 }).setLatLng(latlng).setContent(content).openOn(map);
  }

  map.on("click", (event) => {
    choosePoint(event.latlng);
    if (!desktop.matches) pointPopup(event.latlng);
  });
  $("#use-centre").addEventListener("click", () => choosePoint(map.getCenter()));

  /** Undo a nearby search: remove the point, its results and their shapes. */
  function clearPoint() {
    queryPoint = null;
    queryLayer.clearLayers();
    clearResults();
    map.closePopup();
    $("#query-point").textContent = "No point chosen yet. Click the map, or search around the map centre.";
    actionButtons.forEach((button) => (button.disabled = true));
    $("#clear-point").hidden = true;
    $("#use-centre").focus(); // the clear button is gone; keep keyboard focus in the panel
  }
  $("#clear-point").addEventListener("click", clearPoint);

  // The radius button names its search, e.g. "Find within 250 km".
  $("#within-km").addEventListener("input", () => {
    const km = Number($("#within-km").value);
    const valid = $("#within-km").value !== "" && Number.isFinite(km) && km > 0 && km <= 5000;
    $("#run-within").textContent = valid ? `Find within ${km.toLocaleString("en")} km` : "Find within radius";
    if (valid) validRadius(); // a corrected value clears the old error message
  });
  $("#run-nearest").addEventListener("click", () => run(nearest));
  $("#run-country").addEventListener("click", () => run(countryHere));
  $("#within-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const km = validRadius();
    if (km !== null) run(() => within(km));
  });

  // ---- Map controls: choropleth and cluster links ---------------------

  const RAMP = [
    { below: 500, fill: "#d9d9d9", label: "< 500" },
    { below: 2000, fill: "#a6a6a6", label: "< 2 000" },
    { below: 10000, fill: "#595959", label: "< 10 000" },
    { below: Infinity, fill: "#000", label: "≥ 10 000" },
  ];
  const rampFill = (mw) => (mw <= 0 ? "#fff" : RAMP.find((step) => mw < step.below).fill);

  const choroplethLegend = L.control({ position: "bottomright" });
  choroplethLegend.onAdd = () =>
    el(
      "div",
      { class: "map-legend" },
      el("div", { class: "fw-bold" }, "Total MW per country"),
      el("div", {}, el("span", { class: "ramp", style: "background:#fff" }), "0"),
      RAMP.map((step) => el("div", {}, el("span", { class: "ramp", style: `background:${step.fill}` }), step.label)),
    );

  let choroplethLoaded = false;
  async function toggleChoropleth(on) {
    if (!on) {
      map.removeLayer(choroplethLayer);
      choroplethLegend.remove();
      return;
    }
    if (!choroplethLoaded) {
      const data = await api("/api/countries/stats/");
      L.geoJSON(data, {
        pane: "choropleth",
        style: (f) => ({ fillColor: rampFill(f.properties.total_mw), fillOpacity: 0.75, color: "#000", weight: 0.5 }),
        onEachFeature: (f, layer) => {
          const p = f.properties;
          layer.bindTooltip(el("span", {}, `${p.name}: ${fmtMW(p.total_mw)} · ${p.site_count} sites`), { sticky: true });
        },
      }).addTo(choroplethLayer);
      choroplethLoaded = true;
    }
    choroplethLayer.addTo(map);
    choroplethLegend.addTo(map);
  }

  const linksOn = () => $("#toggle-links").checked;
  function drawLinks() {
    linksLayer.clearLayers();
    const links = sites.map((f) => f.properties.nearest_link).filter(Boolean);
    L.geoJSON(links, { style: { color: "#555", weight: 1 }, interactive: false }).addTo(linksLayer);
  }
  function toggleLinks(on) {
    if (on) {
      drawLinks();
      linksLayer.addTo(map);
    } else {
      map.removeLayer(linksLayer);
    }
  }

  function checkbox(id, text, description, onChange) {
    const input = el("input", { class: "form-check-input", type: "checkbox", id, "aria-describedby": `${id}-help` });
    input.addEventListener("change", () => run(() => onChange(input.checked)));
    return el(
      "div",
      { class: "form-check" },
      input,
      el("label", { class: "form-check-label", for: id }, text),
      el("div", { class: "layer-help", id: `${id}-help` }, description),
    );
  }

  // Layer checkboxes and the size legend share one <details> control. It is
  // open on wider screens; on phones (portrait or landscape) it is a single
  // "Layers" button, so nothing covers the small map.
  const phone = window.matchMedia("(max-width: 575.98px), (max-height: 500px)");
  const sizeLegend = el("div", { class: "size-legend" });
  const layersBox = el(
    "details",
    { class: "map-toggles" },
    el("summary", {}, "Layers"),
    checkbox("toggle-choropleth", "Choropleth (MW)", "Shades countries by total IT power.", toggleChoropleth),
    checkbox("toggle-links", "Cluster links", "Joins each site to its nearest other site.", toggleLinks),
    sizeLegend,
  );
  layersBox.open = !phone.matches;
  const toggles = L.control({ position: "topright" });
  toggles.onAdd = () => {
    L.DomEvent.disableClickPropagation(layersBox);
    L.DomEvent.disableScrollPropagation(layersBox);
    return layersBox;
  };
  toggles.addTo(map);
  // Collapse again when the screen becomes phone-sized (rotation, resize)
  // and after a tap on the map, so the box never stays over the map there.
  phone.addEventListener("change", (event) => (layersBox.open = !event.matches));
  map.on("click", () => {
    if (phone.matches) layersBox.open = false;
  });

  /** "Circles sized by …" with three nested reference circles. */
  function renderSizeLegend() {
    const metric = SIZES[sizeMetric()];
    const size = MAX_RADIUS * 2 + 2;
    const labelX = size + 8;
    // Nested circles sharing their bottom edge; each label sits to the right
    // of its circle's top, joined by a short line.
    const circles = metric.legend
      .map((value, i) => {
        const r = radiusFor(value);
        const top = size - 1 - 2 * r;
        const labelY = Math.max(top, i * 12) + 4;
        return `<circle cx="${size / 2}" cy="${size - 1 - r}" r="${r}" fill="none" stroke="#000"/>` +
          `<line x1="${size / 2}" y1="${top}" x2="${labelX - 2}" y2="${labelY - 4}" stroke="#555" stroke-width="0.75"/>` +
          `<text x="${labelX}" y="${labelY}">${metric.short(value)}</text>`;
      })
      .join("");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", size + 44);
    svg.setAttribute("height", size);
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = circles; // built only from the constants above
    sizeLegend.replaceChildren(
      el("div", { class: "legend-intro" }, "Circles sized by"),
      el("div", { class: "fw-bold" }, metric.title),
      svg,
      el("div", { class: "visually-hidden" }, `Reference sizes: ${metric.legend.map(metric.format).join(", ")}.`),
    );
  }

  // ---- First-visit hint and keyboard ---------------------------------

  function dismissHint() {
    $("#hint").hidden = true;
    try {
      localStorage.setItem(HINT_KEY, "1");
    } catch {
      /* private mode: the hint simply shows again next time */
    }
  }
  try {
    $("#hint").hidden = localStorage.getItem(HINT_KEY) === "1";
  } catch {
    $("#hint").hidden = false;
  }
  $("#hint-close").addEventListener("click", dismissHint);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") map.closePopup();
    // Ctrl+K (⌘K on a Mac) jumps to the search box. A shortcut with a
    // modifier key cannot be set off by speech input or a stray key press
    // (WCAG 2.1.4), unlike a single "/".
    if (event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey) {
      event.preventDefault();
      $("#f-search").focus();
      $("#f-search").select();
    }
  });

  run(() => loadSites({ fit: false }));
})();
