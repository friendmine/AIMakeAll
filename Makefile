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
