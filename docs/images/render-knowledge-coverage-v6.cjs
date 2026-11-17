// SPDX-License-Identifier: MIT
// node docs/images/render-knowledge-coverage-v6.cjs [--png]
// SVG generation uses Node.js only; optional PNG export requires Sharp.
const fs = require('node:fs');
const path = require('node:path');
const domains = [
  ['01', '数学与数值', '线代、概率、数值、方程与信号'],
  ['02', '算法与数据结构', '复杂度、容器、图、搜索与规划'],
  ['03', '编程与程序执行', 'C / ABI、内存、正确性与性能'],
  ['04', '体系结构与加速器', 'CPU / GPU / DSP / NPU、存储'],
  ['05', '操作系统原理', '调度、虚拟内存、并发与持久化'],
  ['06', 'Linux 系统构建', '工具链、用户态、内核与启动'],
  ['07', '模拟器与驱动', 'QEMU、MMIO、DMA 与设备'],
  ['08', 'AI 编译', '计算图、布局、量化与分块'],
  ['09', '深度学习基础', '梯度与泛化、经典 ML、生成比较'],
  ['10', '从零 LLM', '文本、Transformer、训练与微调'],
  ['11', '推理运行时', '模型加载、KV、分派与 CPU 回退'],
  ['12', 'Agent 与检索', '逻辑与概率、工具、感知与控制'],
  ['13', '网络与分布式通信', '通信、分布式训练、推理与服务'],
  ['14', 'I/O 与 PCIe', '片内互连、BAR、DMA 与中断'],
  ['15', 'CXL 与异构内存', 'Type 3、译码、一致性与放置'],
  ['16', '数字设计与时序', '器件与电路、RTL、物理与 PPA'],
  ['17', '系统化验证', '参考、形式、DFT / ECC、故障'],
  ['18', '仿真建模与可信度', '事件、周期、连续系统与可信度'],
];
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const s = [];
const rect = (x,y,w,h,fill,stroke='none',r=10) => s.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}"/>`);
const text = (x,y,value,size=18,fill='#20324a',weight=400) => s.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${esc(value)}</text>`);
s.push('<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="1710" viewBox="0 0 1120 1710" role="img" aria-labelledby="title description">');
s.push('<title id="title">AIMakeAll 知识覆盖图 V6</title><desc id="description">十八个既有领域与十条全景补全路线，涵盖信号、电路、数字实践、异构架构、产品流程、部署、经典 AI、深度学习比较、具身和规模工程。30 个验收节点含既有实验复用，全部待实施。底部给出学习顺序与共同交付，仿真优先，不要求实物。</desc>');
s.push('<g font-family="PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">');
rect(0,0,1120,1710,'#f5f7fb','none',0);
text(36,48,'AIMakeAll · 知识覆盖图 V6',32,'#14283f',600);
text(36,80,'全景通识 → 核心实践 → 专题深入 · 仿真优先，无需实板或流片',18,'#516278');
const stages = ['RISC-V + NPU', 'QEMU + 运行时', '从零 LLM + 编译', 'Agent + 任务评估'];
stages.forEach((label,i) => {
  const x = 36+i*270;
  rect(x,108,238,48,'#e6edf7'); text(x+16,139,label,20,'#243e60',500);
  if(i<3) text(x+247,139,'→',22,'#61758e');
});
text(36,190,'知识范围',21,'#14283f',600);
text(164,190,'保留 01–18 编号；十条补全路线跨领域衔接，覆盖不代表完成',16,'#516278');
domains.forEach(([id,name,detail],i) => {
  const x = 36+(i%3)*356, y = 206+Math.floor(i/3)*94;
  const accent = ['01','04','09','12','13','16','17','18'].includes(id) ? '#3c70b4' : null;
  rect(x,y,336,82,'#ffffff','#dfe5ee');
  if(accent) rect(x,y+13,4,56,accent,'none',2);
  text(x+16,y+31,`${id}  ${name}`,20,'#20324a',500);
  text(x+16,y+60,detail,16,'#526276');
});
text(36,798,'十条全景补全路线 · 每条 3 个验收节点，全部待实施',23,'#14283f',600);
const routes = [
  ['SIG', '数学与信号系统', '01 / 18 · M0 起步', '微分方程 → 采样与卷积 → 状态空间'],
  ['CIR', '电路与半导体器件', '01 / 16 / 18 · SIG 后，与 M1 并行', '电路分析 → MOS / CMOS → 寄生与噪声'],
  ['PRA', '数字设计实践贯通', '16 / 17 / 18 · G1 → M1 → G2', 'FIFO → 故障调试 → 阵列与综合'],
  ['HET', 'CPU / GPU / DSP 对照', '04 / 16 / 18 · ARCH 后，M1/M3 专题', '顺序与乱序 → SIMT → DSP 数据流'],
  ['CHIP', '物理实现与产品流程', '04 / 16 / 17 / 18 · CIR + DD 后', '工艺与单元 → 供电封装 → 测试良率'],
  ['DEP', '编译运行时设备贯通', '07 / 08 / 10 / 11 / 17 · M2/M3 的 G2', '单 Linear → C / QEMU → RTL / 模型'],
  ['CLA', '传统机器学习与经典 AI', '01 / 02 / 09 / 12 · M0/M3 → M4', '树核聚类 → 逻辑与规划 → 概率推理'],
  ['DLE', '深度学习推导与比较', '09 / 10 / 17 · M3 基础与专题', '梯度校验 → 结构性质 → 生成模型比较'],
  ['EMB', '感知控制与具身', '01 / 09 / 12 / 18 · SIG + CLA/DLE 后', '视觉与语音 → 估计与控制 → 仿真机器人'],
  ['SCALE', '大规模 AI 工程', '05 / 11 / 13 / 17 / 18 · M3/M4 + S2', '并行训练 → 分片推理 → 服务与恢复'],
];
routes.forEach(([id,name,where,steps],i) => {
  const x=36+(i%2)*534, y=820+Math.floor(i/2)*122;
  const core=['PRA','DEP','DLE'].includes(id);
  rect(x,y,514,108,core?'#e6f3ef':'#e9f0fb');
  text(x+16,y+29,`${id}  ${name}`,21,core?'#216d63':'#28558c',600);
  text(x+16,y+56,`归属 ${where}`,16,'#526276');
  text(x+16,y+85,steps,18,'#20324a');
});
text(36,1459,'实施顺序：A 共同基础 → B 小闭环 → C 跨层部署 → D 广度专题',21,'#14283f',600);
text(36,1494,'优先兑现 PRA / DEP / DLE；器件、物理、具身与规模工程按前置和预算深入。',18,'#405b7d');
text(36,1526,'30 个节点包含既有实验复用，不与原十组 60 项深化实验简单相加。',18,'#405b7d');
['跨层契约', '资源预算', '共同实验资产', '教材学习者验证'].forEach((label,i) => {
  const x=36+i*267; rect(x,1550,247,44,'#e8ecf2'); text(x+16,1579,label,19);
});
text(36,1628,'已验证起点：Python GEMM 与单 MAC；本轮只补课程、实验规划和覆盖图。',18,'#526276');
text(36,1660,'SPICE / RTL / QEMU / 物理流程 / 多进程 / 机器人仿真分别验收，模型不代替实物证据。',17,'#526276');
s.push('</g></svg>');
const svg = s.join('\n')+'\n';
const base = path.join(__dirname,'knowledge-coverage-v6');
fs.writeFileSync(base+'.svg',svg);
if(process.argv.includes('--png')) {
  require('sharp')(Buffer.from(svg)).png().toFile(base+'.png')
    .then(() => console.log('Wrote V6 SVG and PNG'))
    .catch(err => {console.error(err.message); process.exitCode=1;});
} else console.log('Wrote V6 SVG');
