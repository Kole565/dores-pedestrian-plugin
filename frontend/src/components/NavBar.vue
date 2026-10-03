<script setup lang="ts">
import { RouterLink } from 'vue-router'

const links = [
  { to: '/', label: 'Обзор' },
  { to: '/upload', label: 'Загрузить видео' },
  { to: '/stream', label: 'RTSP-поток' },
  { to: '/lines', label: 'Редактор линий' },
]
</script>

<template>
  <header class="navbar">
    <span class="brand">DORES · Pedestrian Flow</span>
    <nav>
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        active-class="active"
      >
        {{ link.label }}
      </RouterLink>
    </nav>
  </header>
</template>

