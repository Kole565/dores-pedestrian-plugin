import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('@/pages/Overview.vue'),
    },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('@/pages/Upload.vue'),
    },
    {
      path: '/stream',
      name: 'stream',
      component: () => import('@/pages/Stream.vue'),
    },
    {
      path: '/lines',
      name: 'lines',
      component: () => import('@/pages/Lines.vue'),
    },
    {
      path: '/jobs/:id',
      name: 'job-details',
      component: () => import('@/pages/JobDetails.vue'),
      props: true,
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

export default router
