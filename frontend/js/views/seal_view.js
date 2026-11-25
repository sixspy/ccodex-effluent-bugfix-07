export const sealViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>封批快照</h3>
      <table>
        <thead><tr><th>封批号</th><th>采样</th><th>代</th><th>状态</th><th>快照</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="s in seals" :key="s.id">
            <td>{{ s.seal_ref }}</td><td>{{ s.sample_code }}</td><td>{{ s.sample_generation }}</td>
            <td><span :class="s.status==='已封批' ? 'pass' : 'muted'">{{ s.status }}</span></td>
            <td>{{ s.snapshot }}</td><td>{{ s.sealed_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>执行封批</h3>
      <p class="muted">出库未齐正式封批拒写（出库偏航）；可先落影子封批草稿，出库齐后自动升正。</p>
      <label>可封批采样</label>
      <select v-model.number="sealForm.sample_id">
        <option v-for="s in sealableSamples" :key="s.id" :value="s.id">
          {{ s.sample_code }} · {{ s.status }} · {{ s.sludge_status }}
        </option>
      </select>
      <label>快照（可空自动）</label><input v-model="sealForm.snapshot"/>
      <div class="actions">
        <button class="warn" @click="createSeal">封批升代</button>
        <button @click="createShadowSeal">影子封批草稿</button>
      </div>
    </div>
  </div>`;
