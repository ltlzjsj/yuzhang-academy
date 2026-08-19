<script setup lang="ts">
const year = new Date().getFullYear()
</script>

<template>
  <footer id="about" class="ft">
    <div class="ft__content shell">
      <div class="ft__col">
        <h3>联系方式</h3>
        <ul>
          <li>地址：江西省南昌市 · 豫章书院</li>
          <li>电话：0791-1234 5678</li>
          <li>邮箱：info@yuzhang-shuyuan.cn</li>
        </ul>
      </div>
      <div class="ft__col">
        <h3>合作咨询</h3>
        <ul>
          <li><a href="#">学术合作</a></li>
          <li><a href="#">文化交流</a></li>
          <li><a href="#">研学合作</a></li>
        </ul>
      </div>
      <div class="ft__col">
        <h3>友情链接</h3>
        <ul>
          <li><a href="#">江西省文化和旅游厅</a></li>
          <li><a href="#">南昌市文旅局</a></li>
          <li><a href="#">高校合作平台</a></li>
        </ul>
      </div>
      <div class="ft__col">
        <h3>关注我们</h3>
        <p>扫描二维码，关注书院公众号</p>
        <div class="ft__qr"><span>QR</span></div>
      </div>
    </div>
    <div class="ft__copy">
      <p>© {{ year }} 豫章书院　江右理学之源 · 数智书院体验　|　<a href="#">隐私政策</a></p>
    </div>
  </footer>
</template>

<style scoped>
.ft { background: var(--navy); color: #f0f0f0; }
.ft__content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 40px;
  padding-top: 52px;
  padding-bottom: 40px;
}
.ft__col h3 { margin-bottom: 16px; color: #fff; font-size: 16px; font-weight: 700; }
.ft__col ul { list-style: none; }
.ft__col li, .ft__col p { margin-bottom: 9px; font-size: 14px; line-height: 1.7; color: #ccc; }
.ft__col a { color: #ccc; text-decoration: none; transition: color 0.2s var(--ease); }
.ft__col a:hover { color: var(--gold); text-decoration: underline; }
.ft__qr {
  display: grid;
  place-items: center;
  height: 96px;
  width: 96px;
  margin-top: 6px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--navy);
  font-weight: 800;
  letter-spacing: 0.1em;
}
.ft__copy {
  border-top: 1px solid var(--navy-soft);
  text-align: center;
}
.ft__copy p { padding: 18px 16px; font-size: 13.5px; color: #cfd6dd; }
.ft__copy a { color: #cfd6dd; }
.ft__copy a:hover { color: var(--gold); }
</style>
