(() => {
  "use strict";

  const POLL_MS = 3000;

  const els = {
    ts: document.getElementById("ts"),
    pulse: document.getElementById("pulse"),
    bias: document.getElementById("bias"),
    total: document.getElementById("total"),
    premium: document.getElementById("premium"),
    discount: document.getElementById("discount"),
    flat: document.getElementById("flat"),
    avgBasis: document.getElementById("avg-basis"),
    avgAnn: document.getElementById("avg-ann"),
    topPremiums: document.getElementById("top-premiums"),
    topDiscounts: document.getElementById("top-discounts"),
    rows: document.getElementById("rows"),
    emptyHint: document.getElementById("empty-hint"),
    filter: document.getElementById("filter"),
    headers: document.querySelectorAll("th.sortable"),
  };

  const state = {
    rows: [],
    filter: "",
    sortKey: "basis_pct",
    sortDir: "desc",
  };

  // ------------------------------------------------------------- formatters
  const fmtNum = (v, digits = 2) =>
    v == null || Number.isNaN(v) ? "—" : v.toLocaleString("en-IN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });

  const fmtSigned = (v, digits = 2, suffix = "") => {
    if (v == null || Number.isNaN(v)) return "—";
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(digits)}${suffix}`;
  };

  const colorClass = (v) =>
    v == null || Number.isNaN(v) ? "dim" : v > 0 ? "green" : v < 0 ? "red" : "";

  // ----------------------------------------------------------------- render
  function renderSummary(payload) {
    els.ts.textContent = payload.timestamp.replace("T", " ");
    els.total.textContent = payload.totals.total;
    els.premium.textContent = payload.totals.premium;
    els.discount.textContent = payload.totals.discount;
    els.flat.textContent = payload.totals.flat;
    els.avgBasis.textContent = fmtSigned(payload.averages.basis_pct, 3, "%");
    els.avgAnn.textContent = fmtSigned(payload.averages.annualised_pct, 2, "%");

    els.bias.textContent = payload.bias;
    els.bias.className = "bias-badge bias-" + payload.bias.toLowerCase();
  }

  function renderMovers(rows) {
    const valid = rows.filter((r) => r.basis_pct != null);
    const sorted = [...valid].sort((a, b) => b.basis_pct - a.basis_pct);

    const top = sorted.slice(0, 10);
    const bottom = sorted.slice(-10).reverse();

    const maxAbs = Math.max(
      Math.abs(top[0]?.basis_pct ?? 0),
      Math.abs(bottom[0]?.basis_pct ?? 0),
      0.001,
    );

    const buildBar = (row, color) => {
      const width = Math.min(100, (Math.abs(row.basis_pct) / maxAbs) * 100);
      return `<li class="bar">
        <span class="fill ${color}" style="width:${width}%"></span>
        <span class="symbol">${row.symbol}</span>
        <span class="pct ${color}">${fmtSigned(row.basis_pct, 3, "%")}</span>
        <span class="price">${fmtNum(row.spot)} → ${fmtNum(row.future)}</span>
      </li>`;
    };

    els.topPremiums.innerHTML = top.map((r) => buildBar(r, "green")).join("");
    els.topDiscounts.innerHTML = bottom.map((r) => buildBar(r, "red")).join("");
  }

  function renderTable() {
    const filterText = state.filter.trim().toUpperCase();
    let rows = filterText
      ? state.rows.filter((r) => r.symbol.includes(filterText))
      : [...state.rows];

    rows.sort((a, b) => {
      const va = a[state.sortKey];
      const vb = b[state.sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "string") {
        return state.sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      return state.sortDir === "asc" ? va - vb : vb - va;
    });

    if (rows.length === 0) {
      els.rows.innerHTML = "";
      els.emptyHint.textContent = filterText
        ? `No symbols match "${state.filter}".`
        : "Waiting for first snapshot…";
      els.emptyHint.style.display = "block";
      return;
    }
    els.emptyHint.style.display = "none";

    const html = rows
      .map((r) => {
        const basisCls = colorClass(r.basis_pct);
        const annCls = colorClass(r.annualised_pct);
        const expiry = r.expiry ? r.expiry.slice(2) : "—";
        return `<tr>
          <td class="dim">${r.rank}</td>
          <td><strong>${r.symbol}</strong></td>
          <td class="num">${fmtNum(r.spot)}</td>
          <td class="num">${fmtNum(r.future)}</td>
          <td class="dim">${r.futures_symbol}</td>
          <td class="num dim">${r.days_to_expiry}</td>
          <td class="num ${basisCls}">${fmtSigned(r.basis, 2)}</td>
          <td class="num ${basisCls}">${fmtSigned(r.basis_pct, 3, "%")}</td>
          <td class="num ${annCls}">${fmtSigned(r.annualised_pct, 2, "%")}</td>
          <td><span class="stance-pill ${r.stance}">${r.stance}</span></td>
        </tr>`;
      })
      .join("");
    els.rows.innerHTML = html;
  }

  // ------------------------------------------------------------- interactions
  els.filter.addEventListener("input", (e) => {
    state.filter = e.target.value;
    renderTable();
  });

  els.headers.forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDir = key === "symbol" || key === "rank" ? "asc" : "desc";
      }
      els.headers.forEach((h) => h.classList.remove("active", "asc"));
      th.classList.add("active");
      if (state.sortDir === "asc") th.classList.add("asc");
      renderTable();
    });
  });

  // ------------------------------------------------------------------- poll
  let warmedUp = false;

  async function poll() {
    try {
      const resp = await fetch("/api/snapshot", { cache: "no-store" });
      if (resp.status === 503) {
        if (!warmedUp) els.ts.textContent = "warming up…";
        return;
      }
      if (!resp.ok) {
        els.ts.textContent = `error ${resp.status}`;
        return;
      }
      const payload = await resp.json();
      state.rows = payload.rows;
      renderSummary(payload);
      renderMovers(payload.rows);
      renderTable();

      els.pulse.classList.remove("pulsing");
      void els.pulse.offsetWidth; // restart the animation
      els.pulse.classList.add("pulsing");
      warmedUp = true;
    } catch (err) {
      els.ts.textContent = `network error: ${err.message}`;
    }
  }

  poll();
  setInterval(poll, POLL_MS);
})();
