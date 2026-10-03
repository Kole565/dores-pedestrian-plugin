<script setup lang="ts">
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <div class="app-shell">
    <NavBar />
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>
