PYTHON ?= python3
VERILATOR ?= verilator

.PHONY: test demo rtl-test eda-doctor

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	$(PYTHON) -m reference.int8

eda-doctor:
	$(PYTHON) tools/eda/inspect_environment.py --output build/eda-environment.json

rtl-test:
	mkdir -p build/mac
	$(VERILATOR) --cc --exe --build -Wall --top-module mac_int8 --Mdir build/mac hardware/rtl/mac_int8.sv $(CURDIR)/tests/mac_int8_tb.cpp
	./build/mac/Vmac_int8

LINEAR_LAB := labs/01-linear257
LINEAR_QEMU ?= build/qemu-course/out/qemu-system-riscv32
LINEAR_BUDGET ?= 3212
.PHONY: linear linear-rtl linear-all connections
linear:
	$(PYTHON) $(LINEAR_LAB)/walkthrough.py --native --budget $(LINEAR_BUDGET) --report build/linear/host.json

build/linear/mac/Vmac_int8: hardware/rtl/mac_int8.sv $(LINEAR_LAB)/mac_tile.cpp
	mkdir -p build/linear/mac
	$(VERILATOR) --cc --exe --build -Wall --top-module mac_int8 --Mdir build/linear/mac $< $(CURDIR)/$(LINEAR_LAB)/mac_tile.cpp

linear-rtl: build/linear/mac/Vmac_int8
	$(PYTHON) $(LINEAR_LAB)/walkthrough.py --native --rtl $< --budget $(LINEAR_BUDGET) --report build/linear/rtl.json

linear-all: build/linear/mac/Vmac_int8
	$(PYTHON) $(LINEAR_LAB)/walkthrough.py --native --rtl $< --qemu $(LINEAR_QEMU) --budget $(LINEAR_BUDGET) --report build/linear/all-$(LINEAR_BUDGET).json

connections:
	$(PYTHON) $(LINEAR_LAB)/connections.py

.PHONY: design-trial device-test
device-test:
	$(PYTHON) simulator/qemu-v0/check_device.py $(LINEAR_QEMU)

design-trial:
	$(MAKE) linear-all LINEAR_BUDGET=3212
	$(MAKE) linear-all LINEAR_BUDGET=1606
	$(PYTHON) $(LINEAR_LAB)/connections.py handoff --reports build/linear/all-3212.json build/linear/all-1606.json

PROJ_LAB := labs/02-trained-projection
PROJ_BUILD := build/projection
PROJ_TOP := hardware/rtl/projection_tile.sv
PROJ_RTL := $(PROJ_TOP) hardware/rtl/mac_int8.sv
PROJ_SHARED := $(PROJ_BUILD)/shared/Vprojection_tile
PROJ_BANKED := $(PROJ_BUILD)/banked/Vprojection_tile

$(PROJ_SHARED) $(PROJ_BANKED): $(PROJ_RTL) $(PROJ_LAB)/tile_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --trace -Wall --top-module projection_tile "-GBANKED=1'b$(if $(findstring /banked/,$@),1,0)" --Mdir $(@D) $(PROJ_RTL) $(CURDIR)/$(PROJ_LAB)/tile_tb.cpp

.PHONY: projection-rtl projection-train projection-synth
projection-rtl: $(PROJ_SHARED) $(PROJ_BANKED)
	$(PYTHON) $(PROJ_LAB)/replay.py --shared $(PROJ_SHARED) --banked $(PROJ_BANKED) --expected $(PROJ_LAB)/verified-run.json --output $(PROJ_BUILD)

projection-train: $(PROJ_SHARED) $(PROJ_BANKED)
	$(PYTHON) $(PROJ_LAB)/experiment.py --shared $(PROJ_SHARED) --banked $(PROJ_BANKED) --output $(PROJ_BUILD)

YOSYS ?= yosys
projection-synth:
	mkdir -p $(PROJ_BUILD)
	$(YOSYS) -Q -l $(PROJ_BUILD)/shared-yosys.log -p 'read_verilog -sv $(PROJ_RTL); synth -top projection_tile; check -assert; stat' > /dev/null
	$(YOSYS) -Q -l $(PROJ_BUILD)/banked-yosys.log -p 'read_verilog -sv $(PROJ_RTL); chparam -set BANKED 1 projection_tile; synth -top projection_tile; check -assert; stat' > /dev/null

GEN_LAB := labs/03-rv32-generation
GEN_BUILD := build/generation
GEN_SOC := $(GEN_BUILD)/soc/Vgeneration_soc
GEN_RTL := hardware/rtl/generation_soc.sv hardware/rtl/projection_mmio.sv $(PROJ_RTL) hardware/ip/picorv32/picorv32.v
GEN_CHECKPOINT ?= $(PROJ_BUILD)/copy-32.pt
GEN_SAMPLE ?= 0

$(GEN_SOC): $(GEN_RTL) $(GEN_LAB)/soc_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --timescale 1ns/1ps --top-module generation_soc --Mdir $(@D) $(GEN_RTL) $(CURDIR)/$(GEN_LAB)/soc_tb.cpp

$(PROJ_BUILD)/copy-32.pt:
	$(PYTHON) $(PROJ_LAB)/experiment.py --train-only --output $(PROJ_BUILD)

.PHONY: generation generation-rtl generation-synth
generation-rtl: $(GEN_SOC)

generation-synth:
	mkdir -p $(GEN_BUILD)
	$(YOSYS) -Q -l $(GEN_BUILD)/device-synth.log -p 'read_verilog -sv hardware/rtl/projection_mmio.sv $(PROJ_RTL); synth -top projection_mmio; check -assert; stat' > /dev/null

generation: $(GEN_SOC) $(GEN_CHECKPOINT)
	$(PYTHON) $(GEN_LAB)/run.py --checkpoint $(GEN_CHECKPOINT) --sample $(GEN_SAMPLE) --qemu $(LINEAR_QEMU) --rtl $(GEN_SOC) --output $(GEN_BUILD)/sample-$(GEN_SAMPLE)

PERF_LAB := labs/04-rv32-performance
PERF_BUILD ?= build/performance
.PHONY: performance
performance: $(GEN_SOC) $(GEN_CHECKPOINT)
	$(PYTHON) $(PERF_LAB)/compare.py --checkpoint $(GEN_CHECKPOINT) --sample $(GEN_SAMPLE) --rtl $(GEN_SOC) --output $(PERF_BUILD)/sample-$(GEN_SAMPLE)

PREPACK_BUILD ?= build/prepack
.PHONY: prepack
prepack: $(GEN_SOC) $(GEN_CHECKPOINT)
	$(PYTHON) labs/05-weight-prepack/compare.py --checkpoint $(GEN_CHECKPOINT) --sample $(GEN_SAMPLE) --rtl $(GEN_SOC) --output $(PREPACK_BUILD)/sample-$(GEN_SAMPLE)

SWITCH_BUILD ?= build/model-switch
SWITCH_CHECKPOINT_B ?= $(PROJ_BUILD)/copy-24.pt

# The Lab 02 training invocation creates both widths. Recover a missing B on its own too.
$(PROJ_BUILD)/copy-24.pt: | $(PROJ_BUILD)/copy-32.pt
	@test -f $@ || $(PYTHON) $(PROJ_LAB)/experiment.py --train-only --train-width 24 --output $(PROJ_BUILD)

.PHONY: model-switch
model-switch: $(GEN_SOC) $(GEN_CHECKPOINT) $(SWITCH_CHECKPOINT_B)
	$(PYTHON) labs/06-model-switch/run_switch.py --model-a $(GEN_CHECKPOINT) --model-b $(SWITCH_CHECKPOINT_B) --sample $(GEN_SAMPLE) --rtl $(GEN_SOC) --output $(SWITCH_BUILD)/sample-$(GEN_SAMPLE)

QKV_BUILD ?= build/fused-qkv
.PHONY: fused-qkv
fused-qkv: $(GEN_SOC) $(PROJ_BANKED) $(GEN_CHECKPOINT) $(SWITCH_CHECKPOINT_B)
	$(PYTHON) labs/07-fused-qkv/run_qkv.py --model-a $(GEN_CHECKPOINT) --model-b $(SWITCH_CHECKPOINT_B) --sample $(GEN_SAMPLE) --rtl $(GEN_SOC) --tile $(PROJ_BANKED) --output $(QKV_BUILD)/sample-$(GEN_SAMPLE)

BYTE_LAB := labs/08-byte-transfer
BYTE_BUILD ?= build/byte-transfer
BYTE_MODELS ?= $(BYTE_BUILD)/models
BYTE_PAIR ?= 0
$(BYTE_MODELS)/byte-%.pt: $(BYTE_LAB)/train_byte.py $(BYTE_LAB)/corpus.py $(BYTE_LAB)/contract.json models/tiny_copy.py
	$(PYTHON) $(BYTE_LAB)/train_byte.py --width $* --output $@

$(BYTE_MODELS)/baseline/byte-%.pt: $(BYTE_LAB)/train_byte.py $(BYTE_LAB)/corpus.py $(BYTE_LAB)/initial-contract.json models/tiny_copy.py
	$(PYTHON) $(BYTE_LAB)/train_byte.py --width $* --contract $(BYTE_LAB)/initial-contract.json --output $@

.PHONY: byte-transfer
byte-transfer: $(GEN_SOC) $(PROJ_BANKED) $(BYTE_MODELS)/byte-32.pt $(BYTE_MODELS)/byte-24.pt $(BYTE_MODELS)/baseline/byte-32.pt $(BYTE_MODELS)/baseline/byte-24.pt
	$(PYTHON) $(BYTE_LAB)/run_byte.py --models $(BYTE_MODELS) --rtl $(GEN_SOC) --tile $(PROJ_BANKED) --pair $(BYTE_PAIR) --output $(BYTE_BUILD)/pair-$(BYTE_PAIR)

.PHONY: lab09
lab09: $(GEN_SOC) $(PROJ_BANKED) build/byte-transfer/models/byte-32.pt
	$(PYTHON) labs/09-vocabulary-head/quality.py
	$(PYTHON) labs/09-vocabulary-head/timing.py
	$(PYTHON) labs/09-vocabulary-head/check_bus.py
	$(PYTHON) labs/09-vocabulary-head/reject.py
	$(PYTHON) labs/09-vocabulary-head/summarize.py

LM_TRAIN := labs/10-language-model/train.py
build/language/width-%.pt: $(LM_TRAIN) models/byte_lm.py labs/10-language-model/python-help.json.gz
	$(PYTHON) $(LM_TRAIN) --width $*
.PHONY: lab10 lab11
lab10: build/language/width-48.pt
lab11: lab10 build/language/width-40.pt
	$(PYTHON) labs/11-model-width/compare.py

.PHONY: lab12
lab12: lab10 $(PROJ_BANKED)
	$(PYTHON) labs/12-matrix-tiles/run.py

build/dma-arbiter/Vdma_arbiter: hardware/rtl/dma_arbiter.sv labs/13-dma-fifo/bench.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --assert --trace --top-module dma_arbiter --Mdir $(@D) $< $(CURDIR)/labs/13-dma-fifo/bench.cpp
.PHONY: lab13
lab13: build/dma-arbiter/Vdma_arbiter
	$< build/dma-arbiter/trace.vcd > build/dma-arbiter/report.json

STREAM_TILE := build/array-design/stream/Vprojection_stream
$(STREAM_TILE): hardware/rtl/projection_stream.sv hardware/rtl/mac_int8.sv $(PROJ_LAB)/tile_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --trace --top-module projection_stream --Mdir $(@D) -CFLAGS -DSTREAM_TILE $< hardware/rtl/mac_int8.sv $(CURDIR)/$(PROJ_LAB)/tile_tb.cpp
.PHONY: lab14
lab14: lab10 $(STREAM_TILE) $(PROJ_BANKED)
	$(PYTHON) labs/14-streaming-array/compare.py

.PHONY: lab15 lab16
lab15: lab11 $(PROJ_BANKED)
	$(PYTHON) labs/15-execution-plan/compiler.py
	$(PYTHON) labs/15-execution-plan/check_plan.py
lab16: lab15
	$(PYTHON) labs/16-kv-cache/run.py

.PHONY: lab17
lab17: lab15 $(GEN_SOC)
	LINEAR_QEMU=$(abspath $(LINEAR_QEMU)) $(PYTHON) labs/17-language-soc/execute.py

STREAM_SOC := build/array-design/soc/Vgeneration_soc
$(STREAM_SOC): $(GEN_RTL) hardware/rtl/projection_stream.sv $(GEN_LAB)/soc_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --timescale 1ns/1ps -DAIM_STREAM_SOC --top-module generation_soc --Mdir $(@D) $(GEN_RTL) hardware/rtl/projection_stream.sv $(CURDIR)/$(GEN_LAB)/soc_tb.cpp
.PHONY: lab18 lab19
lab18: lab15 $(GEN_SOC) $(STREAM_SOC)
	$(PYTHON) labs/18-joint-selection/select_model.py
lab19: lab18
	$(PYTHON) labs/19-transfer/run.py

.PHONY: lab20
lab20: lab18
	$(PYTHON) labs/20-tool-agent/run.py

.PHONY: course-linux-qemu lab21 lab22 lab23 labs09-23
course-linux-qemu:
	sh labs/21-linux-driver/build.sh
lab21: lab15 course-linux-qemu
	$(PYTHON) labs/21-linux-driver/boot.py 21
lab22: lab15 course-linux-qemu
	$(PYTHON) labs/21-linux-driver/boot.py 22
	$(PYTHON) labs/22-network-pcie/peers.py
lab23: lab15 course-linux-qemu
	$(PYTHON) labs/23-cxl-placement/run.py

labs09-23: lab09 lab10 lab11 lab12 lab13 lab14 lab15 lab16 lab17 lab18 lab19 lab20 lab21 lab22 lab23

WORD_SOC := build/design-challenge/soc/Vgeneration_soc
$(WORD_SOC): $(GEN_RTL) hardware/rtl/projection_stream.sv $(GEN_LAB)/soc_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --timescale 1ns/1ps -DAIM_STREAM_SOC -DAIM_WORD_DMA --top-module generation_soc --Mdir $(@D) $(GEN_RTL) hardware/rtl/projection_stream.sv $(CURDIR)/$(GEN_LAB)/soc_tb.cpp

.PHONY: language-ci lab24 lab25 lab26 labs24-26
language-ci: $(GEN_SOC)
	$(PYTHON) labs/17-language-soc/ci_smoke.py

lab24: lab15 $(STREAM_SOC) $(WORD_SOC) word-dma-test
	$(PYTHON) labs/24-design-challenge/challenge.py

lab25: $(GEN_SOC)
	$(PYTHON) labs/25-model-study/study.py

lab26:
	$(PYTHON) labs/26-postroute/route.py baseline
	$(PYTHON) labs/26-postroute/route.py word_dma
	$(PYTHON) labs/26-postroute/summarize.py

labs24-26: lab24 lab25 lab26

WORD_DMA_TEST := build/design-challenge/dma-test/Vprojection_mmio
$(WORD_DMA_TEST): hardware/rtl/projection_mmio.sv hardware/rtl/projection_stream.sv hardware/rtl/mac_int8.sv labs/24-design-challenge/dma_tb.cpp
	mkdir -p $(@D)
	$(VERILATOR) --cc --exe --build --top-module projection_mmio -DAIM_STREAM_SOC -DAIM_WORD_DMA --Mdir $(@D) $(filter %.sv,$^) $(abspath $(filter %.cpp,$^))
.PHONY: word-dma-test
word-dma-test: $(WORD_DMA_TEST)
	$(WORD_DMA_TEST) > build/design-challenge/dma-check.json
