export const permitsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>排放许可册</h3>
      <table>
        <thead><tr><th>许可号</th><th>厂</th><th>配额</th><th>COD帽</th><th>期别</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="p in permits" :key="p.id">
            <td>{{ p.permit_code }}</td><td>{{ p.plant_code }}</td><td>{{ p.quota_m3d }}</td>
            <td>{{ p.cod_cap }}</td><td>{{ p.period_label }}</td>
            <td :class="statusClass(p.status)">{{ p.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>登记许可</h3>
      <div class="form-row"><div><label>许可号</label><input v-model="permitForm.permit_code"/></div>
      <div><label>厂 ID</label><input type="number" v-model.number="permitForm.plant_id"/></div></div>
      <div class="form-row"><div><label>配额</label><input type="number" v-model.number="permitForm.quota_m3d"/></div>
      <div><label>期别</label><input v-model="permitForm.period_label"/></div></div>
      <div class="form-row">
        <div><label>COD帽</label><input type="number" v-model.number="permitForm.cod_cap"/></div>
        <div><label>氨氮帽</label><input type="number" v-model.number="permitForm.nh3n_cap"/></div>
      </div>
      <label>总磷帽</label><input type="number" v-model.number="permitForm.tp_cap"/>
      <div class="actions"><button @click="createPermit">登记</button></div>
    </div>
  </div>`;
