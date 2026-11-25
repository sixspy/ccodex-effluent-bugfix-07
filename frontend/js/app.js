import { createApi } from "./api.js";
import { dashboardViewTemplate } from "./views/dashboard_view.js";
import { plantsViewTemplate } from "./views/plants_view.js";
import { outfallsViewTemplate } from "./views/outfalls_view.js";
import { samplesViewTemplate } from "./views/samples_view.js";
import { exceedViewTemplate } from "./views/exceed_view.js";
import { releaseViewTemplate } from "./views/release_view.js";
import { sealViewTemplate } from "./views/seal_view.js";
import { permitsViewTemplate } from "./views/permits_view.js";
import { lineageViewTemplate } from "./views/lineage_view.js";
import { reconcileViewTemplate } from "./views/reconcile_view.js";
import { stubsViewTemplate } from "./views/stubs_view.js";

const { createApp, ref, computed, watch, onMounted } = Vue;

createApp({
  setup() {
    const token = ref(localStorage.getItem("effluent_token") || "");
    const user = ref(localStorage.getItem("effluent_user") || "");
    const username = ref("admin");
    const password = ref("admin123");
    const err = ref("");
    const actionErr = ref("");
    const actionOk = ref("");
    const tab = ref(0);
    const nav = ["总览","处理厂","排放口","采样","超标","准排","封批","许可","血缘","对账","空桩"];

    const dash = ref({});
    const plants = ref([]);
    const outfalls = ref([]);
    const samples = ref([]);
    const exceeds = ref([]);
    const releases = ref([]);
    const seals = ref([]);
    const permits = ref([]);
    const lineageEdges = ref([]);
    const labJobs = ref([]);
    const sludgeJobs = ref([]);
    const sludgeInfo = ref({});
    const plantDetail = ref(null);
    const sampleDetail = ref(null);
    const reconOne = ref(null);
    const reconAllItems = ref([]);
    const proofOne = ref(null);
    const reconCode = ref("DP-2026-E01");
    const proofCode = ref("SM-OF-E1-A-001");

    const plantForm = ref({
      plant_code: "PL-NEW-01", name: "新建净化厂", basin: "试验流域", design_cap_m3d: 20000,
    });
    const outfallForm = ref({
      outfall_code: "OF-NEW-A", plant_id: 1, river_reach: "试验河段",
      cod_limit: 50, nh3n_limit: 5, tp_limit: 0.5,
    });
    const sampleForm = ref({
      outfall_id: 1, permit_ref: "DP-2026-E01", sample_code: "",
      cod: 35, nh3n: 2.5, tp: 0.2, flow_m3h: 1800,
    });
    const releaseForm = ref({ sample_id: 0, officer: "值班员" });
    const sealForm = ref({ sample_id: 0, snapshot: "" });
    const permitForm = ref({
      permit_code: "DP-NEW-01", plant_id: 1, quota_m3d: 18000,
      cod_cap: 50, nh3n_cap: 5, tp_cap: 0.5, period_label: "2026Q4",
    });
    const lineageForm = ref({
      from_sample_id: 1, to_sample_id: 2, edge_type: "复测续批", detail: "试验血缘",
    });
    const labForm = ref({ sample_code: "SM-OF-E1-A-001", courier_slot: "A1" });
    const sludgeForm = ref({ plant_id: 1, digester_bay: "D-01", mode: "dry_run" });

    function logout() {
      token.value = "";
      user.value = "";
      localStorage.removeItem("effluent_token");
      localStorage.removeItem("effluent_user");
    }
    const api = createApi(() => token.value, () => logout());

    const releasableSamples = computed(() =>
      samples.value.filter((s) => s.status === "已裁定")
    );
    const sealableSamples = computed(() =>
      samples.value.filter((s) => ["已裁定", "已准排"].includes(s.status))
    );

    function statusClass(s) {
      if (!s) return "muted";
      if (s.includes("停") || s.includes("检修")) return "warn";
      if (s.includes("运行") || s.includes("开放") || s.includes("有效")) return "pass";
      return "muted";
    }
    function sampleClass(s) {
      if (!s) return "muted";
      if (s.includes("挂起")) return "fail";
      if (s.includes("准排") || s.includes("裁定") || s.includes("封批")) return "pass";
      return "muted";
    }
    function fmtMetrics(m) {
      if (!m) return "—";
      return `COD=${m.cod} 氨氮=${m.nh3n} 总磷=${m.tp}`;
    }

    async function flash(fn) {
      actionErr.value = "";
      actionOk.value = "";
      try {
        await fn();
        actionOk.value = "已完成";
        await refresh();
      } catch (e) {
        actionErr.value = e.message || String(e);
      }
    }

    async function login() {
      err.value = "";
      try {
        const data = await api.login(username.value, password.value);
        token.value = data.token;
        user.value = data.username;
        localStorage.setItem("effluent_token", data.token);
        localStorage.setItem("effluent_user", data.username);
        await refresh();
      } catch (e) {
        err.value = e.message || String(e);
      }
    }

    async function refresh() {
      if (!token.value) return;
      dash.value = await api.dashboard();
      plants.value = (await api.plants()).items;
      outfalls.value = (await api.outfalls()).items;
      samples.value = (await api.samples()).items;
      exceeds.value = (await api.exceeds()).items;
      releases.value = (await api.releases()).items;
      seals.value = (await api.seals()).items;
      permits.value = (await api.permits()).items;
      lineageEdges.value = (await api.lineage()).items;
      labJobs.value = (await api.labJobs()).items;
      sludgeInfo.value = await api.sludgeJobs();
      sludgeJobs.value = sludgeInfo.value.items || [];
      if (!releaseForm.value.sample_id && releasableSamples.value.length) {
        releaseForm.value.sample_id = releasableSamples.value[0].id;
      }
      if (!sealForm.value.sample_id && sealableSamples.value.length) {
        sealForm.value.sample_id = sealableSamples.value[0].id;
      }
    }

    async function loadPlant(id) { plantDetail.value = await api.plant(id); }
    async function loadSample(id) { sampleDetail.value = await api.sample(id); }
    async function createPlant() { await flash(() => api.createPlant(plantForm.value)); }
    async function createOutfall() { await flash(() => api.createOutfall(outfallForm.value)); }
    async function createSample() {
      await flash(() => api.createSample({
        outfall_id: sampleForm.value.outfall_id,
        permit_ref: sampleForm.value.permit_ref,
        sample_code: sampleForm.value.sample_code || null,
        flow_m3h: sampleForm.value.flow_m3h,
        metrics: {
          cod: sampleForm.value.cod,
          nh3n: sampleForm.value.nh3n,
          tp: sampleForm.value.tp,
        },
      }));
    }
    async function closeExceed(id) { await flash(() => api.closeExceed({ hold_id: id, note: "页面闭环" })); }
    async function createRelease() { await flash(() => api.createRelease(releaseForm.value)); }
    async function createSeal() {
      await flash(() => api.createSeal({
        sample_id: sealForm.value.sample_id,
        snapshot: sealForm.value.snapshot || null,
      }));
    }
    async function createShadowSeal() {
      await flash(() => api.createShadowSeal({
        sample_id: sealForm.value.sample_id,
        snapshot: sealForm.value.snapshot || null,
      }));
    }
    async function createPermit() { await flash(() => api.createPermit(permitForm.value)); }
    async function createLineage() {
      await flash(() => api.createLineage({
        from_sample_id: lineageForm.value.from_sample_id,
        to_sample_id: lineageForm.value.to_sample_id || null,
        edge_type: lineageForm.value.edge_type,
        detail: lineageForm.value.detail,
      }));
    }
    async function loadReconcile() {
      await flash(async () => { reconAllItems.value = (await api.reconcile()).items; });
    }
    async function loadReconcileOne() {
      await flash(async () => { reconOne.value = await api.reconcileOne(reconCode.value); });
    }
    async function loadProof() {
      await flash(async () => { proofOne.value = await api.proof(proofCode.value); });
    }
    async function enqueueLab() {
      await flash(() => api.labEnqueue({
        sample_code: labForm.value.sample_code,
        courier_slot: labForm.value.courier_slot,
        mode: "dry_run",
      }));
    }
    async function enqueueSludge() {
      await flash(() => api.sludgeEnqueue({
        plant_id: sludgeForm.value.plant_id,
        digester_bay: sludgeForm.value.digester_bay,
        mode: sludgeForm.value.mode,
      }));
    }
    async function completeSludge(job) {
      await flash(() => api.sludgeOutbound(job.id));
    }

    watch(tab, async () => {
      actionErr.value = "";
      actionOk.value = "";
      if (token.value) await refresh();
    });

    onMounted(async () => {
      if (token.value) {
        try { await refresh(); } catch { logout(); }
      }
    });

    return {
      token, user, username, password, err, actionErr, actionOk, tab, nav,
      dash, plants, outfalls, samples, exceeds, releases, seals, permits,
      lineageEdges, labJobs, sludgeJobs, sludgeInfo, plantDetail, sampleDetail,
      reconOne, reconAllItems, proofOne, reconCode, proofCode,
      plantForm, outfallForm, sampleForm, releaseForm, sealForm, permitForm,
      lineageForm, labForm, sludgeForm, releasableSamples, sealableSamples,
      login, logout, refresh, statusClass, sampleClass, fmtMetrics,
      loadPlant, loadSample, createPlant, createOutfall, createSample,
      closeExceed, createRelease, createSeal, createShadowSeal, createPermit, createLineage,
      loadReconcile, loadReconcileOne, loadProof, enqueueLab, enqueueSludge, completeSludge,
    };
  },
  template: `
  <div v-if="!token" class="login-shell">
    <div class="login-card">
      <h1 class="brand-mark">污水排放批</h1>
      <p class="brand-sub">采样 · 超标挂起 · 准排 · 封批 · 许可对账</p>
      <label>账号</label><input v-model="username"/>
      <label>密码</label><input type="password" v-model="password" @keyup.enter="login"/>
      <button @click="login">进入排放批</button>
      <p v-if="err" class="err">{{ err }}</p>
    </div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <div>
        <h1>污水排放批</h1>
        <div class="meta">{{ user }} · 数据工程母仓</div>
      </div>
      <button @click="logout">退出</button>
    </header>
    <nav class="ribbon">
      <button v-for="(n,i) in nav" :key="n" :class="{active: tab===i}" @click="tab=i">{{ n }}</button>
    </nav>
    <main class="main">
      <div v-if="actionErr" class="banner err">{{ actionErr }}</div>
      <div v-else-if="actionOk" class="banner ok">{{ actionOk }}</div>
      <div v-show="tab===0">${dashboardViewTemplate}</div>
      <div v-show="tab===1">${plantsViewTemplate}</div>
      <div v-show="tab===2">${outfallsViewTemplate}</div>
      <div v-show="tab===3">${samplesViewTemplate}</div>
      <div v-show="tab===4">${exceedViewTemplate}</div>
      <div v-show="tab===5">${releaseViewTemplate}</div>
      <div v-show="tab===6">${sealViewTemplate}</div>
      <div v-show="tab===7">${permitsViewTemplate}</div>
      <div v-show="tab===8">${lineageViewTemplate}</div>
      <div v-show="tab===9">${reconcileViewTemplate}</div>
      <div v-show="tab===10">${stubsViewTemplate}</div>
    </main>
  </div>
  `,
}).mount("#app");
