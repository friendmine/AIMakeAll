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
