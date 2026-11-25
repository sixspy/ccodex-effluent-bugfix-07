export const samplesViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>采样批次</h3>
      <table>
        <thead><tr><th>编号</th><th>口</th><th>许可</th><th>流量</th><th>状态</th><th>代</th></tr></thead>
        <tbody>
          <tr v-for="s in samples" :key="s.id" @click="loadSample(s.id)" style="cursor:pointer">
            <td>{{ s.sample_code }}</td><td>{{ s.outfall_code }}</td><td>{{ s.permit_ref }}</td>
            <td>{{ s.flow_m3h }}</td><td :class="sampleClass(s.status)">{{ s.status }}</td>
            <td>{{ s.generation }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="sampleDetail" class="panel" style="margin-top:0.8rem;border-style:dashed">
        <h3>批次详情</h3>
        <div class="kv">
          <span>指标</span><span>{{ fmtMetrics(sampleDetail.sample.metrics) }}</span>
          <span>挂起</span><span>{{ sampleDetail.exceed_holds.length }}</span>
          <span>准排</span><span>{{ sampleDetail.discharge_releases.length }}</span>
          <span>封批</span><span>{{ sampleDetail.discharge_seals.length }}</span>
        </div>
      </div>
    </div>
    <div class="panel">
      <h3>入库采样</h3>
      <div class="form-row"><div><label>排放口 ID</label><input type="number" v-model.number="sampleForm.outfall_id"/></div>
      <div><label>许可号</label><input v-model="sampleForm.permit_ref"/></div></div>
      <div class="form-row">
        <div><label>COD</label><input type="number" v-model.number="sampleForm.cod"/></div>
        <div><label>氨氮</label><input type="number" v-model.number="sampleForm.nh3n"/></div>
      </div>
      <div class="form-row">
        <div><label>总磷</label><input type="number" v-model.number="sampleForm.tp"/></div>
        <div><label>流量 m3/h</label><input type="number" v-model.number="sampleForm.flow_m3h"/></div>
      </div>
      <label>编号（可空自动）</label><input v-model="sampleForm.sample_code"/>
      <div class="actions"><button @click="createSample">入库</button></div>
    </div>
  </div>`;
