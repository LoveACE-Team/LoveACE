import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LoveACE',
  description: '教务系统自动化工具',
  lang: 'zh-CN',
  
  themeConfig: {
    logo: '/images/logo.jpg',
    
    nav: [
      { text: '首页', link: '/' },
      { text: 'API文档', link: '/api/' },
      { text: '配置', link: '/config' },
      { text: '部署', link: '/deploy' },
      { text: '贡献', link: '/contributing' }
    ],

    sidebar: {
      '/': [
        {
          text: '指南',
          items: [
            { text: '介绍', link: '/' },
            { text: '快速开始', link: '/getting-started' },
            { text: '配置', link: '/config' },
            { text: '部署指南', link: '/deploy' }
          ]
        },
        {
          text: 'API文档',
          items: [
            { text: 'API交互式文档', link: '/api/' }
          ]
        },
        {
          text: '其他',
          items: [
            { text: '贡献指南', link: '/contributing' },
            { text: '免责声明', link: '/disclaimer' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/LoveACE-Team/LoveACE' }
    ],

    footer: {
      message: '基于 MIT 许可发布',
      copyright: 'Copyright © 2025 LoveACE'
    },

    search: {
      provider: 'local'
    },

    lastUpdated: {
      text: '最后更新于',
      formatOptions: {
        dateStyle: 'short',
        timeStyle: 'medium'
      }
    }
  },

  head: [
    ['link', { rel: 'icon', href: '/images/logo.jpg' }]
  ],

  markdown: {
    lineNumbers: true
  }
})