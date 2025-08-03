import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import SwaggerUI from '../components/SwaggerUI.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  Layout: () => {
    return h(DefaultTheme.Layout, null, {
      // https://vitepress.dev/guide/extending-default-theme#layout-slots
    })
  },
  enhanceApp({ app, router, siteData }) {
    // 注册全局组件
    app.component('SwaggerUI', SwaggerUI)
  }
}