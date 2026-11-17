PYTHON ?= python3
VERILATOR ?= verilator

.PHONY: test demo rtl-test

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	$(PYTHON) -m reference.int8

rtl-test:
	mkdir -p build/mac
	$(VERILATOR) --cc --exe --build -Wall --top-module mac_int8 --Mdir build/mac hardware/rtl/mac_int8.sv $(CURDIR)/tests/mac_int8_tb.cpp
	./build/mac/Vmac_int8
