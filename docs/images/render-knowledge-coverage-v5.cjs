// SPDX-License-Identifier: MIT
// node docs/images/render-knowledge-coverage-v5.cjs [--png]
// SVG generation uses Node.js only; optional PNG export requires Sharp.
const fs = require('node:fs');
const path = require('node:path');
const domains = [
  ['01', '数学与数值', '证明、线代、概率、数值与位宽'],
  ['02', '算法与数据结构', '复杂度、容器、图与调度'],
  ['03', '编程与程序执行', 'C / ABI、内存、正确性与性能'],
  ['04', '体系结构与加速器', 'RISC-V / NPU、存储与算术结构'],
  ['05', '操作系统原理', '调度、虚拟内存、并发与持久化'],
  ['06', 'Linux 系统构建', '工具链、用户态、内核与启动'],
  ['07', '模拟器与驱动', 'QEMU、MMIO、DMA 与设备'],
  ['08', 'AI 编译', '计算图、布局、量化与分块'],
  ['09', '深度学习基础', '表达、梯度、优化与泛化'],
  ['10', '从零 LLM', '文本、Transformer、训练与微调'],
  ['11', '推理运行时', '模型加载、KV、分派与 CPU 回退'],
  ['12', 'Agent 与检索', '证据、决策、工具与状态恢复'],
  ['13', '网络与分布式通信', 'Socket / RPC、背压与重试'],
  ['14', 'I/O 与 PCIe', '片内互连、BAR、DMA 与中断'],
  ['15', 'CXL 与异构内存', 'Type 3、译码、一致性与放置'],
  ['16', '数字设计与时序', '算术电路、流水线、CDC 与 PPA'],
  ['17', '系统化验证', '参考、形式、ECC 与故障处置'],
  ['18', '仿真建模与可信度', '事件、周期、重放与模型边界'],
];
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const s = [];
const rect = (x,y,w,h,fill,stroke='none',r=10) => s.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}"/>`);
const text = (x,y,value,size=18,fill='#20324a',weight=400) => s.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${esc(value)}</text>`);
s.push('<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="1180" viewBox="0 0 1120 1180" role="img" aria-labelledby="title description">');
s.push('<title id="title">AIMakeAll 知识覆盖图 V5</title><desc id="description">十八个既有知识领域。新增 ARITH 算术电路与 RAS 数据完整性两组，各六项待实现实验，累计十组六十项。底部列出阶段安排与四项共同交付。覆盖不代表完成，不要求实板或流片。</desc>');
s.push('<g font-family="PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">');
rect(0,0,1120,1180,'#f5f7fb','none',0);
text(36,48,'AIMakeAll · 知识覆盖图 V5',32,'#14283f',600);
text(36,80,'18 个领域 · 10 组 / 60 项深化实验计划 · 仿真优先，无需实板或流片',18,'#516278');
const stages = ['RISC-V + NPU', 'QEMU + 运行时', '从零 LLM + 编译', 'Agent + 任务评估'];
stages.forEach((label,i) => {
  const x = 36+i*270;
  rect(x,108,238,48,'#e6edf7'); text(x+16,139,label,20,'#243e60',500);
  if(i<3) text(x+247,139,'→',22,'#61758e');
});
text(36,190,'知识范围',21,'#14283f',600);
text(164,190,'编号与原体系一致；色条标出本轮两组主要归属',16,'#516278');
domains.forEach(([id,name,detail],i) => {
  const x = 36+(i%3)*356, y = 206+Math.floor(i/3)*94;
  const accent = id==='04' ? '#7562aa' : ['01','16'].includes(id) ? '#3c70b4' : id==='17' ? '#238478' : null;
  rect(x,y,336,82,'#ffffff','#dfe5ee');
  if(accent) rect(x,y+13,4,56,accent,'none',2);
  text(x+16,y+31,`${id}  ${name}`,20,'#20324a',500);
  text(x+16,y+60,detail,16,'#526276');
});
text(36,799,'本轮深化 · 两组均待实现，不增加一级领域',21,'#14283f',600);
rect(36,818,514,164,'#e9f0fb');
text(56,849,'ARITH · 计算机算术与算术电路结构',22,'#28558c',600);
text(56,876,'主要归属 01 / 04 / 16 · 连接验证与建模',17,'#405b7d');
text(56,906,'E1–E2  位宽与加法器',18);
text(56,935,'E3–E4  迭代乘法与并行归约',18);
text(56,964,'E5–E6  定点舍入与 MAC 集成',18);
rect(570,818,514,164,'#e6f3ef');
text(590,849,'RAS · 硬件数据完整性与故障处置',22,'#216d63',600);
text(590,876,'主要归属 04 / 17 · 连接存储、驱动与运行时',17,'#416961');
text(590,906,'E1–E2  故障、奇偶校验与 SECDED',18);
text(590,935,'E3–E4  受保护存储与错误上报',18);
text(590,964,'E5–E6  故障注入与 GEMM 处置',18);
text(36,1017,'推进：G0/G1 独立基础 → M1 电路与存储 → G2 MAC 对照 / G3 故障处置',19,'#334b65');
text(36,1051,'四项共同交付贯穿所有阶段',18,'#14283f',500);
['跨层契约', '资源预算', '共同实验资产', '教材学习者验证'].forEach((label,i) => {
  const x=36+i*267; rect(x,1066,247,44,'#e8ecf2'); text(x+16,1095,label,19);
});
text(36,1144,'当前已验证起点：Python GEMM 与单 MAC；新增实验、跨层实现与学习者试读待执行。',17,'#526276');
s.push('</g></svg>');
const svg = s.join('\n')+'\n';
const base = path.join(__dirname,'knowledge-coverage-v5');
fs.writeFileSync(base+'.svg',svg);
if(process.argv.includes('--png')) {
  require('sharp')(Buffer.from(svg)).png().toFile(base+'.png')
    .then(() => console.log('Wrote V5 SVG and PNG'))
    .catch(err => {console.error(err.message); process.exitCode=1;});
} else console.log('Wrote V5 SVG');
