<template>
  <div class="app-shell">
    <header class="topbar">
      <nav class="navigation" aria-label="主导航">
        <button class="nav-item" type="button">设置</button>
        <button class="nav-item" type="button">API</button>
        <button class="nav-item" type="button">教程</button>
      </nav>

      <div class="product-mark" aria-label="Stubuddy desktop">
        <span class="product-mark__dot"></span>
        <span>STUBUDDY / DESKTOP</span>
      </div>
    </header>

    <main class="workspace" aria-label="工作台">
      <button class="workspace-card workspace-card--capture" type="button">
        <span class="card-index">01</span>
        <span class="card-content">
          <strong>截图</strong>
          <small>CAPTURE</small>
        </span>
        <span class="card-arrow" aria-hidden="true">↗</span>
      </button>

      <button class="workspace-card workspace-card--folder" type="button">
        <span class="card-index">02</span>
        <span class="card-content">
          <strong>查看文件夹</strong>
          <small>OPEN FOLDER</small>
        </span>
        <span class="card-arrow" aria-hidden="true">↗</span>
      </button>

      <button class="workspace-card workspace-card--review" type="button">
        <span class="card-index">03</span>
        <span class="review-rule" aria-hidden="true"></span>
        <span class="card-content">
          <strong>审阅台</strong>
          <small>REVIEW DESK</small>
        </span>
        <span class="card-arrow" aria-hidden="true">↗</span>
      </button>
    </main>
  </div>
</template>
