// SPDX-License-Identifier: GPL-2.0-or-later
/* Functional PCIe teaching endpoint. One page holds A, B and four results. */
#include "qemu/osdep.h"
#include "hw/pci/pci_device.h"
#include "hw/pci/pcie.h"
#include "qemu/module.h"
#include "qemu/bswap.h"

#define TYPE_AIM_PCIE "aim-pcie"
OBJECT_DECLARE_SIMPLE_TYPE(AimPCIE, AIM_PCIE)
struct AimPCIE {
    PCIDevice parent;
    MemoryRegion bar;
    uint32_t page, k, status, completed;
};

static uint64_t aim_read(void *opaque, hwaddr off, unsigned size)
{
    AimPCIE *s = opaque;
    switch (off) {
    case 0:
        return 0x41494d31;
    case 4:
        return s->page;
    case 8:
        return s->k;
    case 16:
        return s->status;
    case 20:
        return s->completed;
    default:
        return 0;
    }
}

static void aim_write(void *opaque, hwaddr off, uint64_t value, unsigned size)
{
    AimPCIE *s = opaque;
    int8_t a[32], b[128];
    uint32_t c[4];
    if (off == 4) {
        s->page = value;
    } else if (off == 8) {
        s->k = value;
    } else if (off == 12) {
        if (value == 0) {
            s->status = 0;
            return;
        }
        /* Teaching fault injection: hold BUSY until the driver's reset. */
        if (value == 2 && s->status == 0) {
            s->status = 4;
            return;
        }
        if (s->status == 4) {
            return;
        }
        if (value != 1 || !s->k || s->k > 32 || (s->page & 4095) || s->page < (1u << 20) ||
            s->page >= (384u << 20)) {
            s->status = 2;
            return;
        }
        if (pci_dma_read(PCI_DEVICE(s), s->page, a, s->k) != MEMTX_OK ||
            pci_dma_read(PCI_DEVICE(s), s->page + 64, b, 4 * s->k) != MEMTX_OK) {
            s->status = 3;
            return;
        }
        for (int lane = 0; lane < 4; ++lane) {
            int sum = 0;
            for (int k = 0; k < s->k; ++k) {
                sum += a[k] * b[k * 4 + lane];
            }
            c[lane] = cpu_to_le32(sum);
        }
        if (pci_dma_write(PCI_DEVICE(s), s->page + 256, c, sizeof(c)) != MEMTX_OK) {
            s->status = 3;
            return;
        }
        s->completed++;
        s->status = 1;
    }
}

static const MemoryRegionOps ops = {
    .read = aim_read,
    .write = aim_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = {.min_access_size = 4, .max_access_size = 4},
    .impl = {.min_access_size = 4, .max_access_size = 4},
};

static void aim_realize(PCIDevice *pci, Error **errp)
{
    AimPCIE *s = AIM_PCIE(pci);
    pcie_endpoint_cap_init(pci, 0x80);
    memory_region_init_io(&s->bar, OBJECT(s), &ops, s, TYPE_AIM_PCIE, 4096);
    pci_register_bar(pci, 0, PCI_BASE_ADDRESS_SPACE_MEMORY, &s->bar);
}
static void aim_class_init(ObjectClass *klass, void *data)
{
    PCIDeviceClass *c = PCI_DEVICE_CLASS(klass);
    c->vendor_id = 0x1234;
    c->device_id = 0x10ae;
    c->class_id = PCI_CLASS_OTHERS;
    c->realize = aim_realize;
}
static const TypeInfo info = {
    .name = TYPE_AIM_PCIE,
    .parent = TYPE_PCI_DEVICE,
    .instance_size = sizeof(AimPCIE),
    .class_init = aim_class_init,
    .interfaces = (InterfaceInfo[]){{INTERFACE_PCIE_DEVICE}, {}},
};
static void register_aim(void) { type_register_static(&info); }
type_init(register_aim)
