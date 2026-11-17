// SPDX-License-Identifier: MIT
// node docs/images/render-knowledge-coverage-v7.cjs [--png]
// SVG generation uses Node.js only; optional PNG export requires Sharp.
const fs = require('node:fs');
const path = require('node:path');
const domains = [
  ['01', '数学与数值', '数学、信号、学习界与证明前提'],
  ['02', '算法与数据结构', '数据结构、复杂度、计算边界'],
  ['03', '编程与程序执行', 'C / ABI、内存、正确性与性能'],
  ['04', '体系结构与加速器', '异构计算、存储、SoC 生命周期'],
  ['05', '操作系统原理', '调度、虚拟内存、并发与持久化'],
  ['06', 'Linux 系统构建', '构建、启动链、固件与恢复'],
  ['07', '模拟器与驱动', 'QEMU、MMIO、DMA 与设备'],
  ['08', 'AI 编译', '计算图、布局、量化与分块'],
  ['09', '深度学习基础', '学习与生成、分布变化、校准'],
  ['10', '从零 LLM', '文本、Transformer、训练与微调'],
  ['11', '推理运行时', '认证、加载、KV、版本与回退'],
  ['12', 'Agent 与检索', '方法比较、工具授权、感知控制'],
  ['13', '网络与分布式通信', '通信、分布式训练、推理与服务'],
  ['14', 'I/O 与 PCIe', '片内互连、BAR、DMA 与中断'],
  ['15', 'CXL 与异构内存', 'Type 3、译码、一致性与放置'],
  ['16', '数字设计与时序', '电路、混合信号、RTL 与物理'],
  ['17', '系统化验证', '参考、形式、信任链与故障'],
  ['18', '仿真建模与可信度', '事件、周期、连续系统与可信度'],
];
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const s = [];
const rect = (x,y,w,h,fill,stroke='none',r=10) => s.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}"/>`);
const text = (x,y,value,size=18,fill='#20324a',weight=400) => s.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${esc(value)}</text>`);
s.push('<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="1930" viewBox="0 0 1120 1930" role="img" aria-labelledby="title description">');
s.push('<title id="title">AIMakeAll 知识覆盖图 V7</title><desc id="description">十八个领域、十条全景路线，以及生命周期、信任链、分布变化、方法比较、理论边界和混合信号六项跨层补强。六项各三个验收节点，全部待实施，复用已有课程。阶段与共同交付沿用原规划，状态统一见课程状态总表。</desc>');
s.push('<g font-family="PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">');
rect(0,0,1120,1930,'#f5f7fb','none',0);
text(36,48,'AIMakeAll · 知识覆盖图 V7',32,'#14283f',600);
text(36,80,'全景通识 → 核心实践 → 专题深入 · 仿真优先，无需实板或流片',18,'#516278');
const stages = ['RISC-V + NPU', 'QEMU + 运行时', '从零 LLM + 编译', 'Agent + 任务评估'];
stages.forEach((label,i) => {
  const x = 36+i*270;
  rect(x,108,238,48,'#e6edf7'); text(x+16,139,label,20,'#243e60',500);
  if(i<3) text(x+247,139,'→',22,'#61758e');
});
text(36,190,'知识范围',21,'#14283f',600);
text(164,190,'保留 01–18 编号；新增六项跨层连接，覆盖不代表完成',16,'#516278');
domains.forEach(([id,name,detail],i) => {
  const x = 36+(i%3)*356, y = 206+Math.floor(i/3)*94;
  const accent = ['01','04','09','12','13','16','17','18'].includes(id) ? '#3c70b4' : null;
  rect(x,y,336,82,'#ffffff','#dfe5ee');
  if(accent) rect(x,y+13,4,56,accent,'none',2);
  text(x+16,y+31,`${id}  ${name}`,20,'#20324a',500);
  text(x+16,y+60,detail,16,'#526276');
});
text(36,798,'十条既有全景路线 · 各 3 个验收节点，全部待实施',23,'#14283f',600);
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
  const x=36+(i%2)*534, y=820+Math.floor(i/2)*78;
  const core=['PRA','DEP','DLE'].includes(id);
  rect(x,y,514,68,core?'#e6f3ef':'#e9f0fb');
  text(x+16,y+29,`${id}  ${name}`,19,core?'#216d63':'#28558c',600);
  text(x+16,y+54,steps,17,'#20324a');
});
text(36,1241,'本轮六项跨层补强 · 各 3 个验收节点，全部待实施',23,'#14283f',600);
const strengthening = [
  ['LIFE', 'SoC 完整运行生命周期', '04 / 06 / 07 / 16 / 17 / 18 · G1 → M1/M2', '启动 → 排空与唤醒 → 看门狗与恢复'],
  ['TRUST', '硬件到模型的信任链', '03 / 05 / 07 / 08 / 11 / 12 / 17 · G0 → G3', '信任边界 → 认证与防回滚 → 更新恢复'],
  ['SHIFT', '数据变化后的可靠性', '01 / 09 / 10 / 11 / 12 / 13 / 17 · M3 → M4', '分布变化 → 校准与拒答 → 监测与更新'],
  ['SELECT', '不同 AI 方法统一比较', '02 / 09 / 10 / 12 / 17 · M3/M4', '共同任务 → 多种策略 → 消融与选择'],
  ['LIMIT', '理论边界与可证明范围', '01 / 02 / 09 / 17 / 18 · M0 起，按需深入', '有界与无界 → 复杂度 → 有限样本保证'],
  ['MIX', '模拟与混合信号系统角色', '01 / 04 / 09 / 16 / 18 · SIG/CIR 后', '放大与转换 → 噪声与抖动 → 数字误差'],
];
strengthening.forEach(([id,name,where,steps],i) => {
  const x=36+(i%2)*534, y=1262+Math.floor(i/2)*122;
  rect(x,y,514,108,'#f0eaf8');
  text(x+16,y+29,`${id}  ${name}`,21,'#604783',600);
  text(x+16,y+56,`归属 ${where}`,16,'#526276');
  text(x+16,y+85,steps,18,'#20324a');
});
text(36,1656,'阶段：G0 契约与边界 → G1 小模块 → G2 跨层 → G3 / M4 专题',21,'#14283f',600);
text(36,1690,'每个节点：小课 → 练习 → 最小实验 → 排错 → 迁移；核心仍优先 FIFO / Linear / 小模型。',17,'#405b7d');
text(36,1722,'原十组 60 项、十路线 30 个节点、六项 18 个节点存在复用，不简单累加。',18,'#405b7d');
text(36,1754,'当前状态统一见课程总表：规划 / 教材 / 实现 / 复现 / 独立学习者验证。',18,'#405b7d');
['跨层契约', '资源预算', '共同实验资产', '教材学习者验证'].forEach((label,i) => {
  const x=36+i*267; rect(x,1774,247,44,'#e8ecf2'); text(x+16,1803,label,19);
});
text(36,1856,'已验证起点：Python GEMM 与单 MAC；本轮只更新规划、状态与图，无新增实验成果。',17,'#526276');
text(36,1888,'状态模型 / RTL / 签名工具 / 数据实验 / SPICE 分别验收；不依赖板卡或流片。',17,'#526276');
s.push('</g></svg>');
const svg = s.join('\n')+'\n';
const base = path.join(__dirname,'knowledge-coverage-v7');
fs.writeFileSync(base+'.svg',svg);
if(process.argv.includes('--png')) {
  require('sharp')(Buffer.from(svg)).png().toFile(base+'.png')
    .then(() => console.log('Wrote V7 SVG and PNG'))
    .catch(err => {console.error(err.message); process.exitCode=1;});
} else console.log('Wrote V7 SVG');
