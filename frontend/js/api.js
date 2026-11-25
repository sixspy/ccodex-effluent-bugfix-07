export function createApi(getToken, onUnauthorized) {
  async function request(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    const token = getToken();
    if (token) headers.Authorization = "Bearer " + token;
    const res = await fetch(path, Object.assign({}, options, { headers }));
    if (res.status === 401) {
      onUnauthorized();
      throw new Error("未登录或令牌失效");
    }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    if (!res.ok) {
      const detail = data && (data.detail || data.message);
      throw new Error(typeof detail === "string" ? detail : ("请求失败 " + res.status));
    }
    return data;
  }
  return {
    login: (username, password) => request("/api/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    me: () => request("/api/me"),
    dashboard: () => request("/api/dashboard"),
    plants: () => request("/api/plants"),
    plant: (id) => request("/api/plants/" + id),
    createPlant: (body) => request("/api/plants", { method: "POST", body: JSON.stringify(body) }),
    outfalls: () => request("/api/outfalls"),
    outfall: (id) => request("/api/outfalls/" + id),
    createOutfall: (body) => request("/api/outfalls", { method: "POST", body: JSON.stringify(body) }),
    setOutfallStatus: (id, status) => request("/api/outfalls/" + id + "/status?status=" + encodeURIComponent(status), { method: "POST" }),
    samples: (status) => request("/api/samples" + (status ? ("?status=" + encodeURIComponent(status)) : "")),
    sample: (id) => request("/api/samples/" + id),
    createSample: (body) => request("/api/samples", { method: "POST", body: JSON.stringify(body) }),
    exceeds: (status) => request("/api/exceeds" + (status ? ("?status=" + encodeURIComponent(status)) : "")),
    closeExceed: (body) => request("/api/exceeds/close", { method: "POST", body: JSON.stringify(body) }),
    openExceed: (body) => request("/api/exceeds/open", { method: "POST", body: JSON.stringify(body) }),
    releases: () => request("/api/releases"),
    createRelease: (body) => request("/api/releases", { method: "POST", body: JSON.stringify(body) }),
    seals: () => request("/api/seals"),
    createSeal: (body) => request("/api/seals", { method: "POST", body: JSON.stringify(body) }),
    createShadowSeal: (body) => request("/api/seals/shadow", { method: "POST", body: JSON.stringify(body) }),
    permits: () => request("/api/permits"),
    permit: (code) => request("/api/permits/" + encodeURIComponent(code)),
    createPermit: (body) => request("/api/permits", { method: "POST", body: JSON.stringify(body) }),
    lineage: () => request("/api/lineage"),
    createLineage: (body) => request("/api/lineage", { method: "POST", body: JSON.stringify(body) }),
    reconcile: () => request("/api/reconcile"),
    reconcileOne: (code) => request("/api/reconcile/" + encodeURIComponent(code)),
    proof: (code) => request("/api/proof/sample/" + encodeURIComponent(code)),
    labJobs: () => request("/api/stubs/lab-courier"),
    labEnqueue: (body) => request("/api/stubs/lab-courier", { method: "POST", body: JSON.stringify(body) }),
    sludgeJobs: () => request("/api/stubs/sludge-plan"),
    sludgeEnqueue: (body) => request("/api/stubs/sludge-plan", { method: "POST", body: JSON.stringify(body) }),
    sludgeOutbound: (jobId) => request("/api/stubs/sludge-plan/outbound?job_id=" + jobId, { method: "POST" }),
    audit: () => request("/api/audit"),
  };
}
