// Regenerate with node docs/images/render-knowledge-coverage-v9.cjs [--png].
const fs = require('node:fs')
const path = require('node:path')
const index = fs.readFileSync(path.join(__dirname, '../KNOWLEDGE_COVERAGE.md'), 'utf8')
const domains = [...index.matchAll(/^\| (\d{2}) \| ([^|]+?) \|/gm)]
if (domains.length !== 18) throw new Error('Expected eighteen numbered domains')
const body = []
const ink = '#172b3a', muted = '#425c6b', teal = '#086a68', amber = '#86531a'
function rect(x, y, w, h, color, r = 0) {
  body.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${color}"/>`)
}
function text(x, y, value, size = 19, color = ink, weight = 400) {
  const s = value.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
  body.push(`<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}">${s}</text>`)
}
rect(0, 0, 1120, 1320, '#f7f8f5')
rect(0, 0, 1120, 135, '#193447')
text(48, 56, '芯片与 AI 的学习全景', 38, '#ffffff', 700)
text(50, 103, 'AIMakeAll  /  V9     十八个知识领域，以及可以亲手跑通的一条路径', 22, '#d3e7e5')
text(48, 193, '知识领域', 29, ink, 700)
domains.forEach(([, number, name], i) => {
  const x = 48 + Math.floor(i / 6) * 346, y = 218 + i % 6 * 47
  rect(x, y, 330, 39, '#e7eef0', 5)
  text(x + 13, y + 26, number, 17, muted, 600)
  text(x + 54, y + 27, name, 20)
})
text(48, 554, '实验 01　从固定线性层追到乘加器', 29, teal, 700)
text(48, 588, '同一组 X、W 和偏置　·　5 行输入 × 257 项归约 × 7 个输出通道', 20, muted)
const stages = [
  ['量化和布局', '独立参考读取 W[N,K]', '设备打包为 B[K,N]'],
  ['按命令分块', 'Python 与宿主 C', '逐项比对部分和'],
  ['设备与电路对照', 'RV32 客体提交给 QEMU', '单 MAC 在 RTL 中独立重放'],
  ['合并与还原', '跨段求和、加一次偏置', '复核全部 35 项输出'],
]
stages.forEach(([title, first, second], i) => {
  const x = 48 + 257 * i
  rect(x, 613, 246, 119, '#dceee8', 8)
  text(x + 13, 648, title, 23, teal, 700)
  text(x + 13, 686, first, 17)
  text(x + 13, 713, second, 17)
})
text(48, 775, '设计取舍', 21, teal, 700)
text(176, 775, '3212 B → 1606 B　｜　256 + 1 → 122 + 122 + 13　｜　整数结果一致', 20)
text(48, 841, '用四个小实验连接原理与应用', 28, ink, 700)
const bridges = [
  ['训练与推理', '同一层的前向、反向、一次参数更新及张量账本'],
  ['信息与编码', '无损前缀码、有损量化、信道冗余与失真'],
  ['物理互连', '改变阻抗、采样相位与衰减，观察眼图开口'],
  ['人机协作', '复核助手引用、纠正预算、确认或接管终止'],
]
bridges.forEach(([name, lesson], i) => {
  const y = 885 + 42 * i
  text(52, y, name, 20, teal, 650)
  text(210, y, lesson, 20)
})
rect(48, 1056, 1024, 221, '#f4ebd9', 8)
text(69, 1095, '实验 02–23　从一个投影到自然语言整机与系统接口', 25, amber, 700)
text(69, 1132, '02–09　微型模型、数字阵列与词表投影　｜　量化、缓存、64 条回复和逐步周期', 19)
text(69, 1168, '10–16　两层四头模型、共享 DMA 队列与执行计划　｜　训练、时序、面积和 KV 容量', 19)
text(69, 1203, '17–19　同一固件跑 QEMU 与 PicoRV32　｜　两种模型 × 两种电路，在新预算下复验', 18)
text(69, 1243, '20–23　工具选择、Linux PCIe、双虚拟机 TCP 与 CXL Type 3 内存放置', 18, amber)
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="1320" viewBox="0 0 1120 1320" role="img" aria-labelledby="title"><title id="title">AIMakeAll 知识覆盖与可运行实验 V9</title><g font-family="PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">${body.join('\n')}</g></svg>\n`
const base = path.join(__dirname, 'knowledge-coverage-v9')
fs.writeFileSync(base + '.svg', svg)
if (process.argv.includes('--png')) {
  require('sharp')(Buffer.from(svg)).png().toFile(base + '.png').catch(error => {
    console.error(error.message)
    process.exitCode = 1
  })
}
