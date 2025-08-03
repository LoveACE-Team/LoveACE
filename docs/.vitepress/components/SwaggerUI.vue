<template>
  <div ref="swaggerContainer" id="swagger-ui"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const swaggerContainer = ref<HTMLElement>()

onMounted(async () => {
  if (typeof window !== 'undefined') {
    try {
      // 加载CSS
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = '/swagger-ui.css'
      document.head.appendChild(link)

      // 加载SwaggerUI Bundle
      const bundleScript = document.createElement('script')
      bundleScript.src = '/swagger-ui-bundle.js'
      bundleScript.crossOrigin = 'anonymous'
      
      // 加载Standalone Preset
      const presetScript = document.createElement('script')
      presetScript.src = '/swagger-ui-standalone-preset.js'
      presetScript.crossOrigin = 'anonymous'

      // 等待两个脚本都加载完成
      let bundleLoaded = false
      let presetLoaded = false

      const initSwagger = () => {
        if (bundleLoaded && presetLoaded) {
          // @ts-ignore
          window.ui = window.SwaggerUIBundle({
            url: '/openapi.json',
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
              // @ts-ignore
              SwaggerUIBundle.presets.apis,
              // @ts-ignore
              SwaggerUIStandalonePreset
            ],
            plugins: [
              // @ts-ignore
              SwaggerUIBundle.plugins.DownloadUrl
            ],
            layout: "StandaloneLayout",
            tryItOutEnabled: true,
            displayRequestDuration: true,
            showExtensions: true,
            showCommonExtensions: true,
            requestInterceptor: (request: any) => {
              // 可以在这里添加认证头或其他请求拦截
              console.log('请求拦截:', request)
              return request
            },
            responseInterceptor: (response: any) => {
              // 可以在这里处理响应
              console.log('响应拦截:', response)
              return response
            }
          })
        }
      }

      bundleScript.onload = () => {
        bundleLoaded = true
        initSwagger()
      }

      presetScript.onload = () => {
        presetLoaded = true
        initSwagger()
      }

      bundleScript.onerror = () => {
        console.error('加载SwaggerUI Bundle失败')
      }

      presetScript.onerror = () => {
        console.error('加载SwaggerUI Preset失败')
      }

      document.head.appendChild(bundleScript)
      document.head.appendChild(presetScript)
    } catch (error) {
      console.error('加载SwaggerUI失败:', error)
    }
  }
})

onUnmounted(() => {
  // 清理动态添加的脚本和样式
  const bundleScripts = document.querySelectorAll('script[src*="swagger-ui-bundle"]')
  const presetScripts = document.querySelectorAll('script[src*="swagger-ui-standalone-preset"]')
  const links = document.querySelectorAll('link[href*="swagger-ui.css"]')
  
  bundleScripts.forEach(script => script.remove())
  presetScripts.forEach(script => script.remove())
  links.forEach(link => link.remove())
  
  // 清理全局变量
  if (typeof window !== 'undefined' && (window as any).ui) {
    delete (window as any).ui
  }
})
</script>

<style>
/* SwaggerUI 容器样式 */
#swagger-ui {
  font-family: var(--vp-font-family-base);
  width: 100%;
  min-height: 600px;
}

/* 调整SwaggerUI的主题以匹配VitePress */
#swagger-ui .swagger-ui .topbar {
  display: none !important;
}

#swagger-ui .swagger-ui .info {
  margin: 0 0 20px 0;
}

#swagger-ui .swagger-ui .scheme-container {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  padding: 10px;
  margin: 10px 0;
}

#swagger-ui .swagger-ui .opblock {
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  margin: 10px 0;
  background: var(--vp-c-bg);
}

#swagger-ui .swagger-ui .opblock.opblock-post {
  border-color: var(--vp-c-green-2);
  background: var(--vp-c-green-soft);
}

#swagger-ui .swagger-ui .opblock.opblock-get {
  border-color: var(--vp-c-blue-2);
  background: var(--vp-c-blue-soft);
}

#swagger-ui .swagger-ui .opblock.opblock-put {
  border-color: var(--vp-c-yellow-2);
  background: var(--vp-c-yellow-soft);
}

#swagger-ui .swagger-ui .opblock.opblock-delete {
  border-color: var(--vp-c-red-2);
  background: var(--vp-c-red-soft);
}

#swagger-ui .swagger-ui .opblock-summary {
  padding: 10px 15px;
}

#swagger-ui .swagger-ui .opblock-description-wrapper,
#swagger-ui .swagger-ui .opblock-external-docs-wrapper,
#swagger-ui .swagger-ui .opblock-title_normal {
  padding: 15px;
  background: var(--vp-c-bg-alt);
  border-radius: 4px;
  margin: 10px 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  #swagger-ui .swagger-ui {
    font-size: 14px;
  }
  
  #swagger-ui .swagger-ui .opblock-summary {
    padding: 8px 10px;
  }
}

/* 深色模式适配 */
.dark #swagger-ui .swagger-ui {
  color-scheme: dark;
}

.dark #swagger-ui .swagger-ui .opblock {
  background: var(--vp-c-bg-elv);
}

.dark #swagger-ui .swagger-ui .scheme-container {
  background: var(--vp-c-bg-elv);
}
</style>