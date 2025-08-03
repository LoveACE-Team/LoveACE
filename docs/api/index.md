---
layout: page
title: LoveACE API 文档
description: 基于 OpenAPI 3.1 规范的交互式 API 文档
---

<script setup>
import { onMounted } from 'vue'

onMounted(() => {
  // 为当前页面添加特殊的CSS类，用于样式定制
  document.body.classList.add('api-page')
})
</script>

<div class="api-docs-container">
  <SwaggerUI />
</div>