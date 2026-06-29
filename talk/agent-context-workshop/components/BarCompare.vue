<script setup>
// Lightweight horizontal bar comparison, theme-matched (no charting dep).
// rows: [{ label, value, max, display, color }]
defineProps({
  rows: { type: Array, required: true },
})
</script>

<template>
  <div class="bc">
    <div v-for="(r, i) in rows" :key="i" class="bc-row">
      <span class="bc-label">{{ r.label }}</span>
      <span class="bc-track">
        <span
          class="bc-fill"
          :style="{ width: Math.max(2, (r.value / r.max) * 100) + '%', background: r.color || '#829df3' }"
        />
      </span>
      <span class="bc-val" :style="{ color: r.color || '#e0e0e0' }">{{ r.display ?? r.value }}</span>
    </div>
  </div>
</template>

<style scoped>
.bc {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0.6rem 0 0.35rem;
  background: #161d2b;
  border: 1px solid #242e40;
  border-radius: 10px;
  padding: 0.8rem 1.05rem;
}
.bc-row {
  display: grid;
  grid-template-columns: 5rem 1fr 4.5rem;
  align-items: center;
  gap: 0.9rem;
}
.bc-label {
  text-align: right;
  color: #aeb6c7;
  font-size: 0.95rem;
}
.bc-track {
  background: #1b2433;
  border-radius: 5px;
  height: 1.5rem;
  overflow: hidden;
}
.bc-fill {
  display: block;
  height: 100%;
  border-radius: 5px;
  transition: width 0.55s cubic-bezier(0.2, 0.7, 0.3, 1);
}
.bc-val {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 1.02rem;
}
</style>
