import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import PatientsView from '@/views/PatientsView.vue'
import PatientDetailView from '@/views/PatientDetailView.vue'
import AnalysisView from '@/views/AnalysisView.vue'
import RulesView from '@/views/RulesView.vue'
import HistoryView from '@/views/HistoryView.vue'
import HistoryDetailView from '@/views/HistoryDetailView.vue'
import ModelView from '@/views/ModelView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/patients', name: 'patients', component: PatientsView },
    { path: '/patients/:id', name: 'patient-detail', component: PatientDetailView },
    { path: '/analysis', name: 'analysis', component: AnalysisView },
    { path: '/rules', name: 'rules', component: RulesView },
    { path: '/history', name: 'history', component: HistoryView },
    { path: '/history/:id', name: 'history-detail', component: HistoryDetailView },
    { path: '/model', name: 'model', component: ModelView },
  ],
})
