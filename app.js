const VERDICT_LABELS = {
  good: "Bien",
  renew_creative: "Renovar creativo",
  kill_candidate: "Candidata a apagar",
  insufficient_data: "Datos insuficientes",
};

const VERDICT_ORDER = ["kill_candidate", "renew_creative", "insufficient_data", "good"];

function formatCurrency(value) {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(2)}`;
}

function renderSummary(snapshot) {
  const el = document.getElementById("summary");
  el.innerHTML = `
    <div class="stat"><div>Gasto</div><div class="value">${formatCurrency(snapshot.account_spend)}</div></div>
    <div class="stat"><div>Ventas</div><div class="value">${snapshot.account_purchases}</div></div>
    <div class="stat"><div>CPA</div><div class="value">${formatCurrency(snapshot.account_cpa)}</div></div>
  `;
}

function renderCampaigns(snapshot) {
  const el = document.getElementById("campaigns");
  const sorted = [...snapshot.campaigns].sort(
    (a, b) => VERDICT_ORDER.indexOf(a.verdict) - VERDICT_ORDER.indexOf(b.verdict)
  );

  if (sorted.length === 0) {
    el.innerHTML = "<p>Todavía no hay datos — esperando la primera corrida del Action.</p>";
    return;
  }

  el.innerHTML = sorted
    .map((campaign) => {
      const allReasons = campaign.ads.flatMap((ad) => ad.reasons);
      const uniqueReasons = [...new Set(allReasons)];
      return `
        <article class="campaign ${campaign.verdict}">
          <span class="badge ${campaign.verdict}">${VERDICT_LABELS[campaign.verdict] || campaign.verdict}</span>
          <h2>${campaign.campaign_name}</h2>
          <div class="metrics">Gasto: ${formatCurrency(campaign.spend)} · Ventas: ${campaign.purchases}</div>
          <ul class="reasons">
            ${uniqueReasons.map((r) => `<li>${r}</li>`).join("")}
          </ul>
        </article>
      `;
    })
    .join("");
}

async function main() {
  const updatedAtEl = document.getElementById("updated-at");
  try {
    const response = await fetch("./data/latest.json", { cache: "no-store" });
    const snapshot = await response.json();

    if (!snapshot.generated_at) {
      updatedAtEl.textContent = "Todavía sin datos — esperando la primera corrida.";
    } else {
      updatedAtEl.textContent = `Última actualización: ${snapshot.generated_at}`;
    }

    renderSummary(snapshot);
    renderCampaigns(snapshot);
  } catch (err) {
    updatedAtEl.textContent = "No se pudo cargar data/latest.json.";
    console.error(err);
  }
}

function isLocalDev() {
  return ["localhost", "127.0.0.1"].includes(window.location.hostname);
}

async function handleRefreshClick() {
  const btn = document.getElementById("refresh-btn");
  const updatedAtEl = document.getElementById("updated-at");
  btn.disabled = true;
  btn.textContent = "Actualizando...";
  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    const body = await response.json();
    if (!response.ok || !body.ok) throw new Error(body.error || "Falló el refresh");
    await main();
  } catch (err) {
    updatedAtEl.textContent = `No se pudo refrescar: ${err.message}`;
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Refrescar";
  }
}

function setupRefreshButton() {
  // Only meaningful when served by scripts/dev_server.py, which exposes
  // POST /api/refresh. GitHub Pages is static-only, so keep this hidden
  // there — there's nothing on the other end to call.
  if (!isLocalDev()) return;
  const btn = document.getElementById("refresh-btn");
  btn.hidden = false;
  btn.addEventListener("click", handleRefreshClick);
}

setupRefreshButton();
main();
