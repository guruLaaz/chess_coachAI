import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: () => import('../views/LandingPage.vue'),
  },
  {
    path: '/u/:userPath(.+)/opening/:eco/:color',
    name: 'OpeningDetail',
    component: () => import('../views/OpeningsPage.vue'),
    props: true,
  },
  {
    path: '/u/:userPath(.+)/endgames/all',
    name: 'EndgamesAll',
    component: () => import('../views/EndgamesAllPage.vue'),
  },
  {
    path: '/u/:userPath(.+)/endgames',
    name: 'Endgames',
    component: () => import('../views/EndgamesPage.vue'),
  },
  {
    path: '/u/:userPath(.+)/status',
    name: 'Status',
    component: () => import('../views/StatusPage.vue'),
  },
  {
    path: '/no-games',
    name: 'NoGames',
    component: () => import('../views/NoGamesPage.vue'),
  },
  {
    path: '/u/:userPath(.+)',
    name: 'Openings',
    component: () => import('../views/OpeningsPage.vue'),
  },
  {
    path: '/admin/jobs',
    name: 'AdminJobs',
    component: () => import('../views/AdminJobsPage.vue'),
  },
  {
    path: '/admin/feedback',
    name: 'AdminFeedback',
    component: () => import('../views/AdminFeedbackPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
