// Linux init and userspace driver for a private, single-device QEMU teaching guest.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"

	"net"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}
func require(ok bool, message string) {
	if !ok {
		panic(message)
	}
}

var order = binary.LittleEndian

type device struct {
	bar, page []byte
	bdf       string
}

func (d *device) reg(off int) *uint32   { return (*uint32)(unsafe.Pointer(&d.bar[off])) }
func (d *device) set(off int, v uint32) { atomic.StoreUint32(d.reg(off), v) }
func (d *device) get(off int) uint32    { return atomic.LoadUint32(d.reg(off)) }
func discover() *device {
	paths, e := filepath.Glob("/sys/bus/pci/devices/*")
	check(e)
	for _, p := range paths {
		id, _ := os.ReadFile(p + "/device")
		vendor, _ := os.ReadFile(p + "/vendor")
		if strings.TrimSpace(string(id)) != "0x10ae" || strings.TrimSpace(string(vendor)) != "0x1234" {
			continue
		}
		cfg, e := os.OpenFile(p+"/config", os.O_RDWR, 0)
		check(e)
		defer cfg.Close()
		var cmd [2]byte
		_, e = cfg.ReadAt(cmd[:], 4)
		check(e)
		cmd[0] |= 6
		_, e = cfg.WriteAt(cmd[:], 4)
		check(e)
		f, e := os.OpenFile(p+"/resource0", os.O_RDWR, 0)
		check(e)
		defer f.Close()
		bar, e := syscall.Mmap(int(f.Fd()), 0, 4096, 3, syscall.MAP_SHARED)
		check(e)
		page, e := syscall.Mmap(-1, 0, 4096, 3, syscall.MAP_PRIVATE|syscall.MAP_ANON)
		check(e)
		page[0] = 1
		check(syscall.Mlock(page))
		pm, e := os.Open("/proc/self/pagemap")
		check(e)
		defer pm.Close()
		var entry [8]byte
		_, e = pm.ReadAt(entry[:], int64(uintptr(unsafe.Pointer(&page[0]))/4096)*8)
		check(e)
		info := order.Uint64(entry[:])
		pfn := info & ((1 << 55) - 1)
		require(info>>63 == 1 && pfn > 0 && pfn < 1<<20, "guest DMA page outside 32-bit aperture")
		d := &device{bar, page, filepath.Base(p)}
		require(d.get(0) == 0x41494d31, "wrong BAR signature")
		d.set(4, uint32(pfn*4096))
		return d
	}
	panic("teaching endpoint absent")
}

type timing struct {
	CopyNS, DeviceNS, QueueNS, ServiceNS, ClientNS int64
	Commands                                       int
	Digest                                         string
	Results                                        []byte
	ID                                             int
}
type job struct {
	activation []byte
	id         int
	queued     time.Time
	reply      chan timing
}

func (d *device) project(activation, weights []byte, id int) timing {
	// The caller supplies 32 activations and 256 x 32 packed weights.
	require(len(activation) == 32 && len(weights) == 8192, "invalid payload")
	t := timing{ID: id}
	start := time.Now()
	before := d.get(20)
	var result [1024]byte
	for i := 0; i < 64; i++ {
		tic := time.Now()
		copy(d.page[:32], activation)
		copy(d.page[64:192], weights[i*128:(i+1)*128])
		t.CopyNS += time.Since(tic).Nanoseconds()
		tic = time.Now()
		d.set(8, 32)
		d.set(12, 1)
		require(d.get(16) == 1, "DMA failed")
		t.DeviceNS += time.Since(tic).Nanoseconds()
		tic = time.Now()
		copy(result[i*16:(i+1)*16], d.page[256:272])
		t.CopyNS += time.Since(tic).Nanoseconds()
	}
	t.Commands = int(d.get(20) - before)
	require(t.Commands == 64, "missing commands")
	t.Results = result[:]
	t.Digest = fmt.Sprintf("%x", sha256.Sum256(result[:]))
	t.ServiceNS = time.Since(start).Nanoseconds()
	return t
}
func loopbackUp() {
	fd, e := syscall.Socket(syscall.AF_INET, syscall.SOCK_DGRAM, 0)
	check(e)
	defer syscall.Close(fd)
	var req [40]byte
	copy(req[:], "lo")
	order.PutUint16(req[16:18], 1)
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), syscall.SIOCSIFFLAGS, uintptr(unsafe.Pointer(&req[0])))
	if errno != 0 {
		panic(errno)
	}
}
func run() map[string]any {
	for _, fs := range []struct{ kind, path string }{{"proc", "/proc"}, {"sysfs", "/sys"}} {
		check(syscall.Mount(fs.kind, fs.path, fs.kind, 0, ""))
	}
	data, e := os.ReadFile("/fixture")
	check(e)
	require(len(data) == 8224+1024, "fixture length")
	want := fmt.Sprintf("%x", sha256.Sum256(data[8224:]))
	activation, weights := data[:32], data[32:8224]
	cmdline, e := os.ReadFile("/proc/cmdline")
	check(e)
	if strings.Contains(string(cmdline), "peer=client") {
		configurePeer("192.0.2.2/24")
		return remoteClient(activation, data[8224:], want)
	}
	d := discover()
	d.set(8, 33)
	before := d.get(20)
	d.set(12, 1)
	require(d.get(16) == 2 && d.get(20) == before, "bad shape accepted")
	d.set(12, 0)
	require(d.get(16) == 0, "reset")
	page := d.get(4)
	d.set(8, 32)
	d.set(4, page+1)
	d.set(12, 1)
	require(d.get(16) == 2 && d.get(20) == before, "unaligned DMA accepted")
	d.set(4, 0xf0000000)
	d.set(12, 1)
	require(d.get(16) == 2 && d.get(20) == before, "non-RAM DMA accepted")
	d.set(4, page)
	d.set(12, 0)
	d.set(12, 2)
	timeout := time.Now().Add(2 * time.Millisecond)
	for d.get(16) == 4 && time.Now().Before(timeout) {
	}
	require(d.get(16) == 4 && d.get(20) == before, "injected pending command")
	d.set(12, 0)
	require(d.get(16) == 0, "recovery from timeout")
	jobs := make(chan job, 4)
	go func() {
		for j := range jobs {
			delay := time.Since(j.queued)
			r := d.project(j.activation, weights, j.id)
			r.QueueNS = delay.Nanoseconds()
			j.reply <- r
		}
	}()
	submit := func(id int, a []byte) timing {
		reply := make(chan timing)
		jobs <- job{a, id, time.Now(), reply}
		select {
		case r := <-reply:
			return r
		case <-time.After(3 * time.Second):
			panic("device deadline")
		}
	}
	if strings.Contains(string(cmdline), "peer=server") {
		configurePeer("192.0.2.1/24")
		ln, e := net.Listen("tcp4", "192.0.2.1:2022")
		check(e)
		defer ln.Close()
		count := serve(ln, submit)
		require(count == 12, "expected twelve network requests")
		return map[string]any{"bdf": d.bdf, "served": count, "commands": d.get(20) - before, "expected_sha256": want}
	}
	network := strings.Contains(string(cmdline), "course=22")
	var link net.Conn
	var decoder *json.Decoder
	if network {
		loopbackUp()
		ln, e := net.Listen("tcp4", "127.0.0.1:0")
		check(e)
		defer ln.Close()
		go serve(ln, submit)
		link, e = net.Dial("tcp4", ln.Addr().String())
		check(e)
		defer link.Close()
		decoder = json.NewDecoder(link)
	}
	rows := map[string][]timing{}
	for i := 0; i < 12; i++ {
		paths := []string{"direct"}
		if network {
			paths = []string{"direct", "tcp"}
			if i%2 == 1 {
				paths[0], paths[1] = paths[1], paths[0]
			}
		}
		for _, path := range paths {
			start := time.Now()
			var r timing
			if path == "direct" {
				r = submit(i, activation)
			} else {
				r = call(link, decoder, i, activation)
			}
			r.ClientNS = time.Since(start).Nanoseconds()
			require(r.ID == i && r.Digest == want && bytes.Equal(r.Results, data[8224:]), "request output mismatch")
			r.Results = nil
			rows[path] = append(rows[path], r)
		}
	}
	return map[string]any{"bdf": d.bdf, "expected_sha256": want, "outputs_per_request": 256, "dma_read_bytes": 64 * (32 + 128), "dma_write_bytes": 1024, "tcp_request_bytes": 36, "response_int32_bytes": 1024, "injected_timeout_recovered": true, "invalid_dma_rejected": true, "bad_command_accepted": false, "reset_recovered": true, "rows": rows}
}
func main() {
	defer func() {
		if p := recover(); p != nil {
			fmt.Printf("AIM_ERROR %v\n", p)
		}
		syscall.Sync()
		syscall.Reboot(syscall.LINUX_REBOOT_CMD_POWER_OFF)
		select {}
	}()
	report := run()
	b, e := json.Marshal(report)
	check(e)
	fmt.Printf("AIM_RESULT %s\n", b)
}
