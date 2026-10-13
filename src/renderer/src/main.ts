import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import ReviewApp from './ReviewApp.vue'

const view = new URLSearchParams(window.location.search).get('view')
createApp(view === 'review' ? ReviewApp : App).mount('#app')
