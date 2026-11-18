/* SPDX-License-Identifier: GPL-2.0-or-later
 * Teaching device for a private QEMU 9.2.4 virt machine, single hart.
 */
#include "qemu/osdep.h"
#include "exec/address-spaces.h"
#include "hw/sysbus.h"
#include "qapi/error.h"
#include "qemu/bswap.h"
#include "qemu/timer.h"
#include "aimakeall-npu.h"

#define TYPE_AIM_NPU "aimakeall-npu"
OBJECT_DECLARE_SIMPLE_TYPE(AimNpu, AIM_NPU)
enum { IDLE = 0, BUSY = 1, DONE = 2, FAILED = 4 };
enum { A, B, C, M, N, K, NREG };

struct AimNpu {
    SysBusDevice parent_obj;
    MemoryRegion io;
    QEMUTimer timer;
    uint64_t ram_base, ram_size;
    uint32_t cfg[NREG], status, error;
};

static bool in_ram(AimNpu *s, uint64_t addr, uint64_t len)
{
    return addr >= s->ram_base && addr + len <= s->ram_base + s->ram_size &&
           addr + len <= (1ULL << 32);
}

static unsigned check_command(AimNpu *s)
{
    const uint32_t *r = s->cfg;
    if (!r[M] || !r[N] || !r[K] || r[M] > 256 || r[N] > 256 || r[K] > 256) {
        return 2;
    }
    uint64_t al = r[M] * r[K], bl = r[K] * r[N], cl = 4 * r[M] * r[N];
    if ((r[C] & 3) || !in_ram(s, r[A], al) || !in_ram(s, r[B], bl) ||
        !in_ram(s, r[C], cl)) {
        return 3;
    }
    if ((r[C] < r[A] + al && r[A] < r[C] + cl) ||
        (r[C] < r[B] + bl && r[B] < r[C] + cl)) {
        return 4;
    }
    return 0;
}

static void finish(void *opaque)
{
    AimNpu *s = opaque;
    const uint32_t *r = s->cfg;
    g_autofree int8_t *a = g_malloc(r[M] * r[K]);
    g_autofree int8_t *b = g_malloc(r[N] * r[K]);
    g_autofree uint32_t *c = g_new(uint32_t, r[M] * r[N]);
    if (address_space_read(&address_space_memory, r[A], MEMTXATTRS_UNSPECIFIED,
                           a, r[M] * r[K]) != MEMTX_OK ||
        address_space_read(&address_space_memory, r[B], MEMTXATTRS_UNSPECIFIED,
                           b, r[N] * r[K]) != MEMTX_OK) {
        s->status = FAILED;
        s->error = 3;
        return;
    }
    for (unsigned i = 0; i < r[M]; ++i) {
        for (unsigned j = 0; j < r[N]; ++j) {
            uint32_t sum = 0;
            for (unsigned p = 0; p < r[K]; ++p) {
                sum += (uint32_t)(a[i*r[K]+p] * b[p*r[N]+j]);
            }
            c[i*r[N]+j] = cpu_to_le32(sum);
        }
    }
    if (address_space_write(&address_space_memory, r[C], MEMTXATTRS_UNSPECIFIED,
                            c, 4 * r[M] * r[N]) != MEMTX_OK) {
        s->status = FAILED;
        s->error = 3;
        return;
    }
    s->status = DONE;
}

static MemTxResult read_reg(void *opaque, hwaddr off, uint64_t *v,
                            unsigned size, MemTxAttrs attrs)
{
    AimNpu *s = opaque;
    switch (off) {
    case 0x00: *v = 1; break;
    case 0x08: *v = s->status; break;
    case 0x0c: *v = s->error; break;
    default:
        if (off < 0x10 || off > 0x24) {
            return MEMTX_ERROR;
        }
        *v = s->cfg[(off - 0x10) / 4];
    }
    return MEMTX_OK;
}

static MemTxResult write_reg(void *opaque, hwaddr off, uint64_t v,
                             unsigned size, MemTxAttrs attrs)
{
    AimNpu *s = opaque;
    if (off == 4 && v == 2 && s->status != BUSY) {
        s->status = IDLE;
        s->error = 0;
    } else if (s->status != IDLE) {
        return MEMTX_ERROR;
    } else if (off == 4) {
        s->error = v == 1 ? check_command(s) : 1;
        if (s->error) {
            s->status = FAILED;
        } else {
            s->status = BUSY;
            /* Artificial latency exposes BUSY and permits reset before completion. */
            timer_mod(&s->timer, qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL) + 1000);
        }
    } else if (off >= 0x10 && off <= 0x24) {
        s->cfg[(off - 0x10) / 4] = v;
    } else {
        return MEMTX_ERROR;
    }
    return MEMTX_OK;
}

static const MemoryRegionOps ops = {
    .read_with_attrs = read_reg, .write_with_attrs = write_reg,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 4, .max_access_size = 4, .unaligned = false },
    .impl = { .min_access_size = 4, .max_access_size = 4 },
};

static void reset(DeviceState *dev)
{
    AimNpu *s = AIM_NPU(dev);
    timer_del(&s->timer);
    memset(s->cfg, 0, sizeof(s->cfg));
    s->status = IDLE;
    s->error = 0;
}

static void init(Object *obj)
{
    AimNpu *s = AIM_NPU(obj);
    memory_region_init_io(&s->io, obj, &ops, s, TYPE_AIM_NPU, 0x1000);
    sysbus_init_mmio(SYS_BUS_DEVICE(s), &s->io);
    timer_init_ns(&s->timer, QEMU_CLOCK_VIRTUAL, finish, s);
}

static void fini(Object *obj)
{
    timer_deinit(&AIM_NPU(obj)->timer);
}

static void class_init(ObjectClass *klass, void *data)
{
    device_class_set_legacy_reset(DEVICE_CLASS(klass), reset);
}

static const TypeInfo info = {
    .name = TYPE_AIM_NPU, .parent = TYPE_SYS_BUS_DEVICE,
    .instance_size = sizeof(AimNpu), .instance_init = init,
    .instance_finalize = fini, .class_init = class_init,
};

static void register_types(void) { type_register_static(&info); }
type_init(register_types)

void aim_npu_map(hwaddr base, uint64_t ram_base, uint64_t ram_size)
{
    DeviceState *dev = qdev_new(TYPE_AIM_NPU);
    AimNpu *s = AIM_NPU(dev);
    s->ram_base = ram_base;
    s->ram_size = ram_size;
    sysbus_realize_and_unref(SYS_BUS_DEVICE(dev), &error_fatal);
    sysbus_mmio_map(SYS_BUS_DEVICE(dev), 0, base);
}
