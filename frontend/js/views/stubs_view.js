export const stubsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>空桩 · 外送化验快递</h3>
      <p class="muted">接口可点，默认 dry_run，未接通外送系统。</p>
      <label>采样号</label><input v-model="labForm.sample_code"/>
      <label>快递槽</label><input v-model="labForm.courier_slot"/>
      <div class="actions"><button @click="enqueueLab">演练入队</button></div>
      <table style="margin-top:0.8rem">
        <thead><tr><th>ID</th><th>采样</th><th>槽</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="j in labJobs" :key="j.id"><td>{{ j.id }}</td><td>{{ j.sample_code }}</td><td>{{ j.courier_slot }}</td><td>{{ j.status }}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>空桩 · 污泥消化排程</h3>
      <p class="muted">接口可点，默认 dry_run，未接通污泥仓排程。</p>
      <label>厂 ID</label><input type="number" v-model.number="sludgeForm.plant_id"/>
      <label>消化仓</label><input v-model="sludgeForm.digester_bay"/>
      <div class="actions"><button @click="enqueueSludge">演练入队</button></div>
      <table style="margin-top:0.8rem">
        <thead><tr><th>ID</th><th>仓</th><th>模式</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="j in sludgeJobs" :key="j.id"><td>{{ j.id }}</td><td>{{ j.digester_bay }}</td><td>{{ j.mode }}</td><td>{{ j.status }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>`;
